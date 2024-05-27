import contextlib
import io

import newsqa.exceptions
from newsqa.config import NEWS_SOURCES
from newsqa.util.sys_ import print_error


def is_source_valid(source: str) -> bool:
    """Return true if the news source is supported, otherwise false.

    A validation error is printed if the news source is unsupported.
    """
    if not isinstance(source, str):
        print_error("Source must be a string.")
        return False
    if source != source.strip():
        print_error("Source must not have leading or trailing whitespace.")  # It is assumed that whitespace is stripped before this check.
        return False
    if len(source) == 0:
        print_error("No source was provided.")
        return False
    if source not in NEWS_SOURCES:
        supported_news_sources = ", ".join(sorted(NEWS_SOURCES))
        print_error(f"Source {source!r} is not among the supported news source: {supported_news_sources}")
        return False
    return True


def ensure_source_is_valid(source: str) -> None:
    """Raise `InputError` if the news source is unsupported."""
    error = io.StringIO()
    with contextlib.redirect_stderr(error):
        if not is_source_valid(source):
            error = error.getvalue().rstrip().removeprefix("Error: ")
            raise newsqa.exceptions.InputError(error)


def get_source() -> str:
    """Get news source from user input."""
    assert NEWS_SOURCES
    supported_news_sources = dict(zip(range(1, len(NEWS_SOURCES) + 1), sorted(NEWS_SOURCES)))
    print("The supported news sources are:")
    for source_num, source in supported_news_sources.items():
        print(f"\t{source_num}. {source}")

    source = None
    while not source:
        source = input("Specify the name or number of a supported news source: ")
        source = source.strip().lower()
        if source in supported_news_sources:
            source = supported_news_sources[source]

        if not is_source_valid(source):
            source = None
    return source
