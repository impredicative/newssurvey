import io
import contextlib
import re
from types import ModuleType

import newsqa.exceptions
from newsqa.types import SearchResult
from newsqa.config import PROMPTS
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


def filter_search_results(user_query: str, source_module: ModuleType, results: list[SearchResult]) -> list[SearchResult]:
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
    prompt = PROMPTS["0. common"].format(**prompt_data) + "\n\n" + PROMPTS["2. filter_search_results"].format(**prompt_data)
    response = get_content(prompt)

    if response == "0":
        return []

    num_response_lines = len(response.splitlines())
    if num_response_lines > 1:
        raise newsqa.exceptions.LanguageModelOutputStructureError(f"While filtering search results, the received completion was expected to have a single line, but it has {num_response_lines} lines:\n{response}")

    if _RESPONSE_PATTERN.fullmatch(response) is None:
        raise newsqa.exceptions.LanguageModelOutputStructureError(f"While filtering search results, the received completion does not match the expected regular expression pattern {_RESPONSE_PATTERN.pattern}:\n{response}")

    responses = response.split(" ")
    num_results, num_responses = len(results), len(responses)
    if num_responses > num_results:
        raise newsqa.exceptions.LanguageModelOutputStructureError(f"While filtering search results, the received completion has {num_responses} responses for {num_results} original results:\n{response}")

    error = io.StringIO()
    with contextlib.redirect_stderr(error):
        if not _are_responses_valid(responses):
            error = error.getvalue().rstrip().removeprefix("Error: ")
            raise newsqa.exceptions.LanguageModelOutputStructureError(f"While filtering search results, the received completion has an error. {error}")

    responses = [int(r) for r in responses]
    filtered_results = [results[r - 1] for r in responses]
    return filtered_results
