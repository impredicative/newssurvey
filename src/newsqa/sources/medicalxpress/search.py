import datetime

import hext
import requests

from _common import DISKCACHE
from newsqa.config import REQUEST_HEADERS
from newsqa.exceptions import RequestError
from newsqa.util.sys import print_error

_DEFAULTS = {"sort_by": "relevancy", "page_num": 1}
_HEXT = hext.Rule("""
    <h2 class="mb-2">
      <a href:link class="news-link" @text:title />
    </h2>
    <p class="mb-4" @text:description />
    """)
MAX_PAGE_NUM = 40


class UnsupportedPageError(RequestError):
    """Excessive page number request error."""


@DISKCACHE.memoize(expire=datetime.timedelta(hours=4).total_seconds(), tag="_get_search_response")
def _get_search_response(query: str, *, sort_by: str, page_num: int) -> requests.Response:  # Note: Default values are intentionally not specified for any arg in order to cache explicitly.
    """Return a response from the MedicalXpress website for a given query, sorting preference, and page number.

    Parameters:
        query (str): The search term used to query the website.
        sort_by (str): The method of sorting the search results ('relevancy' or 'date').
        page_num (int): The page number of the search results to retrieve.

    Returns:
        requests.Response: The HTTP response object containing the search results.

    Raises:
        UnsupportedPageError: If the page number is higher than the maximum allowed.
    """
    url = f"https://medicalxpress.com/search/page{page_num}.html"
    params = {"search": query, "s": {"relevancy": 0, "date": 1}[sort_by]}
    description = f'page {page_num} of search results for "{query}" sorted by {sort_by}'
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
    return response


def get_search_results(query: str, *, sort_by: str = _DEFAULTS["sort_by"], page_num: int = _DEFAULTS["page_num"]) -> list[dict]:
    """Return search results as a list of dictionaries, each containing the 'title', 'link', and 'description' of an article.

    Parameters:
        query (str): The search term.
        sort_by (str, optional): The sorting method for the search results, with a default value of 'relevancy'.
        page_num (int, optional): The page number to retrieve, with a default value of 1.

    Returns:
        list[dict]: A list of dictionaries where each dictionary represents an article with its title, link, and description.

    An empty list is returned if the requested page number exceeds its maximum limit.
    """
    try:
        response = _get_search_response(query, sort_by=sort_by, page_num=page_num)
    except UnsupportedPageError:
        return []
    # except requests.HTTPError as exc:
    #     if exc.response.status_code == 404:  # Observed when `page_num > MAX_PAGE_NUM`.
    #         return []
    #     raise
    html = response.text
    html = hext.Html(html)
    rule = _HEXT
    results = rule.extract(html)
    return results


def get_printable_search_results(query: str, *, sort_by: str = _DEFAULTS["sort_by"], page_num: int = _DEFAULTS["page_num"]) -> str:
    """Return the search results as a printable string with enumerated articles.

    Parameters:
        query (str): The search term.
        sort_by (str, optional): The sorting method for the search results, with a default value of 'relevancy'.
        page_num (int, optional): The page number to retrieve, with a default value of 1.

    Returns:
        str: A formatted string containing the search results, with each result numbered and displayed with its title, link, and description.

    A message indicating no results is returned if there are none.
    """

    results = get_search_results(query, sort_by=sort_by, page_num=page_num)
    heading = f'Search results for "{query}" by {sort_by} (page {page_num}):'
    if results:
        printable_results = heading + "\n\n" + "\n\n".join(f'#{num}: {r['title']}\n{r['link']}\n{r['description']}' for num, r in enumerate(results, start=1))
    else:
        printable_results = heading + "\n(none)"
    return printable_results
