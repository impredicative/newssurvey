import concurrent.futures
import contextlib
import copy
import io
import re
from types import ModuleType
from typing import Required, TypedDict

from newssurvey.config import PROMPTS, CITATION_OPEN_CHAR, CITATION_CLOSE_CHAR, CITATION_GROUP_PATTERN
from newssurvey.exceptions import LanguageModelOutputStructureError, SourceInsufficiencyError
from newssurvey.types import AnalyzedArticleGen2, AnalyzedSectionGen2, ArticleSectionPairGen2, CitationGen1, SearchArticle, SectionGen1
from newssurvey.util.openai_ import get_content, MODELS, MAX_OUTPUT_TOKENS, MAX_OPENAI_WORKERS
from newssurvey.util.sys_ import print_warning, print_error
from newssurvey.util.textwrap import tab_indent
from newssurvey.util.tiktoken_ import count_tokens, fit_items_to_input_token_limit

_MODEL_SIZE = [
    "small",  # Do not use. Does not generate citations well.
    "large",  # Good.
    "deprecated",  # Do not use. Does not follow instructions equally well as 4o. Does not generate citations.
][1]
_MODEL = MODELS["text"][_MODEL_SIZE]

_INVALID_BRACKETS = ["〖〗", "〈〉"]  # These have been observed in the output.
_INVALID_BRACKETS_PATTERNS = {f"{invalid_open_bracket}{invalid_close_bracket}": re.compile(CITATION_GROUP_PATTERN.pattern.translate(str.maketrans(f"{CITATION_OPEN_CHAR}{CITATION_CLOSE_CHAR}", f"{invalid_open_bracket}{invalid_close_bracket}"))) for invalid_open_bracket, invalid_close_bracket in _INVALID_BRACKETS}
_INVALID_DIGITS = "①②③④⑤⑥⑦⑧⑨"  # These have been observed in the output.
_MARKDOWN_LIST_SNIPPETS = ["\n1. **", "\n- **"]  # These have been observed in the output.


