from types import ModuleType

from newsqa.types import SearchArticle, SearchResult


def _get_article(source_module: ModuleType, search_result: SearchResult) -> SearchArticle:
    """Return the article for the given search result."""
    article_text = source_module.get_article_text(search_result["link"])
    article = SearchArticle(**search_result, text=article_text)
    assert article_text.startswith(search_result["title"]), article  # If this fails, fix the parsing to ensure it is true.
    print(f'Received article text for {article["title"]!r}.')
    return article


def get_articles(source_module: ModuleType, search_results: list[SearchResult]) -> list[SearchArticle]:
    """Return a list of articles for the given search results."""
    # Note: Concurrency is not used because of the tighter rate limit which is expected to be enforced by `get_article_text`.
    return [_get_article(source_module, search_result) for search_result in search_results]
