from typing import Callable, Optional

import tiktoken

from newssurvey.util.openai_ import MAX_INPUT_TOKENS, MAX_OUTPUT_TOKENS

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


def fit_items_to_input_token_limit(items: list, *, model: str, formatter: Callable[[list], str] = "\n".join, approach: str = "binary") -> tuple[int, str]:
    """Return the number of items used and the text that fits the input token limit for the given items and model.

    The items are formatted to a string using the given formatter function.
    """
    # Tests:
    # _=fit_items_to_input_token_limit([string.printable]*10_000, model="gpt-4o-2024-08-06", approach='binary') -> Using 3,487/10,000 items of text for model gpt-4o-2024-08-06 and encoding o200k_base, with 111,583/111,606 tokens.
    # _=fit_items_to_input_token_limit(''.join(random.Random(0).choices(string.printable, k=1_000_000)).split('\n'), model="gpt-4o-2024-08-06", approach='binary') -> Using 1,480/9,929 items of text for model gpt-4o-2024-08-06 and encoding o200k_base, with 111,410/111,606 tokens.
    encoding = get_encoding(model).name
    text = formatter(items)
    usage = calc_input_token_usage(text, model=model)
    num_items = len(items)
    if is_input_token_usage_allowable(text, model=model, usage=usage):
        print(f"Using all {num_items:,} items of text for model {model} and encoding {encoding}, with {usage['num_tokens']:,}/{usage['max_tokens']:,} tokens.")
        return num_items, text

    iteration = 0
    match approach:
        case "binary":
            # Binary search
            lo, hi = 1, num_items
            while lo < hi:
                iteration += 1
                mid = (lo + hi + 1) // 2
                mid_text = formatter(items[:mid])
                usage = calc_input_token_usage(mid_text, model=model)
                num_items_used = mid
                if is_input_token_usage_allowable(mid_text, model=model, usage=usage):
                    lo = mid
                else:
                    hi = mid - 1
                print(f"Tried {num_items_used:,}/{num_items:,} items of text for model {model} in iteration {iteration:,} using {usage['num_tokens']:,}/{usage['max_tokens']:,} tokens.")
            num_items_used = lo
        case "rate":
            # Rate-based search
            num_items_used = num_items
            items_to_excess_tokens: dict[int, int] = {}
            while True:
                if (num_items_used in items_to_excess_tokens) and (items_to_excess_tokens[num_items_used] <= 0):
                    num_items_used = max({p: e for p, e in items_to_excess_tokens.items() if e < 0}, key=items_to_excess_tokens.__getitem__)
                    candidate_num_items_used = num_items_used + 1
                    if (candidate_num_items_used in items_to_excess_tokens) and (items_to_excess_tokens[candidate_num_items_used] > 0):
                        break
                    num_items_used = candidate_num_items_used
                iteration += 1
                usage = calc_input_token_usage(formatter(items[:num_items_used]), model=model)
                items_to_excess_tokens[num_items_used] = usage["num_tokens"] - usage["max_tokens"]
                rate = usage["num_tokens"] / usage["max_tokens"]
                print(f"Tried {num_items_used:,}/{num_items:,} items of text for model {model} in iteration {iteration:,} using {usage['num_tokens']:,}/{usage['max_tokens']:,} tokens.")
                num_items_used = num_items_used / rate
                num_items_used = int(num_items_used)  # Note: Always using `round` or `math.ceil` instead of `int` was observed to lead to an infinite loop.
                num_items_used = min(num_items, num_items_used)
        case _:
            raise ValueError(f"Unsupported approach {approach!r}.")

    encoding = get_encoding(model).name
    text_used = formatter(items[:num_items_used])
    usage = calc_input_token_usage(text_used, model=model)
    print(f"Using {num_items_used:,}/{num_items:,} items of text for model {model} and encoding {encoding}, with {usage['num_tokens']:,}/{usage['max_tokens']:,} tokens.")
    return num_items_used, text_used
