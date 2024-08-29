from typing import NotRequired, Required, TypedDict


class SearchResult(TypedDict):
    title: Required[str]
    link: Required[str]
    description: NotRequired[str]


class SearchArticle(SearchResult):
    text: Required[str]


class AnalyzedArticleGen1(TypedDict):
    article: Required[SearchArticle]
    sections: NotRequired[list[str]]


class RatedSection(TypedDict):
    section: Required[str]
    rating: Required[int]


class AnalyzedArticleGen2(TypedDict):
    article: Required[SearchArticle]
    sections: Required[list[RatedSection]]
