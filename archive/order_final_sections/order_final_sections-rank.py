import contextlib
import copy
import io
import itertools
import re
from types import ModuleType

from newssurvey.config import PROMPTS
from newssurvey.exceptions import LanguageModelOutputStructureError
from newssurvey.util.openai_ import get_content
from newssurvey.util.sys_ import print_error, print_warning

_INPUT_SECTION_PATTERN = re.compile(r"(?P<num>\d+)\. (?P<section>.+?)")
_OUTPUT_SECTION_PATTERN = re.compile(r"(?P<num>\d+)\. (?P<section>.+?) → (?P<rank>\d+)")


def _are_sections_valid(numbered_input_sections: list[str], numbered_output_sections: list[str]) -> bool:
    """Return true if the output sections have a valid ranking of the input sections."""
    if not numbered_input_sections:
        print_error("No input section names exist.")
        return False

    if not numbered_output_sections:
        print_error("No output section names exist.")
        return False

    num_input_sections, num_output_sections = len(numbered_input_sections), len(numbered_output_sections)
    if num_input_sections != num_output_sections:
        print_error(f"The number of input sections ({num_input_sections}) and output sections ({num_output_sections}) are unequal.")
        return False

    for num, (numbered_input_section, numbered_output_section) in enumerate(itertools.zip_longest(numbered_input_sections, numbered_output_sections), start=1):
        if not isinstance(numbered_input_section, str):  # Can be None if the list is exhausted given the use of zip_longest.
            print_error(f"Input section #{num} is missing.")
            return False
        if not isinstance(numbered_output_section, str):  # Can be None if the list is exhausted given the use of zip_longest.
            print_error(f"Output section #{num} is missing.")
            return False

        input_match = _INPUT_SECTION_PATTERN.fullmatch(numbered_input_section)
        if not input_match:
            print_error(f"Input section string #{num} is invalid: {numbered_input_section!r}")
            return False
        output_match = _OUTPUT_SECTION_PATTERN.fullmatch(numbered_output_section)
        if not output_match:
            print_error(f"Output section string #{num} is invalid: {numbered_output_section!r}")
            return False

        input_num, output_num = int(input_match.group("num")), int(output_match.group("num"))
        if num != input_num:
            print_error(f"The expected input section number ({num}) and actual input section number ({input_num}) are unequal. The input section string is: {numbered_input_section!r}")
            return False
        if input_num != output_num:
            print_error(f"The input section number ({input_num}) and output section number ({output_num}) are unequal. The output section string is: {numbered_output_section!r}")
            return False

        input_section = input_match.group("section")
        if input_section != input_section.strip():
            print_error(f"The #{num} input section name has leading or trailing whitespace: {input_section!r}")
            return False
        if not input_section:
            print_error(f"The #{num} input section name is empty. The input section string is: {numbered_input_section!r}")
            return False
        output_section = output_match.group("section")
        if input_section != output_section:
            print_error(f"The #{num} input section name ({input_section!r}) and output section name ({output_section!r}) are unequal. The output section string is: {numbered_output_section!r}")
            return False

        rank = int(output_match.group("rank"))
        if rank < 1:
            print_error(f"Section #{num} has an invalid output rank of {rank}. The output section string is: {numbered_output_section!r}")
            return False

    return True


def _order_final_sections(user_query: str, source_module: ModuleType, sections: list[str], *, max_attempts: int = 1) -> list[str]:
    """Return a list of sections ordered by relevance to the user query.

    `LanguageModelOutputError` is raised if the model output has an error.
    Specifically, its subclass `LanguageModelOutputStructureError` is raised if the output is structurally invalid.
    """
    assert user_query
    assert sections

    input_sections = sections
    del sections

    prompt_source_data = {"user_query": user_query, "source_site_name": source_module.SOURCE_SITE_NAME, "source_type": source_module.SOURCE_TYPE}
    num_input_sections = len(input_sections)
    numbered_input_sections = [f"{i}. {s}" for i, s in enumerate(input_sections, start=1)]
    numbered_input_sections_str = "\n".join(numbered_input_sections)
    prompt_data = copy.deepcopy(prompt_source_data)
    prompt_data["task"] = PROMPTS["5. rank_final_sections"].format(**prompt_data, unordered_subtopics=numbered_input_sections_str, num_subtopics=num_input_sections)
    prompt = PROMPTS["0. common"].format(**prompt_data)

    for num_attempt in range(1, max_attempts + 1):
        response = get_content(prompt, model_size="large", log=(num_attempt > 1))  # Note: small model performed poorly.
        numbered_output_sections = [line.strip() for line in response.splitlines()]
        numbered_output_sections = [line for line in numbered_output_sections if line]

        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            response_is_valid = _are_sections_valid(numbered_input_sections, numbered_output_sections)
        if not response_is_valid:
            error = error.getvalue().rstrip().removeprefix("Error: ")
            if num_attempt == max_attempts:
                raise LanguageModelOutputStructureError(error)
            else:
                print_warning(f"Fault in attempt {num_attempt} of {max_attempts} while getting ranked section names: {error}")
                continue

        break

    output_matches = [_OUTPUT_SECTION_PATTERN.fullmatch(line) for line in numbered_output_sections]
    output_sections = [{"num": int(match.group("num")), "section": match.group("section"), "rank": int(match.group("rank"))} for match in output_matches]
    output_sections.sort(key=lambda section: (section["rank"], section["num"]))
    output_sections = [section["section"] for section in output_sections]

    assert len(output_sections) == num_input_sections
    assert set(output_sections) == set(input_sections)
    assert len(output_sections) == len(set(output_sections))
    return output_sections


def order_final_sections(user_query: str, source_module: ModuleType, sections: list[str]) -> list[str]:
    """Return a list of sections ordered by relevance to the user query.

    The internal function `_order_final_sections` raises `LanguageModelOutputError` if the model output has an error.
    Specifically, its subclass `LanguageModelOutputStructureError` is raised by it if the output is structurally invalid.
    """
    assert len(sections) == len(set(sections))  # Ensure there are no duplicate sections.
    sections = sorted(sections)  # Note: Without this, the LLM response cannot be cached because the order of the input sections was not deterministic.
    num_sections = len(sections)

    num_successive_convergences_required = 1  # Results were not observed to benefit with >1.

    iteration = 0
    num_successive_convergences = 0
    prev_ordered_sections = [None] * num_sections
    ordered_sections = sections
    while True:
        num_ordered = sum(1 for (prev_section, section) in itertools.zip_longest(prev_ordered_sections, ordered_sections) if (prev_section == section))
        print(f"After iteration {iteration}, there are {num_ordered} out of {num_sections} sections in order.")
        if (iteration > 0) and (num_ordered == num_sections):
            num_successive_convergences += 1
            print(f"Convergence {num_successive_convergences}/{num_successive_convergences_required} reached after {iteration} iterations for ordering section names.")
            if num_successive_convergences == num_successive_convergences_required:
                break
        elif num_successive_convergences > 0:
            num_successive_convergences = 0
        iteration += 1
        prev_ordered_sections = ordered_sections

        ordered_sections = _order_final_sections(user_query, source_module, ordered_sections)

    assert len(ordered_sections) == len(sections)
    assert set(ordered_sections) == set(sections)
    assert len(ordered_sections) == len(set(ordered_sections))
    return ordered_sections
