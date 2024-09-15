import contextlib
import io
from types import ModuleType

from newssurvey.config import PROMPTS, NUM_SECTIONS_MIN, NUM_SECTIONS_MAX
from newssurvey.exceptions import LanguageModelOutputStructureError, LanguageModelOutputConvergenceError
from newssurvey.util.difflib_ import ndiffstr
from newssurvey.util.openai_ import get_content, MODELS
from newssurvey.util.scipy_ import sort_by_distance
from newssurvey.util.sys_ import print_warning
from newssurvey.util.textwrap import tab_indent
from newssurvey.util.tiktoken_ import fit_items_to_input_token_limit
from newssurvey.workflow.llm.list_sections import SECTION_PATTERN, are_sections_valid


def _refine_sections(user_query: str, source_module: ModuleType, *, sections: list[str], titles: list[str], max_sections: int, max_attempts: int = 3) -> list[str]:
    assert user_query
    assert sections
    assert titles

    prompt_data = {"user_query": user_query, "source_site_name": source_module.SOURCE_SITE_NAME, "source_type": source_module.SOURCE_TYPE}
    numbered_sections = [f"{i}. {s}" for i, s in enumerate(sections, start=1)]
    numbered_sections_str = "\n".join(numbered_sections)

    def prompt_formatter(titles_truncated: list[str]) -> str:
        numbered_titles = [f"{i}. {s}" for i, s in enumerate(titles_truncated, start=1)]
        numbered_titles_str = "\n".join(numbered_titles)
        prompt_data["task"] = PROMPTS["3.2. refine_sections"].format(num_sections=len(sections), sections=numbered_sections_str, num_titles=len(titles_truncated), titles=numbered_titles_str, max_sections=max_sections)
        prompt = PROMPTS["0. common"].format(**prompt_data)
        return prompt

    model_size = "large"
    num_titles_used, prompt = fit_items_to_input_token_limit(titles, model=MODELS["text"][model_size], formatter=prompt_formatter, approach="rate")
    if num_titles_used < len(titles):
        num_titles_not_used = len(titles) - num_titles_used
        print_warning(f"Used only {num_titles_used:,}/{len(titles):,} titles for getting section names, leaving the last {num_titles_not_used:,} titles unused.")

    for num_attempt in range(1, max_attempts + 1):
        response = get_content(prompt, model_size=model_size, log=True, read_cache=(num_attempt == 1))

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
                print_warning(f"Fault in attempt {num_attempt} of {max_attempts} while refining section names: {error}")
                continue

        break

    numbered_response_matches = [SECTION_PATTERN.fullmatch(line) for line in numbered_response_sections]
    sections = [match["section"] for match in numbered_response_matches]
    return sections


def refine_sections(user_query: str, source_module: ModuleType, *, sections: list[str], titles: list[str], max_sections: int) -> list[str]:
    """Return a refined ordered list of section names.

    The internal functions raise `LanguageModelOutputError` if the model output has an error.
    The subclass `LanguageModelOutputStructureError` is raised if the output is structurally invalid.
    """
    assert NUM_SECTIONS_MIN <= max_sections <= NUM_SECTIONS_MAX, (max_sections, NUM_SECTIONS_MIN, NUM_SECTIONS_MAX)
    assert sections
    num_original_sections = len(sections)
    assert num_original_sections <= max_sections, (num_original_sections, max_sections)  # Note: NUM_SECTIONS_MIN is intentionally not checked.

    titles = sort_by_distance(user_query, titles, model_size="large", distance="cosine")

    iteration = 1
    max_iterations = 20  # Max observed = 10
    while True:
        if iteration > max_iterations:
            raise LanguageModelOutputConvergenceError(f"Failed to converge refining section names after {max_iterations} iterations.")
        num_old_sections = len(sections)
        new_sections = _refine_sections(user_query, source_module, sections=sections, titles=titles, max_sections=max_sections)
        assert new_sections
        num_new_sections = len(new_sections)
        assert num_new_sections <= max_sections, (num_new_sections, max_sections)
        print(f"Section counts in {iteration=}/{max_iterations}: original={num_original_sections} old={num_old_sections} new={num_new_sections}")
        if sections == new_sections:
            print(f"Section changes in {iteration=}/{max_iterations}: (none)")
            break
        else:
            diff = ndiffstr(sections, new_sections)
            print(f"Section changes in {iteration=}/{max_iterations}:\n{tab_indent(diff)}")
            sections = new_sections
            iteration += 1

    assert sections
    return sections
