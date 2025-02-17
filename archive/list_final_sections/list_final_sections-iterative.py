import concurrent.futures
import contextlib
import copy
import io
import itertools
import random
import re
from types import ModuleType
from typing import Any, Callable, Final

from scipy.spatial.distance import cosine

from newssurvey.config import PROMPTS, NUM_SECTIONS_MIN, NUM_SECTIONS_MAX
from newssurvey.exceptions import LanguageModelOutputStructureError
from newssurvey.types import AnalyzedArticleGen1
from newssurvey.util.dict import dereference_dict
from newssurvey.util.itertools_ import get_batches
from newssurvey.util.openai_ import get_content, get_vector, MAX_WORKERS
from newssurvey.util.sys_ import print_error, print_warning

_DRAFT_SECTION_PATTERN = re.compile(r"(?P<num>\d+)\. (?P<draft>.+?)")
_DRAFT_SECTION_PATTERN_WITH_COUNT = re.compile(r"(?P<num>\d+)\. (?P<draft>.+?) \(refs=(?P<count>\d+)\)")
_RESPONSE_SECTION_PATTERN = re.compile(r"(?P<num>\d+)\. (?P<draft>.+?) → (?P<final>.+)")

_ABSTAINED_FINAL_SECTION_NAME = "(abstain)"
_INVALID_FINAL_SECTION_NAMES_TITLECASED = {
    "Not Applicable",  # Observed.
    "Abstain",  # Preemptive.
    "(Duplicate)",  # Observed.
    "Duplicate",  # Preemptive.
}
assert all(s.istitle() for s in _INVALID_FINAL_SECTION_NAMES_TITLECASED)

DraftSection = dict[str, Any]
DraftSections = list[DraftSection]
DraftSectionsBatch = list[DraftSections]


def _are_sections_valid(numbered_draft_sections: list[str], numbered_response_sections: list[str], use_article_counts: bool) -> bool:
    """Return true if the draft and final section names are valid, otherwise false.

    A validation error is printed if a section name is invalid.

    Example of draft section: "123. Relation of Daytime Drowsiness to Alzheimer's Disease Risk"
    Example of response section: "123. Relation of Daytime Drowsiness to Alzheimer's Disease Risk → Alzheimer's Disease and Daytime Drowsiness"
    """
    draft_section_pattern = {True: _DRAFT_SECTION_PATTERN_WITH_COUNT, False: _DRAFT_SECTION_PATTERN}[use_article_counts]

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

        draft_match = draft_section_pattern.fullmatch(numbered_draft_section)
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
            return False
        if (response_final_section != draft_section) and (response_final_section.title() in _INVALID_FINAL_SECTION_NAMES_TITLECASED):
            print_error(f"The #{num} final section name ({response_final_section!r}) is invalid. The response section string is: {numbered_response_section!r}")
            return False
        if _DRAFT_SECTION_PATTERN.fullmatch(response_final_section):
            # Note: This has been observed when a numbered pattern, e.g. "123. ", was mistakenly prefixed to the final section name. It does however risk a false positive.
            print_error(f"The #{num} final section name ({response_final_section!r}) is invalid. The response section string is: {numbered_response_section!r}")
            return False

    return True


