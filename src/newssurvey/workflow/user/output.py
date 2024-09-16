import datetime
import json
import re

from newssurvey.config import CITATION_GROUP_PATTERN, PROMPTS
from newssurvey.types import SectionGen2, CitationGen2

_DISCLAIMER = PROMPTS["disclaimer"]
SUPPORTED_OUTPUT_FORMATS: list[str] = ["txt", "gfm.md", "md", "html", "pdf", "json"]  # Note: 'gfm.md' must remain before 'md' to avoid matching 'md' first.


def _get_date_string() -> str:
    """Return the current date as a string."""
    date = datetime.date.today()
    return f"{date.strftime('%B')} {date.day}, {date.year}"  # Platform-independent date formatting. Example: "September 8, 2024"


def format_text_output(title: str, sections: list[SectionGen2], citations: list[CitationGen2]) -> str:
    """Return the text string output for the given sections and citations."""
    sections = [SectionGen2(title=section["title"], text=CITATION_GROUP_PATTERN.sub(r"[\1]", section["text"])) for section in sections]  # Uses standard brackets for citations.

    text = f"{title}\n\n" + f"{_get_date_string()}\n\n{_DISCLAIMER}\n\n" + "Sections:\n" + "\n".join([f"{num}: {section['title']}" for num, section in enumerate(sections, start=1)]) + "\n\n" + "\n\n".join(f'Section {num}: {s["title"]}:\n\n{s["text"]}' for num, s in enumerate(sections, start=1)) + "\n\n" + "References:\n\n" + "\n\n".join([f"{c['number']}: {c['title']}\n{c['link']}" for c in citations])
    return text


def format_markdown_output(title: str, sections: list[SectionGen2], citations: list[CitationGen2]) -> str:
    """Return the markdown string output for the given sections and citations."""
    contents = [f"{num}. [{section['title']}](#section-{num})" for num, section in enumerate(sections, start=1)]
    contents.append(f"{len(contents) + 1}. [References](#references)")

    def repl(match: re.Match) -> str:
        """Return the match text with the plain citation numbers in the citation group replaced with linked citation numbers."""
        return "<sup>[" + ",".join(f"[{citation_num}](#citation-{citation_num})" for citation_num in match.group(1).split(",")) + "]</sup>"

    sections = [SectionGen2(title=section["title"], text=CITATION_GROUP_PATTERN.sub(repl, section["text"])) for section in sections]

    text = f"# {title}\n\n" + f"{_get_date_string()}\n\n_{_DISCLAIMER}_\n\n" + "## Contents\n" + "\n".join(contents) + "\n\n" + "\n\n".join(f'## <a id="section-{num}"></a>{num}. {s["title"]}\n\n{s["text"]}' for num, s in enumerate(sections, start=1)) + "\n\n" + '## <a id="references"></a>References\n\n' + "\n\n".join([f'<a id="citation-{c["number"]}"></a>{c["number"]}. [{c["title"]}]({c["link"]})' for c in citations])
    return text


def format_gfm_output(title: str, sections: list[SectionGen2], citations: list[CitationGen2]) -> str:
    """Return the GitHub Flavored markdown string output for the given sections and citations."""
    contents = [f"{num}. [{section['title']}](#section-{num})" for num, section in enumerate(sections, start=1)]
    contents.append(f"{len(contents) + 1}. [References](#references)")

    def repl(match: re.Match) -> str:
        """Return the match text with the plain citation numbers in the citation group replaced with GitHub Flavored citation numbers."""
        return "".join(f"[^{citation_num}]" for citation_num in match.group(1).split(","))

    sections = [SectionGen2(title=section["title"], text=CITATION_GROUP_PATTERN.sub(repl, section["text"])) for section in sections]

    text = f"# {title}\n\n" + f"{_get_date_string()}\n\n_{_DISCLAIMER}_\n\n" + "## Contents\n" + "\n".join(contents) + "\n\n" + "\n\n".join(f'## <a id="section-{num}"></a>{num}. {s["title"]}\n\n{s["text"]}' for num, s in enumerate(sections, start=1)) + "\n\n" + '## <a id="references"></a>References\n\n' + "\n\n".join([f'[^{c["number"]}]: [{c["title"]}]({c["link"]})' for c in citations])
    return text


