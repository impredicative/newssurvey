import datetime
import os
from typing import Optional

import dotenv
import openai

import newsqa.exceptions
from newsqa.util.diskcache_ import get_diskcache

dotenv.load_dotenv()

ChatCompletion = openai.types.chat.chat_completion.ChatCompletion

_DISKCACHE = get_diskcache(__file__)
MODELS = {  # Ref: https://platform.openai.com/docs/models/
    "text": "gpt-4o-2024-05-13",
    "embeddings": "text-embedding-3-large",
}


def ensure_openai_key() -> None:
    """Raise `EnvError` if the environment variable OPENAI_API_KEY is unavailable."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise newsqa.exceptions.EnvError("The environment variable OPENAI_API_KEY is unavailable. It can optionally be defined in an .env file.")


@_DISKCACHE.memoize(expire=datetime.timedelta(weeks=52).total_seconds(), tag="get_completion")
def get_completion(prompt: str) -> ChatCompletion:
    """Return the completion for the given prompt."""
    client = openai.OpenAI()
    print(f"Requesting completion for prompt of length {len(prompt)}.")
    completion = client.chat.completions.create(model=MODELS["text"], messages=[{"role": "user", "content": prompt}])
    print(f"Received completion for prompt of length {len(prompt)}.")
    # Note: Specifying max_tokens=4096 with gpt-4-turbo-preview did not benefit in increasing output length, and a higher value is disallowed. Ref: https://platform.openai.com/docs/api-reference/chat/create
    return completion


def get_content(prompt: str, *, completion: Optional[ChatCompletion] = None) -> str:
    """Return the completion content for the given prompt."""
    if not completion:
        completion = get_completion(prompt)
    content = completion.choices[0].message.content
    content = content.strip()
    assert content
    print(f'\nPROMPT:\n{prompt}\nCOMPLETION:\n{content}')
    return content
