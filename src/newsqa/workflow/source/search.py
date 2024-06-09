from types import ModuleType

from newsqa.exceptions import SourceInsufficiencyError
from newsqa.workflow.llm.filter_search_results import filter_search_results
from newsqa.types import SearchResult
from newsqa.util.dict import dict_str


def _get_filtered_search_results_for_search_term(user_query: str, source_module: ModuleType, search_term: str) -> list[SearchResult]:
    results = {}

    def insert_paged_results(**kwargs) -> None:
        assert "query" not in kwargs, kwargs
        assert "page_num" not in kwargs, kwargs
        page_num = 1
        while True:
            page_results = source_module.get_search_results(query=search_term, page_num=page_num, **kwargs)
            if not page_results:
                break
            filtered_page_results = filter_search_results(user_query=user_query, source_module=source_module, results=page_results)
            print(f"Limited {len(page_results)} original results to {len(filtered_page_results)} filtered results for page {page_num} of search term {search_term!r} with arguments: {dict_str(kwargs)}")
            if not filtered_page_results:
                break
            for result in filtered_page_results:
                result_link = result["link"]
                if result_link not in results:
                    results[result_link] = result
            page_num += 1
        print(f"Obtained {len(results)} filtered results for search term {search_term!r}.")

    source_module.run_searches(insert_paged_results)

    results = list(results.values())
    return results


def get_filtered_search_results(user_query: str, source_module: ModuleType, search_terms: list[str]) -> list[SearchResult]:
    """Get filtered search results.

    Results are filtered for relevance by the LLM.

    Returns:
        list[searchResult]: A list of dictionaries where each dictionary represents an article with its title, link, and description.

    `SourceInsufficiencyError` is raised if no filtered results are available.
    """
    results = {}
    num_terms = len(search_terms)
    for term_num, term in enumerate(search_terms, start=1):
        results_for_term = _get_filtered_search_results_for_search_term(user_query=user_query, source_module=source_module, search_term=term)
        for result in results_for_term:
            result_link = result["link"]
            if result_link not in results:
                results[result_link] = result
        print(f"Accumulated a running total of {len(results)} filtered results for {term_num}/{num_terms} search terms.")

    if not results:
        raise SourceInsufficiencyError("No filtered search results exist for query.")

    results = list(results.values())
    assert len(results) == len(set(r["link"] for r in results))  # Ensures no duplicates.
    return results
