import os
from pathlib import Path
from typing import Optional

import click

import newssurvey.exceptions
from newssurvey.config import NUM_SECTIONS_DEFAULT, NUM_SECTIONS_MIN, NUM_SECTIONS_MAX
from newssurvey.newssurvey import generate_response
from newssurvey.util.openai_ import ensure_openai_key
from newssurvey.util.sys_ import print_error
from newssurvey.workflow.user.query import get_query, ensure_query_is_valid
from newssurvey.workflow.user.source import get_source, get_source_module, ensure_source_is_valid


@click.command(context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 120})
@click.option("--source", "-s", default=None, help="Name of supported news source. If not given, the user is prompted for it.")
@click.option("--query", "-q", default=None, help="Question or concern answerable by the news source. If a path to a file, the file text is read as text. If not given, the user is prompted for it.")
@click.option("--max-sections", "-m", default=NUM_SECTIONS_DEFAULT, type=click.IntRange(NUM_SECTIONS_MIN, NUM_SECTIONS_MAX), help=f"Maximum number of sections to include in the response, between {NUM_SECTIONS_MIN} and {NUM_SECTIONS_MAX}. Its recommended value, also the default, is {NUM_SECTIONS_DEFAULT}.")
@click.option("--output-path", "-o", required=True, type=Path, help="Output file path with extension txt (for text), md (for GitHub Flavored markdown), or html (for HTML). The response is written to this file except if there is an error.")
@click.option("--confirm/--no-confirm", "-c/-nc", default=True, help="Confirm as the workflow progresses. If `--confirm`, a confirmation is interactively sought as each step of the workflow progresses, and this is the default. If `--no-confirm`, the workflow progresses without any confirmation.")
def main(source: Optional[str], query: Optional[str], max_sections: int, output_path: Path, confirm: bool) -> None:
    """Generate and write a response to a question or concern using a supported news source.

    The progress is printed to stdout.

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

        assert isinstance(max_sections, int), (max_sections, type(max_sections))
        assert NUM_SECTIONS_MIN <= max_sections <= NUM_SECTIONS_MAX, (max_sections, NUM_SECTIONS_MIN, NUM_SECTIONS_MAX)

        assert isinstance(output_path, Path), (output_path, type(output_path))
        assert not output_path.is_dir(), output_path
        output_path_suffix = output_path.suffix
        assert output_path_suffix in (".txt", ".md", ".html"), (output_path, output_path_suffix)
        output_format = output_path_suffix.lstrip(".")

        assert isinstance(confirm, bool), (confirm, type(confirm))

        response = generate_response(source=source, query=query, max_sections=max_sections, output_format=output_format, confirm=confirm)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(response)
        print(f"Wrote response to {output_path.resolve()}.")
    except newssurvey.exceptions.Error as exc:
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
