import contextlib
import io

import newsqa.exceptions
from newsqa.util.sys_ import print_error


def is_query_valid(query: str) -> bool:
    """Return true if the query is structurally valid, otherwise false.

    A validation error is printed if the query is false.
    """
    if not isinstance(query, str):  # Note: This happens if `-t` flag is provided without any value.
        print_error("Query must be a string.")
        return False
    if query != query.strip():
        print_error("Query must not have leading or trailing whitespace.")  # It is assumed that whitespace is stripped before this check.
        return False
    if len(query) == 0:
        print_error("No query was provided.")
        return False
    if len(query) < 2:
        print_error("Query must be at least two characters long.")
        return False
    return True


def ensure_query_is_valid(query: str) -> None:
    """Raise `InputError` if the query is structurally invalid."""
    error = io.StringIO()
    with contextlib.redirect_stderr(error):
        if not is_query_valid(query):
            error = error.getvalue().rstrip().removeprefix("Error: ")
            raise newsqa.exceptions.InputError(error)


def get_query() -> str:
    """Get user query from user input."""
    query = None
    while not query:
        query = input("Specify the medical question or concern: ")
        query = query.strip()
        if not is_query_valid(query):
            query = None
    return query
