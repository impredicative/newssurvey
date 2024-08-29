import contextlib
import copy
import io
import re
from types import ModuleType

from newsqa.config import PROMPTS, NUM_SECTIONS_MIN, NUM_SECTIONS_MAX
from newsqa.exceptions import LanguageModelOutputStructureError
from newsqa.types import SearchArticle, AnalyzedArticleGen2
from newsqa.util.openai_ import get_content, MODELS
from newsqa.util.scipy_ import sort_by_distance
from newsqa.util.sys_ import print_error, print_warning
from newsqa.util.tiktoken_ import fit_input_items_to_token_limit

_INPUT_SECTION_PATTERN = re.compile(r"(?P<num>\d+)\. (?P<section>.+?)")
_OUTPUT_SECTION_PATTERN = re.compile(r"(?P<num>\d+)\. (?P<section>.+?) → (?P<rating>\d{1,3})")


def _rate_article(user_query: str, source_module: ModuleType, article: SearchArticle, sections: list[str], *, max_attempts: int = 3) -> list[str]:
    assert user_query
    assert sections

    numbered_sections = [f"{i}. {s}" for i, s in enumerate(sections, start=1)]
    numbered_sections_str = "\n".join(numbered_sections)

    prompt_data = {"user_query": user_query, "source_site_name": source_module.SOURCE_SITE_NAME, "source_type": source_module.SOURCE_TYPE}
    assert article['text'].startswith(article["title"]), article  # If this fails, fix the parsing to ensure it is true.

    prompt_data["task"] = PROMPTS["5. rate_articles"].format(**prompt_data, num_sections=len(sections), sections=numbered_sections_str, article=article['text'])
    prompt = PROMPTS["0. common"].format(**prompt_data)
    response = get_content(prompt, model_size="large", log=True)


def rate_articles(user_query: str, source_module: ModuleType, *, articles: list[SearchArticle], sections: list[str]) -> list[AnalyzedArticleGen2]:
    """Return a list of dictionaries containing the search article and rated final section names.

    The rating represents how well the article can contribute to the section in the context of the user query.

    The internal functions raise `LanguageModelOutputError` if the model output has an error.
    Specifically, its subclass `LanguageModelOutputStructureError` is raised by it if the output is structurally invalid.
    """
    articles = sorted(articles, key=lambda a: len(a['link']), reverse=True)  # For reproducible testing.
    num_articles, num_sections = len(articles), len(sections)

    rated_articles: list[AnalyzedArticleGen2] = []
    for article_num, article in enumerate(articles, start=1):
        rated_sections = _rate_article(user_query=user_query, source_module=source_module, article=article, sections=sections)
        rated_sections = [s for s in rated_sections if s['rating'] > 0]
        if not rated_sections:
            print(f"No rated section names exist for article #{article_num}: {article['title']}")
            continue
        print(f"#{article_num}: {article['title']} ({len(rated_sections)}/{num_sections} sections):\n\t" + "\n\t".join(f'{section_num}. {s['section']} (r={s['rating']})' for section_num, s in enumerate(rated_sections, start=1)))
        rated_articles.append(AnalyzedArticleGen2(article=article, sections=rated_sections))

    print(f"{len(rated_articles)}/{num_articles} articles remain with rated sections.")
    return rated_articles