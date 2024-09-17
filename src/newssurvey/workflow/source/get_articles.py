import concurrent.futures
import itertools
from types import ModuleType

from newssurvey.types import SearchArticle, SearchResult


def get_articles(source_module: ModuleType, search_results: list[SearchResult]) -> list[SearchArticle]:
    """Return a list of articles for the given search results."""
    num_articles = len(search_results)
    counter = itertools.count(1)

    def _get_article(search_result: SearchResult) -> SearchArticle:
        """Return the article for the given search result."""
        article_text = source_module.get_article_text(search_result["link"])
        article = SearchArticle(**search_result, text=article_text)
        assert article_text.startswith(search_result["title"]), article  # If this fails, fix the parsing to ensure it is true.
        count = next(counter)
        print(f'Received text of article {count}/{num_articles} having title: {article["title"]}')
        return article

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        articles = list(executor.map(_get_article, search_results))
    return articles
