import copy
import contextlib
import io
import random
from types import ModuleType

from newsqa.exceptions import LanguageModelOutputStructureError
from newsqa.config import PROMPTS
from newsqa.types import AnalyzedArticle
from newsqa.util.openai_ import get_content
from newsqa.util.sys_ import print_error


def _list_final_sections_for_sample(user_query: str, source_module: ModuleType, draft_sections: list[str]) -> dict[str, str]:
    """Return a mapping of the given sample of draft section names to their proposed final section names.

    `LanguageModelOutputError` is raised if the model output has an error.
    Specifically, its subclass `LanguageModelOutputStructureError` is raised if the output is structurally invalid.
    """
    # return {draft_section: draft_section.title() for draft_section in draft_sections}  # Placeholder.
    assert user_query
    assert draft_sections

    prompt_data = {"user_query": user_query, "source_site_name": source_module.SOURCE_SITE_NAME, "source_type": source_module.SOURCE_TYPE}
    numbered_draft_sections = "\n".join(f"{i}. {s}" for i, s in enumerate(draft_sections, start=1))
    prompt_data["task"] = PROMPTS["4. list_final_sections"].format(**prompt_data, draft_sections=numbered_draft_sections)
    prompt = PROMPTS["0. common"].format(**prompt_data)
    response = get_content(prompt, model_size="small", log=True)
    
    assert False  # incomplete


def list_final_sections(user_query: str, source_module: ModuleType, articles_and_draft_sections: list[AnalyzedArticle]) -> list[AnalyzedArticle]:
    """Return a list of tuples containing the search article and respective final section names.

    The internal function `_list_final_sections_for_sample` raises `LanguageModelOutputError` if the model output has an error.
    Specifically, its subclass `LanguageModelOutputStructureError` is raised by it if the output is structurally invalid.
    """
    articles_and_sections = copy.deepcopy(articles_and_draft_sections)
    del articles_and_draft_sections  # Note: This prevents accidental modification of draft sections.
    max_section_sample_size = 500  # Note: Using 1000 was observed to lead to a premature truncation of the response by the model after the first 800.
    votes_needed_to_finalize_section = {"test": 1, "qa": 2, "prod": 3}["prod"]
    rng = random.Random(0)

    draft_to_final_section_candidate_counts: dict[str, dict[str, int]] = {}
    iteration_num = 0
    while True:
        unique_sections = {s for a in articles_and_sections for s in a["sections"]}
        num_unique_sections = len(unique_sections)
        num_unique_sections_finalized = sum((max(draft_to_final_section_candidate_counts.get(s, {}).values(), default=0) >= votes_needed_to_finalize_section) for s in unique_sections)
        pct_unique_sections_finalized = num_unique_sections_finalized / num_unique_sections
        print(f"After iteration {iteration_num}, {num_unique_sections_finalized}/{num_unique_sections} ({pct_unique_sections_finalized:.2%}) sections are finalized.")
        if num_unique_sections == num_unique_sections_finalized:
            break
        iteration_num += 1

        sample_draft_sections = rng.sample(sorted(unique_sections), min(max_section_sample_size, num_unique_sections))  # Note: `sorted` is used to ensure deterministic sample selection.
        sample_final_sections = _list_final_sections_for_sample(user_query, source_module, sample_draft_sections)
        for draft_section, final_section in sample_final_sections.items():
            draft_to_final_section_candidate_counts.setdefault(draft_section, {})
            final_section_candidate_count = draft_to_final_section_candidate_counts[draft_section].get(final_section, 0) + 1
            draft_to_final_section_candidate_counts[draft_section][final_section] = final_section_candidate_count
            if (draft_section != final_section) and (final_section_candidate_count >= votes_needed_to_finalize_section) and (final_section_candidate_count == max(draft_to_final_section_candidate_counts[draft_section].values())):
                for article in articles_and_sections:
                    article_sections = article["sections"]
                    assert article_sections
                    if draft_section in article_sections:
                        article_sections.remove(draft_section)
                        if final_section not in article_sections:
                            article_sections.append(final_section)
                        assert draft_section not in article["sections"]
                        assert final_section in article["sections"]
                # print(f'In iteration {iteration_num}, renamed draft section {draft_section!r} to final section {final_section!r}.')

    return articles_and_sections
