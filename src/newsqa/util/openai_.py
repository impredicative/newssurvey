import datetime
import os
from typing import Optional

import dotenv
import openai

import newsqa.exceptions
from newsqa.util.diskcache_ import get_diskcache

dotenv.load_dotenv()

ChatCompletion = openai.types.chat.chat_completion.ChatCompletion

_COLOR_LIGHT_GRAY = "\033[0;37m"
_COLOR_RESET = "\033[0m"

_DISKCACHE = get_diskcache(__file__, size_gib=10)
MODELS = {  # Ref: https://platform.openai.com/docs/models/
    "text": ["gpt-4o-2024-05-13", "gpt-4-turbo-2024-04-09"][0],
    "embeddings": "text-embedding-3-large",
}


def ensure_openai_key() -> None:
    """Raise `EnvError` if the environment variable OPENAI_API_KEY is unavailable."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise newsqa.exceptions.EnvError("The environment variable OPENAI_API_KEY is unavailable. It can optionally be defined in an .env file.")


@_DISKCACHE.memoize(expire=datetime.timedelta(weeks=52).total_seconds(), tag="get_completion")
def get_completion(prompt: str, model: str) -> ChatCompletion:  # Note: `model` is explicitly specified to allow model-specific caching.
    """Return the completion for the given prompt."""
    client = openai.OpenAI()
    print(f"Requesting completion for prompt of length {len(prompt)}.")
    completion = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}])
    print(f"Received completion for prompt of length {len(prompt)}.")
    # Note: Specifying max_tokens=4096 with gpt-4-turbo-preview did not benefit in increasing output length, and a higher value is disallowed. Ref: https://platform.openai.com/docs/api-reference/chat/create
    return completion


def get_content(prompt: str, *, completion: Optional[ChatCompletion] = None, log: bool = True) -> str:
    """Return the completion content for the given prompt."""
    if not completion:
        completion = get_completion(prompt, model=MODELS["text"])
    content = completion.choices[0].message.content
    content = content.strip()
    assert content
    if log:
        print(f"\n{_COLOR_LIGHT_GRAY}PROMPT:\n{prompt}\nCOMPLETION:\n{content}{_COLOR_RESET}")
    return content
