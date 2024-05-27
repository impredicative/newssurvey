from pathlib import Path
from typing import Optional


def generate_response(source: str, query: str, output_path: Optional[Path] = None, confirm: bool = False) -> str:
    """Return a response for the given source and query.

    The progress is printed to stdout.

    Params:
    * `source` (-s): Name of supported news source.
    * `query` (-q): Question or concern answerable by the news source.
    * `path (-p)`: Output file path. If given, the response is also written to this text file except if there is an error.
    * `confirm` (-c): Confirm as the workflow progresses. If true, a confirmation is interactively sought as each step of the workflow progresses. Its default is false.

    If failed, a subclass of the `newsqa.exceptions.Error` exception is raised.
    """
