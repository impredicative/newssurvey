import contextlib
import copy
import io
import itertools
import random
import re
from types import ModuleType
from typing import Callable, Final

from newsqa.config import PROMPTS
from newsqa.exceptions import LanguageModelOutputStructureError
from newsqa.types import AnalyzedArticle
from newsqa.util.openai_ import get_content
from newsqa.util.sys_ import print_error, print_warning


_SECTION_PATTERN = re.compile(r"(?P<num>\d+)\. (?P<section>.+?)")

def _are_sections_valid(numbered_input_sections: list[str], numbered_output_sections: list[str]) -> bool:
    """Return true if the output sections are a valid permutation of the input sections."""
    if not numbered_input_sections:
        print_error("No input section names exist.")
        return False

    if not numbered_output_sections:
        print_error("No output section names exist.")
        return False

    num_input_sections, numbered_output_sections = len(numbered_input_sections), len(numbered_output_sections)
    if num_input_sections != numbered_output_sections:
        print_error(f"The number of input sections ({num_dranum_input_sectionsft_sections}) and output sections ({numbered_output_sections}) are unequal.")
        return False

    for num, (input_section, output_section) in enumerate(itertools.zip_longest(numbered_input_sections, numbered_output_sections), start=1):
        if input_section != output_section:
            print_error(f"Input section {num} ({input_section}) does not match output section {num} ({output_section}).")
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

    numbered_output_matches = [_SECTION_PATTERN.fullmatch(line) for line in numbered_output_sections]
    output_sections = [match["section"] for match in numbered_output_matches]

    assert output_sections
    return output_sections

def order_final_sections(user_query: str, source_module: ModuleType, sections: list[str]) -> list[str]:
    """Return a list of sections ordered by relevance to the user query."""
    return _order_final_sections(user_query, source_module, sections)
