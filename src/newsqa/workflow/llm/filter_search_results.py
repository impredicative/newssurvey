from types import ModuleType

from newsqa.config import PROMPTS
from newsqa.util.openai_ import get_content


def filter_search_results(user_query: str, source_module: ModuleType, results: list[dict]) -> list[dict]:
    assert user_query
    assert results
    prompt_data = {
        "user_query": user_query,
        "source_site_name": source_module.SOURCE_SITE_NAME,
        "source_type": source_module.SOURCE_TYPE,
        "search_results": "\n\n".join(f'{num}. {result['title']}\n{result.get('description', '')}'.rstrip() for num, result in enumerate(results, start=1)),
    }
    prompt = PROMPTS["0. common"].format(**prompt_data) + "\n\n" + PROMPTS["2. filter_search_results"].format(**prompt_data)
    _response = get_content(prompt)
    return []
