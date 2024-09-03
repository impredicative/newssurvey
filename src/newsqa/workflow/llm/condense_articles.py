import contextlib
import io
import textwrap
from types import ModuleType
from typing import Optional

from newsqa.config import PROMPTS
from newsqa.exceptions import LanguageModelOutputStructureError, SourceInsufficiencyError
from newsqa.types import SearchArticle, AnalyzedArticleGen2, AnalyzedArticleGen3
from newsqa.util.openai_ import get_content
from newsqa.util.str import is_none_response
from newsqa.util.sys_ import print_warning, print_error


def _is_output_valid(text: str, article_title: str, section_name: str) -> bool:
    """Return true if the output text is valid, otherwise false.

    A validation error is printed if the output text is invalid.
    """
    if text != text.strip():
        print_error(f"The text for the article {article_title!r} for the section {section_name!r} has leading or trailing whitespace.")
        return False

    if not text:
        print_error(f"The text for the article {article_title!r} for the section {section_name!r} is empty.")
        return False

    def is_valid_starting_line(starting_line: str, invalid_line: str) -> bool:
        invalid_starting_lines = (invalid_line, f"{invalid_line}:", f"**{invalid_line}**", f"**{invalid_line}**:")
        return starting_line not in invalid_starting_lines

    starting_line = text.split("\n", 1)[0]
    for invalid_line in (article_title, section_name):
        if not is_valid_starting_line(starting_line, invalid_line):
            print_error(f"The text for the article {article_title!r} for the section {section_name!r} starts with the invalid line: {starting_line!r}")
            return False

    return True


def _condense_article(user_query: str, source_module: ModuleType, *, article: SearchArticle, sections: list[str], section: str, max_attempts: int = 1) -> Optional[str]:
    assert user_query
    assert sections

    numbered_sections = [f"{i}. {s}" for i, s in enumerate(sections, start=1)]
    numbered_sections_str = "\n".join(numbered_sections)
    numbered_section = f"{sections.index(section) + 1}. {section}"

    prompt_data = {"user_query": user_query, "source_site_name": source_module.SOURCE_SITE_NAME, "source_type": source_module.SOURCE_TYPE}
    assert article["text"].startswith(article["title"]), article  # If this fails, fix the parsing to ensure it is true.

    prompt_data["task"] = PROMPTS["6. condense_article"].format(**prompt_data, num_sections=len(sections), sections=numbered_sections_str, section=numbered_section, article=article["text"])
    prompt = PROMPTS["0. common"].format(**prompt_data)

    for num_attempt in range(1, max_attempts + 1):
        response = get_content(prompt, model_size="small", log=(num_attempt > 1), read_cache=(num_attempt == 1))

        if is_none_response(response):
            return

        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            response_is_valid = _is_output_valid(response, article["title"], section)
        if not response_is_valid:
            error = error.getvalue().rstrip().removeprefix("Error: ")
            if num_attempt == max_attempts:
                raise LanguageModelOutputStructureError(error)
            else:
                print_warning(f"Fault in attempt {num_attempt} of {max_attempts} while getting a condensed article: {error}")
                continue

        break

    return response


def condense_articles(user_query: str, source_module: ModuleType, *, articles: list[AnalyzedArticleGen2], sections: list[str]) -> list[AnalyzedArticleGen3]:
    """Return a list of dictionaries containing the given search article, the given rated section names, with the corresponding text for each section.

    The returned text for each article-section pair is the condensed version of the article in the context of the section and the user query.

    Article-section pairs with no text are skipped. Articles with no remaining sections are also skipped.

    The internal functions raise `LanguageModelOutputError` if the model output has an error.
    Specifically, its subclass `LanguageModelOutputStructureError` is raised by it if the output is structurally invalid.

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
            assert section["rating"] > 0
            section_name = section["section"]
            condensed_text = _condense_article(user_query, source_module, article=article["article"], sections=sections, section=section_name)
            if condensed_text is None:
                print(f"There is no text for the article {article_title!r} for the section {section_name!r}.")
                continue
            print(f'The text for the article {article_title!r} for the section {section_name!r} with rating {section['rating']}/100 is:\n{textwrap.indent(condensed_text, prefix="\t")}')
            condensed_sections.append({**section, "text": condensed_text})
            input("Press Enter to continue...")

        if not condensed_sections:
            print_warning(f"There is no text for any section of the article {article_title!r}.")
            continue

        condensed_articles.append(AnalyzedArticleGen3(article=article["article"], sections=condensed_sections))

    if not condensed_articles:
        raise SourceInsufficiencyError("No usable articles exist for the query.")
    return condensed_articles
