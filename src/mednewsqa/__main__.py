from typing import Optional

import fire
import os
from pathlib import Path

import mednewsqa.exceptions
from mednewsqa.util.openai import ensure_openai_key
from mednewsqa.util.sys import print_error
from mednewsqa.workflow.query import get_query, ensure_query_is_valid


def main(query: Optional[str] = None, path: Optional[Path] = None, confirm: bool = False) -> None:
    """Generate and optionally write a response to a medical question or concern using medical news.

    The progress and response are written to stdout.

    Params:
    * `query` (-q): Medical question or concern. If not given, the user is prompted for it.
    * `path (-p)`: Output file path. If given, the response is also written to this text file except if there is an error.
    * `confirm` (-c): Confirm as the workflow progresses.
        If true, a confirmation is interactively sought as each step of the workflow progresses. Its default is false.

    A nonzero exitcode exists if there is an error.
    """
    try:
        ensure_openai_key()

        if not query:
            query = get_query()
        ensure_query_is_valid(query)

        if path:
            path = Path(path)

        if not isinstance(confirm, bool):
            raise mednewsqa.exceptions.InputError("`confirm` (-c) argument has an invalid value. No value is to explicitly be specified for it since it is a boolean.")

        # generate_response(query, output_path=path, confirm=confirm)
    except mednewsqa.exceptions.Error as exc:
        print_error(str(exc))
        sep = '\n' if (isinstance(query, str) and (len(query.splitlines()) > 1)) else ' '
        print_error(f"Failed to generate response for query:{sep}{query}")
        exit(1)
    except KeyboardInterrupt:
        print()  # This separates "^C" from the subsequent error.
        print_error("Interrupted by user.")
        os._exit(-2)  # Plain `exit` is not used because it may not immediately terminate, with background threads potentially still running.


if __name__ == "__main__":
    fire.Fire(main)
