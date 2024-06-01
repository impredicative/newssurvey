import importlib
from typing import Optional

import fire
import os
from pathlib import Path

import newsqa.exceptions
from newsqa.config import NEWS_SOURCES
from newsqa.newsqa import generate_response
from newsqa.util.openai_ import ensure_openai_key
from newsqa.util.sys_ import print_error
from newsqa.workflow.user.query import get_query, ensure_query_is_valid
from newsqa.workflow.user.source import get_source, ensure_source_is_valid


def main(source: Optional[str] = None, query: Optional[str] = None, path: Optional[Path] = None, confirm: bool = False) -> None:
    """Generate, print, and optionally write a response to a question or concern using a supported news source.

    The progress and response both are printed to stdout.

    Params:
    * `source` (-s): Name of supported news source. If not given, the user is prompted for it.
    * `query` (-q): Question or concern answerable by the news source. If not given, the user is prompted for it.
    * `path (-p)`: Output file path. If given, the response is also written to this text file except if there is an error.
    * `confirm` (-c): Confirm as the workflow progresses. If true, a confirmation is interactively sought as each step of the workflow progresses. Its default is false.

    A nonzero exitcode exists if there is an error.
    """
    try:
        ensure_openai_key()

        if not source:
            source = get_source()
        ensure_source_is_valid(source)
        source_module = importlib.import_module(NEWS_SOURCES[source].name)

        if not query:
            query = get_query(source_type=source_module.NEWS_TYPE)
        ensure_query_is_valid(query)

        if path:
            path = Path(path)

        if not isinstance(confirm, bool):
            raise newsqa.exceptions.InputError("`confirm` (-c) argument has an invalid value. No value is to explicitly be specified for it since it is a boolean.")

        response = generate_response(source=source, query=query, output_path=path, confirm=confirm)
        print(response)
    except newsqa.exceptions.Error as exc:
        print_error(str(exc))
        query_sep = "\n" if (isinstance(query, str) and (len(query.splitlines()) > 1)) else " "
        print_error(f"Failed to generate response for source {source} for query:{query_sep}{query}")
        exit(1)
    except KeyboardInterrupt:
        print()  # This separates "^C" from the subsequent error.
        print_error("Interrupted by user.")
        os._exit(-2)  # Plain `exit` is not used because it may not immediately terminate, with any background threads potentially still running.


if __name__ == "__main__":
    fire.Fire(main)
