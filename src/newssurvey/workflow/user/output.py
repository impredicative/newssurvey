import datetime

from newssurvey.config import CITATION_GROUP_PATTERN
from newssurvey.types import SectionGen2, CitationGen2


def _get_date_string() -> str:
    """Return the current date as a string."""
    date = datetime.date.today()
    return f"{date.strftime('%B')} {date.day}, {date.year}"  # Platform-independent date formatting. Example: "September 8, 2024"


def format_text_output(title: str, sections: list[SectionGen2], citations: list[CitationGen2]) -> str:
    """Return the text output for the given sections and citations."""
    sections = [SectionGen2(title=section["title"], text=CITATION_GROUP_PATTERN.sub(r"[\1]", section["text"])) for section in sections]  # Use standard brackets for citations.

    text = f"{title}\n\n" + f"{_get_date_string()}\n\n" + "Sections:\n" + "\n".join([f"{num}: {section['title']}" for num, section in enumerate(sections, start=1)]) + "\n\n" + "\n\n".join(f'Section {num}: {s["title"]}:\n\n{s["text"]}' for num, s in enumerate(sections, start=1)) + "\n\n" + "References:\n\n" + "\n\n".join([f"{c['number']}: {c['title']}\n{c['link']}" for c in citations])
    return text


def format_markdown_output(title: str, sections: list[SectionGen2], citations: list[CitationGen2]) -> str:
    """Return the GitHub Flavored markdown output for the given sections and citations."""
    contents = [f"{num}. [{section['title']}](#section-{num})" for num, section in enumerate(sections, start=1)]
    references_contents_num = len(contents) + 1
    contents.append(f"{references_contents_num}. [References](#references)")

    sections = [SectionGen2(title=section["title"], text=CITATION_GROUP_PATTERN.sub(r"[\1]", section["text"])) for section in sections]  # Use standard brackets for citations.

    text = f"# {title}\n\n" + f"{_get_date_string()}\n\n" + "## Contents:\n" + "\n".join(contents) + "\n\n" + "\n\n".join(f'## <a id="section-{num}"></a>{num}. {s["title"]}\n\n{s["text"]}' for num, s in enumerate(sections, start=1)) + "\n\n" + f'## <a id="references"></a>{references_contents_num}. References\n\n' + "\n\n".join([f"{c['number']}. [{c['title']}]({c['link']})" for c in citations])
    return text
