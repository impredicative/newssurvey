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


class Section(TypedDict):
    title: Required[str]
    text: Required[str]
