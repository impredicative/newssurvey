# @_DISKCACHE.memoize(expire=datetime.timedelta(weeks=52).total_seconds(), tag="get_dual_prompt_completion")
# def get_dual_prompt_completion(system_prompt: str, user_prompt: str, model: str) -> ChatCompletion:  # Note: `model` is explicitly specified to allow model-specific caching.
#     """Return the completion for the given prompt."""
#     assert model in MODELS["text"].values(), model
#     assert model in MAX_OUTPUT_TOKENS, model
#     client = openai.OpenAI()
#     print(f"Requesting completion for system prompt of length {len(system_prompt):,} and user prompt of length {len(user_prompt):,} using model {model}.")
#     time_start = time.monotonic()
#     messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
#     completion = client.chat.completions.create(model=model, messages=messages, max_tokens=MAX_OUTPUT_TOKENS[model])  # Ref: https://platform.openai.com/docs/api-reference/chat/create
#     time_used = time.monotonic() - time_start
#     print(f"Received completion for system prompt of length {len(system_prompt):,} and user prompt of length {len(user_prompt):,} using model {model} in {time_used:.1f}s.")
#     return completion
