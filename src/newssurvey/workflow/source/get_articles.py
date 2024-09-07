import concurrent.futures
from types import ModuleType
from newssurvey.types import SearchArticle, SearchResult


def _get_article(source_module: ModuleType, search_result: SearchResult) -> SearchArticle:
    """Return the article for the given search result."""
    article_text = source_module.get_article_text(search_result["link"])
    article = SearchArticle(**search_result, text=article_text)
    assert article_text.startswith(search_result["title"]), article  # If this fails, fix the parsing to ensure it is true.
    print(f'Received article text for {article["title"]!r}.')
    return article


def get_articles(source_module: ModuleType, search_results: list[SearchResult]) -> list[SearchArticle]:
    """Return a list of articles for the given search results."""
    fetch_article = lambda search_result: _get_article(source_module, search_result)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        articles = list(executor.map(fetch_article, search_results))
    return articles
