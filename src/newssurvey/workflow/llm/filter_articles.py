import collections
import concurrent.futures
import contextlib
import copy
import io
import re
from types import ModuleType
from typing import Literal, Required

from newssurvey.config import PROMPTS
from newssurvey.exceptions import LanguageModelOutputStructureError, SourceInsufficiencyError
from newssurvey.types import AnalyzedArticleGen2, ArticleSectionPairGen2
from newssurvey.util.diskcache_ import MAX_DISKCACHE_WORKERS
from newssurvey.util.openai_ import get_content, MAX_OPENAI_WORKERS, MODELS
from newssurvey.util.str import is_none_response
from newssurvey.util.sys_ import print_warning, print_error
from newssurvey.util.textwrap import tab_indent
from newssurvey.util.tiktoken_ import fit_items_to_input_token_limit

_MIN_FILTERING_THRESHOLD = 1
_MODEL_SIZE = [
    "small",  # Bad because it routinely returns invalid numbers which are higher than the number of articles. Example: Response #11 has a value of 337 which is invalid because it is greater than the number of articles (323): 'REMOVE: 4 28 68 177 206 245 256 276 305 311 337 368 404 419 428 445 463 477 487 580 589 601 611 617 665 688 698 708 719 792 802 809 819 830 847 872 875 887 895 906 911 917 924 929 948 959 963 979 997'
    "large",  # Good but very expensive due to multiple iterations per section when there are many articles.
][1]
_MODEL = MODELS["text"][_MODEL_SIZE]
_RESPONSE_PREFIX = "REMOVE: "
_RESPONSE_PATTERN = re.compile(rf"{_RESPONSE_PREFIX}\d+(?: \d+)*")


class TrackedArticleSectionPairGen2(ArticleSectionPairGen2):
    status: Required[Literal["kept", "removed", "undetermined"]]
    iteration: Required[int]


def _is_response_valid(response: str, num_articles: int) -> bool:
    """Return true if the response is valid, otherwise false.

    :param response: Valid example: 'REMOVE: 3 5 8'

    A validation error is printed if a search term is invalid.
    """
    if not response:
        print_error("No response exists.")
        return False

    if response != response.strip():
        print_error(f"Response is invalid because it has leading or trailing whitespace: {response!r}")
        return False

    num_response_lines = len(response.splitlines())
    if num_response_lines > 1:
        print_error(f"Response is invalid because it has multiple lines: {response!r}")
        return False

    if _RESPONSE_PATTERN.fullmatch(response) is None:
        print_error(f"Response is invalid because it does not match the expected pattern: {response!r}")
        return False

    responses = response.removeprefix(_RESPONSE_PREFIX).split(" ")
    num_responses = len(responses)
    if num_responses > num_articles:
        print_error(f"Response is invalid because it has more entries ({num_responses}) than expected for the articles ({num_articles}): {response!r}")
        return False

    seen = set()
    for count, value in enumerate(responses, start=1):
        assert value.isdigit()  # This is already checked by the regex.
        number = int(value)

        if number > num_articles:
            print_error(f"Response #{count} has a value of {number} which is invalid because it is greater than the number of articles ({num_articles}): {response!r}")
            return False

        # # Note: This is not strictly necessary.
        # if number in seen:
        #     print_error(f"Response #{count} has a value of {number} which is invalid because it is a duplicate: {response!r}")
        #     return False

        seen.add(number)

        # Note: This is not strictly necessary.
        # if number < max(seen):
        #     print_error(f"Response {count} is invalid because it is not in ascending order: {number}")
        #     return False

    # Note: This is not enforced so as to allow for the possibility of removing all articles for a section.
    # if seen == set(range(1, num_articles + 1)):
    #     print_error(f"Response is invalid because it removes all {num_articles} articles: {response!r}")
    #     return False

    return True


def get_article_texts(article_section_pairs: list[ArticleSectionPairGen2], /) -> list[str]:  # Note: Also used in combine_articles.
    """Return the texts for the given article-section pairs."""
    return [f'[ARTICLE {num}]\n\n{a["article"]["title"]}\n\n{a["section"]["text"]}' for num, a in enumerate(article_section_pairs, start=1)]


def join_article_texts(article_texts: list[str], /) -> str:  # Note: Also used in combine_articles.
    """Return the joined article texts."""
    return "\n\n---\n\n".join(article_texts)


