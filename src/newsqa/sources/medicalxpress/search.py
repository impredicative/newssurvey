import datetime
import time

import hext
import requests

from newsqa.config import REQUEST_HEADERS
from newsqa.exceptions import RequestError
from newsqa.util.diskcache_ import get_diskcache
from newsqa.util.sys_ import print_error

from ._common import SLEEP_TIME_BETWEEN_NEWS_REQUESTS

_DISKCACHE = get_diskcache(__file__)
_HEXT = hext.Rule("""
    <h2 class="mb-2">
      <a href:link class="news-link" @text:title />
    </h2>
    <p class="mb-4" @text:description />
    """)
MAX_PAGE_NUM = 40  # Observed empirically. Ex: https://medicalxpress.com/search/page41.html?search=papaya&s=0


class UnsupportedPageError(RequestError):
    """Excessive page number request error."""


@_DISKCACHE.memoize(expire=datetime.timedelta(hours=4).total_seconds(), tag="_get_search_response")
def _get_search_response(query: str, *, sort_by: str = "relevancy", headlines: bool = False, page_num: int = 1) -> requests.Response:
    """Return a response from the MedicalXpress website for a given query, sorting preference, and page number.

    Parameters:
        query (str): The search term used to query the website.
        sort_by (str, optional): The sorting method for the search results ('relevancy' or 'date'), with a default value of 'relevancy'.
        headlines (bool): The filter to limit search results to headlines matches only, with a default value of False.
        page_num (int, optional): The page number to retrieve, with a default value of 1.

    Returns:
        requests.Response: The HTTP response object containing the search results.

    Raises:
        UnsupportedPageError: If the page number is higher than the maximum allowed.
    """
    url = f"https://medicalxpress.com/search/page{page_num}.html"
    params = {"search": query, "s": {"relevancy": 0, "date": 1}[sort_by], "h": {True: 1, False: 0}[headlines]}
    headlines_filter_status = "with" if headlines else "without"
    description = f'page {page_num} of search results {headlines_filter_status} the headlines filter for "{query}" sorted by {sort_by}'
    if page_num > MAX_PAGE_NUM:
        raise UnsupportedPageError(f"Unable to request {description} because it exceeds the max page number of {MAX_PAGE_NUM}.")
    print(f"Requesting {description}.")
    response = requests.get(url, params=params, headers=REQUEST_HEADERS)
    try:
        response.raise_for_status()
    except requests.RequestException:
        print_error(f"Failed to receive {description} due to status code {response.status_code}.")
        raise
    print(f"Received {description} with status code {response.status_code}.")
    time.sleep(SLEEP_TIME_BETWEEN_NEWS_REQUESTS)
    return response


def get_search_results(**kwargs) -> list[dict]:
    """Return search results as a list of dictionaries, each containing the 'title', 'link', and 'description' of an article.

    `kwargs` are forwarded to `_get_search_response`.

    Returns:
        list[dict]: A list of dictionaries where each dictionary represents an article with its title, link, and description.

    An empty list is returned if the requested page number exceeds its maximum limit.
    """
    try:
        response = _get_search_response(**kwargs)
    except UnsupportedPageError:
        return []
    html = response.text
    html = hext.Html(html)
    rule = _HEXT
    results = rule.extract(html)
    return results


def get_printable_search_results(**kwargs) -> str:
    """Return the search results as a printable string with enumerated articles.

    `kwargs` are forwarded to `get_search_results`.

    Returns:
        str: A formatted string containing the search results, with each result numbered and displayed with its title, link, and description.

    A message indicating no results is returned if there are none.
    """

    results = get_search_results(**kwargs)
    heading = "Search results:"
    if results:
        printable_results = heading + "\n\n" + "\n\n".join(f'#{num}: {r['title']}\n{r['link']}\n{r['description']}' for num, r in enumerate(results, start=1))
    else:
        printable_results = heading + "\n(none)"
    return printable_results