def _list_final_sections_for_sample(user_query: str, source_module: ModuleType, draft_sections: DraftSections, *, model_size: str, selection_method: str, use_article_counts: bool, max_attempts: int = 3) -> dict[str, str]:
    """Return a mapping of the given sample of draft section names to their suggested final section names.

    Any draft section names that the model abstains from providing final section names for are skipped from the returned mapping.

    The order of draft sections in the returned mapping is not guaranteed to be the same as the input order. This is due to conditional use of order randomization.

    `LanguageModelOutputError` is raised if the model output has an error.
    Specifically, its subclass `LanguageModelOutputStructureError` is raised if the output is structurally invalid.
    """
    # return {draft_section: draft_section.title() for draft_section in draft_sections}  # Placeholder.
    draft_section_formatter = {True: "{num}. {section} (refs={count})", False: "{num}. {section}"}[use_article_counts]
    prompt_key = {True: "4. list_final_sections_using_counts", False: "4. list_final_sections"}[use_article_counts]

    assert user_query
    assert draft_sections
    draft_sections = draft_sections.copy()  # Note: This is done to prevent an accidental modification of the input, such as by a random shuffle.

    rng = random.Random(0)
    prompt_source_data = {"user_query": user_query, "source_site_name": source_module.SOURCE_SITE_NAME, "source_type": source_module.SOURCE_TYPE}

    for num_attempt in range(1, max_attempts + 1):
        read_cache = True
        if num_attempt > 1:
            match selection_method:
                case "random" | "random_concurrent":
                    rng.shuffle(draft_sections)  # Note: This is done to try to prevent the model from repeatedly failing on a fixed order of draft sections as has been observed.
                    # Note: read_cache remains true.
                case "embedding":
                    read_cache = False
                case _:
                    raise ValueError(f"Unsupported selection method: {selection_method!r}")

        numbered_draft_sections = [draft_section_formatter.format(num=i, **s) for i, s in enumerate(draft_sections, start=1)]
        numbered_draft_sections_str = "\n".join(numbered_draft_sections)
        prompt_data = copy.deepcopy(prompt_source_data)
        prompt_data["task"] = PROMPTS[prompt_key].format(**prompt_source_data, draft_sections=numbered_draft_sections_str)
        prompt = PROMPTS["0. common"].format(**prompt_data)

        response = get_content(prompt, model_size=model_size, log=(num_attempt == max_attempts), read_cache=read_cache)

        numbered_response_sections = [line.strip() for line in response.splitlines()]
        numbered_response_sections = [line for line in numbered_response_sections if line]

        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            response_is_valid = _are_sections_valid(numbered_draft_sections, numbered_response_sections, use_article_counts=use_article_counts)
        if not response_is_valid:
            error = error.getvalue().rstrip().removeprefix("Error: ")
            if num_attempt == max_attempts:
                raise LanguageModelOutputStructureError(error)
            else:
                print_warning(f"Fault in attempt {num_attempt} of {max_attempts} while getting final section names using {model_size} model: {error}")
                continue

        break

    numbered_response_matches = [_RESPONSE_SECTION_PATTERN.fullmatch(line) for line in numbered_response_sections]
    draft_to_final_sections = {m.group("draft"): m.group("final") for m in numbered_response_matches}

    abstained_draft_sections = [draft_section_name for draft_section_name, final_section_name in draft_to_final_sections.items() if (final_section_name.lower() == _ABSTAINED_FINAL_SECTION_NAME)]
    if abstained_draft_sections:
        # Note: This feature is implemented to discourage the model from emitting an invalid value for the final section name, e.g. "Not Applicable", as had otherwise been observed.
        num_draft_sections, num_abstained_draft_sections = len(draft_to_final_sections), len(abstained_draft_sections)
        msg = f"The {model_size} model abstained from providing final section names for {num_abstained_draft_sections}/{num_draft_sections} draft sections names."
        if num_abstained_draft_sections == num_draft_sections:
            raise LanguageModelOutputStructureError(msg)  # Note: If this gets observed, the condition can perhaps be handled as a failed attempt by checking for it in `_are_sections_valid` instead.
        print(msg)
        for abstained_draft_section in abstained_draft_sections:
            assert draft_to_final_sections[abstained_draft_section].lower() == _ABSTAINED_FINAL_SECTION_NAME
            del draft_to_final_sections[abstained_draft_section]  # skipped from the returned mapping.
            # draft_to_final_sections[abstained_draft_section] = abstained_draft_section  # mapped to the corresponding draft section names.

    assert draft_to_final_sections
    return draft_to_final_sections


