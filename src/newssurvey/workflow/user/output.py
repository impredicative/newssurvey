import datetime
import re

from newssurvey.config import CITATION_GROUP_PATTERN
from newssurvey.types import SectionGen2, CitationGen2


def _get_date_string() -> str:
    """Return the current date as a string."""
    date = datetime.date.today()
    return f"{date.strftime('%B')} {date.day}, {date.year}"  # Platform-independent date formatting. Example: "September 8, 2024"


def format_text_output(title: str, sections: list[SectionGen2], citations: list[CitationGen2]) -> str:
    """Return the text output for the given sections and citations."""
    sections = [SectionGen2(title=section["title"], text=CITATION_GROUP_PATTERN.sub(r"[\1]", section["text"])) for section in sections]  # Uses standard brackets for citations.

    text = f"{title}\n\n" + f"{_get_date_string()}\n\n" + "Sections:\n" + "\n".join([f"{num}: {section['title']}" for num, section in enumerate(sections, start=1)]) + "\n\n" + "\n\n".join(f'Section {num}: {s["title"]}:\n\n{s["text"]}' for num, s in enumerate(sections, start=1)) + "\n\n" + "References:\n\n" + "\n\n".join([f"{c['number']}: {c['title']}\n{c['link']}" for c in citations])
    return text


def format_markdown_output(title: str, sections: list[SectionGen2], citations: list[CitationGen2]) -> str:
    """Return the GitHub Flavored markdown output for the given sections and citations."""
    contents = [f"{num}. [{section['title']}](#section-{num})" for num, section in enumerate(sections, start=1)]
    contents.append(f"{len(contents) + 1}. [References](#references)")

    def repl(match: re.Match) -> str:
        """Replace the plain citation numbers in the citation group with linked citation numbers."""
        return "[" + ",".join(f"[{citation_num}](#citation-{citation_num})" for citation_num in match.group(1).split(",")) + "]"

    sections = [SectionGen2(title=section["title"], text=CITATION_GROUP_PATTERN.sub(repl, section["text"])) for section in sections]

    text = f"# {title}\n\n" + f"{_get_date_string()}\n\n" + "## Contents\n" + "\n".join(contents) + "\n\n" + "\n\n".join(f'## <a id="section-{num}"></a>{num}. {s["title"]}\n\n{s["text"]}' for num, s in enumerate(sections, start=1)) + "\n\n" + '## <a id="references"></a>References\n\n' + "\n\n".join([f'<a id="citation-{c["number"]}"></a>{c["number"]}. [{c["title"]}]({c["link"]})' for c in citations])
    return text


def format_html_output(title: str, sections: list[dict], citations: list[dict]) -> str:
    """Return the HTML output for the given sections and citations."""
    contents = [f'<li><a href="#section-{num}">{section["title"]}</a></li>' for num, section in enumerate(sections, start=1)]
    contents.append('<li><a href="#references">References</a></li>')

    def repl(match: re.Match) -> str:
        """Replace the plain citation numbers in the citation group with linked citation numbers."""
        return "[" + ",".join(f'<a href="#citation-{citation_num}">{citation_num}</a>' for citation_num in match.group(1).split(",")) + "]"

    sections_html = [f'<h2 id="section-{num}">{num}. {section["title"]}</h2>\n<p>{CITATION_GROUP_PATTERN.sub(repl, section["text"])}</p>' for num, section in enumerate(sections, start=1)]
    references_html = [f'<li id="citation-{citation["number"]}"><a href="{citation["link"]}">{citation["title"]}</a></li>' for citation in citations]

    html_output = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>
<body>

<h1>{title}</h1>
<p>{_get_date_string()}</p>

<h2>Contents</h2>
<ol>
    {'\n    '.join(contents)}
</ol>

{'\n\n'.join(sections_html)}

<h2 id="references">References</h2>
<ol>
    {'\n    '.join(references_html)}
</ol>

</body>
</html>
    """

    return html_output
