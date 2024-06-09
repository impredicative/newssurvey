from typing import NotRequired, Required, TypedDict


class SearchResult(TypedDict):
    title: Required[str]
    link: Required[str]
    description: NotRequired[str]