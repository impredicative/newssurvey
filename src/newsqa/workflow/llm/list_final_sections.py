import contextlib
import copy
import io
import itertools
import random
import re
from types import ModuleType
from typing import Final

from newsqa.config import PROMPTS
from newsqa.exceptions import LanguageModelOutputStructureError
from newsqa.types import AnalyzedArticle
from newsqa.util.openai_ import get_content
from newsqa.util.sys_ import print_error, print_warning

_DRAFT_SECTION_PATTERN = re.compile(r"(?P<num>\d+)\. (?P<draft>.+?)")
_RESPONSE_SECTION_PATTERN = re.compile(r"(?P<num>\d+)\. (?P<draft>.+?) → (?P<final>.+)")

_ABSTAINED_FINAL_SECTION_NAME = "(abstain)"
_INVALID_FINAL_SECTION_NAMES_TITLECASED = {"Not Applicable", "Abstain"}
assert all(s.istitle() for s in _INVALID_FINAL_SECTION_NAMES_TITLECASED)


def _are_sections_valid(numbered_draft_sections: list[str], numbered_response_sections: list[str]) -> bool:
    """Return true if the draft and final section names are valid, otherwise false.

    A validation error is printed if a section name is invalid.

    Example of draft section: "123. Relation of Daytime Drowsiness to Alzheimer's Disease Risk"
    Example of response section: "123. Relation of Daytime Drowsiness to Alzheimer's Disease Risk → Alzheimer's Disease and Daytime Drowsiness"
    """
    if not numbered_draft_sections:
        print_error("No draft section names exist.")
        return False

    if not numbered_response_sections:
        print_error("No response section names exist.")
        return False

    num_draft_sections = len(numbered_draft_sections)
    num_response_sections = len(numbered_response_sections)
    if num_draft_sections != num_response_sections:
        print_error(f"The number of draft sections ({num_draft_sections}) and response sections ({num_response_sections}) are unequal.")
        return False

    for num, (numbered_draft_section, numbered_response_section) in enumerate(itertools.zip_longest(numbered_draft_sections, numbered_response_sections), start=1):
        if not isinstance(numbered_draft_section, str):  # Can be None if the list is exhausted given the use of zip_longest.
            print_error(f"Draft section #{num} is missing.")
            return False
        if not isinstance(numbered_response_section, str):  # Can be None if the list is exhausted given the use of zip_longest.
            print_error(f"Response section #{num} is missing.")
            return False

        draft_match = _DRAFT_SECTION_PATTERN.fullmatch(numbered_draft_section)
        if not draft_match:
            print_error(f"Draft section string #{num} is invalid: {numbered_draft_section!r}")
            return False
        response_match = _RESPONSE_SECTION_PATTERN.fullmatch(numbered_response_section)
        if not response_match:
            print_error(f"Response section string #{num} is invalid: {numbered_response_section!r}")
            return False

        draft_num, response_num = int(draft_match.group("num")), int(response_match.group("num"))
        if num != draft_num:
            print_error(f"The expected draft section number ({num}) and actual draft section number ({draft_num}) are unequal. The draft section string is: {numbered_draft_section!r}")
            return False
        if draft_num != response_num:
            print_error(f"The draft section number ({draft_num}) and response section number ({response_num}) are unequal. The response section string is: {numbered_response_section!r}")
            return False

        draft_section, response_draft_section = draft_match.group("draft"), response_match.group("draft")
        if draft_section.casefold() != response_draft_section.casefold():
            print_error(f"The #{num} draft section name ({draft_section!r}) and response draft section name ({response_draft_section!r}) are unequal. The response section string is: {numbered_response_section!r}")
            return False

        response_final_section = response_match.group("final")
        if response_final_section != response_final_section.strip():
            print_error(f"The #{num} final section name has leading or trailing whitespace: {response_final_section!r}")
            return False
        if not response_final_section:
            print_error(f"The #{num} final section name is empty. The response section string is: {numbered_response_section!r}")
        if (response_final_section != draft_section) and (response_final_section.title() in _INVALID_FINAL_SECTION_NAMES_TITLECASED):
            print_error(f"The #{num} final section name ({response_final_section!r}) is invalid. The response section string is: {numbered_response_section!r}")
            return False

    return True


