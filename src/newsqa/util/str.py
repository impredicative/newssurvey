def prefix_lines(string: str, /, *, prefix: str = "> ") -> str:
    """Return the given string with each line prefixed by the given prefix."""
    return "\n".join(prefix + line for line in string.splitlines())
