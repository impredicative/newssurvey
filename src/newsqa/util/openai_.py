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
    print(f"Requesting completion for prompt of length {len(prompt)} using model {model}.")
    completion = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}])
    print(f"Received completion for prompt of length {len(prompt)} using model {model}.")
    # Note: Specifying max_tokens=4096 with gpt-4-turbo-preview did not benefit in increasing output length, and a higher value is disallowed. Ref: https://platform.openai.com/docs/api-reference/chat/create
    return completion


def get_content(prompt: str, *, model_size: str, completion: Optional[ChatCompletion] = None, log: bool = False) -> str:  # Note: `model_size` is explicitly required to avoid error with an unintended model size.
    """Return the completion content for the given prompt."""
    assert model_size in MODELS["text"], model_size
    model = MODELS["text"][model_size]
    if not completion:
        completion = get_completion(prompt, model=model)
    content = completion.choices[0].message.content
    content = content.strip()
    assert content
    if log:
        print(f"\n{_COLOR_LIGHT_GRAY}PROMPT:\n{prompt}\nCOMPLETION:\n{content}{_COLOR_RESET}")
    return content
