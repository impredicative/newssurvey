import contextlib
import copy
import io
import re
from types import ModuleType

from newsqa.config import PROMPTS, NUM_SECTIONS_MIN, NUM_SECTIONS_MAX
from newsqa.exceptions import LanguageModelOutputStructureError
from newsqa.types import AnalyzedArticleGen1
from newsqa.util.openai_ import get_content, MODELS
from newsqa.util.scipy_ import sort_by_distance
from newsqa.util.sys_ import print_error, print_warning
from newsqa.util.tiktoken_ import fit_items_to_input_token_limit

_SECTION_PATTERN = re.compile(r"(?P<num>\d+)\. (?P<section>.+?)")


def _are_sections_valid(numbered_sections: list[str]) -> bool:
    """Return true if the section names are valid, otherwise false.

    A validation error is printed if a section name is invalid.

    Example of valid section: "3. Epidemiology of daytime drowsiness"
    """
    if not numbered_sections:
        print_error("No sections found.")
        return False

    seen = set()
    for num, numbered_section in enumerate(numbered_sections, start=1):
        if not isinstance(numbered_section, str):
            print_error(f"Section {num} is not a string.")
            return False

        match = _SECTION_PATTERN.fullmatch(numbered_section)
        if not match:
            print_error(f"Section line #{num} does not match expected pattern. The section string is: {numbered_section!r}")
            return False

        section_num = int(match["num"])
        if section_num != num:
            print_error(f"Section number #{num} is not sequential. The section string is: {numbered_section!r}")
            return False

        section = match["section"]
        section_casefold = section.casefold()
        if section_casefold in seen:
            print_error(f"Section name #{num} is a duplicate. The section string is: {numbered_section!r}")
            return False
        seen.add(section_casefold)

    return True


def _list_final_sections(user_query: str, source_module: ModuleType, draft_sections: list[str], *, max_sections: int, max_attempts: int = 3) -> list[str]:
    assert user_query
    assert draft_sections

    prompt_data = {"user_query": user_query, "source_site_name": source_module.SOURCE_SITE_NAME, "source_type": source_module.SOURCE_TYPE}

    def prompt_formatter(draft_sections_truncated: list[str]) -> str:
        numbered_draft_sections = [f"{i}. {s}" for i, s in enumerate(draft_sections_truncated, start=1)]
        numbered_draft_sections_str = "\n".join(numbered_draft_sections)
        prompt_data["task"] = PROMPTS["4. list_final_sections"].format(**prompt_data, draft_sections=numbered_draft_sections_str, max_sections=max_sections)
        prompt = PROMPTS["0. common"].format(**prompt_data)
        return prompt

    model_size = "large"
    prompt = fit_items_to_input_token_limit(draft_sections, model=MODELS["text"][model_size], formatter=prompt_formatter, approach="rate")

    for num_attempt in range(1, max_attempts + 1):
        response = get_content(prompt, model_size=model_size, log=True or (num_attempt == max_attempts), read_cache=(num_attempt == 1))

        numbered_response_sections = [line.strip() for line in response.splitlines()]
        numbered_response_sections = [line for line in numbered_response_sections if line]

        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            response_is_valid = _are_sections_valid(numbered_response_sections)
        if not response_is_valid:
            error = error.getvalue().rstrip().removeprefix("Error: ")
            if num_attempt == max_attempts:
                raise LanguageModelOutputStructureError(error)
            else:
                print_warning(f"Fault in attempt {num_attempt} of {max_attempts} while getting final section names: {error}")
                continue

        break

    numbered_response_matches = [_SECTION_PATTERN.fullmatch(line) for line in numbered_response_sections]
    final_sections = [match["section"] for match in numbered_response_matches]
    return final_sections


def list_final_sections(user_query: str, source_module: ModuleType, *, articles_and_draft_sections: list[AnalyzedArticleGen1], max_sections: int) -> list[str]:
    """Return a list of dictionaries containing the ordered final section names.

    The internal functions raise `LanguageModelOutputError` if the model output has an error.
    Specifically, its subclass `LanguageModelOutputStructureError` is raised by it if the output is structurally invalid.
    """
    assert NUM_SECTIONS_MIN <= max_sections <= NUM_SECTIONS_MAX, (max_sections, NUM_SECTIONS_MIN, NUM_SECTIONS_MAX)

    articles_and_sections = copy.deepcopy(articles_and_draft_sections)
    del articles_and_draft_sections  # Note: This prevents accidental modification of draft sections.

    draft_sections = list({s for a in articles_and_sections for s in a["sections"]})
    draft_sections = sort_by_distance(user_query, draft_sections, model_size="large", distance="cosine")
    final_sections = _list_final_sections(user_query, source_module, draft_sections, max_sections=max_sections)

    assert final_sections
    return final_sections
