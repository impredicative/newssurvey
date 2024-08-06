import contextlib
import io
import itertools
import re
from types import ModuleType

from newsqa.config import PROMPTS
from newsqa.exceptions import LanguageModelOutputStructureError
from newsqa.util.openai_ import get_content
from newsqa.util.sys_ import print_error


_SECTION_PATTERN = re.compile(r"(?P<num>\d+)\. (?P<section>.+?)")


def _are_sections_valid(numbered_input_sections: list[str], numbered_output_sections: list[str]) -> bool:
    """Return true if the output sections are a valid permutation of the input sections."""
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

    input_sections, output_sections = set(), set()
    for num, (numbered_input_section, numbered_output_section) in enumerate(itertools.zip_longest(numbered_input_sections, numbered_output_sections), start=1):
        if not isinstance(numbered_input_section, str):  # Can be None if the list is exhausted given the use of zip_longest.
            print_error(f"Input section #{num} is missing.")
            return False
        if not isinstance(numbered_output_section, str):  # Can be None if the list is exhausted given the use of zip_longest.
            print_error(f"Response section #{num} is missing.")
            return False

        input_match = _SECTION_PATTERN.fullmatch(numbered_input_section)
        if not input_match:
            print_error(f"Input section string #{num} is invalid: {numbered_input_section!r}")
            return False
        output_match = _SECTION_PATTERN.fullmatch(numbered_output_section)
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
        if input_section in input_sections:
            print_error(f"The #{num} input section name is a duplicate: {input_section!r}")
            return False
        else:
            input_sections.add(input_section)
        output_section = output_match.group("section")
        if output_section != output_section.strip():
            print_error(f"The #{num} output section name has leading or trailing whitespace: {output_section!r}")
            return False
        if not output_section:
            print_error(f"The #{num} output section name is empty. The output section string is: {numbered_output_section!r}")
            return False
        if output_section in output_sections:
            print_error(f"The #{num} output section name is a duplicate: {output_section!r}")
            return False
        else:
            output_sections.add(output_section)

    if input_sections != output_sections:
        print_error("The input and output section names are unequal.")
        return False

    return True


def _order_final_sections(user_query: str, source_module: ModuleType, sections: list[str]) -> list[str]:
    """Return a list of sections ordered by relevance to the user query."""
    assert user_query
    assert sections

    input_sections = sections
    del sections

    prompt_data = {"user_query": user_query, "source_site_name": source_module.SOURCE_SITE_NAME, "source_type": source_module.SOURCE_TYPE}
    numbered_input_sections = [f"{i}. {s}" for i, s in enumerate(input_sections, start=1)]
    numbered_input_sections_str = "\n".join(numbered_input_sections)
    prompt_data["task"] = PROMPTS["5. order_final_sections"].format(**prompt_data, unordered_subtopics=numbered_input_sections_str)
    prompt = PROMPTS["0. common"].format(**prompt_data)

    response = get_content(prompt, model_size="large", log=True)

    if response.strip().lower() == "(ordered)":
        return input_sections

    numbered_output_sections = [line.strip() for line in response.splitlines()]
    numbered_output_sections = [line for line in numbered_output_sections if line]

    error = io.StringIO()
    with contextlib.redirect_stderr(error):
        response_is_valid = _are_sections_valid(numbered_input_sections, numbered_output_sections)
    if not response_is_valid:
        error = error.getvalue().rstrip().removeprefix("Error: ")
        raise LanguageModelOutputStructureError(error)

    numbered_output_matches = [_SECTION_PATTERN.fullmatch(line) for line in numbered_output_sections]
    output_sections = [match["section"] for match in numbered_output_matches]

    assert output_sections
    return output_sections


def order_final_sections(user_query: str, source_module: ModuleType, sections: list[str]) -> list[str]:
    """Return a list of sections ordered by relevance to the user query."""
    sections = sorted(sections)  # Note: Without this, the LLM response cannot be cached because the order of the input sections was not deterministic.
    return _order_final_sections(user_query, source_module, sections)