def format_html_output(title: str, sections: list[SectionGen2], citations: list[CitationGen2]) -> str:
    """Return the HTML string output for the given sections and citations."""
    citation_map = {str(citation["number"]): citation for citation in citations}

    contents = [f'<li><a href="#section-{num}">{section["title"]}</a></li>' for num, section in enumerate(sections, start=1)]
    contents.append('<li><a href="#references">References</a></li>')

    def repl(match: re.Match) -> str:
        """Return the match text with the plain citation numbers in the citation group replaced with linked citation numbers and separate hover tooltips."""
        return "<sup>[</sup>" + "<sup>,</sup>".join(f'<a href="#citation-{citation_num}" class="citation-link"><sup>{citation_num}</sup></a>' f'<a href="{citation_map[citation_num]["link"]}" class="citation-tooltip" target="_blank">{citation_map[citation_num]["title"]}</a>' for citation_num in match.group(1).split(",")) + "<sup>]</sup>"

    def format_section_text(text: str) -> str:
        """Return the section text wrapped in HTML paragraph tags and replace citation numbers with linked citation numbers."""
        paragraphs = text.split("\n\n")
        wrapped_paragraphs = [f"<p>{CITATION_GROUP_PATTERN.sub(repl, paragraph.strip())}</p>" for paragraph in paragraphs]
        return "\n".join(wrapped_paragraphs)

    sections_html = [f'<h2 id="section-{num}">{num}. {section["title"]}</h2>\n{format_section_text(section["text"])}' for num, section in enumerate(sections, start=1)]

    references_html = [f'<li id="citation-{citation["number"]}"><a href="{citation["link"]}" target="_blank">{citation["title"]}</a></li>' for citation in citations]

    html_output = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&family=Merriweather:wght@400;700&display=swap" rel="stylesheet">
    <style>
        body {{
            font-family: 'Roboto', sans-serif;
            margin: 40px;
            line-height: 1.6;
        }}
        h1, h2 {{
            font-family: 'Merriweather', serif;
            color: #333;
        }}
        h1 {{
            font-size: 2.5em;
            margin-bottom: 0.5em;
        }}
        h2 {{
            font-size: 1.75em;
            margin-top: 2em;
        }}
        p {{
            font-size: 1.1em;
        }}
        ol {{
            padding-left: 20px;
        }}
        a {{
            color: #1a73e8;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}

        .citation-link {{
            color: #1a73e8;
            text-decoration: none;
        }}
        .citation-link:hover + .citation-tooltip {{
            display: inline-block;
        }}
        .citation-tooltip {{
            display: none;
            position: absolute;
            background-color: #f9f9f9;
            border: 1px solid #ccc;
            padding: 5px;
            font-size: 0.9em;
            white-space: nowrap;
            z-index: 10;
            box-shadow: 0px 4px 8px rgba(0, 0, 0, 0.1);
            cursor: pointer;
            color: #1a73e8;
        }}
        .citation-tooltip:hover {{
            display: inline-block;
        }}

        /* Mobile responsiveness */
        @media (max-width: 600px) {{
            body {{
                margin: 20px;
            }}
            h1 {{
                font-size: 2em;
            }}
            h2 {{
                font-size: 1.5em;
            }}
            ol {{
                padding-left: 15px;
            }}
        }}
    </style>
</head>
<body>

<h1>{title}</h1>
<p>{_get_date_string()}</p>
<p><em>{_DISCLAIMER}</em></p>

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


def format_json_output(title: str, sections: list[SectionGen2], citations: list[CitationGen2]) -> str:
    """Return a JSON string output for the given sections and citations."""
    data = {
        "title": title,
        "date": _get_date_string(),
        "disclaimer": _DISCLAIMER,
        "sections": [{"number": num, "title": section["title"], "text": section["text"]} for num, section in enumerate(sections, start=1)],
        "citations": [{"number": citation["number"], "title": citation["title"], "link": citation["link"]} for citation in citations],
    }
    return json.dumps(data, indent=4)


def format_pdf_output(title: str, sections: list[SectionGen2], citations: list[CitationGen2]) -> bytes:
    """Return the PDF bytes output for the given sections and citations."""
    from io import BytesIO
    from reportlab.platypus import Flowable, SimpleDocTemplate, Paragraph, Spacer, PageBreak, ListFlowable, ListItem
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.pdfgen.canvas import Canvas

    class MyDocTemplate(SimpleDocTemplate):
        def __init__(self, *args, **kwargs):
            # kwargs['compress'] = True  # Made no difference to output size.
            super().__init__(*args, **kwargs)
            self._bookmark_id = 0

        def afterFlowable(self, flowable: Flowable) -> None:
            """Add bookmark and outline entries for the flowable if a Paragraph with a style of "Title", "Heading1", or "Heading2"."""
            if isinstance(flowable, Paragraph):
                text = flowable.getPlainText()
                style_name = flowable.style.name
                level = 0 if style_name == "Title" else 1 if style_name in ("Heading1", "Heading2") else None
                if level is not None:
                    key = f"bk_{self._bookmark_id}"
                    self._bookmark_id += 1
                    self.canv.bookmarkPage(key, fit="XYZ", left=0, zoom=None)
                    self.canv.addOutlineEntry(text, key, level=level, closed=False)

        def onPage(self, canvas: Canvas, doc: SimpleDocTemplate) -> None:
            """Add the page number to the footer of each page."""
            page_num = doc.page
            text = f"{page_num}"
            canvas.saveState()
            canvas.setFont("Helvetica", 9)
            canvas.drawCentredString(letter[0] / 2.0, 0.5 * inch, text)  # Page number at bottom center
            canvas.restoreState()

    buffer = BytesIO()
    doc = MyDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TOC", parent=styles["Normal"], fontSize=12, leading=14, leftIndent=20))
    styles.add(ParagraphStyle(name="Center", parent=styles["Normal"], alignment=1))

    story = [Paragraph(title, styles["Title"]), Spacer(1, 12), Paragraph(_get_date_string(), styles["Center"]), Spacer(1, 12), Paragraph(_DISCLAIMER, styles["Italic"]), Spacer(1, 12), Paragraph('<a name="contents"/>Contents', styles["Heading1"]), Spacer(1, 12)]

    toc_items = [ListItem(Paragraph(f'<a href="#section_{num}">{section["title"]}</a>', styles["TOC"])) for num, section in enumerate(sections, start=1)]
    toc_items.append(ListItem(Paragraph('<a href="#references">References</a>', styles["TOC"])))
    story += [ListFlowable(toc_items, bulletType="1"), PageBreak()]

    def replace_citations(text):
        return CITATION_GROUP_PATTERN.sub(lambda match: "<super>" + ",".join([f'<a href="#citation_{num.strip()}">{num.strip()}</a>' for num in match.group(1).split(",")]) + "</super>", text)

    num_sections = len(sections)
    for section_num, section in enumerate(sections, start=1):
        story += [Paragraph(f'{section_num}. <a name="section_{section_num}"/>{section["title"]}', styles["Heading1"]), Spacer(1, 12)]
        paragraphs = replace_citations(section["text"]).split("\n\n")
        num_paragraphs = len(paragraphs)
        for para_num, para_text in enumerate(paragraphs, start=1):
            story.append(Paragraph(para_text, styles["Normal"]))
            if (section_num != num_sections) or (para_num != num_paragraphs):
                story.append(Spacer(1, 12))

    story += [PageBreak(), Paragraph('<a name="references"/>References', styles["Heading1"]), Spacer(1, 12)]

    num_citations = len(citations)
    for citation_num, citation in enumerate(citations, start=1):
        citation_text = f'<a name="citation_{citation["number"]}"/><b>{citation["number"]}.</b> <a href="{citation["link"]}">{citation["title"]}</a><br/><a href="{citation["link"]}">{citation["link"]}</a>'
        story.append(Paragraph(citation_text, styles["Normal"]))
        if citation_num != num_citations:
            story.append(Spacer(1, 12))

    doc.build(story, onFirstPage=doc.onPage, onLaterPages=doc.onPage)
    pdf_value = buffer.getvalue()
    buffer.close()
    return pdf_value


def format_output(*, title: str, sections: list[SectionGen2], citations: list[CitationGen2], output_format: str, **kwargs) -> str:
    """Return the formatted output for the given sections and citations in the specified format."""
    if output_format not in SUPPORTED_OUTPUT_FORMATS:
        raise ValueError(f"Unsupported output format: {output_format!r}")

    formatters = {
        "txt": format_text_output,
        "md": format_markdown_output,
        "gfm.md": format_gfm_output,
        "html": format_html_output,
        "pdf": format_pdf_output,
        "json": format_json_output,
    }
    formatter = formatters[output_format]
    output = formatter(title=title, sections=sections, citations=citations, **kwargs)
    return output
