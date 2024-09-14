import contextlib
import io
from types import ModuleType

from newssurvey.exceptions import LanguageModelOutputStructureError
from newssurvey.config import PROMPTS
from newssurvey.util.openai_ import get_content
from newssurvey.util.str import is_none_response
from newssurvey.util.sys_ import print_warning
from newssurvey.workflow.llm.list_search_terms import is_search_terms_list_valid


def _accumulate_search_terms(user_query: str, source_module: ModuleType, search_terms: list[str], max_attempts: int = 3) -> list[str]:
    """Return the accumulated search terms."""
    assert search_terms

    prompt_data = {"user_query": user_query, "source_site_name": source_module.SOURCE_SITE_NAME, "source_type": source_module.SOURCE_TYPE}
    prompt_data["task"] = PROMPTS["1.2. accumulate_search_terms"].format(**prompt_data, num_terms=len(search_terms), terms="\n".join(search_terms))
    prompt = PROMPTS["0. common"].format(**prompt_data)

    for num_attempt in range(1, max_attempts + 1):
        response = get_content(prompt, model_size="large", log=True, read_cache=(num_attempt == 1))

        if is_none_response(response):
            return []

        new_terms = [t.strip() for t in response.splitlines()]
        new_terms = [t for t in new_terms if t]
        new_terms = [t for t in new_terms if not is_none_response(t)]
        new_terms = [t for t in new_terms if t not in search_terms]

        if not new_terms:
            return []

        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            response_is_valid = is_search_terms_list_valid(new_terms)
        if not response_is_valid:
            error = error.getvalue().rstrip().removeprefix("Error: ")
            if num_attempt == max_attempts:
                raise LanguageModelOutputStructureError(error)
            else:
                print_warning(f"Fault in attempt {num_attempt} of {max_attempts} while accumulating section terms: {error}")
                continue

        break

    assert new_terms
    return new_terms


def accumulate_search_terms(user_query: str, source_module: ModuleType, search_terms: list[str]) -> list[str]:
    """Return the current and accumulated search terms.

    The internal functions raise `LanguageModelOutputError` if the model output has an error.
    The subclass `LanguageModelOutputStructureError` is raised by it if the output is structurally invalid.
    """
    assert search_terms
    num_original_search_terms = len(search_terms)

    iteration = 1
    while True:
        num_old_search_terms = len(search_terms)
        # Note: It is useful for the order of search_terms to be preserved as is.
        new_search_terms = _accumulate_search_terms(user_query, source_module, search_terms)
        search_terms.extend(new_search_terms)
        print(f"Search terms counts: {iteration=} original={num_original_search_terms} old={num_old_search_terms} new={len(new_search_terms)}, total={len(search_terms)}")
        if new_search_terms:
            print(f"New search terms ({len(new_search_terms)}) in iteration {iteration}: " + ", ".join(new_search_terms))
        else:
            break
        iteration += 1

    return search_terms
