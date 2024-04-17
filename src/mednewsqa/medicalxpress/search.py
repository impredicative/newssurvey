import hext
import requests

from mednewsqa.config import REQUEST_HEADERS

_HEXT = hext.Rule("""
    <h2 class="mb-2">
      <a href:link class="news-link" @text:title />
    </h2>
    <p class="mb-4" @text:description />
    """)


def _get_search_response(query: str, *, sort_by: str = "relevancy", page_num: int = 1) -> requests.Response:
    url = f"https://medicalxpress.com/search/page{page_num}.html"
    params = {"search": query, "s": {"relevancy": 0, "date": 1}[sort_by]}
    response = requests.get(url, params=params, headers=REQUEST_HEADERS)
    return response


def get_search_results(query: str, *, sort_by: str = "relevancy", page_num: int = 1) -> list[dict]:
    try:
        response = _get_search_response(query, sort_by=sort_by, page_num=page_num)
        response.raise_for_status()
    except requests.HTTPError as exc:
        if exc.response.status_code == 404:
            return []
        raise
    html = response.text
    html = hext.Html(html)
    rule = _HEXT
    results = rule.extract(html)
    return results
