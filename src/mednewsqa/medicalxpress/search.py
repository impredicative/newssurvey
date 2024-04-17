import datetime

import hext
import requests

from mednewsqa.config import DISKCACHE, REQUEST_HEADERS
from mednewsqa.exceptions import RequestError

_DEFAULTS = {"sort_by": "relevancy", "page_num": 1}
_HEXT = hext.Rule("""
    <h2 class="mb-2">
      <a href:link class="news-link" @text:title />
    </h2>
    <p class="mb-4" @text:description />
    """)
MAX_PAGE_NUM = 40


class UnsupportedPageError(RequestError):
    pass


@DISKCACHE.memoize(expire=datetime.timedelta(hours=1).total_seconds(), tag="_get_search_response")
def _get_search_response(query: str, *, sort_by: str, page_num: int) -> requests.Response:  # Note: Default values are intentionally not specified for any arg in order to cache explicitly.
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
        print(f"Failed to receive {description} due to status code {response.status_code}.")
        raise
    print(f"Received {description} with status code {response.status_code}.")
    return response


def get_search_results(query: str, *, sort_by: str = _DEFAULTS["sort_by"], page_num: int = _DEFAULTS["page_num"]) -> list[dict]:
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
    results = get_search_results(query, sort_by=sort_by, page_num=page_num)
    heading = f'Search results for "{query}" by {sort_by} (page {page_num}):'
    if results:
        printable_results = heading + "\n\n" + "\n\n".join(f'#{num}: {r['title']}\n{r['link']}\n{r['description']}' for num, r in enumerate(results, start=1))
    else:
        printable_results = heading + "\n(none)"
    return printable_results
