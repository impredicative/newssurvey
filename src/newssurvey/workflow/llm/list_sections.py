import contextlib
import io
import re
from types import ModuleType
from typing import Optional

from newssurvey.config import PROMPTS, NUM_SECTIONS_MIN, NUM_SECTIONS_MAX
from newssurvey.exceptions import LanguageModelOutputRejectionError, LanguageModelOutputStructureError
from newssurvey.util.openai_ import get_content, MODELS
from newssurvey.util.scipy_ import sort_by_distance
from newssurvey.util.str import is_none_response
from newssurvey.util.sys_ import print_error, print_warning
from newssurvey.util.tiktoken_ import fit_items_to_input_token_limit

SECTION_PATTERN = re.compile(r"(?P<num>\d+)\. (?P<section>.+?)")  # Also used by refine_sections.


def are_sections_valid(numbered_sections: list[str], max_sections: int) -> bool:  # Also used by refine_sections.
    """Return true if the section names are valid, otherwise false.

    A validation error is printed if a section name is invalid.

    Example of valid section: "3. Epidemiology of daytime drowsiness"
    """
    if not numbered_sections:
        print_error("No sections found.")
        return False

    if len(numbered_sections) > max_sections:
        print_error(f"Number of sections ({len(numbered_sections)}) exceeds the maximum number of permissible sections ({max_sections}).")
        return False

    seen = set()
    for num, numbered_section in enumerate(numbered_sections, start=1):
        if not isinstance(numbered_section, str):
            print_error(f"Section {num} is not a string.")
            return False

        match = SECTION_PATTERN.fullmatch(numbered_section)
        if not match:
            print_error(f"Section line #{num} does not match expected pattern. The section string is: {numbered_section!r}")
            return False

        section_num = int(match["num"])
        if section_num != num:
            print_error(f"Section #{num} is not sequential. The section string is: {numbered_section!r}")
            return False

        section = match["section"]
        section_casefold = section.casefold()
        if section_casefold in seen:
            print_error(f"Section #{num} is a duplicate. The section string is: {numbered_section!r}")
            return False
        seen.add(section_casefold)

        if section.endswith(":"):
            print_error(f"Section #{num} ends with a colon. The section string is: {numbered_section!r}")
            return False

    return True


def _list_sections(user_query: str, source_module: ModuleType, *, titles: list[str], max_sections: int, max_attempts: int = 3) -> Optional[list[str]]:
    assert user_query
    assert titles

    prompt_data = {"user_query": user_query, "source_site_name": source_module.SOURCE_SITE_NAME, "source_type": source_module.SOURCE_TYPE}

    def prompt_formatter(titles_truncated: list[str]) -> str:
        numbered_titles = [f"{i}. {s}" for i, s in enumerate(titles_truncated, start=1)]
        numbered_titles_str = "\n".join(numbered_titles)
        prompt_data["task"] = PROMPTS["3.1. list_sections"].format(num_titles=len(titles_truncated), titles=numbered_titles_str, max_sections=max_sections)
        prompt = PROMPTS["0. common"].format(**prompt_data)
        return prompt

    model_size = "large"
    num_titles_used, prompt = fit_items_to_input_token_limit(titles, model=MODELS["text"][model_size], formatter=prompt_formatter, approach="rate")
    if num_titles_used < len(titles):
        num_titles_not_used = len(titles) - num_titles_used
        print_warning(f"Used only {num_titles_used:,}/{len(titles):,} titles for getting section names, leaving the last {num_titles_not_used:,} titles unused.")

    for num_attempt in range(1, max_attempts + 1):
        response = get_content(prompt, model_size=model_size, log=True, read_cache=(num_attempt == 1))

        if is_none_response(response):
            return

        numbered_response_sections = [line.strip() for line in response.splitlines()]
        numbered_response_sections = [line for line in numbered_response_sections if line]

        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            response_is_valid = are_sections_valid(numbered_response_sections, max_sections)
        if not response_is_valid:
            error = error.getvalue().rstrip().removeprefix("Error: ")
            if num_attempt == max_attempts:
                raise LanguageModelOutputStructureError(error)
            else:
                print_warning(f"Fault in attempt {num_attempt} of {max_attempts} while getting section names: {error}")
                continue

        break

    numbered_response_matches = [SECTION_PATTERN.fullmatch(line) for line in numbered_response_sections]
    sections = [match["section"] for match in numbered_response_matches]
    return sections


def list_sections(user_query: str, source_module: ModuleType, *, titles: list[str], max_sections: int) -> list[str]:
    """Return an ordered list of section names.

    The internal functions raise `LanguageModelOutputError` if the model output has an error.
    The subclass `LanguageModelOutputRejectionError` is raised if the output is rejected.
    The subclass `LanguageModelOutputStructureError` is raised if the output is structurally invalid.
    """
    assert NUM_SECTIONS_MIN <= max_sections <= NUM_SECTIONS_MAX, (max_sections, NUM_SECTIONS_MIN, NUM_SECTIONS_MAX)

    titles = sort_by_distance(user_query, titles, model_size="large", distance="cosine")
    sections = _list_sections(user_query, source_module, titles=titles, max_sections=max_sections)

    if sections is None:
        raise LanguageModelOutputRejectionError("No sections were listed for the query based on the available articles.")

    assert sections
    return sections
