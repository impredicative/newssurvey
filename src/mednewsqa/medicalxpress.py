import hext
import requests

BASE_URL = "https://medicalxpress.com/"
HEXT = {
    "search": hext.Rule("""
    <h2 class="mb-2">
      <a href:link class="news-link" @text:title />
    </h2>
    <p class="mb-4" @text:description />
""")
}
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0"


def get_search_results_response(query: str, *, sort_by: str = "relevancy", page_num: int = 1) -> requests.Response:
    url = f"{BASE_URL}search/page{page_num}.html"
    params = {"search": query, "s": {"relevancy": 0, "date": 1}[sort_by]}
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(url, params=params, headers=headers)
    return response


def get_search_results(*args, **kwargs) -> list[dict]:
    try:
        response = get_search_results_response(*args, **kwargs)
        response.raise_for_status()
    except requests.HTTPError as exc:
        if exc.response.status_code == 404:
            return []
        raise
    html = response.text
    html = hext.Html(html)
    rule = HEXT["search"]
    results = rule.extract(html)
    return results
