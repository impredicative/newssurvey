import concurrent.futures
import os
import time
from typing import Literal, Optional

import openai

from newssurvey.config import CACHE_EXPIRATION_BY_TAG, CACHE_SIZES_GiB
import newssurvey.exceptions
from newssurvey.util.dict import dict_str
from newssurvey.util.diskcache_ import get_diskcache
from newssurvey.util.dotenv_ import load_dotenv
from newssurvey.util.sys_ import print_warning

load_dotenv()

ChatCompletion = openai.types.chat.chat_completion.ChatCompletion
CreateEmbeddingResponse = openai.types.create_embedding_response.CreateEmbeddingResponse

# _COLOR_LIGHT_GRAY = "\033[0;37m"
# _COLOR_LIGHT_BLUE = "\033[1;34m"
_COLOR_GRAY = "\033[0;90m"
_COLOR_RESET = "\033[0m"

_DISKCACHE = get_diskcache(__file__, size_gib=CACHE_SIZES_GiB["medium"])
MODELS = {  # Ref: https://platform.openai.com/docs/models/
    "text": {
        "deprecated": "gpt-4-0125-preview",  # Note: Can require more prompt tuning for successful use. gpt-4-turbo-2024-04-09 is worse.
        "large": "gpt-4o-2024-08-06",
        "large_previous": "gpt-4o-2024-05-13",  # For token measurement purposes.
        "small": "gpt-4o-mini-2024-07-18",
    },
    "embedding": {
        "large": "text-embedding-3-large",  # Output vector length is 3072.
        "small": "text-embedding-3-small",  # Output vector length is 1536.
    },
}
TextModelSizeType = Literal["large", "small"]
EmbeddingModelSizeType = Literal["large", "small"]

MAX_INPUT_TOKENS = {
    "gpt-4-0125-preview": 128_000,
    "gpt-4o-2024-08-06": 128_000,
    "gpt-4o-2024-05-13": 128_000,
    "gpt-4o-mini-2024-07-18": 128_000,
}
MAX_OUTPUT_TOKENS = {
    "gpt-4-0125-preview": 4096,
    "gpt-4o-2024-08-06": 16_384,
    "gpt-4o-2024-05-13": 4096,
    "gpt-4o-mini-2024-07-18": 16_384,
}
MAX_WORKERS = 16