def _list_final_sections_for_sample(user_query: str, source_module: ModuleType, draft_sections: list[str], *, max_attempts: int = 3) -> dict[str, str]:
    """Return a mapping of the given sample of draft section names to their suggested final section names.

    Any draft section names that the model abstains from providing final section names for are skipped from the returned mapping.

    `LanguageModelOutputError` is raised if the model output has an error.
    Specifically, its subclass `LanguageModelOutputStructureError` is raised if the output is structurally invalid.
    """
    # return {draft_section: draft_section.title() for draft_section in draft_sections}  # Placeholder.
    assert user_query
    assert draft_sections

    prompt_data = {"user_query": user_query, "source_site_name": source_module.SOURCE_SITE_NAME, "source_type": source_module.SOURCE_TYPE}
    numbered_draft_sections = [f"{i}. {s}" for i, s in enumerate(draft_sections, start=1)]
    numbered_draft_sections_str = "\n".join(numbered_draft_sections)
    prompt_data["task"] = PROMPTS["4. list_final_sections"].format(**prompt_data, draft_sections=numbered_draft_sections_str)
    prompt = PROMPTS["0. common"].format(**prompt_data)

    for num_attempt in range(1, max_attempts + 1):
        response = get_content(prompt, model_size="small", log=True, read_cache=num_attempt == 1)

        numbered_response_sections = [line.strip() for line in response.splitlines()]
        numbered_response_sections = [line for line in numbered_response_sections if line]

        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            response_is_valid = _are_sections_valid(numbered_draft_sections, numbered_response_sections)
        if not response_is_valid:
            error = error.getvalue().rstrip().removeprefix("Error: ")
            if num_attempt == max_attempts:
                raise LanguageModelOutputStructureError(error)
            else:
                print_warning(f"Fault in attempt {num_attempt} of {max_attempts} while getting final section names: {error}")
                # Observed message: Error: The #79 draft section name ('Circadian Rhythms and Sleep Patterns') and response draft section name ('Circadian Rhythms and Their Impact on Sleep Patterns') are unequal. The response section string is: '79. Circadian Rhythms and Their Impact on Sleep Patterns → Circadian Rhythms and Sleep'
                continue

        break

    numbered_response_matches = [_RESPONSE_SECTION_PATTERN.fullmatch(line) for line in numbered_response_sections]
    draft_to_final_sections = {m.group("draft"): m.group("final") for m in numbered_response_matches}

    abstained_draft_sections = [draft_section_name for draft_section_name, final_section_name in draft_to_final_sections.items() if (final_section_name.lower() == _ABSTAINED_FINAL_SECTION_NAME)]
    if abstained_draft_sections:
        # Note: This feature is implemented to discourage the model from emitting an invalid value for the final section name, e.g. "Not Applicable", as had otherwise been observed.
        num_draft_sections, num_abstained_draft_sections = len(draft_to_final_sections), len(abstained_draft_sections)
        msg = f"The model abstained from providing final section names for {num_abstained_draft_sections}/{num_draft_sections} draft sections names: {", ".join(abstained_draft_sections)}"
        if num_abstained_draft_sections == num_draft_sections:
            raise LanguageModelOutputStructureError(msg)
        print(msg)
        for abstained_draft_section in abstained_draft_sections:
            assert draft_to_final_sections[abstained_draft_section].lower() == _ABSTAINED_FINAL_SECTION_NAME
            del draft_to_final_sections[abstained_draft_section]  # skipped from the returned mapping.
            # draft_to_final_sections[abstained_draft_section] = abstained_draft_section  # mapped to the corresponding draft section names.

    assert draft_to_final_sections
    return draft_to_final_sections


