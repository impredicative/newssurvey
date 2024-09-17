import contextlib
import concurrent.futures
import itertools
import io
import re
from types import ModuleType

from newssurvey.config import PROMPTS
from newssurvey.exceptions import LanguageModelOutputStructureError, SourceInsufficiencyError
from newssurvey.types import SearchArticle, AnalyzedArticleGen1, AnalyzedSectionGen1
from newssurvey.util.openai_ import get_content, MAX_WORKERS
from newssurvey.util.scipy_ import sort_by_distance
from newssurvey.util.sys_ import print_error, print_warning

_INPUT_SECTION_PATTERN = re.compile(r"(?P<num>\d+)\. (?P<section>.+?)")
_OUTPUT_SECTION_PATTERN = re.compile(r"(?P<num>\d+)\. (?P<section>.+?) → (?P<rating>\d{1,3})")


def _are_sections_valid(sections: list[str], numbered_input_sections: list[str], numbered_output_sections: list[str]) -> bool:
    """Return true if the output sections have a valid rating of the input sections, otherwise false.

    A validation error is printed if a rating is invalid.
    """
    if not numbered_input_sections:
        print_error("No input section names exist.")
        return False

    if not numbered_output_sections:
        print_error("No output section names exist.")
        return False

    num_input_sections, num_output_sections = len(numbered_input_sections), len(numbered_output_sections)
    if num_input_sections != num_output_sections:
        print_error(f"The number of input sections ({num_input_sections}) and output sections ({num_output_sections}) are unequal.")
        return False

    for num, (numbered_input_section, numbered_output_section) in enumerate(itertools.zip_longest(numbered_input_sections, numbered_output_sections), start=1):
        if not isinstance(numbered_input_section, str):  # Can be None if the list is exhausted given the use of zip_longest.
            print_error(f"Input section #{num} is missing.")
            return False
        if not isinstance(numbered_output_section, str):  # Can be None if the list is exhausted given the use of zip_longest.
            print_error(f"Output section #{num} is missing.")
            return False

        input_match = _INPUT_SECTION_PATTERN.fullmatch(numbered_input_section)
        if not input_match:
            print_error(f"Input section string #{num} is invalid: {numbered_input_section!r}")
            return False
        output_match = _OUTPUT_SECTION_PATTERN.fullmatch(numbered_output_section)
        if not output_match:
            print_error(f"Output section string #{num} is invalid: {numbered_output_section!r}")
            return False

        input_num, output_num = int(input_match.group("num")), int(output_match.group("num"))
        if num != input_num:
            print_error(f"The expected input section number ({num}) and actual input section number ({input_num}) are unequal. The input section string is: {numbered_input_section!r}")
            return False
        if input_num != output_num:
            print_error(f"The input section number ({input_num}) and output section number ({output_num}) are unequal. The output section string is: {numbered_output_section!r}")
            return False

        input_section = input_match.group("section")
        if input_section != input_section.strip():
            print_error(f"The #{num} input section name has leading or trailing whitespace: {input_section!r}")
            return False
        if not input_section:
            print_error(f"The #{num} input section name is empty. The input section string is: {numbered_input_section!r}")
            return False
        output_section = output_match.group("section")
        if input_section != output_section:
            closest_input_section = sort_by_distance(output_section, sections, model_size="large", distance="cosine")[0]
            if closest_input_section == input_section:
                print_warning(f"The #{num} input section name ({input_section!r}) and output section name ({output_section!r}) are unequal, although the output section name is closest to the input section name.")
            else:
                print_error(f"The #{num} input section name ({input_section!r}) and output section name ({output_section!r}) are unequal. The closest input section name is: {closest_input_section!r}")
                return False

        rating = int(output_match.group("rating"))
        if not (0 <= rating <= 100):
            print_error(f"Section #{num} has an invalid output rating of {rating}. The output section string is: {numbered_output_section!r}")
            return False

    return True


