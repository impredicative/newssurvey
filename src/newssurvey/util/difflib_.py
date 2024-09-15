import difflib


def ndiffstr(a: list[str], b: list[str]) -> str:
    """Return the difference between two lists of strings as a string."""
    return "\n".join(difflib.ndiff(a, b))
