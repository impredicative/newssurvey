import textwrap


def tab_indent(text: str, prefix: str = "\t") -> str:
    return textwrap.indent(text, prefix=prefix)