def _rate_article(user_query: str, source_module: ModuleType, article: SearchArticle, sections: list[str], *, max_attempts: int = 3) -> list[dict[str, int]]:
    assert user_query
    assert sections

    numbered_input_sections = [f"{i}. {s}" for i, s in enumerate(sections, start=1)]
    numbered_input_sections_str = "\n".join(numbered_input_sections)

    prompt_data = {"user_query": user_query, "source_site_name": source_module.SOURCE_SITE_NAME, "source_type": source_module.SOURCE_TYPE}
    assert article["text"].startswith(article["title"]), article  # If this fails, fix the parsing to ensure it is true.

    prompt_data["task"] = PROMPTS["4. rate_article"].format(num_sections=len(sections), sections=numbered_input_sections_str, article=article["text"])
    prompt = PROMPTS["0. common"].format(**prompt_data)

    for num_attempt in range(1, max_attempts + 1):
        response = get_content(prompt, model_size="small", log=(num_attempt > 1), read_cache=(num_attempt == 1))  # Note: A dynamic model_size cannot be used because it breaks the cache.
        numbered_output_sections = [line.strip() for line in response.splitlines()]
        numbered_output_sections = [line for line in numbered_output_sections if line]

        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            response_is_valid = _are_sections_valid(sections, numbered_input_sections, numbered_output_sections)
        if not response_is_valid:
            error = error.getvalue().rstrip().removeprefix("Error: ")
            if num_attempt == max_attempts:
                raise LanguageModelOutputStructureError(error)
            else:
                print_warning(f"Fault in attempt {num_attempt} of {max_attempts} while getting section ratings: {error}")
                continue

        break

    output_matches = [_OUTPUT_SECTION_PATTERN.fullmatch(line) for line in numbered_output_sections]
    assert len(output_matches) == len(sections), (len(output_matches), len(sections))
    rated_sections = [AnalyzedSectionGen1(section=section, rating=int(match.group("rating"))) for section, match in zip(sections, output_matches)]
    # Note: match.group("section") is not used for section because it can sometimes be different from the input section name. For example, despite many attempts, the input section name 'Particle Candidates: MACHOs, WIMPs, SIMPs, and More' was rated as 'Particle Candidates: MACHOs, WIMPs, and More' by the model.

    assert len(rated_sections) == len(sections)
    assert [s["section"] for s in rated_sections] == sections
    return rated_sections


def rate_articles(user_query: str, source_module: ModuleType, *, articles: list[SearchArticle], sections: list[str]) -> list[AnalyzedArticleGen1]:
    """Return a list of dictionaries containing the search article and rated final section names.

    The rating represents how well the article can contribute to the section in the context of the user query.

    Articles with no positively rated sections are skipped.

    The internal functions raise `LanguageModelOutputError` if the model output has an error.
    Specifically, its subclass `LanguageModelOutputStructureError` is raised by it if the output is structurally invalid.

    `SourceInsufficiencyError` is raised if no usable articles remain for the query.
    """
    # articles = sorted(articles, key=lambda a: len(a["link"]), reverse=True)  # For reproducible testing, but not necessary for cache.
    num_articles, num_sections = len(articles), len(sections)
    rated_articles: list[AnalyzedArticleGen1] = []
    skipped_articles: list[SearchArticle] = []

    def rate_article(article: SearchArticle) -> AnalyzedArticleGen1:
        rated_sections = _rate_article(user_query=user_query, source_module=source_module, article=article, sections=sections)
        rated_sections = [s for s in rated_sections if s["rating"] > 0]
        return AnalyzedArticleGen1(article=article, sections=rated_sections)

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(rate_article, article): article for article in articles}
        for future_num, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            analyzed_article = future.result()
            if rated_sections := analyzed_article["sections"]:
                print(f"#{future_num}/{num_articles}: {analyzed_article['article']['title']} ({len(rated_sections)}/{num_sections} sections):\n\t" + "\n\t".join(f'{section_num}. {s['section']} (r={s['rating']})' for section_num, s in enumerate(rated_sections, start=1)))
                rated_articles.append(analyzed_article)
            else:
                print(f"No positively rated section names exist for article #{future_num}/{num_articles}: {analyzed_article['article']['title']}")
                skipped_articles.append(analyzed_article["article"])

    print(f"{len(skipped_articles)}/{num_articles} articles were skipped due to no positively rated sections:\n\t" + "\n\t".join(f'{num}. {a["title"]}' for num, a in enumerate(skipped_articles, start=1)))
    print(f"{len(rated_articles)}/{num_articles} articles remain with positively rated sections.")

    rated_articles.sort(key=lambda a: sum(s["rating"] for s in a["sections"]), reverse=True)

    if not rated_articles:
        raise SourceInsufficiencyError("No usable articles remain for the query.")
    return rated_articles
