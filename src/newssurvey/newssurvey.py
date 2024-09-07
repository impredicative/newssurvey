from pathlib import Path
from typing import Optional

from newssurvey.config import NUM_SECTIONS_DEFAULT, NUM_SECTIONS_MIN, NUM_SECTIONS_MAX
from newssurvey.exceptions import InputError
from newssurvey.types import AnalyzedArticleGen1, SearchResult, SearchArticle, SectionGen1
from newssurvey.util.input import get_confirmation
from newssurvey.util.openai_ import ensure_openai_key, MODELS
from newssurvey.workflow.user.query import ensure_query_is_valid
from newssurvey.workflow.user.source import ensure_source_is_valid, get_source_module
from newssurvey.workflow.llm.list_search_terms import list_search_terms
from newssurvey.workflow.llm.filter_search_results import filter_search_results
from newssurvey.workflow.llm.list_sections import list_sections
from newssurvey.workflow.llm.create_title import create_title
from newssurvey.workflow.llm.rate_articles import rate_articles
from newssurvey.workflow.llm.condense_articles import condense_articles
from newssurvey.workflow.llm.combine_articles import combine_articles
from newssurvey.workflow.source.get_articles import get_articles


def generate_response(source: str, query: str, max_sections: int = NUM_SECTIONS_DEFAULT, output_path: Optional[Path] = None, confirm: bool = False) -> str:
    f"""Return a response for the given source and query.

    The progress is printed to stdout.

    Params:
    * `source`: Name of supported news source.
    * `query`: Question or concern answerable by the news source.
    * `max_sections`: Maximum number of sections to include in the response, between {NUM_SECTIONS_MIN} and {NUM_SECTIONS_MAX}. Its recommended value, also the default, is {NUM_SECTIONS_DEFAULT}.
    * `path`: Output file path. If given, the response is also written to this text file.
    * `confirm`: Confirm as the workflow progresses. If true, a confirmation is interactively sought as each step of the workflow progresses. Its default is false.

    If failed, a subclass of the `newssurvey.exceptions.Error` exception is raised.
    """
    ensure_openai_key()

    ensure_source_is_valid(source)
    print(f"SOURCE: {source}")
    source_module = get_source_module(source)

    ensure_query_is_valid(query)
    query_sep = "\n" if (len(query.splitlines()) > 1) else " "
    print(f"QUERY:{query_sep}{query}")

    if not (NUM_SECTIONS_MIN <= max_sections <= NUM_SECTIONS_MAX):
        raise InputError(f"Invalid number of sections: {max_sections}. It must be between {NUM_SECTIONS_MIN} and {NUM_SECTIONS_MAX}.")
    print(f"MAX SECTIONS: {max_sections}")

    print(f"MODELS: text:large={MODELS["text"]["large"]}, text:small={MODELS["text"]["small"]}, embedding:large={MODELS["embedding"]["large"]}")

    search_terms: list[str] = list_search_terms(user_query=query, source_module=source_module)
    print(f"SEARCH TERMS ({len(search_terms)}): " + ", ".join(search_terms))

    if confirm:
        get_confirmation("getting search results")
    search_results: list[SearchResult] = filter_search_results(user_query=query, source_module=source_module, search_terms=search_terms)
    print(f"SEARCH RESULTS ({len(search_results)}):\n" + "\n".join(f'#{num}: {r['title']}\n{r['link']}\n{r['description']}' for num, r in enumerate(search_results, start=1)))

    if confirm:
        get_confirmation("getting articles")
    articles: list[SearchArticle] = get_articles(source_module=source_module, search_results=search_results)

    if confirm:
        get_confirmation("listing sections")
    sections: list[str] = list_sections(user_query=query, source_module=source_module, titles=[r["title"] for r in articles], max_sections=max_sections)
    num_sections = len(sections)
    section_names_str = f"SECTIONS ({num_sections}):\n" + "\n".join([f"{num}: {section}" for num, section in enumerate(sections, start=1)])
    print(section_names_str)

    if confirm:
        get_confirmation("creating title")
    title: str = create_title(user_query=query, source_module=source_module, sections=sections)
    print(f"TITLE: {title}")

    if confirm:
        get_confirmation("rating articles")
    articles_and_sections: list[AnalyzedArticleGen1] = rate_articles(user_query=query, source_module=source_module, articles=articles, sections=sections)
    print(f"RATED ARTICLES x SECTIONS PAIRS SUMMARY: {len(articles_and_sections)} articles x {num_sections} sections = {sum(len(a['sections']) for a in articles_and_sections):,} actual pairs / {len(articles_and_sections) * num_sections:,} possible pairs")
    print(section_names_str)

    if confirm:
        get_confirmation("condensing articles")
    articles_and_sections: list[AnalyzedArticleGen1] = condense_articles(user_query=query, source_module=source_module, articles=articles_and_sections, sections=sections)
    print("RATED SECTIONS BY ARTICLE:\n" + "\n".join(f'#{a_num}: {a["article"]["title"]} ({len(a["sections"])}/{num_sections} sections) (r={sum(s['rating'] for s in a['sections'])})\n\t{"\n\t".join(f'{s_num}. {s["section"]} (r={s["rating"]})' for s_num, s in enumerate(a["sections"], start=1))}' for a_num, a in enumerate(articles_and_sections, start=1)))
    print(f"ARTICLES BY SECTION ({num_sections}):")
    for section_num, section in enumerate(sections, start=1):
        section_articles = [a for a in articles_and_sections if any(section == s["section"] for s in a["sections"])]
        section_rating = sum(s["rating"] for a in section_articles for s in a["sections"] if section == s["section"])
        print(f"{section_num}. {section} ({len(section_articles)} articles) (r={section_rating:,})")
        section_articles.sort(key=lambda a: (next(s["rating"] for s in a["sections"] if section == s["section"]), sum(s["rating"] for s in a["sections"])), reverse=True)
        for article_num, article in enumerate(section_articles, start=1):
            article_section_pair_rating = next(s["rating"] for s in article["sections"] if section == s["section"])
            article_rating = sum(s["rating"] for s in article["sections"])
            print(f"\t{article_num}: {article['article']['title']} (r={article_section_pair_rating}/{article_rating})")
    print(f"CONDENSED ARTICLES x SECTIONS PAIRS SUMMARY: {len(articles_and_sections)} articles x {num_sections} sections = {sum(len(a['sections']) for a in articles_and_sections):,} actual pairs / {len(articles_and_sections) * num_sections:,} possible pairs")
    print(section_names_str)

    if confirm:
        get_confirmation("generate section texts")
    section_texts: list[SectionGen1] = combine_articles(user_query=query, source_module=source_module, articles=articles_and_sections, sections=sections)
    response_text = f"{title}\n\n" + f"Sections:\n" + "\n".join([f"{num}: {section}" for num, section in enumerate(sections, start=1)]) + '\n\n' + "\n\n".join(f'Section {num}. {s["title"]}:\n\n{s["text"]}' for num, s in enumerate(section_texts, start=1))
    print(f"REPORT:\n\n{response_text}")

    return response_text