def _is_output_valid(text: str, *, section: str, num_articles: int) -> bool:
    """Return true if the output text is valid, otherwise false.

    A validation error is printed if the output text is invalid.
    """
    if text != text.strip():
        print_error(f"The text for the section {section!r} has leading or trailing whitespace.")
        return False

    if not text:
        print_error(f"The text for the section {section!r} is empty.")
        return False

    for snippet in _MARKDOWN_LIST_SNIPPETS:
        if snippet in text:
            print_error(f"The text for the section {section!r} contains a markdown list snippet {snippet!r}.")
            return False

    if text.startswith(CITATION_OPEN_CHAR):
        print_error(f"The text for the section {section!r} starts with an opening bracket meant for a citation group.")
        return False

    if text.endswith(CITATION_CLOSE_CHAR):
        print_error(f"The text for the section {section!r} ends with a closing bracket meant for a citation group.")
        return False

    if f"{CITATION_OPEN_CHAR}{CITATION_CLOSE_CHAR}" in text:
        print_error(f"The text for the section {section!r} contains an empty citation group.")
        return False

    if f"{CITATION_CLOSE_CHAR}{CITATION_OPEN_CHAR}" in text:
        print_error(f"The text for the section {section!r} could contain two adjacent citation groups.")
        return False

    num_opens, num_closes = text.count(CITATION_OPEN_CHAR), text.count(CITATION_CLOSE_CHAR)
    if num_opens != num_closes:
        print_error(f"The text for the section {section!r} has {num_opens} opening brackets but {num_closes} closing brackets meant for citation groups.")
        return False

    # Ensure citation brackets are balanced.
    # Passing example: "〚1,2,3〛"
    # Failing example: "〚1,2,〚3〛〛"
    balance = 0
    for char in text:
        if char == CITATION_OPEN_CHAR:
            balance += 1
        elif char == CITATION_CLOSE_CHAR:
            balance -= 1
        if balance not in (0, 1):
            print_error(f"The text for the section {section!r} has unbalanced citation brackets.")
            return False

    citation_groups = CITATION_GROUP_PATTERN.findall(text)

    if (num_articles > 0) and (not citation_groups):
        print_error(f"The text for the section {section!r} does not contain any citation groups despite there being {num_articles} articles.")
        return False

    for num_citation_group, citation_group_str in enumerate(citation_groups, start=1):
        if not citation_group_str:
            print_error(f"The citation group #{num_citation_group} for the section {section!r} is empty.")
            return False

        citation_group = [g.strip() for g in citation_group_str.split(",")]
        for citation_str in citation_group:
            if not citation_str.isdigit():
                print_error(f"The citation {citation_str!r} in citation group #{num_citation_group} ({citation_group_str!r}) for the section {section!r} is not a number.")
                return False

            citation = int(citation_str)
            if not 1 <= citation <= num_articles:
                print_error(f"The citation {citation} in citation group #{num_citation_group} ({citation_group_str!r}) for the section {section!r} is not within the expected range of 1 to {num_articles}.")
                return False

            # Note: Duplicates are not checked because they can be managed.

    # Check for invalid brackets
    for brackets, pattern in _INVALID_BRACKETS_PATTERNS.items():
        if pattern.search(text):
            print_error(f"The text for the section {section!r} contains invalid brackets {brackets}.")
            # Note: A regex substitution could in principle be used to replace the invalid brackets with valid ones, but it is not used so as to ensure that the LLM is paying attention.
            return False

    # Check for invalid digits
    for digit in _INVALID_DIGITS:
        if digit in text:
            print_error(f"The text for the section {section!r} contains an invalid digit {digit}.")
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
        print(f"Filtering section {section!r} from {num_articles_used} used articles out of {len(articles)} supplied articles using the {_MODEL_SIZE} model {_MODEL} in attempt {num_attempt}.")
        print(prompt)  # TODO: Remove line.
        input("Press Enter to continue...")  # TODO: Remove line.
        response = get_content(prompt, model_size=_MODEL_SIZE, log=(num_attempt >= 1), read_cache=(num_attempt == 1))

        if response == "REMOVE: none":
            return num_articles_used, []

        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            response_is_valid = _is_output_valid(response, num_articles=num_articles_used)
        if not response_is_valid:
            error = error.getvalue().rstrip().removeprefix("Error: ")
            if num_attempt == max_attempts:
                raise LanguageModelOutputStructureError(error)
            else:
                print_warning(f"Fault in attempt {num_attempt} of {max_attempts} while getting a section: {error}")
                continue

        break

    removed_article_numbers = [int(s) for s in response.split(" ")]
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
        article_section_pairs.sort(key=lambda a: (a["section"]["rating"], article_link_to_rating_map["link"], a["article"]["link"]), reverse=True)  # Link is used as a unique tiebreaker for reproducibility to facilitate a cache hit. It is also used because it often contains the article's publication date.
        
        iteration = 0
        while True:
            iteration += 1
            num_article_section_pairs = len(article_section_pairs)
            num_article_section_pairs_used, removed_article_section_pairs = _filter_articles(user_query, source_module, sections=sections, section=section, articles=article_section_pairs)
            assert num_article_section_pairs_used <= num_article_section_pairs
            num_article_section_pairs_unused = num_article_section_pairs - num_article_section_pairs_used
            num_article_section_pairs_removed = len(removed_article_section_pairs)
            for removed_article_section_pair in removed_article_section_pairs:
                article_section_pairs.remove(removed_article_section_pair)
            filtered_articles_str = "\n".join([f"{iteration}.{num}: {a['article']['title']}" for num, a in enumerate(removed_article_section_pairs, start=1)])
            filtered_articles_suffix_str = f':\n{tab_indent(filtered_articles_str)}' if filtered_articles_str else "."
            print(f"Filtered section {section_num}/{num_sections} {section!r} in iteration {iteration}, removing {num_article_section_pairs_removed} filtered articles out of {num_article_section_pairs_used} used articles out of {num_article_section_pairs} supplied articles out of {num_articles} total articles{filtered_articles_suffix_str}")

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