def _filter_articles(user_query: str, source_module: ModuleType, *, sections: list[str], section: str, articles: list[TrackedArticleSectionPairGen2], batch_num: int, max_attempts: int = 3) -> None:
    """Update the given articles in-place with their updated tracking status after filtering the ones that can be filtered."""
    assert user_query
    assert section
    assert articles
    assert all((article["status"] == "undetermined") for article in articles)

    article_texts = get_article_texts(articles)
    prompt_data = {"user_query": user_query, "source_site_name": source_module.SOURCE_SITE_NAME, "source_type": source_module.SOURCE_TYPE}
    num_sections = len(sections)
    numbered_sections = [f"{num}. {s}" for num, s in enumerate(sections, start=1)]
    numbered_sections_str = "\n".join(numbered_sections)
    section_number = sections.index(section) + 1
    numbered_section = f"{section_number}. {section}"

    def prompt_formatter(article_texts_truncated: list[str]) -> str:
        num_articles = len(article_texts_truncated)
        numbered_articles = join_article_texts(article_texts_truncated)
        prompt_data["task"] = PROMPTS["6. filter_articles"].format(num_sections=num_sections, sections=numbered_sections_str, section=numbered_section, num_articles=num_articles, batch_num=batch_num, articles=numbered_articles)
        prompt = PROMPTS["0. common"].format(**prompt_data)
        return prompt

    num_articles_used, prompt = fit_items_to_input_token_limit(article_texts, model=_MODEL, formatter=prompt_formatter, approach="rate")

    for num_attempt in range(1, max_attempts + 1):
        print(f"Filtering batch {batch_num} of section {section!r} using {num_articles_used} articles out of {len(articles)} supplied articles in attempt {num_attempt}.")
        response = get_content(prompt, model_size=_MODEL_SIZE, log=(num_attempt > 1), read_cache=(num_attempt == 1))

        if is_none_response(response.removeprefix(_RESPONSE_PREFIX)):
            response = _RESPONSE_PREFIX
            break

        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            response_is_valid = _is_response_valid(response, num_articles=num_articles_used)
        if not response_is_valid:
            error = error.getvalue().rstrip().removeprefix("Error: ")
            if num_attempt == max_attempts:
                raise LanguageModelOutputStructureError(error)
            else:
                print_warning(f"Fault in attempt {num_attempt} of {max_attempts} while filtering section {section}: {error}")
                continue

        break

    response = response.removeprefix(_RESPONSE_PREFIX)
    removed_article_numbers = [int(s) for s in response.split(" ")] if response else []  # Note: "".split(" ") returns [''], so it is handled separately.
    removed_article_numbers = list(dict.fromkeys(removed_article_numbers))  # Remove duplicates as have been observed.
    removed_article_numbers.sort()

    status_map = {True: "removed", False: "kept"}
    for a_num, a in enumerate(articles, start=1):
        assert a["status"] == "undetermined"
        if a_num <= num_articles_used:
            a["status"] = status_map[a_num in removed_article_numbers]
        a["iteration"] = batch_num

    print(f"Filtered batch {batch_num} of section {section!r} using {num_articles_used} articles out of {len(articles)} supplied articles in attempt {num_attempt} with {len(removed_article_numbers)} articles removed.")


