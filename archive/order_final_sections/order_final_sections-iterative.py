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
            print_error(f"Output section #{num} is missing.")
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


def _update_scores(scores: dict[str, dict[str, int]], ordered_sample: list[str], *, increment: str = "linear") -> None:
    """Update the scores in-place based on the ordered sample.

    The `increment` parameter can be either "linear" or "triangular".
    """
    sample_len = len(ordered_sample)
    for idx, item in enumerate(ordered_sample):
        old_score = scores[item]["score"]
        score_increment = sample_len - idx  # Converges. Note: `- 1` is intentionally not appended in order to avoid the last section getting a score of 0.
        match increment:
            case "linear":
                pass
            case "triangular":
                score_increment = triangular_number(score_increment)  # Not necessary. Converges in fewer iterations. For slightly slower convergence, append `// 2`.
            case _:
                raise ValueError(f"Invalid increment: {increment!r}")
        new_score = old_score + score_increment
        scores[item]["score"] = new_score
        scores[item]["hits"] += 1
        scores[item]["adj_score"] = scores[item]["score"] / scores[item]["hits"]


def _get_sort_solution(items: list[str], scores: dict[str, dict[str, int]]) -> list[str]:
    """Get a sort solution, whether full or partial, based on the current scores."""
    min_hits_threshold = 3
    sorted_items = sorted(items, key=lambda item: scores[item]["adj_score"], reverse=True)

    ordered_items = []
    for idx, item in enumerate(sorted_items[:-1]):
        item_hits = scores[item]["hits"]
        if item_hits < min_hits_threshold:
            print(f"Insufficient hits: section={item!r} (hits={item_hits})")
            break
        next_item = sorted_items[idx + 1]
        item_score, next_item_score = scores[item]["adj_score"], scores[next_item]["adj_score"]
        if item_score > next_item_score > 0:
            ordered_items.append(item)
        else:
            print(f"Invalid order: section={item!r} (adj_score={item_score:.2f}) next_section={next_item!r} (adj_score={next_item_score:.2f})")
            break
    else:
        item = sorted_items[-1]
        item_hits = scores[item]["hits"]
        if item_hits >= min_hits_threshold:
            ordered_items.append(sorted_items[-1])
            assert sorted_items == ordered_items
        else:
            print(f"Insufficient hits: section={item!r} (hits={item_hits})")

    return ordered_items


def order_final_sections(user_query: str, source_module: ModuleType, sections: list[str]) -> list[str]:
    """Return a list of sections ordered by relevance to the user query.

    The internal function `_order_final_sections` raises `LanguageModelOutputError` if the model output has an error.
    Specifically, its subclass `LanguageModelOutputStructureError` is raised by it if the output is structurally invalid.
    """
    assert len(sections) == len(set(sections))  # Ensure there are no duplicate sections.
    sections = sorted(sections)  # Note: Without this, the LLM response cannot be cached because the order of the input sections was not deterministic.
    num_sections = len(sections)

    max_section_sample_size = 20  # Values ≥30 were observed to fail with the small model. 25 may still work, but 20 is a safe choice.
    if num_sections <= max_section_sample_size:
        return _order_final_sections(user_query, source_module, sections)
    rng = random.Random(0)
    scores = {item: {"hits": 0, "score": 0, "adj_score": 0} for item in sections}

    iteration = 0
    while True:
        ordered_sections = _get_sort_solution(sections, scores)
        print(f"After iteration {iteration}, there are {len(ordered_sections)} out of {num_sections} sections in order.")
        if len(ordered_sections) == num_sections:
            print("The section ordering and scores are:\n\t" + "\n\t".join([f"{i}. {s} (hits={scores[s]['hits']}, score={scores[s]['score']}, adj_score={scores[s]['adj_score']:.1f})" for i, s in enumerate(ordered_sections, start=1)]))
            break
        iteration += 1

        sample_sections = rng.sample(sections, min(max_section_sample_size, num_sections))
        ordered_sample_sections = _order_final_sections(user_query, source_module, sample_sections)
        _update_scores(scores, ordered_sample_sections)

    assert len(ordered_sections) == len(sections)
    assert set(ordered_sections) == set(sections)
    assert len(ordered_sections) == len(set(ordered_sections))
    return ordered_sections
