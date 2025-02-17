import concurrent.futures
import contextlib
import io
from types import ModuleType

from newssurvey.config import PROMPTS
from newssurvey.exceptions import LanguageModelOutputStructureError, SourceInsufficiencyError
from newssurvey.types import AnalyzedArticleGen1, SearchArticle, SearchResult
from newssurvey.util.openai_ import get_content, MAX_WORKERS
from newssurvey.util.str import is_none_response
from newssurvey.util.sys_ import print_error


def _are_sections_valid(sections: list[str]) -> bool:
    """Return true if the section names are valid, otherwise false.

    A validation error is printed if a section name is invalid.
    """
    if not sections:
        print_error("No section names exist.")
        return False

    seen = set()
    for section in sections:
        if section != section.strip():
            print_error(f"Section name is invalid because it has leading or trailing whitespace: {section!r}")
            return False

        if section.startswith(("- ", "* ", "• ")):
            print_error(f"Section name is invalid because it has a leading bullet prefix: {section}")
            return False

        if section in seen:
            print_error(f"Section name is invalid because it is a duplicate: {section}")
            return False
        seen.add(section)

    return True


def _list_draft_sections_for_search_result(user_query: str, source_module: ModuleType, search_result: SearchResult) -> AnalyzedArticleGen1:
    """Return a tuple containing the search article and a list of draft section names for the given search result.

    `LanguageModelOutputError` is raised if the model output has an error.
    Specifically, its subclass `LanguageModelOutputStructureError` is raised if the output is structurally invalid.
    """
    assert user_query

    article_text = source_module.get_article_text(search_result["link"])
    article = SearchArticle(**search_result, text=article_text)
    assert article_text.startswith(search_result["title"]), article  # If this fails, fix the parsing to ensure it is true.

    prompt_data = {"user_query": user_query, "source_site_name": source_module.SOURCE_SITE_NAME, "source_type": source_module.SOURCE_TYPE}
    prompt_data["task"] = PROMPTS["3. list_draft_sections"].format(**prompt_data, article=article_text)
    prompt = PROMPTS["0. common"].format(**prompt_data)
    response = get_content(prompt, model_size="small", log=False)

    if is_none_response(response):
        print(f'No draft section names exist for article: {search_result['title']}')
        return AnalyzedArticleGen1(article=article, sections=[])

    sections = [line.strip() for line in response.splitlines()]  # Note: Trailing whitespace has been observed in a name.
    sections = [line for line in sections if line]  # Note: Empty intermediate lines have been observed between names.

    error = io.StringIO()
    with contextlib.redirect_stderr(error):
        if not _are_sections_valid(sections):
            error = error.getvalue().rstrip().removeprefix("Error: ")
            raise LanguageModelOutputStructureError(error)

    print(f'Obtained {len(sections)} draft section names for article: {search_result['title']}: ' + ", ".join(sections))
    return AnalyzedArticleGen1(article=article, sections=sections)


def list_draft_sections(user_query: str, source_module: ModuleType, search_results: list[SearchResult]) -> list[AnalyzedArticleGen1]:
    """Return a list of tuples containing the search article and respective draft section names.

    The internal function `_list_draft_sections_for_search_result` raises `LanguageModelOutputError` if the model output has an error.
    Specifically, its subclass `LanguageModelOutputStructureError` is raised by it if the output is structurally invalid.

    `SourceInsufficiencyError` is raised if no draft section names are available.
    """

    def analyze_article(search_result: SearchResult) -> AnalyzedArticleGen1:
        return _list_draft_sections_for_search_result(user_query=user_query, source_module=source_module, search_result=search_result)

    num_search_results = len(search_results)
    analyzed_articles = []
    all_sections = set()

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(analyze_article, search_result): search_result for search_result in search_results}
        for future_num, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            analyzed_article = future.result()
            if sections := analyzed_article["sections"]:
                analyzed_articles.append(analyzed_article)
                for section in sections:
                    if section not in all_sections:
                        all_sections.add(section)
            print(f"Accumulated a running total of {len(all_sections)} draft section names for {future_num}/{num_search_results} search results.")

    if not all_sections:
        raise SourceInsufficiencyError("No draft section names were suggested for query.")
    return analyzed_articles
