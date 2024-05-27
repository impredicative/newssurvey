from pathlib import Path
from typing import Optional

from newsqa.util.openai_ import ensure_openai_key, MODELS
from newsqa.workflow.query import ensure_query_is_valid
from newsqa.workflow.source import ensure_source_is_valid


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
    ensure_openai_key()

    ensure_source_is_valid(source)
    print(f"SOURCE: {source}")

    ensure_query_is_valid(query)
    query_sep = "\n" if (len(query.splitlines()) > 1) else " "
    print(f"QUERY:{query_sep}{query}")

    print(f"MODELS: text={MODELS["text"]}, embeddings={MODELS["embeddings"]}")
