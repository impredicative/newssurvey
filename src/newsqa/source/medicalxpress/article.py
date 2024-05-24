import datetime
import itertools
import re

import hext
import requests

from newsqa.config import REQUEST_HEADERS
from newsqa.util.diskcache_ import get_diskcache
from newsqa.util.sys_ import print_error

_DISKCACHE = get_diskcache(__file__)
_HEXT = hext.Rule("""
    <html>
        <body>
            { <p @text:content /> }
        </body>
    </html>
    """)
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
    "Copyright ©",
)
_POST_CONTENT_BLACKLIST = {
    "Explore further",
}
_POST_CONTENT_STARTSWITH_BLACKLIST = ()
_CONTENT_SUFFIX_REMOVELIST = (" Read the original article.",)


@_DISKCACHE.memoize(expire=datetime.timedelta(weeks=52).total_seconds(), tag="_get_article_response")
def _get_article_response(url: str) -> requests.Response:
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

    # Replace heading tags with paragraph tag
    # This is done because the hext rule extracts text from p tags only.
    for heading_level in range(1, 7):
        heading_tag_half_open, heading_tag_full_open, heading_tag_close = f"<h{heading_level} ", f"<h{heading_level}>", f"</h{heading_level}>"
        if heading_tag_close in html:
            html = html.replace(heading_tag_half_open, "<p ")
            html = html.replace(heading_tag_full_open, "<p>")
            html = html.replace(heading_tag_close, "</p>")
            # print(f"Replaced h{heading_level} with p tags.")

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
