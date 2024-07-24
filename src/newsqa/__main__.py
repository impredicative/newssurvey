import os
from pathlib import Path
from typing import Optional

import click

import newsqa.exceptions
from newsqa.newsqa import generate_response
from newsqa.util.openai_ import ensure_openai_key
from newsqa.util.sys_ import print_error
from newsqa.workflow.user.query import get_query, ensure_query_is_valid
from newsqa.workflow.user.source import get_source, get_source_module, ensure_source_is_valid


@click.command(context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 120})
@click.option("--source", "-s", default=None, help="Name of supported news source. If not given, the user is prompted for it.")
@click.option("--query", "-q", default=None, help="Question or concern answerable by the news source. If a path to a file, the file text is read. If not given, the user is prompted for it.")
@click.option("--output-path", "-o", default=None, type=Path, help="Output file path. If given, the response is also written to this text file except if there is an error.")
@click.option("--confirm/--no-confirm", "-c/-nc", default=True, help="Confirm as the workflow progresses. If `--confirm`, a confirmation is interactively sought as each step of the workflow progresses, and this is the default. If `--no-confirm`, the workflow progresses without any confirmation.")
def main(source: Optional[str], query: Optional[str], output_path: Optional[Path], confirm: bool) -> None:
    """Generate, print, and optionally write a response to a question or concern using a supported news source.

    The progress and response both are printed to stdout.

    A nonzero exitcode exists if there is an error.
    """
    try:
        ensure_openai_key()

        if not source:
            source = get_source()
        ensure_source_is_valid(source)
        source_module = get_source_module(source)

        if not query:
            query = get_query(source_type=source_module.SOURCE_TYPE)
        elif (query_path := Path(query)).is_file():
            assert query_path.exists()
            query = query_path.read_text().strip()
        ensure_query_is_valid(query)

        if output_path:
            assert isinstance(output_path, Path), (output_path, type(output_path))
        assert isinstance(confirm, bool), (confirm, type(confirm))

        response = generate_response(source=source, query=query, output_path=output_path, confirm=confirm)
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
    main()
