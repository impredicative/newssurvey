import contextlib
import copy
import io
import itertools
import random
import re
from types import ModuleType

from newsqa.config import PROMPTS
from newsqa.exceptions import LanguageModelOutputStructureError
from newsqa.util.int import triangular_number
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


def _order_final_sections(user_query: str, source_module: ModuleType, sections: list[str], *, max_attempts: int = 5) -> list[str]:
    """Return a list of sections ordered by relevance to the user query.

    `LanguageModelOutputError` is raised if the model output has an error.
    Specifically, its subclass `LanguageModelOutputStructureError` is raised if the output is structurally invalid.
    """
    assert user_query
    assert sections

    input_sections = sections
    del sections

    rng = random.Random(0)
    prompt_source_data = {"user_query": user_query, "source_site_name": source_module.SOURCE_SITE_NAME, "source_type": source_module.SOURCE_TYPE}

    for num_attempt in range(1, max_attempts + 1):
        if num_attempt > 1:
            rng.shuffle(input_sections)

        numbered_input_sections = [f"{i}. {s}" for i, s in enumerate(input_sections, start=1)]
        numbered_input_sections_str = "\n".join(numbered_input_sections)
        prompt_data = copy.deepcopy(prompt_source_data)
        prompt_data["task"] = PROMPTS["5. order_final_sections"].format(**prompt_data, unordered_subtopics=numbered_input_sections_str)
        prompt = PROMPTS["0. common"].format(**prompt_data)

        response = get_content(prompt, model_size="small", log=(num_attempt > 1))

        if response.strip().lower() == "(ordered)":
            # return input_sections
            response = numbered_input_sections_str

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
                print_warning(f"Fault in attempt {num_attempt} of {max_attempts} while getting ordered section names: {error}")
                continue

        break

    numbered_output_matches = [_SECTION_PATTERN.fullmatch(line) for line in numbered_output_sections]
    output_sections = [match["section"] for match in numbered_output_matches]

    assert output_sections
    return output_sections


def _update_scores(scores: dict[str, int], ordered_sample: list[str]) -> None:
    """Update the scores in-place based on the ordered sample."""
    sample_len = len(ordered_sample)
    for idx, item in enumerate(ordered_sample[:-1]):
        old_score = scores[item]
        increment = sample_len - idx - 1  # Does not converge by itself due to insufficient separation between scores.
        increment = triangular_number(increment)  # Converges. For slightly slower convergence, append `// 2`.
        new_score = old_score + increment
        scores[item] = new_score
        # print(f"Section {item!r} with a score of {old_score} has been incremented by {increment} to a new score of {new_score}.")


def _get_sort_solution(items: list[str], scores: dict[str, int]) -> list[str]:
    """Get a sort solution, whether full or partial, based on the current scores."""
    sorted_items = sorted(items, key=lambda item: scores[item], reverse=True)

    ordered_items = []
    for idx, item in enumerate(sorted_items[:-1]):
        next_item = sorted_items[idx + 1]
        item_score, next_item_score = scores[item], scores[next_item]
        if item_score > next_item_score:
            ordered_items.append(item)
        else:
            print(f"Invalid order: Section {item!r} of index {idx} with a score of {item_score} does not have a greater score than next section {next_item!r} with a score of {next_item_score}.")
            break
    else:
        ordered_items.append(sorted_items[-1])
        assert sorted_items == ordered_items

    return ordered_items


def order_final_sections(user_query: str, source_module: ModuleType, sections: list[str]) -> list[str]:
    """Return a list of sections ordered by relevance to the user query.

    The internal function `_order_final_sections` raises `LanguageModelOutputError` if the model output has an error.
    Specifically, its subclass `LanguageModelOutputStructureError` is raised by it if the output is structurally invalid.
    """
    assert len(sections) == len(set(sections))  # Ensure there are no duplicate sections.
    sections = sorted(sections)  # Note: Without this, the LLM response cannot be cached because the order of the input sections was not deterministic.
    num_sections = len(sections)

    max_section_sample_size = 20  # Number of iterations observed to be required for 76 sections: 10→118; 20→45; 25→20 (risky due to retried errors); 30→failure
    if num_sections <= max_section_sample_size:
        return _order_final_sections(user_query, source_module, sections)
    rng = random.Random(0)
    scores = {item: 0 for item in sections}

    iteration = 0
    while True:
        ordered_sections = _get_sort_solution(sections, scores)
        print(f"After iteration {iteration}, there are {len(ordered_sections)} out of {num_sections} sections in order.")
        if len(ordered_sections) == num_sections:
            print("The section ordering and scores are:\n\t" + "\n\t".join([f"{i}. {s} ({scores[s]})" for i, s in enumerate(ordered_sections, start=1)]))
            break
        iteration += 1

        sample_sections = rng.sample(sections, min(max_section_sample_size, num_sections))
        ordered_sample_sections = _order_final_sections(user_query, source_module, sample_sections)
        _update_scores(scores, ordered_sample_sections)

    assert len(ordered_sections) == len(sections)
    assert set(ordered_sections) == set(sections)
    assert len(ordered_sections) == len(set(ordered_sections))
    return ordered_sections
