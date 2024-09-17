import itertools
import re

import hext
import requests

from newssurvey.config import CACHE_EXPIRATION_BY_TAG, CACHE_SIZES_GiB
from newssurvey.util.diskcache_ import get_diskcache
from newssurvey.util.sys_ import print_error

from ._common import REQUEST_HEADERS, request_cooldown_lock

_DISKCACHE = get_diskcache(__file__, size_gib=CACHE_SIZES_GiB["large"])
_EXPECTED_ARTICLE_URL_PREFIX = "https://phys.org/news/"
_HEXT = hext.Rule("""
    <html>
        <body>
            { <*:type-matches(/^(p)$|^(h[1-6])$/) @text:content /> }
        </body>
    </html>
    """)  # Ref: https://github.com/html-extract/hext/issues/30#issuecomment-2072869699
_PRE_CONTENT_BLACKLIST = {
    "Science X Account",
    "Forget Password?",
    "Learn more",
    "share this!",
    "Twit",
    "Share",
    "Email",
}
_PRE_CONTENT_STARTSWITH_BLACKLIST = ("Click here to ",)
_PRE_CONTENT_RE_FULLMATCH_BLACKLIST = [
    re.compile(p)
    for p in (
        r"\d+(?:\.\d+)?K",  # Example: 1.9K
        r"\d+",  # Example: 39
    )
]
_MID_CONTENT_BLACKLIST = {
    "written by researcher(s)",
    #
    # Review attributes:
    "fact-checked",
    "peer-reviewed publication",
    "trusted source",
    "proofread",
    "reputable news agency",
}
_MID_CONTENT_STARTSWITH_BLACKLIST = (
    "This article has been reviewed ",
    "©",
    "Copyright ",
)
_POST_CONTENT_BLACKLIST = {
    "Explore further",
}
_POST_CONTENT_STARTSWITH_BLACKLIST = ()
_CONTENT_SUFFIX_REMOVELIST = (" Read the original article.",)


@_DISKCACHE.memoize(expire=CACHE_EXPIRATION_BY_TAG["get_article_response"], tag="get_article_response")
def _get_article_response(url: str) -> requests.Response:
    assert url.startswith(_EXPECTED_ARTICLE_URL_PREFIX), url
    with request_cooldown_lock:
        print(f"Reading {url}.")
        response = requests.get(url, headers=REQUEST_HEADERS)
        # Note: params={"deviceType": "mobile"} is not specified because it results in the loss of the article date.
    try:
        response.raise_for_status()
    except requests.RequestException:
        print_error(f"Failed to read {url} due to status code {response.status_code}.")
        raise
    print(f"Read {url} with status code {response.status_code}.")
    return response


def _get_article_content(url: str) -> list[str]:
    response = _get_article_response(url)
    html = response.text

    rule = _HEXT
    html = hext.Html(html)
    results = rule.extract(html)
    results = results[0]["content"]

    results = [r.strip() for r in results]
    results = [r for r in results if r]

    return results


def _get_filtered_article_content(url: str) -> list[str]:
    content = _get_article_content(url)
    assert content

    # Remove invalid pre-article content
    dropwhile_predicate = lambda c: ((c in _PRE_CONTENT_BLACKLIST) or (c.startswith(_PRE_CONTENT_STARTSWITH_BLACKLIST)) or any(p.fullmatch(c) for p in _PRE_CONTENT_RE_FULLMATCH_BLACKLIST))
    content = list(itertools.dropwhile(dropwhile_predicate, content))

    # Remove invalid post-article content
    takewhile_predicate = lambda c: ((c not in _POST_CONTENT_BLACKLIST) and (not c.startswith(_POST_CONTENT_STARTSWITH_BLACKLIST)))
    content = list(itertools.takewhile(takewhile_predicate, content))

    # Remove invalid mid-article content
    content = [c for c in content if ((c not in _MID_CONTENT_BLACKLIST) and (not c.startswith(_MID_CONTENT_STARTSWITH_BLACKLIST)))]

    # Remove invalid suffix
    for idx, c in enumerate(content.copy()):
        for suffix in _CONTENT_SUFFIX_REMOVELIST:
            if c.endswith(suffix):
                content[idx] = c.removesuffix(suffix)

    assert content
    return content


def get_article_text(url: str) -> str:
    content = _get_filtered_article_content(url)
    text = "\n\n".join(content)
    text = text.strip()
    return text
