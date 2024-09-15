import os
import tempfile
from pathlib import Path
from typing import Optional

import click
import datetime
import locket
import pathvalidate

import newssurvey.exceptions
from newssurvey.config import CWD, NUM_SECTIONS_DEFAULT, NUM_SECTIONS_MIN, NUM_SECTIONS_MAX, OUTPUT_FORMAT_DEFAULT, PACKAGE_NAME
from newssurvey.newssurvey import generate_response
from newssurvey.util.openai_ import ensure_openai_key
from newssurvey.util.sys_ import print_error
from newssurvey.workflow.user.query import get_query, ensure_query_is_valid
from newssurvey.workflow.user.source import get_source, get_source_module, ensure_source_is_valid
from newssurvey.workflow.user.output import SUPPORTED_OUTPUT_FORMATS


def _get_default_output_format_and_filename(*, title: str, output_format: Optional[str]) -> str:
    """Return the default output format and filename for the given title."""
    now = datetime.datetime.now().isoformat(timespec="seconds")
    output_stem = f"{now} {title}"
    output_format = output_format or OUTPUT_FORMAT_DEFAULT
    output_name = f"{output_stem}.{output_format}"
    output_name = pathvalidate.sanitize_filename(output_name, platform="auto")
    return output_format, output_name


def _get_output_format_and_path(*, output_format: Optional[str], output_path: Path, title: Optional[str] = None) -> tuple[str, Path]:
    """Return the output format and path, ensuring they are valid."""
    if (output_format is not None) and (output_format not in SUPPORTED_OUTPUT_FORMATS):
        raise newssurvey.exceptions.InputError(f"Output format {output_format!r} is not supported. Supported formats are: {', '.join(SUPPORTED_OUTPUT_FORMATS)}")

    if output_path is None:
        if title:
            output_format, output_filename = _get_default_output_format_and_filename(title=title, output_format=output_format)
            output_path = CWD / output_filename
        else:
            output_format = output_format or OUTPUT_FORMAT_DEFAULT
            output_path = CWD
    else:
        assert isinstance(output_path, Path), (output_path, type(output_path))
    output_path = output_path.expanduser().resolve()

    if output_path.is_dir():
        assert output_path.exists()
        if title:
            output_format, output_filename = _get_default_output_format_and_filename(title=title, output_format=output_format)
            output_path = output_path / output_filename
        else:
            output_format = output_format or OUTPUT_FORMAT_DEFAULT
    else:
        supported_output_suffixes = tuple(f".{suffix}" for suffix in SUPPORTED_OUTPUT_FORMATS)
        if not output_path.name.endswith(supported_output_suffixes):
            raise newssurvey.exceptions.InputError(f"Output file path suffix {output_path.suffix!r} of output file name {output_path.name!r} is not supported. Supported suffixes are: {', '.join(supported_output_suffixes)}. If intended as a directory, it must exist.")
        extracted_output_suffix = next(suffix for suffix in supported_output_suffixes if output_path.name.endswith(suffix))
        extracted_output_format = extracted_output_suffix.lstrip(".")
        assert extracted_output_format in SUPPORTED_OUTPUT_FORMATS, (extracted_output_format, SUPPORTED_OUTPUT_FORMATS)
        if output_format and (output_format != extracted_output_format):
            raise newssurvey.exceptions.InputError(f"Output file path format {extracted_output_format!r} does not match the specified output format {output_format!r}.")
        output_format = extracted_output_format
        output_path.parent.mkdir(parents=True, exist_ok=True)

    pathvalidate.validate_filepath(output_path, platform="auto")
    return output_format, output_path


