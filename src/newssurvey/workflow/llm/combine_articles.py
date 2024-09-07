import contextlib
import io
import re
from types import ModuleType

from newssurvey.config import PROMPTS
from newssurvey.exceptions import LanguageModelOutputStructureError
from newssurvey.types import AnalyzedArticleGen2, SectionGen1
from newssurvey.util.openai_ import get_content, MODELS, MAX_OUTPUT_TOKENS
from newssurvey.util.sys_ import print_warning, print_error
from newssurvey.util.textwrap import tab_indent
from newssurvey.util.tiktoken_ import count_tokens, fit_items_to_input_token_limit

_MODEL_SIZE = [
    "small",  # Do not use. Does not generate citations well.
    "large",  # Good.
    "deprecated",  # Do not use. Does not follow instructions equally well as 4o. Does not generate citations.
][1]
_MODEL = MODELS["text"][_MODEL_SIZE]

_CITATION_OPEN_CHAR, _CITATION_CLOSE_CHAR = "〚〛"
_CITATION_GROUP_PATTERN = re.compile(_CITATION_OPEN_CHAR + r"(.*?)" + _CITATION_CLOSE_CHAR)


def _is_output_valid(text: str, *, section: str, num_articles: int) -> bool:
    """Return true if the output text is valid, otherwise false.

    A validation error is printed if the output text is invalid.
    """
    if text != text.strip():
        print_error(f"The text for the section {section!r} has leading or trailing whitespace.")
        return False

    if not text:
        print_error(f"The text for the section {section!r} is empty.")
        return False

    if text.startswith(_CITATION_OPEN_CHAR):
        print_error(f"The text for the section {section!r} starts with an opening bracket meant for a citation group.")
        return False

    if text.endswith(_CITATION_CLOSE_CHAR):
        print_error(f"The text for the section {section!r} ends with a closing bracket meant for a citation group.")
        return False

    if f"{_CITATION_OPEN_CHAR}{_CITATION_CLOSE_CHAR}" in text:
        print_error(f"The text for the section {section!r} contains an empty citation group.")
        return False

    if f"{_CITATION_CLOSE_CHAR}{_CITATION_OPEN_CHAR}" in text:
        print_error(f"The text for the section {section!r} could contain two adjacent citation groups.")
        return False

    num_opens, num_closes = text.count(_CITATION_OPEN_CHAR), text.count(_CITATION_CLOSE_CHAR)
    if num_opens != num_closes:
        print_error(f"The text for the section {section!r} has {num_opens} opening brackets but {num_closes} closing brackets meant for citation groups.")
        return False

    # Ensure citation brackets are balanced.
    # Passing example: "〚1,2,3〛"
    # Failing example: "〚1,2,〚3〛〛"
    balance = 0
    for char in text:
        if char == _CITATION_OPEN_CHAR:
            balance += 1
        elif char == _CITATION_CLOSE_CHAR:
            balance -= 1
        if balance not in (0, 1):
            print_error(f"The text for the section {section!r} has unbalanced citation brackets.")
            return False

    # Note: Having no citations is allowed for now.

    citation_groups = _CITATION_GROUP_PATTERN.findall(text)
    for num_citation_group, citation_group_str in enumerate(citation_groups, start=1):
        if not citation_group_str:
            print_error(f"The citation group #{num_citation_group} for the section {section!r} is empty.")
            return False

        citation_group = [g.strip() for g in citation_group_str.split(",")]
        for citation_str in citation_group:
            if not citation_str.isdigit():
                print_error(f"The citation {citation_str!r} in citation group #{num_citation_group} ({citation_group_str!r}) for the section {section!r} is not a number.")
                return False

            citation = int(citation_str)
            if not 1 <= citation <= num_articles:
                print_error(f"The citation {citation} in citation group #{num_citation_group} ({citation_group_str!r}) for the section {section!r} is not within the expected range of 1 to {num_articles}.")
                return False

            # Note: Duplicates are not checked because they can be managed.

    return True


