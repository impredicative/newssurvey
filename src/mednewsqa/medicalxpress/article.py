import datetime
import re

import hext
import requests

from mednewsqa.config import DISKCACHE, REQUEST_HEADERS

_HEXT = hext.Rule("""
    <html>
        <body>
            { <p @text:content /> }
        </body>
    </html>
    """)
_CONTENT_BLACKLIST = {
    # Observed before article text.
    "Forget Password?",
    "Learn more",
    "share this!",
    "Twit",
    "Share",
    "Email",
    #
    # Review attributes observed before article text.
    "fact-checked",
    "peer-reviewed publication",
    "trusted source",
    "proofread",
    "reputable news agency",
    #
    # Observed after article text.
    "Explore further",
    "Facebook",
    "Twitter",
    "Email",
    "Feedback to editors",
    "0",
    "",
    "More information Privacy policy",
    "1 hour ago",
}
_CONTENT_STARTSWITH_BLACKLIST = (
    # Observed before article text.
    "Click here to ",
    "This article has been reviewed ",
    #
    # Observed after article text.
    "Use this form if you have come across a ",
    "Please select the most appropriate ",
    "Thank you for taking time ",
    "Your feedback is ",
    "Your email address is ",
    "Get weekly and/or daily updates ",
    "We keep our content ",
    "Daily science news ",
    "The latest engineering, electronics ",
    "The most comprehensive sci-tech news ",
    "©",
)
_CONTENT_RE_FULLMATCH_BLACKLIST = [
    re.compile(p)
    for p in (
        # Observed before article text:
        r"\d+",  # Example: 39
        #
        # Observed after article text:
        r"\d+ minutes ago",  # Example: 8 minutes ago
        r"\d+ hours ago",  # Example: 5 hours ago
    )
]
_CONTENT_TRAILING_RE_BLACKLISTED = re.compile(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{1,2}), (\d{4})$")


@DISKCACHE.memoize(expire=datetime.timedelta(weeks=52).total_seconds(), tag="_get_article_response")
def _get_article_response(url: str) -> requests.Response:
    print(f"Reading {url}.")
    response = requests.get(url, headers=REQUEST_HEADERS)
    try:
        response.raise_for_status()
    except requests.RequestException:
        print(f"Failed to read {url} due to status code {response.status_code}.")
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
    return results


def _get_filtered_article_content(url: str) -> list[str]:
    content = _get_article_content(url)
    assert content
    content = [c for c in content if c not in _CONTENT_BLACKLIST]
    content = [c for c in content if not c.startswith(_CONTENT_STARTSWITH_BLACKLIST)]
    content = [c for c in content if not any(p.fullmatch(c) for p in _CONTENT_RE_FULLMATCH_BLACKLIST)]

    # Remove trailing dates
    while True:
        entry = content[-1]
        if _CONTENT_TRAILING_RE_BLACKLISTED.fullmatch(entry):
            content = content[:-1]
        else:
            break

    return content


def get_article_text(url: str) -> str:
    content = _get_filtered_article_content(url)
    text = "\n\n* ".join(content)
    text = text.strip()
    return text
