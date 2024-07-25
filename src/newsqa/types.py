from typing import NotRequired, Required, TypedDict


class SearchResult(TypedDict):
    title: Required[str]
    link: Required[str]
    description: NotRequired[str]


class SearchArticle(SearchResult):
    text: Required[str]


class AnalyzedArticle(TypedDict):
    article: Required[SearchArticle]
    sections: NotRequired[list[str]]