def _combine_articles(user_query: str, source_module: ModuleType, *, sections: list[str], section: str, articles: list[str], max_attempts: int = 3) -> tuple[int, str]:
    assert user_query
    assert section

    prompt_data = {"user_query": user_query, "source_site_name": source_module.SOURCE_SITE_NAME, "source_type": source_module.SOURCE_TYPE}
    num_sections = len(sections)
    numbered_sections = [f"{num}. {s}" for num, s in enumerate(sections, start=1)]
    numbered_sections_str = "\n".join(numbered_sections)
    section_number = sections.index(section) + 1
    numbered_section = f"{section_number}. {section}"
    max_output_tokens = MAX_OUTPUT_TOKENS[_MODEL]

    def prompt_formatter(articles_truncated: list[str]) -> str:
        numbered_articles = "\n\n---\n\n".join([f"[ARTICLE {num}]\n\n{article}" for num, article in enumerate(articles_truncated, start=1)])
        prompt_data["task"] = PROMPTS["7. combine_articles"].format(max_output_tokens=max_output_tokens, num_sections=num_sections, sections=numbered_sections_str, section=numbered_section, num_articles=len(articles_truncated), articles=numbered_articles)
        prompt = PROMPTS["0. common"].format(**prompt_data)
        return prompt

    num_articles_used, prompt = fit_items_to_input_token_limit(articles, model=_MODEL, formatter=prompt_formatter, approach="rate")

    for num_attempt in range(1, max_attempts + 1):
        print(f"Generating section {section!r} from {num_articles_used} used articles out of {len(articles)} supplied articles using the {_MODEL_SIZE} model {_MODEL} in attempt {num_attempt}.")
        response = get_content(prompt, model_size=_MODEL_SIZE, log=True, read_cache=(num_attempt == 1))
        # Note:
        # Specifying frequency_penalty<0 produced garbage output or otherwise takes forever to return.
        # Specifying presence_penalty<0 helped produce more tokens only with presence_penalty=-2 which is risky to use.

        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            response_is_valid = _is_output_valid(response, section=section, num_articles=num_articles_used)
        if not response_is_valid:
            error = error.getvalue().rstrip().removeprefix("Error: ")
            if num_attempt == max_attempts:
                raise LanguageModelOutputStructureError(error)
            else:
                print_warning(f"Fault in attempt {num_attempt} of {max_attempts} while getting a section: {error}")
                continue

        break

    return num_articles_used, response


def combine_articles(user_query: str, source_module: ModuleType, *, articles: list[AnalyzedArticleGen2], sections: list[str]) -> list[SectionGen1]:
    """Return a list of sections with texts generated from the given articles.
    
    The internal functions raise `LanguageModelOutputError` if the model output has an error.
    Specifically, its subclass `LanguageModelOutputStructureError` is raised by it if the output is structurally invalid.
    """
    num_articles = len(articles)
    num_sections = len(sections)
    section_texts = []

    for article in articles:
        article["article"]["rating"] = sum(article_section["rating"] for article_section in article["sections"])

    for section_num, section in enumerate(sections, start=1):
        section_articles = []
        for article in articles:
            for article_section in article["sections"]:
                if article_section["section"] == section:
                    assert article_section["rating"] > 0
                    section_article = {"article": article["article"], "section": article_section}
                    section_articles.append(section_article)
                    break
        assert section_articles, section
        num_section_articles = len(section_articles)
        section_articles.sort(key=lambda a: (a["section"]["rating"], a["article"]["rating"], a["article"]["link"]), reverse=True)  # Link is used as a unique tiebreaker for reproducibility to facilitate a cache hit. It is also used because it often contains the article's publication date.
        section_articles_texts = [f'{a['article']['title']}\n\n{a['section']['text']}' for a in section_articles]
        num_section_articles_used, section_text = _combine_articles(user_query, source_module, sections=sections, section=section, articles=section_articles_texts)
        num_section_text_tokens = count_tokens(section_text, model=_MODEL)
        print(f"Generated section {section_num}/{num_sections} {section!r} from {num_section_articles_used} used articles out of {num_section_articles} supplied articles out of {num_articles} total articles, with {num_section_text_tokens:,} tokens generated using the {_MODEL_SIZE} model {_MODEL}:\n{tab_indent(section_text)}")
        section_articles_used = [a['article'] for a in section_articles[:num_section_articles_used]]
        section_data = SectionGen1(title=section, text=section_text, articles=section_articles_used)
        section_texts.append(section_data)

    return section_texts