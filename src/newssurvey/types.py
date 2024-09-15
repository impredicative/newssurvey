import dataclasses
from typing import NotRequired, Required, TypedDict


class SearchResult(TypedDict):
    title: Required[str]
    link: Required[str]
    description: NotRequired[str]


class SearchArticle(SearchResult):
    text: Required[str]


class AnalyzedSectionGen1(TypedDict):
    section: Required[str]
    rating: Required[int]


class AnalyzedArticleGen1(TypedDict):
    article: Required[SearchArticle]
    sections: Required[list[AnalyzedSectionGen1]]


class AnalyzedSectionGen2(TypedDict):
    section: Required[str]
    rating: Required[int]
    text: Required[str]


class AnalyzedArticleGen2(TypedDict):
    article: Required[SearchArticle]
    sections: Required[list[AnalyzedSectionGen2]]


class CitationGen1(TypedDict):
    title: Required[str]
    link: Required[str]


class SectionGen1(TypedDict):
    title: Required[str]
    text: Required[str]
    citations: Required[list[CitationGen1]]


class CitationGen2(TypedDict):
    number: Required[int]
    title: Required[str]
    link: Required[str]


class SectionGen2(TypedDict):
    title: Required[str]
    text: Required[str]


@dataclasses.dataclass(frozen=True, kw_only=True)
class Response:
    format: str
    title: str  # Included to facilitate writing the response to file with the title in its name.
    response: str | bytes
