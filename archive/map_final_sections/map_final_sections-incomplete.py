import contextlib
import copy
import io
import re
from types import ModuleType

from newsqa.config import PROMPTS, NUM_SECTIONS_MIN, NUM_SECTIONS_MAX
from newsqa.exceptions import LanguageModelOutputStructureError, SourceInsufficiencyError
from newsqa.types import AnalyzedArticleGen1, SearchArticle, SearchResult
from newsqa.util.openai_ import get_content
from newsqa.util.scipy_ import sort_by_distance
from newsqa.util.sys_ import print_error, print_warning

def _map_final_sections(user_query: str, source_module: ModuleType, *, final_sections: list[str], final_section: str, draft_sections: list[str], max_attempts: int = 3) -> list[AnalyzedArticleGen1]:
    assert user_query
    assert draft_sections

    # TODO: Truncate sections if prompt is too long. Refer to:
    #       https://platform.openai.com/docs/advanced-usage/managing-tokens 
    #       https://github.com/openai/tiktoken/issues/305
    #       https://github.com/openai/tiktoken/issues/98
    #       https://cookbook.openai.com/examples/how_to_count_tokens_with_tiktoken
    
    prompt_data = {"user_query": user_query, "source_site_name": source_module.SOURCE_SITE_NAME, "source_type": source_module.SOURCE_TYPE}
    numbered_final_sections = [f"{i}. {s}" for i, s in enumerate(final_sections, start=1)]
    numbered_final_sections_str = "\n".join(numbered_final_sections)
    assert final_section in final_sections
    numbered_final_section: str = next((f"{i}. {s}" for i, s in enumerate(final_sections, start=1) if s == final_section))
    numbered_draft_sections = [f"{i}. {s}" for i, s in enumerate(draft_sections, start=1)]
    numbered_draft_sections_str = "\n".join(numbered_draft_sections)
    prompt_data["task"] = PROMPTS["5. map_final_sections"].format(**prompt_data, num_final_sections=len(final_sections), final_sections=numbered_final_sections_str, numbered_final_section=numbered_final_section, num_draft_sections=len(draft_sections), draft_sections=numbered_draft_sections_str)
    prompt = PROMPTS["0. common"].format(**prompt_data)

    for num_attempt in range(1, max_attempts + 1):
        response = get_content(prompt, model_size="large", log=True or (num_attempt == max_attempts), read_cache=(num_attempt == 1))
        
        numbered_response_sections = [line.strip() for line in response.splitlines()]
        numbered_response_sections = [line for line in numbered_response_sections if line]
    
        # error = io.StringIO()
        # with contextlib.redirect_stderr(error):
        #     response_is_valid = _are_sections_valid(numbered_response_sections)
        # if not response_is_valid:
        #     error = error.getvalue().rstrip().removeprefix("Error: ")
        #     if num_attempt == max_attempts:
        #         raise LanguageModelOutputStructureError(error)
        #     else:
        #         print_warning(f"Fault in attempt {num_attempt} of {max_attempts} while getting final section names: {error}")
        #         continue

        # break


def map_final_sections(user_query: str, source_module: ModuleType, *, articles_and_draft_sections: list[AnalyzedArticleGen1], final_sections: list[str]) -> list[AnalyzedArticleGen1]:
    """Return a list of dictionaries containing the search article and respective final section names.

    The internal functions raise `LanguageModelOutputError` if the model output has an error.
    Specifically, its subclass `LanguageModelOutputStructureError` is raised by it if the output is structurally invalid.
    """
    assert articles_and_draft_sections
    assert final_sections
    assert len(final_sections) == len(set(final_sections))

    draft_sections_all = sorted({s for a in articles_and_draft_sections for s in a["sections"]})  # Sorting is for deterministic output in case distances are same.
    assert draft_sections_all

    draft_to_final_sections: dict[str, set[str]] = {}
    for final_section_num, final_section in enumerate(final_sections, start=1):
        draft_sections_by_distance = sort_by_distance(final_section, draft_sections_all, model_size="large", distance="cosine")
        draft_sections_cur = _map_final_sections(user_query=user_query, source_module=source_module, final_sections=final_sections, final_section=final_section, draft_sections=draft_sections_by_distance)
        print(f"Final section #{final_section_num} {final_section!r} has {len(draft_sections_cur)} draft sections: \n\t" + "\n\t".join(draft_sections_cur))
        for draft_section in draft_sections_cur:
            draft_to_final_sections.setdefault(draft_section, set()).add(final_section)
        # input("Press Enter to continue...")

    articles_and_final_sections = []
    for article_and_draft_sections in articles_and_draft_sections:
        article, draft_sections_cur = article_and_draft_sections["article"], article_and_draft_sections["sections"]
        final_sections_cur = [final_section for final_section in final_sections if any((final_section in draft_to_final_sections[draft_section]) for draft_section in draft_sections_cur)]  # Order preserving.
        articles_and_final_sections.append(AnalyzedArticleGen1(article=article, sections=final_sections_cur))

    return articles_and_final_sections
