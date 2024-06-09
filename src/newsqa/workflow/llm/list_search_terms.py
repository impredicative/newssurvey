import contextlib
import io
from types import ModuleType

from newsqa.exceptions import LanguageModelOutputRejectionError, LanguageModelOutputStructureError
from newsqa.config import PROMPTS
from newsqa.util.openai_ import get_content
from newsqa.util.sys_ import print_error


def is_search_terms_list_valid(terms: list[str]) -> bool:
    """Return true if the search terms are structurally valid, otherwise false.

    A validation error is printed if a search term is invalid.
    """
    if not terms:
        print_error("No search terms exist.")
        return False

    seen = set()
    for term in terms:
        if term != term.strip():
            print_error(f"Search term is invalid because it has leading or trailing whitespace: {term!r}")
            return False

        if term in seen:
            print_error(f"Search term is invalid because it is a duplicate: {term}")
            return False
        seen.add(term)

    return True


def list_search_terms(user_query: str, source_module: ModuleType) -> list[str]:
    """Return the list of search topics.

    `LanguageModelOutputError` is raised if the model output has an error.
    The subclass `LanguageModelOutputRejectionError` is raised if the output is rejected.
    The subclass `LanguageModelOutputStructureError` is raised if the output is structurally invalid.
    """
    assert user_query
    prompt_data = {"user_query": user_query, "source_site_name": source_module.SOURCE_SITE_NAME, "source_type": source_module.SOURCE_TYPE}
    prompt = PROMPTS["0. common"].format(**prompt_data) + "\n\n" + PROMPTS["1. list_search_terms"].format(**prompt_data)
    response = get_content(prompt)

    none_responses = ("none", "none.")
    if response.lower() in none_responses:
        raise LanguageModelOutputRejectionError("No search terms exist for query.")

    invalid_terms = ("", *none_responses)
    terms = [t.strip() for t in response.splitlines() if t.strip().lower() not in invalid_terms]  # Note: A terminal "None" line has been observed with valid entries before it.

    error = io.StringIO()
    with contextlib.redirect_stderr(error):
        if not is_search_terms_list_valid(terms):
            error = error.getvalue().rstrip().removeprefix("Error: ")
            raise LanguageModelOutputStructureError(error)

    assert terms
    return terms