def _list_final_sections_for_sample_concurrently(user_query: str, source_module: ModuleType, draft_sections_batch: DraftSectionsBatch, **kwargs) -> dict[str, str]:
    num_batches = len(draft_sections_batch)
    assert num_batches > 0
    if num_batches == 1:
        return _list_final_sections_for_sample(user_query=user_query, source_module=source_module, draft_sections=draft_sections_batch[0], **kwargs)

    num_draft_sections = sum(len(draft_sections) for draft_sections in draft_sections_batch)
    all_draft_to_final_sections = {}
    print(f"Concurrently processing {num_batches} batches with a total of {num_draft_sections} draft sections.")
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_draft_section = {executor.submit(_list_final_sections_for_sample, user_query=user_query, source_module=source_module, draft_sections=draft_sections, **kwargs): draft_sections for draft_sections in draft_sections_batch}
        for future in concurrent.futures.as_completed(future_to_draft_section):
            draft_to_final_sections = future.result()
            assert isinstance(draft_to_final_sections, dict) and draft_to_final_sections
            for draft_section, final_section in draft_to_final_sections.items():
                assert draft_section not in all_draft_to_final_sections, draft_section
                all_draft_to_final_sections[draft_section] = final_section
    all_draft_to_final_sections = dict(sorted(all_draft_to_final_sections.items()))  # Note: This is necessary to ensure deterministic order for caching.
    num_final_sections = len(all_draft_to_final_sections)
    print(f"Concurrently processed {num_batches} batches with a total of {num_final_sections}/{num_draft_sections} final sections.")

    all_draft_to_final_sections = dereference_dict(all_draft_to_final_sections)
    assert list(all_draft_to_final_sections) == sorted(all_draft_to_final_sections)
    num_dereferenced_sections = len(all_draft_to_final_sections)
    print(f"Dereferenced {num_dereferenced_sections}/{num_final_sections}/{num_draft_sections} sections.")

    return all_draft_to_final_sections


