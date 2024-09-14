import contextlib
import io

import click

import newssurvey.exceptions
from newssurvey.util.sys_ import print_error


def is_query_valid(query: str) -> bool:
    """Return true if the query is structurally valid, otherwise false.

    A validation error is printed if the query is invalid.
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
    if any(ln.lstrip().startswith("#") for ln in query.splitlines()):
        print_error("Query may not contain any line starting with # as it will interfere with separating sections in the prompts.")
        # Note:
        # - Technically, only level 1 to 2 headings need to be avoided, with level 3 and lower levels being acceptable.
        # - More technically, user supplied level 1 or 2 headings can if necessary be dedented to level 3 and lower headings.
        return False
    return True


def ensure_query_is_valid(query: str) -> None:
    """Raise `InputError` if the query is structurally invalid."""
    error = io.StringIO()
    with contextlib.redirect_stderr(error):
        if not is_query_valid(query):
            error = error.getvalue().rstrip().removeprefix("Error: ")
            raise newssurvey.exceptions.InputError(error)


def get_query(*, source_type: str, approach: str = "click.edit") -> str:
    """Get user query from user input.

    `source_type` is a string that corresponds to the SOURCE_TYPE variable of the corresponding source.

    `InputError` is raised if the approach is "click.edit" and the user-supplied query is empty.
    """
    query = None
    while not query:
        match approach:
            case "input":
                query = input(f"Specify the {source_type} question or concern: ")
            case "click.edit":
                query = click.edit(text=f"\n# Specify the {source_type} question or concern in one or more lines.\n# Lines starting with # will be skipped.", require_save=False) or ""
                query = "\n".join(ln for ln in query.splitlines() if not ln.lstrip().startswith("#"))
                if not query.strip():
                    raise newssurvey.exceptions.InputError("No query was provided.")  # Note: This is the only way for the user to abort the editor.
            case _:
                assert False, approach
        query = query.strip()
        if not is_query_valid(query):
            query = None
    return query
