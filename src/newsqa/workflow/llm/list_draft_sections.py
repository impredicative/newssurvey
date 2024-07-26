import contextlib
import io
from types import ModuleType

from newsqa.exceptions import LanguageModelOutputStructureError, SourceInsufficiencyError
from newsqa.config import PROMPTS
from newsqa.types import AnalyzedArticle, SearchArticle, SearchResult
from newsqa.util.openai_ import get_content
from newsqa.util.sys_ import print_error


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


def _list_draft_sections_for_search_result(user_query: str, source_module: ModuleType, search_result: SearchResult) -> AnalyzedArticle:
    """Return a tuple containing the search article and a list of draft section names for the given search result.

    `LanguageModelOutputError` is raised if the model output has an error.
    The subclass `LanguageModelOutputStructureError` is raised if the output is structurally invalid.
    """
    assert user_query

    article_text = source_module.get_article_text(search_result["link"])
    article = SearchArticle(**search_result, text=article_text)
    assert article_text.startswith(search_result["title"]), article  # If this fails, fix the parsing to ensure it is true.

    prompt_data = {"user_query": user_query, "source_site_name": source_module.SOURCE_SITE_NAME, "source_type": source_module.SOURCE_TYPE}
    prompt_data["task"] = PROMPTS["3. list_draft_sections"].format(**prompt_data, article=article_text)
    prompt = PROMPTS["0. common"].format(**prompt_data)
    response = get_content(prompt, model_size="small", log=False)

    none_responses = ("none", "none.")
    if response.lower() in none_responses:
        print(f'No draft section names exist for article: {search_result['title']}')
        return AnalyzedArticle(article=article, sections=[])

    sections = [line.strip() for line in response.splitlines()]  # Note: Trailing whitespace has been observed in a name.
    sections = [line for line in sections if line]  # Note: Empty intermediate lines have been observed between names.

    error = io.StringIO()
    with contextlib.redirect_stderr(error):
        if not _are_sections_valid(sections):
            error = error.getvalue().rstrip().removeprefix("Error: ")
            raise LanguageModelOutputStructureError(error)

    print(f'Obtained {len(sections)} draft section names for article: {search_result['title']}.')
    # for section in sections:
    #     print(f"  {section}")

    return AnalyzedArticle(article=article, sections=sections)


def list_draft_sections(user_query: str, source_module: ModuleType, search_results: list[SearchResult]) -> list[AnalyzedArticle]:
    """Return a list of tuples containing the search article and respective draft section names.

    The internal function `_list_draft_sections_for_search_result` raises `LanguageModelOutputError` if the model output has an error.
    The subclass `LanguageModelOutputStructureError` is raised by it if the output is structurally invalid.

    `SourceInsufficiencyError` is raised if no draft section names are available.
    """
    analyzed_articles = []
    num_search_results = len(search_results)
    all_sections = set()
    for search_result_num, search_result in enumerate(search_results, start=1):
        analyzed_article = _list_draft_sections_for_search_result(user_query=user_query, source_module=source_module, search_result=search_result)
        if sections := analyzed_article["sections"]:
            analyzed_articles.append(analyzed_article)
            for section in sections:
                if section not in all_sections:
                    all_sections.add(section)
        print(f"Accumulated a running total of {len(all_sections)} draft section names for {search_result_num}/{num_search_results} search results.")

    if not all_sections:
        raise SourceInsufficiencyError("No draft section names were suggested for query.")
    return analyzed_articles
