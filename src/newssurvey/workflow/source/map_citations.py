import re

from newssurvey.config import CITATION_OPEN_CHAR, CITATION_CLOSE_CHAR, CITATION_GROUP_PATTERN
from newssurvey.types import CitationGen2, SectionGen1, SectionGen2


def map_citations(sections: list[SectionGen1]) -> tuple[list[SectionGen2], list[CitationGen2]]:
    """Return transformed and mapped citations used in the individual sections to a globally consistent list of citations."""
    link_citation_map: dict[str, CitationGen2] = {}

    num_sections = len(sections)
    sections_old = sections
    del sections
    sections_new = []

    for section_num, section_old in enumerate(sections_old, start=1):
        citation_nums_old = [citation_num for citation_group in CITATION_GROUP_PATTERN.findall(section_old["text"]) for citation_num in map(int, citation_group.split(","))]
        citation_nums_old = list(dict.fromkeys(citation_nums_old))  # Remove duplicates while preserving order. Order preservation is important, otherwise the new citation numbers will be out of order.
        citation_nums_new = []
        for citation_num_old in citation_nums_old:
            assert citation_num_old > 0
            citation_old = section_old["citations"][citation_num_old - 1]
            citation_link = citation_old["link"]
            if citation_link in link_citation_map:
                citation_num_new = link_citation_map[citation_link]["number"]
                citation_map_type = "existing"
            else:
                citation_num_new = len(link_citation_map) + 1
                link_citation_map[citation_link] = CitationGen2(number=citation_num_new, title=citation_old["title"], link=citation_link)
                citation_map_type = "new"
            print(f'Mapped citation {citation_num_old} in section {section_num} {section_old["title"]!r} to {citation_map_type} citation {citation_num_new}.')
            assert citation_num_new > 0
            citation_nums_new.append(citation_num_new)

        assert len(citation_nums_old) == len(citation_nums_new)
        citation_nums_map = dict(zip(citation_nums_old, citation_nums_new))

        def repl(match: re.Match) -> str:
            """Replace the old citation numbers in the citation group with their corresponding new citation numbers."""
            # Note: To output map of old→new, add prefix: str(int(citation_num)) + '→' +
            return CITATION_OPEN_CHAR + ",".join(str(citation_nums_map[int(citation_num)]) for citation_num in match.group(1).split(",")) + CITATION_CLOSE_CHAR

        new_text = CITATION_GROUP_PATTERN.sub(repl, section_old["text"])
        section_new = SectionGen2(title=section_old["title"], text=new_text)
        sections_new.append(section_new)
        print(f'Mapped {len(citation_nums_old)} citations for section {section_num}/{num_sections} {section_old["title"]!r}.')

    assert len(sections_new) == len(sections_old)
    citations = list(link_citation_map.values())
    assert all(citation["number"] == num for num, citation in enumerate(citations, start=1))

    return sections_new, citations
