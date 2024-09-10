from typing import Callable

import hext
import requests

from newssurvey.config import CACHE_EXPIRATION_BY_TAG, CACHE_SIZES_GiB
from newssurvey.exceptions import RequestError
from newssurvey.types import SearchResult
from newssurvey.util.diskcache_ import get_diskcache
from newssurvey.util.sys_ import print_error

from ._common import REQUEST_HEADERS, request_cooldown_lock

_DISKCACHE = get_diskcache(__file__, size_gib=CACHE_SIZES_GiB["small"])
_HEXT = hext.Rule("""
    <h2 class="mb-2">
      <a href:link class="news-link" @text:title />
    </h2>
    <p class="mb-4" @text:description />
    """)
MAX_PAGE_NUM = 40  # Observed empirically. Ex: https://medicalxpress.com/search/page41.html?search=papaya&s=0


class UnsupportedPageError(RequestError):
    """Excessive page number request error."""


@_DISKCACHE.memoize(expire=CACHE_EXPIRATION_BY_TAG["get_search_response"], tag="get_search_response")
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
    with request_cooldown_lock:
        print(f"Requesting {description}.")
        response = requests.get(url, params=params, headers=REQUEST_HEADERS)
    try:
        response.raise_for_status()
    except requests.RequestException:
        print_error(f"Failed to receive {description} due to status code {response.status_code}.")
        raise
    print(f"Received {description} with status code {response.status_code}.")
    return response


def get_search_results(**kwargs) -> list[SearchResult]:
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

    for result in results:
        result["title"] = result["title"].rstrip()  # Removes observed trailing character like \xa0, \u202f, etc.
        assert result["title"] == result["title"].strip(), (result["title"], result["title"].strip())  # If leading whitespace is observed, it may then have to be removed from both the title and the text.

    return results


def run_searches(target: Callable) -> None:
    """Call the given target function with the respective keyword arguments for each type of search that can be conducted.

    Note: The keyword arguments `query` and `page_num` are managed automatically by the target function, and are therefore not provided.
    """
    for sort_by in ("relevancy", "date"):
        for headlines in (True, False):
            target(sort_by=sort_by, headlines=headlines)
