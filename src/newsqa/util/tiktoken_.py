from typing import Optional

import tiktoken

from newsqa.util.openai_ import MAX_INPUT_TOKENS, MAX_OUTPUT_TOKENS

HEADER_TOKENS_PER_MESSAGE: int = 4  # Estimate as per https://platform.openai.com/docs/advanced-usage/managing-tokens.
FOOTER_TOKENS: int = 2  # Estimate as per https://platform.openai.com/docs/advanced-usage/managing-tokens.


def get_encoding(model: str) -> tiktoken.Encoding:
    """Return the encoding for the given model."""
    return tiktoken.encoding_for_model(model)


def count_tokens(text: str, *, model: str) -> int:
    """Return the number of tokens used by the given text and model."""
    encoding = get_encoding(model)
    encoded = encoding.encode(text)
    return len(encoded)


def calc_input_token_usage(text: str, *, model: str) -> dict[str, int]:
    """Return the input token usage for the given text and model.

    The returned dictionary has the following keys:
    * `num_tokens`: Number of tokens used by input.
    * `max_tokens`: Maximum number of input tokens allowed, leaving maximum room for output tokens.
    """
    num_tokens = count_tokens(text, model=model)
    assert MAX_INPUT_TOKENS[model] >= MAX_OUTPUT_TOKENS[model]

    max_tokens = max(0, MAX_INPUT_TOKENS[model] - MAX_OUTPUT_TOKENS[model] - (HEADER_TOKENS_PER_MESSAGE * 2) - FOOTER_TOKENS)
    return {"num_tokens": num_tokens, "max_tokens": max_tokens}


def is_input_token_usage_allowable(text: str, *, model: str, usage: Optional[dict] = None) -> bool:
    """Return true if the input token usage is allowable for the given text and model."""
    if usage is None:
        usage = calc_input_token_usage(text, model=model)
    return usage["num_tokens"] <= usage["max_tokens"]


def fit_input_parts_to_token_limit(parts: list[str], *, model: str, sep: str = "\n", approach: str = "rate") -> str:
    """Return a text that fits the input token limit for the given parts and model.

    The parts are joined by the given separator.
    """
    # Tests:
    # _=fit_input_parts_to_token_limit([string.printable]*10_000, model="gpt-4o-2024-08-06", approach='binary') -> Using 3,487/10,000 parts of text for model gpt-4o-2024-08-06 and encoding o200k_base, with 111,583/111,606 tokens.
    # _=fit_input_parts_to_token_limit(''.join(random.Random(0).choices(string.printable, k=1_000_000)).split('\n'), model="gpt-4o-2024-08-06", approach='binary') -> Using 1,480/9,929 parts of text for model gpt-4o-2024-08-06 and encoding o200k_base, with 111,410/111,606 tokens.
    encoding = get_encoding(model).name
    text = sep.join(parts)
    usage = calc_input_token_usage(text, model=model)
    num_parts = len(parts)
    if is_input_token_usage_allowable(text, model=model, usage=usage):
        print(f"Using all {num_parts:,} parts of text for model {model} and encoding {encoding}, with {usage['num_tokens']:,}/{usage['max_tokens']:,} tokens.")
        return text

    iteration = 0
    match approach:
        case "binary":
            # Binary search
            lo, hi = 1, num_parts
            while lo < hi:
                iteration += 1
                mid = (lo + hi + 1) // 2
                mid_text = sep.join(parts[:mid])
                usage = calc_input_token_usage(mid_text, model=model)
                num_parts_used = mid
                if is_input_token_usage_allowable(mid_text, model=model, usage=usage):
                    lo = mid
                else:
                    hi = mid - 1
                print(f"Tried {num_parts_used:,}/{num_parts:,} parts of text for model {model} in iteration {iteration:,} using {usage['num_tokens']:,}/{usage['max_tokens']:,} tokens.")
            num_parts_used = lo
        case "rate":
            # Rate-based search
            num_parts_used = num_parts
            parts_to_rates: dict[int, float] = {}
            while True:
                if (num_parts_used in parts_to_rates) and (parts_to_rates[num_parts_used] <= 1):
                    break
                iteration += 1
                usage = calc_input_token_usage(sep.join(parts[:num_parts_used]), model=model)
                rate = usage["num_tokens"] / usage["max_tokens"]
                parts_to_rates[num_parts_used] = rate
                print(f"Tried {num_parts_used:,}/{num_parts:,} parts of text for model {model} in iteration {iteration:,} using {usage['num_tokens']:,}/{usage['max_tokens']:,} tokens.")
                num_parts_used = num_parts_used / rate
                num_parts_used = int(num_parts_used)  # Note: Using `round` instead of `int` was observed to lead to an infinite loop.
                num_parts_used = min(num_parts, num_parts_used)
        case _:
            raise ValueError(f"Unsupported approach {approach!r}.")

    encoding = get_encoding(model).name
    text_used = sep.join(parts[:num_parts_used])
    usage = calc_input_token_usage(text_used, model=model)
    print(f"Using {num_parts_used:,}/{num_parts:,} parts of text for model {model} and encoding {encoding}, with {usage['num_tokens']:,}/{usage['max_tokens']:,} tokens.")
    return text_used
