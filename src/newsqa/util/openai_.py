import datetime
import os
import time
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
    "text": {
        "large": "gpt-4o-2024-05-13",
        "small": "gpt-4o-mini-2024-07-18",
    },
    "embeddings": "text-embedding-3-large",
}


def ensure_openai_key() -> None:
    """Raise `EnvError` if the environment variable OPENAI_API_KEY is unavailable."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise newsqa.exceptions.EnvError("The environment variable OPENAI_API_KEY is unavailable. It can optionally be defined in an .env file.")


@_DISKCACHE.memoize(expire=datetime.timedelta(weeks=52).total_seconds(), tag="get_completion")
def get_completion(prompt: str, model: str) -> ChatCompletion:  # Note: `model` is explicitly specified to allow model-specific caching.
    """Return the completion for the given prompt."""
    assert model in MODELS["text"].values(), model
    client = openai.OpenAI()
    print(f"Requesting completion for prompt of length {len(prompt):,} using model {model}.")
    time_start = time.monotonic()
    completion = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}])
    time_used = time.monotonic() - time_start
    print(f"Received completion for prompt of length {len(prompt):,} using model {model} in {time_used:.1f}s.")
    # Note: Specifying max_tokens=4096 with gpt-4-turbo-preview did not benefit in increasing output length, and a higher value is disallowed. Ref: https://platform.openai.com/docs/api-reference/chat/create
    return completion


def get_content(prompt: str, *, model_size: str, completion: Optional[ChatCompletion] = None, log: bool = False, read_cache: bool = True) -> str:  # Note: `model_size` is explicitly required to avoid error with an unintended model size.
    """Return the completion content for the given prompt."""
    assert model_size in MODELS["text"], model_size
    model = MODELS["text"][model_size]
    if not completion:
        if read_cache:
            completion = get_completion(prompt, model=model)
        else:
            cache_key = get_completion.__cache_key__(prompt, model=model)
            cache_key_deletion_status = _DISKCACHE.delete(cache_key)
            if cache_key_deletion_status:
                print(f"Deleted cache key for prompt of length {len(prompt):,} using model {model}.")
            else:
                print(f"Cache key for prompt of length {len(prompt):,} using model {model} was not found.")
            completion = get_completion(prompt, model=model)
    content = completion.choices[0].message.content
    content = content.strip()
    assert content
    if log:
        print(f"\n{_COLOR_LIGHT_GRAY}PROMPT:\n{prompt}\nCOMPLETION:\n{content}{_COLOR_RESET}")
    return content
