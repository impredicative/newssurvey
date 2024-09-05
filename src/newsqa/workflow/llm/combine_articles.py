import concurrent.futures
import contextlib
import copy
import io
import textwrap
from types import ModuleType
from typing import Optional

from newsqa.config import PROMPTS
from newsqa.exceptions import LanguageModelOutputStructureError
from newsqa.types import SearchArticle, AnalyzedArticleGen1, AnalyzedArticleGen2, AnalyzedSectionGen1, AnalyzedSectionGen2
from newsqa.util.openai_ import get_content, MODELS
from newsqa.util.str import is_none_response
from newsqa.util.sys_ import print_warning, print_error
from newsqa.util.textwrap import tab_indent
from newsqa.util.tiktoken_ import count_tokens, fit_items_to_input_token_limit

_MODEL_SIZE = ['small', 'large'][1]
_MODEL = MODELS['text'][_MODEL_SIZE]


def _combine_articles(user_query: str, source_module: ModuleType, *, sections: list[str], section: str, articles: list[str], max_attempts: int = 3) -> str:
    assert user_query
    assert section

    prompt_data = {"user_query": user_query, "source_site_name": source_module.SOURCE_SITE_NAME, "source_type": source_module.SOURCE_TYPE}
    num_sections = len(sections)
    numbered_sections = [f"{num}. {s}" for num, s in enumerate(sections, start=1)]
    numbered_sections_str = '\n'.join(numbered_sections)
    section_number = sections.index(section) + 1
    numbered_section = f"{section_number}. {section}"

    def prompt_formatter(articles_truncated: list[str]) -> str:
        numbered_articles = '\n\n---\n\n'.join([f'[ARTICLE {num}]\n\n{article}' for num, article in enumerate(articles_truncated, start=1)])
        prompt_data['task'] = PROMPTS["6. combine_articles"].format(**prompt_data, num_sections=num_sections, sections=numbered_sections_str, section=numbered_section, num_articles=len(articles_truncated), articles=numbered_articles)
        prompt = PROMPTS["0. common"].format(**prompt_data)
        return prompt
    
    prompt = fit_items_to_input_token_limit(articles, model=_MODEL, formatter=prompt_formatter, approach='rate')

    for num_attempt in range(1, max_attempts + 1):
        response = get_content(prompt, model_size=_MODEL_SIZE, log=True, read_cache=(num_attempt == 1))
        
        break

    return response


def combine_articles(user_query: str, source_module: ModuleType, *, articles: list[AnalyzedArticleGen2], sections: list[str]) -> list[dict]:
    num_articles = len(articles)
    num_sections = len(sections)
    section_texts = []

    # articles = copy.deepcopy(articles)
    for article in articles:
        article['article']['rating'] = sum(article_section['rating'] for article_section in article['sections'])

    for section_num, section in enumerate(sections, start=1):
        section_articles = []
        for article in articles:
            for article_section in article["sections"]:
                if article_section["section"] == section:
                    assert article_section['rating'] > 0
                    section_article = {'article': article['article'], 'section': article_section}
                    section_articles.append(section_article)
                    break
        assert section_articles, section

        section_articles.sort(key=lambda a: (a['section']['rating'], a['article']['rating'], a['article']['link']), reverse=True)  # Link is used as a tiebreaker for reproducibility to facilitate a cache hit and also because it often contains the article's publication date.
        section_texts = [f'{a['article']['title']}\n\n{a['section']['text']}' for a in section_articles]
        section_text = _combine_articles(user_query, source_module, sections=sections, section=section, articles=section_texts)
        num_section_text_tokens = count_tokens(section_text, model=_MODEL)
        print(f'Generated section {section_num}/{num_sections} {section!r} given {len(section_articles)}/{num_articles} articles, with {num_section_text_tokens:,} tokens generated using the {_MODEL_SIZE} model {_MODEL}:\n{tab_indent(section_text)}')
        section_text = {'section': section, 'text': section_text, 'articles': section_articles}
        section_texts.append(section_text)
        input('Press Enter to continue with next section...')
    
    return section_texts