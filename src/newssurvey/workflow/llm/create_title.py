import contextlib
import io
from types import ModuleType

from newssurvey.config import PROMPTS
from newssurvey.exceptions import LanguageModelOutputStructureError
from newssurvey.util.openai_ import get_content
from newssurvey.util.sys_ import print_error, print_warning


def _is_title_valid(title: str) -> bool:
    """Return true if the title is valid, otherwise false.

    A validation error is printed if the title is invalid.
    """
    if not title:
        print_error("The title is empty.")
        return False

    if title != title.strip():
        print_error(f"The title has leading or trailing whitespace: {title!r}")
        return False

    num_lines = title.splitlines()
    if len(num_lines) != 1:
        print_error(f"The title has {num_lines} lines but a single line was expected: {title!r}")
        return False

    if title.startswith('"') and title.endswith('"'):
        print_error(f"The title is wrapped in double quotes: {title!r}")
        return False

    return True


def create_title(user_query: str, source_module: ModuleType, *, sections: list[str], max_attempts: int = 1) -> str:
    """Return a title using the given section names.

    `LanguageModelOutputError` is raised if the model output has an error.
    Specifically, its subclass `LanguageModelOutputStructureError` is raised by it if the output is structurally invalid.
    """
    assert sections

    numbered_sections = [f"{i}. {s}" for i, s in enumerate(sections, start=1)]
    numbered_sections_str = "\n".join(numbered_sections)

    prompt_data = {"user_query": user_query, "source_site_name": source_module.SOURCE_SITE_NAME, "source_type": source_module.SOURCE_TYPE}
    prompt_data["task"] = PROMPTS["7. create_title"].format(sections=numbered_sections_str)
    prompt = PROMPTS["0. common"].format(**prompt_data)

    for num_attempt in range(1, max_attempts + 1):
        response = get_content(prompt, model_size="large", log=True, read_cache=(num_attempt == 1))

        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            response_is_valid = _is_title_valid(response)
        if not response_is_valid:
            error = error.getvalue().rstrip().removeprefix("Error: ")
            if num_attempt == max_attempts:
                raise LanguageModelOutputStructureError(error)
            else:
                print_warning(f"Fault in attempt {num_attempt} of {max_attempts} while getting title: {error}")
                continue

        break

    return response