def list_final_sections(user_query: str, source_module: ModuleType, articles_and_draft_sections: list[AnalyzedArticle]) -> list[AnalyzedArticle]:
    """Return a list of tuples containing the search article and respective final section names.

    The internal function `_list_final_sections_for_sample` raises `LanguageModelOutputError` if the model output has an error.
    Specifically, its subclass `LanguageModelOutputStructureError` is raised by it if the output is structurally invalid.
    """
    num_unique_original_sections: Final[int] = len({s for a in articles_and_draft_sections for s in a["sections"]})
    articles_and_sections = copy.deepcopy(articles_and_draft_sections)
    del articles_and_draft_sections  # Note: This prevents accidental modification of draft sections.

    votes_needed_to_finalize_section = 1  # Note: Using a value >1, e.g. 2, whether initially or incrementally, led to extremely slow progress with convergence in comparison to a fixed value of 1.
    rng = random.Random(0)

    draft_to_final_section_candidate_counts: dict[str, dict[str, int]] = {}
    cycle_num, iteration_num = 1, 0
    num_unique_sections_by_cycle: list[int] = [num_unique_original_sections]
    while True:
        unique_sections = {s for a in articles_and_sections for s in a["sections"]}
        num_unique_sections = len(unique_sections)
        num_unique_sections_finalized = sum((max(draft_to_final_section_candidate_counts.get(s, {}).values(), default=0) >= votes_needed_to_finalize_section) for s in unique_sections)
        num_votes_cast = sum(sum(draft_to_final_section_candidate_counts.get(s, {}).values()) for s in unique_sections)
        print(f"After iteration {iteration_num} in cycle {cycle_num}, with {num_votes_cast:,} active votes, the section name counts are: finalized={num_unique_sections_finalized} draft={num_unique_sections} original={num_unique_original_sections}")
        if num_unique_sections == num_unique_sections_finalized:
            num_unique_sections_by_cycle.append(num_unique_sections)
            assert num_unique_sections_by_cycle[cycle_num] == num_unique_sections_by_cycle[-1] == num_unique_sections
            if num_unique_sections_by_cycle[-1] == num_unique_sections_by_cycle[-2]:
                print(f"Convergence reached after {iteration_num} iterations in cycle {cycle_num} for finalizing section names.")
                break
            cycle_num += 1
            draft_to_final_section_candidate_counts.clear()
        iteration_num += 1
        # input("Press Enter to continue...")

        max_section_sample_size = {num_unique_sections >= 100: 100, num_unique_sections < 100: 50}[True]
        # Note:
        # * Using 200 or 300 led to a very slow response requiring over a minute.
        # * Using 100 led to a convergence at just over 80 final sections.
        # * Dynamically using 50 led to a convergence at just over 50 final sections.

        sample_draft_sections = rng.sample(sorted(unique_sections), min(max_section_sample_size, num_unique_sections))  # Note: `sorted` is used to ensure deterministic sample selection.
        sample_draft_to_final_sections = _list_final_sections_for_sample(user_query, source_module, sample_draft_sections)
        for draft_section, final_section in sample_draft_to_final_sections.items():
            draft_to_final_section_candidate_counts.setdefault(draft_section, {})
            prev_max_final_section_candidate_count = max(draft_to_final_section_candidate_counts[draft_section].values(), default=0)
            final_section_candidate_count = draft_to_final_section_candidate_counts[draft_section].get(final_section, 0) + 1
            draft_to_final_section_candidate_counts[draft_section][final_section] = final_section_candidate_count
            if (draft_section != final_section) and (final_section_candidate_count >= votes_needed_to_finalize_section) and (final_section_candidate_count >= prev_max_final_section_candidate_count):
                # Note: `>=` is intentionally used when tie-breaking against prev_max_final_section_candidate_count. This is considering that the latest vote is considered to be over a more finalized sample, and is therefore preferred.
                for article in articles_and_sections:
                    article_sections = article["sections"]
                    assert article_sections
                    if draft_section in article_sections:
                        article_sections.remove(draft_section)
                        if final_section not in article_sections:
                            article_sections.append(final_section)
                        assert draft_section not in article["sections"]
                        assert final_section in article["sections"]
                print(f"In iteration {iteration_num} in cycle {cycle_num}, renamed draft section {draft_section!r} to final section {final_section!r}.")

    return articles_and_sections
