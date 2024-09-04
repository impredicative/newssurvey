import concurrent.futures
import contextlib
import io
import textwrap
from types import ModuleType
from typing import Optional

from newsqa.config import PROMPTS
from newsqa.exceptions import LanguageModelOutputStructureError, Section
from newsqa.types import SearchArticle, AnalyzedArticleGen1, AnalyzedArticleGen2, AnalyzedSectionGen1, AnalyzedSectionGen2
from newsqa.util.openai_ import get_content, MAX_WORKERS
from newsqa.util.str import is_none_response
from newsqa.util.sys_ import print_warning, print_error


def _write_section(user_query: str, source_module: ModuleType, *, article: SearchArticle, section: Section, max_attempts: int = 3) -> Optional[str]:
    assert user_query
    assert section

    prompt_data = {"user_query": user_query, "source_site_name": source_module.SOURCE_SITE_NAME, "source_type": source_module.SOURCE_TYPE}
    assert article["text"].startswith(article["title"]), article  # If this fails, fix the parsing to ensure it is true.

    prompt_data["task"] = PROMPTS["6. write_section"].format(**prompt_data, section=section["title"], article=article["text"])
    prompt = PROMPTS["0. common"].format(**prompt_data)

    for num_attempt in range(1, max_attempts + 1):
        response = get_content(prompt, model_size="small", log=(num_attempt > 1), read_cache=(num_attempt == 1))

        if is_none_response(response):
            return

        try:
            text = response["choices"][0]["text"].strip()
        except (KeyError, IndexError):
            raise LanguageModelOutputStructureError(response)

        if _is_output_valid(text, article["title"], section["title"]):
            return text

    print_warning(f"Failed to condense the article {article['title']!r} for the section {section['title']!r} after {max_attempts} attempts.")
    return


def write_sections(user_query: str, source_module: ModuleType, *, articles: list[AnalyzedArticleGen2], sections: list[str]) -> list[AnalyzedArticleGen2]:
    written_sections = []


    for section in sections:
        section_articles = []
        for article in articles:
            for article_section in article["sections"]:
                if article_section["section"] == section:
                    assert article_section['rating'] > 0
                    section_article = {'article': article['article'], 'section': article_section}
                    section_articles.append(section_article)
                    break
        assert section_articles, section

