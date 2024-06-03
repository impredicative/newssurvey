from types import ModuleType

from newsqa.workflow.llm.filter_search_results import filter_search_results
from newsqa.workflow.user.source import get_source_module_name
from newsqa.util.sys_ import print_warning


def _get_filtered_search_results_for_search_term(user_query: str, source_module: ModuleType, search_term: str) -> list[dict]:
    results = {}

    def insert_paged_results(**kwargs) -> None:
        page_num = 1
        while True:
            page_results = source_module.get_search_results(query=search_term, page_num=page_num, **kwargs)
            if not page_results:
                break
            page_results = filter_search_results(user_query=user_query, source_module=source_module, results=page_results)
            if not page_results:
                break
            for result in page_results:
                result_link = result["link"]
                if result_link not in results:
                    results[result_link] = result
            page_num += 1

    source = get_source_module_name(source_module)
    match source:
        case "medicalxpress":
            for sort_by in ("relevancy", "date"):
                for headlines in (False, True):
                    insert_paged_results(sort_by=sort_by, headlines=headlines)
        case _:
            print_warning(f"Customized acquisition of search results is not implemented for the {source} source, and so the default acquisition will be used.")
            insert_paged_results()

    results = list(results.values())
    return results


def get_filtered_search_results(user_query: str, source_module: ModuleType, search_terms: list[str]) -> list[dict]:
    """Get filtered search results.

    Results are filtered for relevance by the LLM.

    Returns:
        list[dict]: A list of dictionaries where each dictionary represents an article with its title, link, and description.
    """
    results = {}
    for term in search_terms:
        results_for_term = _get_filtered_search_results_for_search_term(user_query=user_query, source_module=source_module, search_term=term)
        for result in results_for_term:
            result_link = result["link"]
            if result_link not in results:
                results[result_link] = result
    results = list(results.values())
    return results
