import concurrent.futures
import contextlib
import copy
import io
import re
from types import ModuleType

from newssurvey.config import PROMPTS
from newssurvey.exceptions import LanguageModelOutputStructureError, SourceInsufficiencyError
from newssurvey.types import AnalyzedArticleGen2, ArticleSectionPairGen2
from newssurvey.util.openai_ import get_content, MAX_OPENAI_WORKERS, MODELS
from newssurvey.util.str import is_none_response
from newssurvey.util.sys_ import print_warning, print_error
from newssurvey.util.textwrap import tab_indent
from newssurvey.util.tiktoken_ import fit_items_to_input_token_limit

_MIN_FILTERING_THRESHOLD = 2
_MODEL_SIZE = "large"
_MODEL = MODELS["text"][_MODEL_SIZE]
_RESPONSE_PREFIX = "REMOVE: "
_RESPONSE_PATTERN = re.compile(rf"{_RESPONSE_PREFIX}\d+(?: \d+)*")


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

        if number in seen:
            print_error(f"Response #{count} has a value of {number} which is invalid because it is a duplicate: {response!r}")
            return False
        seen.add(number)

        # Note: This is not strictly necessary.
        # if number < max(seen):
        #     print_error(f"Response {count} is invalid because it is not in ascending order: {number}")
        #     return False

    if seen == set(range(1, num_articles + 1)):
        print_error(f"Response is invalid because it removes all {num_articles} articles: {response!r}")
        return False

    return True


def get_article_texts(article_section_pairs: list[ArticleSectionPairGen2], /) -> list[str]:  # Note: Also used in combine_articles.
    """Return the texts for the given article-section pairs."""
    return [f'[ARTICLE {num}]\n\n{a["article"]["title"]}\n\n{a["section"]["text"]}' for num, a in enumerate(article_section_pairs, start=1)]


def join_article_texts(article_texts: list[str], /) -> str:  # Note: Also used in combine_articles.
    """Return the joined article texts."""
    return "\n\n---\n\n".join(article_texts)


def _filter_articles(user_query: str, source_module: ModuleType, *, sections: list[str], section: str, articles: list[ArticleSectionPairGen2], max_attempts: int = 3) -> tuple[int, str]:
    """Return the number of articles used and the articles that were removed."""
    assert user_query
    assert section
    assert articles

    article_texts = get_article_texts(articles)
    prompt_data = {"user_query": user_query, "source_site_name": source_module.SOURCE_SITE_NAME, "source_type": source_module.SOURCE_TYPE}
    num_sections = len(sections)
    numbered_sections = [f"{num}. {s}" for num, s in enumerate(sections, start=1)]
    numbered_sections_str = "\n".join(numbered_sections)
    section_number = sections.index(section) + 1
    numbered_section = f"{section_number}. {section}"

    def prompt_formatter(article_texts_truncated: list[str]) -> str:
        numbered_articles = join_article_texts(article_texts_truncated)
        prompt_data["task"] = PROMPTS["6. filter_articles"].format(num_sections=num_sections, sections=numbered_sections_str, section=numbered_section, num_articles=len(article_texts_truncated), articles=numbered_articles)
        prompt = PROMPTS["0. common"].format(**prompt_data)
        return prompt

    num_articles_used, prompt = fit_items_to_input_token_limit(article_texts, model=_MODEL, formatter=prompt_formatter, approach="rate")

    for num_attempt in range(1, max_attempts + 1):
        print(f"Filtering section {section!r} using {num_articles_used} articles out of {len(articles)} supplied articles in attempt {num_attempt}.")
        response = get_content(prompt, model_size=_MODEL_SIZE, log=(num_attempt >= 1), read_cache=(num_attempt == 1))  # TODO: Fix log value.

        if is_none_response(response.removeprefix(_RESPONSE_PREFIX)):
            return num_articles_used, []

        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            response_is_valid = _is_response_valid(response, num_articles=num_articles_used)
        if not response_is_valid:
            error = error.getvalue().rstrip().removeprefix("Error: ")
            if num_attempt == max_attempts:
                raise LanguageModelOutputStructureError(error)
            else:
                print_warning(f"Fault in attempt {num_attempt} of {max_attempts} while filtering section {section}: {error}")
                input("Press Enter to continue...")  # TODO: Remove line.
                continue

        break

    removed_article_numbers = [int(s) for s in response.removeprefix(_RESPONSE_PREFIX).split(" ")]
    removed_article_numbers.sort()
    removed_articles = [articles[num - 1] for num in removed_article_numbers]
    return num_articles_used, removed_articles


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

        iteration = 0
        while True:
            iteration += 1
            num_article_section_pairs = len(article_section_pairs)
            if num_article_section_pairs < _MIN_FILTERING_THRESHOLD:
                print(f"Skipping filtering section {section_num}/{num_sections} {section!r} in iteration {iteration} because it has {num_article_section_pairs} articles which is less than the minimum filtering threshold of {_MIN_FILTERING_THRESHOLD}.")
                input("Press Enter to continue...")  # TODO: Remove line.
                break

            num_article_section_pairs_used, removed_article_section_pairs = _filter_articles(user_query, source_module, sections=sections, section=section, articles=article_section_pairs)
            assert num_article_section_pairs_used <= num_article_section_pairs
            num_article_section_pairs_unused = num_article_section_pairs - num_article_section_pairs_used
            num_article_section_pairs_removed = len(removed_article_section_pairs)
            for removed_article_section_pair in removed_article_section_pairs:
                article_section_pairs.remove(removed_article_section_pair)
            filtered_articles_str = "\n".join([f"{iteration}.{num}: {a['article']['title']} (r={a["section"]["rating"]})" for num, a in enumerate(removed_article_section_pairs, start=1)])
            filtered_articles_suffix_str = f":\n{tab_indent(filtered_articles_str)}" if filtered_articles_str else "."
            print(f"Filtered section {section_num}/{num_sections} {section!r} in iteration {iteration}, removing {num_article_section_pairs_removed} filtered articles out of {num_article_section_pairs_used} used articles out of {num_article_section_pairs} supplied articles out of {num_articles} total articles{filtered_articles_suffix_str}")
            input("Press Enter to continue...")  # TODO: Remove line.

            if num_article_section_pairs_unused == 0:
                break
            if (num_article_section_pairs_removed == 0) and (num_article_section_pairs_unused > 0):
                print_warning(f"Aborting filtering section {section_num}/{num_sections} {section!r} after iteration {iteration} with {num_article_section_pairs_unused} unused articles out of {num_article_section_pairs} supplied articles out of {num_articles} total articles.")
                input("Press Enter to continue...")  # TODO: Remove line.
                break

        assert article_section_pairs, section
        return article_section_pairs

    max_workers = min(1, MAX_OPENAI_WORKERS)  # TODO: Replace 1 with 8.
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
