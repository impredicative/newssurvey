import io
import contextlib
import re
from types import ModuleType

import newsqa.exceptions
from newsqa.types import SearchResult
from newsqa.config import PROMPTS
from newsqa.util.openai_ import get_content
from newsqa.util.sys_ import print_error

_RESPONSE_PATTERN = re.compile(r"\d+=[yn](?:, \d+=[yn])*")


def _are_responses_valid(responses: list[str]) -> bool:
    """Return true if the responses are valid, otherwise false.

    :param responses: Expected sample: ['1=y', '2=y', '3=y', '4=n', '5=y', '6=n', '7=n', '8=n', '9=n', '10=n']

    A validation error is printed if a search term is invalid.
    """
    if not responses:
        print_error("No responses exist.")
        return False

    seen = set()
    for count, response in enumerate(responses, start=1):
        split_response = response.split("=", maxsplit=1)

        if len(split_response) != 2:
            print_error(f"Response {count} is invalid because it is not a key and value pair: {response}")
            return False

        key, value = split_response
        if not key.isdigit():
            print_error(f"Response {count} is invalid because its key is not digits: {key}")
            return False
        number = int(key)

        if count != number:
            print_error(f"Response {count} is invalid because its key is incorrect: {number}")
            return False

        if number in seen:
            print_error(f"Response {count} is invalid because its key is a duplicate: {number}")
            return False
        seen.add(number)

        if value not in "yn":
            print_error(f"Response {count} is invalid because its value is not 'y' or 'n': {value!r}")
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

    num_response_lines = len(response.splitlines())
    if num_response_lines > 1:
        raise newsqa.exceptions.LanguageModelOutputStructureError(f"While filtering search results, the received completion was expected to have 1 line, but it has {num_response_lines} lines:\n{response}")

    if _RESPONSE_PATTERN.fullmatch(response) is None:
        raise newsqa.exceptions.LanguageModelOutputStructureError(f"While filtering search results, the received completion does not match the expected regular expression pattern {_RESPONSE_PATTERN.pattern}:\n{response}")

    responses = [r for r in response.split(", ")]

    num_results, num_responses = len(results), len(responses)
    if num_results != num_responses:
        raise newsqa.exceptions.LanguageModelOutputStructureError(f"While filtering {num_results} search results, the received completion has {num_responses} responses instead of {num_results}:\n{response}")

    error = io.StringIO()
    with contextlib.redirect_stderr(error):
        if not _are_responses_valid(responses):
            error = error.getvalue().rstrip().removeprefix("Error: ")
            raise newsqa.exceptions.LanguageModelOutputStructureError(f"While filtering search results, the received completion has an error. {error}")

    responses = [r.split("=") for r in responses]
    responses = dict((int(k), {"y": True, "n": False}[v]) for k, v in responses)

    filtered_results = [result for num, result in enumerate(results, start=1) if responses[num]]
    return filtered_results
