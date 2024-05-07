import os
from typing import Optional

import dotenv
import openai

import newsqa.exceptions

dotenv.load_dotenv()

ChatCompletion = openai.types.chat.chat_completion.ChatCompletion
OpenAI = openai.OpenAI

MAX_TTS_INPUT_LEN = 4096
MODELS = {
    "text": "gpt-4-turbo-2024-04-09",
}


def ensure_openai_key() -> None:
    """Raise `EnvError` if the environment variable OPENAI_API_KEY is unavailable."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise newsqa.exceptions.EnvError("The environment variable OPENAI_API_KEY is unavailable. It can optionally be defined in an .env file.")


def get_openai_client() -> OpenAI:
    """Return the OpenAI client."""
    return OpenAI()


def get_completion(prompt: str, *, client: Optional[OpenAI] = None) -> ChatCompletion:
    """Return the completion for the given prompt."""
    if not client:
        client = get_openai_client()
    # print(f"Requesting completion for prompt of length {len(prompt)}.")
    completion = client.chat.completions.create(model=MODELS["text"], messages=[{"role": "user", "content": prompt}])
    # Note: Specifying max_tokens=4096 with gpt-4-turbo-preview did not benefit in increasing output length, and a higher value is disallowed. Ref: https://platform.openai.com/docs/api-reference/chat/create
    return completion


def get_content(prompt: str, *, client: Optional[OpenAI] = None, completion: Optional[ChatCompletion] = None) -> str:
    """Return the content for the given prompt."""
    if not completion:
        completion = get_completion(prompt, client=client)
    content = completion.choices[0].message.content
    content = content.strip()
    assert content
    return content
