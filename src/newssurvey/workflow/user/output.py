import datetime

from newssurvey.config import CITATION_GROUP_PATTERN
from newssurvey.types import SectionGen2, CitationGen2


def format_text_output(title: str, sections: list[SectionGen2], citations: list[CitationGen2]) -> str:
    """Return the formatted text output for the given sections and citations."""
    date = datetime.date.today()
    date = f"{date.strftime('%B')} {date.day}, {date.year}"  # Platform-independent date formatting. Example: "September 8, 2024"

    sections = [SectionGen2(title=section["title"], text=CITATION_GROUP_PATTERN.sub(r"[\1]", section["text"])) for section in sections]  # Use standard brackets for citations.

    text = f"{title}\n\n" + f"{date}\n\n" + "Sections:\n" + "\n".join([f"{num}: {section['title']}" for num, section in enumerate(sections, start=1)]) + "\n\n" + "\n\n".join(f'Section {num}. {s["title"]}:\n\n{s["text"]}' for num, s in enumerate(sections, start=1)) + "\n\n" + "References:\n\n" + "\n\n".join([f"{c['number']}: {c['title']}\n{c['link']}" for c in citations])
    return text
