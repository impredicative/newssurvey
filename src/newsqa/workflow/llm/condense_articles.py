import textwrap
from types import ModuleType

from newsqa.config import PROMPTS
from newsqa.exceptions import SourceInsufficiencyError
from newsqa.types import SearchArticle, AnalyzedArticleGen2, AnalyzedArticleGen3
from newsqa.util.openai_ import get_content
from newsqa.util.sys_ import print_warning


def _condense_article(user_query: str, source_module: ModuleType, *, article: SearchArticle, sections: list[str], section: str) -> None:
    assert user_query
    assert sections

    numbered_sections = [f"{i}. {s}" for i, s in enumerate(sections, start=1)]
    numbered_sections_str = "\n".join(numbered_sections)
    numbered_section = f"{sections.index(section) + 1}. {section}"

    prompt_data = {"user_query": user_query, "source_site_name": source_module.SOURCE_SITE_NAME, "source_type": source_module.SOURCE_TYPE}
    assert article["text"].startswith(article["title"]), article  # If this fails, fix the parsing to ensure it is true.

    prompt_data["task"] = PROMPTS["6. condense_article"].format(**prompt_data, num_sections=len(sections), sections=numbered_sections_str, section=numbered_section, article=article["text"])
    prompt = PROMPTS["0. common"].format(**prompt_data)

    response = get_content(prompt, model_size="small", log=True)
    return response


def condense_articles(user_query: str, source_module: ModuleType, *, articles: list[AnalyzedArticleGen2], sections: list[str]) -> list[AnalyzedArticleGen3]:
    """Return a list of dictionaries containing the given search article, the given rated section names, with the corresponding text for each section.

    The returned text for each article-section pair is the condensed version of the article in the context of the section and the user query.

    Article-section pairs with no text are skipped. Articles with no remaining sections are also skipped.

    `SourceInsufficiencyError` is raised if no usable articles remain for the query.
    """
    assert articles
    assert sections
    articles = sorted(articles, key=lambda a: len(a["article"]["link"]), reverse=True)  # For reproducible testing, but not necessary for cache.

    condensed_articles = []
    for article in articles:
        article_title = article["article"]["title"]

        condensed_sections = []
        for section in article["sections"]:
            section_name = section["section"]
            condensed_text = _condense_article(user_query, source_module, article=article["article"], sections=sections, section=section_name)
            if condensed_text is None:
                print_warning(f"There is no text for the article {article_title!r} for the section {section_name!r}.")
                continue
            print(f'The text for the article {article_title!r} for the section {section_name!r} is:\n{textwrap.indent(condensed_text, prefix="\t")}')
            condensed_sections.append({**section, "text": condensed_text})

        if not condensed_sections:
            print_warning(f"There is no text for any section of the article {article_title!r}.")
            continue

        condensed_articles.append(AnalyzedArticleGen3(article=article["article"], sections=condensed_sections))
        input("Press Enter to continue...")

    if not condensed_articles:
        raise SourceInsufficiencyError("No usable articles exist for the query.")
    return condensed_articles
