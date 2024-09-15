def prefix_lines(string: str, /, *, prefix: str = "> ") -> str:
    """Return the given string with each line prefixed by the given prefix."""
    return "\n".join(prefix + line for line in string.splitlines())


def is_none_response(text: str) -> bool:
    """Return true if the given text is a "none" response, otherwise false."""
    return text.lower() in ("none", "none.")


def is_ok_response(text: str) -> bool:
    """Return true if the given text is an "OK" response, otherwise false."""
    return text.upper() in ("OK", "OK.")