def ensure_openai_key() -> None:
    """Raise `EnvError` if the environment variable OPENAI_API_KEY is unavailable."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise newssurvey.exceptions.EnvError("The environment variable OPENAI_API_KEY is unavailable. It can optionally be defined in an .env file.")


@_DISKCACHE.memoize(expire=CACHE_EXPIRATION_BY_TAG["get_completion"], tag="get_completion")
def get_completion(prompt: str, model: str, **kwargs) -> ChatCompletion:  # Note: `model` is explicitly specified to allow model-specific caching.
    """Return the completion for the given prompt and model.

    `kwargs` are forwarded to the create call.
    ."""
    assert model in MODELS["text"].values(), model
    assert model in MAX_OUTPUT_TOKENS, model

    assert model not in kwargs
    kwargs.setdefault("max_tokens", MAX_OUTPUT_TOKENS[model])

    client = openai.OpenAI()
    print(f"Requesting completion for prompt of length {len(prompt):,} using model {model} with keyword arguments: {dict_str(kwargs)}")
    time_start = time.monotonic()
    messages = [{"role": "user", "content": prompt}]

    max_attempts = 3
    for num_attempt in range(1, max_attempts + 1):
        try:
            completion = client.chat.completions.create(model=model, messages=messages, **kwargs)  # Ref: https://platform.openai.com/docs/api-reference/chat/create
        except (openai.InternalServerError, openai.PermissionDeniedError) as exc:
            if num_attempt < max_attempts:
                print_warning(f"Completion for prompt of length {len(prompt):,} using model {model} failed in attempt {num_attempt} of {max_attempts}: {exc}")
                time.sleep(5 * num_attempt)
                continue
            else:
                assert num_attempt == max_attempts
                raise
        else:
            break

    time_used = time.monotonic() - time_start
    print(f"Received completion for prompt of length {len(prompt):,} using model {model} in {time_used:.1f}s.")
    return completion


def get_content(prompt: str, *, model_size: TextModelSizeType, completion: Optional[ChatCompletion] = None, log: bool = False, read_cache: bool = True, **kwargs) -> str:  # Note: `model_size` is explicitly required to avoid error with an unintended model size.
    """Return the completion content for the given prompt.

    `kwargs` are forwarded to the create call.
    """
    assert model_size in MODELS["text"], model_size
    model = MODELS["text"][model_size]
    if not completion:
        cache_lookup_time_start = time.monotonic()
        cache_key = get_completion.__cache_key__(prompt, model=model, **kwargs)
        if read_cache:
            cache_key_existence_status = cache_key in _DISKCACHE
            cache_lookup_time_used = time.monotonic() - cache_lookup_time_start
            if cache_key_existence_status:
                print(f"Found cache key for prompt of length {len(prompt):,} using model {model} in {cache_lookup_time_used:.1f}s.")
            else:
                print(f"Cache key for prompt of length {len(prompt):,} using model {model} was not found in {cache_lookup_time_used:.1f}s.")
        else:
            cache_key_deletion_status = _DISKCACHE.delete(cache_key)
            cache_cleanup_time_used = time.monotonic() - cache_lookup_time_start
            if cache_key_deletion_status:
                print(f"Deleted cache key for prompt of length {len(prompt):,} using model {model} in {cache_cleanup_time_used:.1f}s.")
            else:
                print(f"Cache key for prompt of length {len(prompt):,} using model {model} was not found in {cache_cleanup_time_used:.1f}s.")
        completion = get_completion(prompt, model=model, **kwargs)
    content = completion.choices[0].message.content
    content = content.strip()
    assert content
    if log:
        print(f"\n{_COLOR_GRAY}PROMPT:\n{prompt}\nCOMPLETION:\n{content}{_COLOR_RESET}")
        # print(prefix_lines(f"PROMPT\n{prompt}\nCOMPLETION\n{content}"))
    return content


@_DISKCACHE.memoize(expire=CACHE_EXPIRATION_BY_TAG["get_embedding"], tag="get_embedding")
def get_embedding(text: str, model: str) -> CreateEmbeddingResponse:  # Note: `model` is explicitly specified to allow model-specific caching.
    """Return the embedding response for the given text."""
    assert model in MODELS["embedding"].values(), model
    client = openai.OpenAI()
    text_log = text[:100] + "..." if (len(text) > 100) else text
    print(f"Requesting embedding for text {text_log!r} of length {len(text):,} using model {model}.")
    # time_start = time.monotonic()
    response = client.embeddings.create(input=text, model=model)
    # time_used = time.monotonic() - time_start
    # print(f"Received embedding for text {text_log!r} of length {len(text):,} using model {model} in {time_used:.1f}s.")
    return response


def get_vector(text: str, *, model_size: str, embedding: Optional[CreateEmbeddingResponse] = None, log: bool = False) -> list[float]:  # Note: `model_size` is explicitly required to avoid error with an unintended model size.
    """Return the embedding vector for the given text."""
    assert model_size in MODELS["embedding"], model_size
    model = MODELS["embedding"][model_size]
    if not embedding:
        embedding = get_embedding(text, model=model)
    vector = embedding.data[0].embedding
    assert vector
    if log:
        print(f"\n{_COLOR_GRAY}TEXT:\n{text}\nEMBEDDING: {vector}{_COLOR_RESET}")
        # print(prefix_lines(f"TEXT\n{text}\nEMBEDDING: {embedding}"))
    return vector


def get_vectors_concurrently(texts: list[str], *, model_size: str, log: bool = False) -> dict[str, list[float]]:  # Note: `model_size` is explicitly required to avoid error with an unintended model size.
    """Return the embedding vectors for the given texts."""
    assert model_size in MODELS["embedding"], model_size
    fn_get_vector = lambda text: (text, get_vector(text, model_size=model_size, log=log))
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        return dict(executor.map(fn_get_vector, texts))