@click.command(context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 120})
@click.option("--source", "-s", default=None, help="Name of supported news source. If not given, the user is prompted for it.")
@click.option("--query", "-q", default=None, help="Question or concern answerable by the news source. If a path to a file, the file text is read as text. If not given, the user is prompted for it.")
@click.option("--max-sections", "-m", default=NUM_SECTIONS_DEFAULT, type=click.IntRange(NUM_SECTIONS_MIN, NUM_SECTIONS_MAX), help=f"Maximum number of sections to include in the response, between {NUM_SECTIONS_MIN} and {NUM_SECTIONS_MAX}. Its recommended value, also the default, is {NUM_SECTIONS_DEFAULT}.")
@click.option("--output-format", "-f", default=None, help=f"Output format of the response. It can be txt (for text), md (for markdown), gfm.md (for GitHub Flavored markdown), html, pdf, or json. If not specified, but if an output filename is specified via '--output-path', it is determined automatically from the file extension. If not specified, and if an output filename is not specified either, its default is {OUTPUT_FORMAT_DEFAULT}.")
@click.option("--output-path", "-o", default=None, type=Path, help="Output directory path or file path. If intended as a directory path, it must exist, and the file name is auto-determined. If intended as a file path, its extension can be txt (for text), md (for markdown), gfm.md (for GitHub Flavored markdown), html, pdf, or json. If not specified, the output file is written to the current working directory with an auto-determined file name. The response is written to the file except if there is an error.")
@click.option("--confirm/--no-confirm", "-c/-nc", default=True, help="Confirm as the workflow progresses. If `--confirm`, a confirmation is interactively sought as each step of the workflow progresses, and this is the default. If `--no-confirm`, the workflow progresses without any confirmation.")
def main(*args, **kwargs) -> None:
    """Generate and write a response to a question or concern using a supported news source.

    A single instance of this method is enforced.
    """
    lockfile_path = Path(tempfile.gettempdir()) / f"{PACKAGE_NAME}.lock"
    try:
        with locket.lock_file(lockfile_path, timeout=1):
            _main(*args, **kwargs)
    except locket.LockError:
        print_error(f"Only a single instance of {PACKAGE_NAME} can be run at a time. This is intended to avoid remote throttling of requests. Another instance of it may be running using the lock file {lockfile_path}.")
        exit(1)


def _main(source: Optional[str], query: Optional[str], max_sections: int, output_format: str, output_path: Path, confirm: bool) -> None:
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

        query_origin = "arg"
        if not query:
            query = get_query(source_type=source_module.SOURCE_TYPE)
            query_origin = "prompt"
        elif (query_path := Path(query)).is_file():
            assert query_path.exists()
            query = query_path.read_text().strip()
            query_origin = "file"
        ensure_query_is_valid(query)

        assert isinstance(max_sections, int), (max_sections, type(max_sections))
        assert NUM_SECTIONS_MIN <= max_sections <= NUM_SECTIONS_MAX, (max_sections, NUM_SECTIONS_MIN, NUM_SECTIONS_MAX)

        output_format, output_path = _get_output_format_and_path(output_format=output_format, output_path=output_path)
        if (query_origin == "file") and (query_path.resolve() == output_path.resolve()):
            raise newssurvey.exceptions.InputError(f"Output file path {str(output_path.resolve())!r} is the same as the query file path {str(query_path.resolve())!r}.")

        assert isinstance(confirm, bool), (confirm, type(confirm))

        response = generate_response(source=source, query=query, max_sections=max_sections, output_format=output_format, confirm=confirm)
        assert output_format == response.format, (output_format, response.format)

        output_format, output_path = _get_output_format_and_path(output_format=output_format, output_path=output_path, title=response.title)
        if (query_origin == "file") and (query_path.resolve() == output_path.resolve()):
            raise newssurvey.exceptions.InputError(f"Output file path {str(output_path.resolve())!r} is the same as the query file path {str(query_path.resolve())!r}.")

        response_data = response.response
        if isinstance(response_data, str):
            output_path.write_text(response_data)
        elif isinstance(response_data, bytes):
            output_path.write_bytes(response_data)
        else:
            assert False, type(response_data)
        print(f"Wrote response titled {response.title!r} in format {response.format} to {str(output_path.resolve())!r}.")
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
