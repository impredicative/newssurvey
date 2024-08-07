import datetime
import os
import time
from typing import Literal, Optional

import dotenv
import openai

import newsqa.exceptions
from newsqa.util.diskcache_ import get_diskcache

dotenv.load_dotenv()

ChatCompletion = openai.types.chat.chat_completion.ChatCompletion
CreateEmbeddingResponse = openai.types.create_embedding_response.CreateEmbeddingResponse

# _COLOR_LIGHT_GRAY = "\033[0;37m"
# _COLOR_LIGHT_BLUE = "\033[1;34m"
_COLOR_GRAY = "\033[0;90m"
_COLOR_RESET = "\033[0m"

_DISKCACHE = get_diskcache(__file__, size_gib=10)
MODELS = {  # Ref: https://platform.openai.com/docs/models/
    "text": {
        "large": ["gpt-4o-2024-05-13", "gpt-4o-2024-08-06"][-1],
        "small": "gpt-4o-mini-2024-07-18",
    },
    "embeddings": {
        "large": "text-embedding-3-large",  # Output vector length is 3072.
        "small": "text-embedding-3-small",  # Output vector length is 1536.
    },
}
TextModelSizeType = Literal["large", "small"]
EmbeddingModelSizeType = Literal["large", "small"]

MAX_OUTPUT_TOKENS = {
    "gpt-4o-2024-08-06": 16_384,
    "gpt-4o-2024-05-13": 4096,
    "gpt-4o-mini-2024-07-18": 16_384,
}


def ensure_openai_key() -> None:
    """Raise `EnvError` if the environment variable OPENAI_API_KEY is unavailable."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise newsqa.exceptions.EnvError("The environment variable OPENAI_API_KEY is unavailable. It can optionally be defined in an .env file.")


@_DISKCACHE.memoize(expire=datetime.timedelta(weeks=52).total_seconds(), tag="get_completion")
def get_completion(prompt: str, model: str) -> ChatCompletion:  # Note: `model` is explicitly specified to allow model-specific caching.
    """Return the completion for the given prompt."""
    assert model in MODELS["text"].values(), model
    assert model in MAX_OUTPUT_TOKENS, model
    client = openai.OpenAI()
    print(f"Requesting completion for prompt of length {len(prompt):,} using model {model}.")
    time_start = time.monotonic()
    completion = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}], max_tokens=MAX_OUTPUT_TOKENS[model])
    time_used = time.monotonic() - time_start
    print(f"Received completion for prompt of length {len(prompt):,} using model {model} in {time_used:.1f}s.")
    return completion


def get_content(prompt: str, *, model_size: str, completion: Optional[ChatCompletion] = None, log: bool = False, read_cache: bool = True) -> str:  # Note: `model_size` is explicitly required to avoid error with an unintended model size.
    """Return the completion content for the given prompt."""
    assert model_size in MODELS["text"], model_size
    model = MODELS["text"][model_size]
    if not completion:
        if read_cache:
            cache_key = get_completion.__cache_key__(prompt, model=model)
            cache_key_existence_status = cache_key in _DISKCACHE
            if cache_key_existence_status:
                print(f"Found cache key for prompt of length {len(prompt):,} using model {model}.")
            else:
                print(f"Cache key for prompt of length {len(prompt):,} using model {model} was not found.")
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
        print(f"\n{_COLOR_GRAY}PROMPT:\n{prompt}\nCOMPLETION:\n{content}{_COLOR_RESET}")
        # print(prefix_lines(f"PROMPT\n{prompt}\nCOMPLETION\n{content}"))
    return content


@_DISKCACHE.memoize(tag="get_embedding")
def get_embedding(text: str, model: str) -> CreateEmbeddingResponse:  # Note: `model` is explicitly specified to allow model-specific caching.
    """Return the embedding response for the given text."""
    assert model in MODELS["embeddings"].values(), model
    client = openai.OpenAI()
    print(f"Requesting embedding for text of length {len(text):,} using model {model}.")
    time_start = time.monotonic()
    response = client.embeddings.create(input=text, model=model)
    time_used = time.monotonic() - time_start
    print(f"Received embedding for text of length {len(text):,} using model {model} in {time_used:.1f}s.")
    return response


def get_vector(text: str, *, model_size: str, embedding: Optional[CreateEmbeddingResponse] = None, log: bool = False) -> list[float]:  # Note: `model_size` is explicitly required to avoid error with an unintended model size.
    """Return the embedding vector for the given text."""
    assert model_size in MODELS["embeddings"], model_size
    model = MODELS["embeddings"][model_size]
    if not embedding:
        embedding = get_embedding(text, model=model)
    vector = embedding.data[0].embedding
    assert vector
    if log:
        print(f"\n{_COLOR_GRAY}TEXT:\n{text}\nEMBEDDING: {vector}{_COLOR_RESET}")
        # print(prefix_lines(f"TEXT\n{text}\nEMBEDDING: {embedding}"))
    return vector
