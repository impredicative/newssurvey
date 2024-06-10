import io
import contextlib
import re
from types import ModuleType

from newsqa.exceptions import LanguageModelOutputStructureError, SourceInsufficiencyError
from newsqa.types import SearchResult
from newsqa.config import PROMPTS
from newsqa.util.dict import dict_str
from newsqa.util.openai_ import get_content
from newsqa.util.sys_ import print_error

_RESPONSE_PATTERN = re.compile(r"\d+(?: \d+)*")


def _are_responses_valid(responses: list[str]) -> bool:
    """Return true if the responses are valid, otherwise false.

    :param responses: Expected sample: ['3', '5', '8']

    A validation error is printed if a search term is invalid.
    """
    if not responses:
        print_error("No responses exist.")
        return False

    seen = set()
    for count, response in enumerate(responses, start=1):
        if not response.isdigit():
            print_error(f"Response {count} is invalid because it is not digits: {response}")
            return False
        number = int(response)

        if number in seen:
            print_error(f"Response {count} is invalid because it is a duplicate: {number}")
            return False
        seen.add(number)

        if number < max(seen):
            print_error(f"Response {count} is invalid because it is not in ascending order: {number}")
            return False

    return True


def _filter_search_results(user_query: str, source_module: ModuleType, results: list[SearchResult]) -> list[SearchResult]:
    """Return the list of relevant search results.

    `LanguageModelOutputError` is raised if the model output has an error.
    The subclass `LanguageModelOutputStructureError` is raised if the output is structurally invalid.
    """
    assert user_query
    assert results
    prompt_data = {
        "user_query": user_query,
        "source_site_name": source_module.SOURCE_SITE_NAME,
        "source_type": source_module.SOURCE_TYPE,
        "search_results": "\n\n".join(f'{num}. {result['title']}\n{result.get('description', '')}'.rstrip() for num, result in enumerate(results, start=1)),
    }
    prompt_data["task"] = PROMPTS["2. filter_search_results"].format(**prompt_data)
    prompt = PROMPTS["0. common"].format(**prompt_data)
    response = get_content(prompt, log=False)

    if response == "0":
        return []

    num_response_lines = len(response.splitlines())
    if num_response_lines > 1:
        raise LanguageModelOutputStructureError(f"While filtering search results, the received completion was expected to have a single line, but it has {num_response_lines} lines:\n{response}")

    if _RESPONSE_PATTERN.fullmatch(response) is None:
        raise LanguageModelOutputStructureError(f"While filtering search results, the received completion does not match the expected regular expression pattern {_RESPONSE_PATTERN.pattern}:\n{response}")

    responses = response.split(" ")
    num_results, num_responses = len(results), len(responses)
    if num_responses > num_results:
        raise LanguageModelOutputStructureError(f"While filtering search results, the received completion has {num_responses} responses for {num_results} original results:\n{response}")

    error = io.StringIO()
    with contextlib.redirect_stderr(error):
        if not _are_responses_valid(responses):
            error = error.getvalue().rstrip().removeprefix("Error: ")
            raise LanguageModelOutputStructureError(f"While filtering search results, the received completion has an error. {error}")

    responses = [int(r) for r in responses]
    filtered_results = [results[r - 1] for r in responses]
    return filtered_results


def _filter_search_results_for_search_term(user_query: str, source_module: ModuleType, search_term: str) -> list[SearchResult]:
    results = {}

    def insert_paged_results(**kwargs) -> None:
        assert "query" not in kwargs, kwargs
        assert "page_num" not in kwargs, kwargs
        page_num = 1
        while True:
            page_results = source_module.get_search_results(query=search_term, page_num=page_num, **kwargs)
            if not page_results:
                break
            filtered_page_results = _filter_search_results(user_query=user_query, source_module=source_module, results=page_results)
            print(f"Limited {len(page_results)} original results to {len(filtered_page_results)} filtered results for page {page_num} of search term {search_term!r} with arguments: {dict_str(kwargs)}")
            if not filtered_page_results:
                break
            for result in filtered_page_results:
                result_link = result["link"]
                if result_link not in results:
                    results[result_link] = result
            page_num += 1
        print(f"Obtained {len(results)} filtered results for search term {search_term!r}.")

    source_module.run_searches(insert_paged_results)

    results = list(results.values())
    return results


def filter_search_results(user_query: str, source_module: ModuleType, search_terms: list[str]) -> list[SearchResult]:
    """Return filtered search results.

    Results are filtered for relevance by the LLM.

    Returns:
        list[searchResult]: A list of dictionaries where each dictionary represents an article with its title, link, and description.

    `SourceInsufficiencyError` is raised if no filtered results are available.
    """
    results = {}
    num_terms = len(search_terms)
    for term_num, term in enumerate(search_terms, start=1):
        results_for_term = _filter_search_results_for_search_term(user_query=user_query, source_module=source_module, search_term=term)
        for result in results_for_term:
            result_link = result["link"]
            if result_link not in results:
                results[result_link] = result
        print(f"Accumulated a running total of {len(results)} filtered results for {term_num}/{num_terms} search terms.")

    if not results:
        raise SourceInsufficiencyError("No filtered search results exist for query.")

    results = list(results.values())
    assert len(results) == len(set(r["link"] for r in results))  # Ensures no duplicates.
    return results