def filter_articles(user_query: str, source_module: ModuleType, *, articles: list[AnalyzedArticleGen2], sections: list[str]) -> list[AnalyzedArticleGen2]:
    """Return a filtered list of the given articles with filtered sections.

    If an article does not have any remaining sections after filtering, it is not returned.

    The internal functions raise `LanguageModelOutputError` if the model output has an error.
    Specifically, its subclass `LanguageModelOutputStructureError` is raised by it if the output is structurally invalid.

    `SourceInsufficiencyError` is raised if no usable articles remain for the query.
    """
    articles = copy.deepcopy(articles)  # This avoids subsequent modifications to the input.
    num_articles, num_sections = len(articles), len(sections)

    article_link_to_rating_map: dict[str, int] = {article["article"]["link"]: sum(article_section["rating"] for article_section in article["sections"]) for article in articles}
    # Note: Technically this summed rating could be updated after each iteration of each section, but this would break reproducible caching for concurrent processing, and so it is not updated hereafter.

    def process_section(section_num: int, section: str) -> list[ArticleSectionPairGen2]:
        """Return articles to keep for the given section."""
        article_section_pairs: list[ArticleSectionPairGen2] = []
        for article in articles:
            for article_section in article["sections"]:
                if article_section["section"] == section:
                    assert article_section["rating"] > 0
                    article_section_pair = {"article": article["article"], "section": article_section}
                    article_section_pairs.append(article_section_pair)
                    break
        assert article_section_pairs, section
        article_section_pairs.sort(key=lambda a: (a["section"]["rating"], article_link_to_rating_map[a["article"]["link"]], a["article"]["link"]), reverse=True)  # Link is used as a unique tiebreaker for reproducibility to facilitate a cache hit. It is also used because it often contains the article's publication date.
        num_article_section_pairs = len(article_section_pairs)
        if num_article_section_pairs < _MIN_FILTERING_THRESHOLD:
            print(f"Skipping filtering section {section_num}/{num_sections} {section!r} because it has {num_article_section_pairs} articles which is less than the minimum filtering threshold of {_MIN_FILTERING_THRESHOLD}.")
            return article_section_pairs
        tracked_article_section_pairs = [TrackedArticleSectionPairGen2(**a, status="undetermined", iteration=0) for a in article_section_pairs]
        del article_section_pairs

        iteration = 0
        while True:
            iteration += 1

            num_keepable_article_section_pairs = sum(1 for a in tracked_article_section_pairs if (a["status"] in ("kept", "undetermined")))
            if num_keepable_article_section_pairs < _MIN_FILTERING_THRESHOLD:
                print(f"Skipping filtering section {section_num}/{num_sections} {section!r} in iteration {iteration} because it has {num_keepable_article_section_pairs} keepable articles which is less than the minimum filtering threshold of {_MIN_FILTERING_THRESHOLD}.")
                for a in tracked_article_section_pairs:
                    if a["status"] == "undetermined":
                        a.update({"status": "kept", "iteration": iteration})
                break

            unfiltered_article_section_pairs = [a for a in tracked_article_section_pairs if a["status"] == "undetermined"]
            if not unfiltered_article_section_pairs:
                print(f"No unfiltered articles remain for section {section_num}/{num_sections} {section!r} in iteration {iteration}.")
                break

            _filter_articles(user_query, source_module, sections=sections, section=section, articles=unfiltered_article_section_pairs, batch_num=iteration)  # Note: This should effectively update tracked_article_section_pairs in-place.
            # Note: Previously filtered articles are not included in the call to _filter_articles because:
            # 1. They have already been filtered once.
            # 2. Filtering them again is very cost prohibitive. Only the big model can filter articles, and it can be very expensive to include the filtered articles repeatedly when there are many articles.

            num_article_section_pairs_curr = len(unfiltered_article_section_pairs)
            num_article_section_pairs_by_status = collections.Counter(a["status"] for a in unfiltered_article_section_pairs)
            num_article_section_pairs_used = num_article_section_pairs_by_status["kept"] + num_article_section_pairs_by_status["removed"]
            num_article_section_pairs_unused = num_article_section_pairs_by_status["undetermined"]
            assert num_article_section_pairs_used + num_article_section_pairs_unused == num_article_section_pairs_curr, (num_article_section_pairs_used, num_article_section_pairs_unused, num_article_section_pairs_curr)

            printable_samples = []
            sample_status = None
            for a_num, a in enumerate(tracked_article_section_pairs, start=1):
                if (a["iteration"] != iteration) or (a["status"] == sample_status):
                    continue
                sample_status = a["status"]
                printable_sample = f"[{sample_status[0]}] s{section_num}.i{iteration}.a{a_num}: {a['article']['title']} (r={a["section"]["rating"]})"
                printable_samples.append(printable_sample)
            printable_samples_str = "\n".join([tab_indent(s) for s in printable_samples])

            print(f"Filtered section {section_num}/{num_sections} {section!r} in iteration {iteration}, keeping {num_article_section_pairs_by_status['kept']} and removing {num_article_section_pairs_by_status['removed']} articles out of {num_article_section_pairs_used} used and {num_article_section_pairs_unused} unused articles out of {num_article_section_pairs_curr} current articles out of {num_article_section_pairs} section articles out of {num_articles} total articles. Sample statuses ({len(printable_samples)}):\n{printable_samples_str}")

            if num_article_section_pairs_unused == 0:
                break
            # if (num_article_section_pairs_by_status["removed"] == 0) and (num_article_section_pairs_unused > 0):
            #     print_warning(f"Aborting filtering section {section_num}/{num_sections} {section!r} after iteration {iteration} with {num_article_section_pairs_unused} unused articles out of {num_article_section_pairs} supplied articles out of {num_articles} total articles.")
            #     break  # Note: A premature break was observed.

        kept_article_section_pairs = [ArticleSectionPairGen2(article=a["article"], section=a["section"]) for a in tracked_article_section_pairs if a["status"] == "kept"]
        msg = f"Section {section_num}/{num_sections} {section!r} has {len(kept_article_section_pairs)} out {num_article_section_pairs} articles that remain after {iteration} iterations."
        printer = print if kept_article_section_pairs else print_warning
        printer(msg)
        return kept_article_section_pairs

    max_workers = min(MAX_DISKCACHE_WORKERS, MAX_OPENAI_WORKERS)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        sections_to_futures = {section: executor.submit(process_section, section_num, section) for section_num, section in enumerate(sections, start=1)}
        sections_to_articles: dict[str, list[ArticleSectionPairGen2]] = {section: sections_to_futures[section].result() for section in sections}
    sections_to_links: dict[str, set[str]] = {section: {a["article"]["link"] for a in sections_to_articles[section]} for section in sections}

    for article in articles:
        article_link = article["article"]["link"]
        article["sections"] = [article_section for article_section in article["sections"] if (article_link in sections_to_links[article_section["section"]])]
    articles = [article for article in articles if article["sections"]]

    articles.sort(key=lambda a: sum(s["rating"] for s in a["sections"]), reverse=True)
    if not articles:
        raise SourceInsufficiencyError("No usable articles remain for the query.")
    return articles
