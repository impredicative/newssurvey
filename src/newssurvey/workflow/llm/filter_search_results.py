import io
import contextlib
import re
from types import ModuleType

from newssurvey.exceptions import LanguageModelOutputStructureError, SourceInsufficiencyError
from newssurvey.types import SearchResult
from newssurvey.config import PROMPTS
from newssurvey.util.dict import dict_str
from newssurvey.util.openai_ import get_content
from newssurvey.util.sys_ import print_error, print_warning

_RESPONSE_PATTERN = re.compile(r"\d+(?: \d+)*")


def _is_response_valid(response: str, num_search_results: int) -> bool:
    """Return true if the response is valid, otherwise false.

    :param response: Valid example: '3 5 8'

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

    responses = response.split(" ")
    num_responses = len(responses)
    if num_responses > num_search_results:
        print_error(f"Response is invalid because it has more entries ({num_responses}) than expected for the search results ({num_search_results}): {response!r}")
        return False

    seen = set()
    for count, response in enumerate(responses, start=1):
        assert response.isdigit()  # This is already checked by the regex.
        number = int(response)

        if number > num_search_results:
            print_error(f"Response #{count} has a value of {number} which is invalid because it is greater than the number of search results: {response!r}")
            return False

        if number in seen:
            print_error(f"Response #{count} has a value of {number} which is invalid because it is a duplicate: {responses!r}")
            return False
        seen.add(number)

        # Note: This fails sometimes when using the small gpt-4o-mini-2024-07-18 model. It is not strictly necessary.
        # if number < max(seen):
        #     print_error(f"Response {count} is invalid because it is not in ascending order: {number}")
        #     return False

    return True


def _filter_search_results(user_query: str, source_module: ModuleType, *, results: list[SearchResult], max_attempts: int = 3) -> list[SearchResult]:
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
        "search_results": "\n\n".join(f'{num}. {result['title']}\n{result['link']}\n{result.get('description', '')}'.rstrip() for num, result in enumerate(results, start=1)),  # Note: Link is included because it contains the year and month.
    }
    prompt_data["task"] = PROMPTS["2. filter_search_results"].format(**prompt_data)
    prompt = PROMPTS["0. common"].format(**prompt_data)

    for num_attempt in range(1, max_attempts + 1):
        response = get_content(prompt, model_size="small", log=(num_attempt > 1), read_cache=(num_attempt == 1))

        if response == "0":
            return []

        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            response_is_valid = _is_response_valid(response, len(results))
        if not response_is_valid:
            error = error.getvalue().rstrip().removeprefix("Error: ")
            if num_attempt == max_attempts:
                raise LanguageModelOutputStructureError(error)
            else:
                print_warning(f"Fault in attempt {num_attempt} of {max_attempts} while filtering search results: {error}")
                continue

        break

    responses = response.split(" ")
    responses = [int(r) for r in responses]
    responses = [r for r in responses if (r != 0)]
    responses.sort()
    filtered_results = [results[r - 1] for r in responses]
    return filtered_results


def _filter_search_results_for_search_term(user_query: str, source_module: ModuleType, search_term: str) -> list[SearchResult]:
    results = {}

    def insert_paged_results(**kwargs) -> None:
        assert "query" not in kwargs, kwargs
        assert "page_num" not in kwargs, kwargs
        num_total_results = 0
        page_num = 1
        while True:
            page_results = source_module.get_search_results(query=search_term, page_num=page_num, **kwargs)
            if not page_results:
                break
            num_total_results += len(page_results)
            filtered_page_results = _filter_search_results(user_query=user_query, source_module=source_module, results=page_results)
            print(f"Limited {len(page_results)} original results to {len(filtered_page_results)} filtered results for page {page_num} of search term {search_term!r} with arguments: {dict_str(kwargs)}")
            if not filtered_page_results:
                break
            for result in filtered_page_results:
                result_link = result["link"]
                if result_link not in results:
                    results[result_link] = result
            page_num += 1
        print(f"Obtained {len(results)} filtered results out of {num_total_results} total results for search term {search_term!r}.")

    source_module.run_searches(insert_paged_results)

    results = list(results.values())
    return results


def filter_search_results(user_query: str, source_module: ModuleType, search_terms: list[str]) -> list[SearchResult]:
    """Return filtered search results.

    Results are filtered for relevance by the LLM.

    Returns:
        list[searchResult]: A list of dictionaries where each dictionary represents an article with its title, link, and description.

    The internal function `_filter_search_results` raises `LanguageModelOutputError` if the model output has an error.
    The subclass `LanguageModelOutputStructureError` is raised by it if the output is structurally invalid.

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