def list_final_sections(user_query: str, source_module: ModuleType, *, articles_and_draft_sections: list[AnalyzedArticleGen1], max_sections: int) -> list[AnalyzedArticleGen1]:
    """Return a list of dictionaries containing the search article and respective final section names.

    The internal function `_list_final_sections_for_sample` raises `LanguageModelOutputError` if the model output has an error.
    Specifically, its subclass `LanguageModelOutputStructureError` is raised by it if the output is structurally invalid.
    """
    assert NUM_SECTIONS_MIN <= max_sections <= NUM_SECTIONS_MAX, (max_sections, NUM_SECTIONS_MIN, NUM_SECTIONS_MAX)

    num_unique_original_sections: Final[int] = len({s for a in articles_and_draft_sections for s in a["sections"]})
    articles_and_sections = copy.deepcopy(articles_and_draft_sections)
    del articles_and_draft_sections  # Note: This prevents accidental modification of draft sections.

    sample_selection_method = [
        "random",  # Required 245 iterations to finalize to 60/1959 sections of high quality. (w/ use_article_counts=False)
        "random_concurrent",  # Required 138 iterations to finalize to 70/1959 sections of fair quality. (w/ use_article_counts=False)
        "embedding",  # Required 103 iterations to finalize to 43/1959 sections of substandard quality. (w/ use_article_counts=False)
    ][1]
    use_article_counts = [
        False,  # Required 245 iterations to finalize to 60/1959 sections with random sampling.
        True,  # Required 290 iterations to finalize to 80/1959 sections with random sampling. Required 208 iterations to finalize to 94/1959 sections with random_concurrent sampling.
    ][0]
    max_section_sample_size = 100  # Note: Using 200 or 300 led to a very slow response requiring over a minute. Also see the code condition and note in its usage for convergence.
    assert max_sections <= max_section_sample_size, (max_sections, max_section_sample_size)
    num_successive_convergences_required_ordered_by_model = {
        "small": 1,  # Observed counts of sections for a user query: 1: 1569→86; 2: 86→19; 3: 19→19; 5: 11→11; (all w/ max_section_sample_size condition)
        # "large": 1,  # Observed counts of sections for a user query: 1: 86→7 (w/ max_section_sample_size condition); 1: 950→3 (w/o max_section_sample_size condition);
    }  # Note: Only the small model is used because the large model converges only after an over-reduction in the number of sections, also at a noticeably greater cost.
    rng = random.Random(0)
    section_embeddings: dict[str, list[float]] = {}
    get_unique_sections: Callable[[], set[str]] = lambda: {s for a in articles_and_sections for s in a["sections"]}

    for model_size, num_successive_convergences_required in num_successive_convergences_required_ordered_by_model.items():
        iteration_num = 0
        num_successive_convergences = 0
        prev_unique_sections: set[str] = get_unique_sections()

        while True:
            unique_sections: set[str] = get_unique_sections()
            num_unique_sections, num_prev_unique_sections = len(unique_sections), len(prev_unique_sections)
            print(f"After iteration {iteration_num} using {model_size} model, the section counts are: current={num_unique_sections} previous={num_prev_unique_sections} original={num_unique_original_sections}")

            if (iteration_num > 0) and (num_unique_sections <= max_section_sample_size) and (num_unique_sections <= max_sections) and (unique_sections == prev_unique_sections):
                # Note: The condition `num_unique_sections <= max_section_sample_size` ensures that convergence is over the entire population, not the sample.
                num_successive_convergences += 1
                print(f"Convergence {num_successive_convergences}/{num_successive_convergences_required} using {model_size} model reached after {iteration_num} iterations for finalizing section names.")
                if num_successive_convergences == num_successive_convergences_required:
                    break
            elif num_successive_convergences > 0:
                num_successive_convergences = 0
            iteration_num += 1
            prev_unique_sections = unique_sections

            if (sample_selection_method == "random") or (num_unique_sections <= max_section_sample_size):
                sample_draft_sections = rng.sample(sorted(unique_sections), min(max_section_sample_size, num_unique_sections))  # Note: `sorted` is used to ensure deterministic sample selection.
                # Note: sample_draft_sections is intentionally not fully sorted because that would be counterproductive when the sample size is equal to the number of remaining sections, preventing any order randomization.
            elif sample_selection_method == "random_concurrent":
                sample_draft_sections = sorted(unique_sections)
                rng.shuffle(sample_draft_sections)
            elif sample_selection_method == "embedding":
                assert num_unique_sections > max_section_sample_size
                for section in sorted(unique_sections):  # Note: `sorted` is used to log progress in an alphabetical order.
                    if section not in section_embeddings:
                        section_embeddings[section] = get_vector(section, model_size="large")
                sample_draft_section = rng.choice(sorted(unique_sections))  # Note: `sorted` is used to ensure deterministic sample selection.
                sample_draft_section_embedding = section_embeddings[sample_draft_section]
                sample_draft_section_distances = {s: cosine(sample_draft_section_embedding, section_embeddings[s]) for s in unique_sections}
                sample_draft_sections = sorted(unique_sections, key=sample_draft_section_distances.__getitem__)[: min(max_section_sample_size, num_unique_sections)]  # Note: This doesn't make the sample fully sorted because `sample_draft_section` is still random and all other values in the sample depend on it.
            else:
                raise ValueError(f"Invalid sample selection method: {sample_selection_method!r}")

            if use_article_counts:
                sample_draft_sections = [{"section": s, "count": sum(s in a["sections"] for a in articles_and_sections)} for s in sample_draft_sections]
            else:
                sample_draft_sections = [{"section": s} for s in sample_draft_sections]

            common_kwargs = {"user_query": user_query, "source_module": source_module, "model_size": model_size, "selection_method": sample_selection_method, "use_article_counts": use_article_counts}
            if (sample_selection_method == "random_concurrent") and (len(sample_draft_sections) > max_section_sample_size):
                batched_draft_sections = get_batches(sample_draft_sections, batch_size=max_section_sample_size, include_incomplete=False)  # Note: `include_incomplete=False` is used to ensure a minimum batch size.
                sample_draft_to_final_sections = _list_final_sections_for_sample_concurrently(draft_sections_batch=batched_draft_sections, **common_kwargs)
            else:
                sample_draft_to_final_sections = _list_final_sections_for_sample(draft_sections=sample_draft_sections, **common_kwargs)

            for draft_section, final_section in sample_draft_to_final_sections.items():
                if draft_section != final_section:
                    for article in articles_and_sections:
                        article_sections = article["sections"]
                        assert article_sections
                        if draft_section in article_sections:
                            article_sections.remove(draft_section)
                            if final_section not in article_sections:
                                article_sections.append(final_section)
                            assert draft_section not in article["sections"]
                            assert final_section in article["sections"]
                    print(f"In iteration {iteration_num} using {model_size} text model, renamed draft section {draft_section!r} to final section {final_section!r}.")

    return articles_and_sections
