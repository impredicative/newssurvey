from importlib.metadata import version
from newssurvey.util.openai_ import get_completion, MODELS
from newssurvey.util.tiktoken_ import count_tokens

print("Packages: " + " ".join(f"{package}={version(package)}" for package in ("openai", "tiktoken")))

prompt = """
Ignore this Lorem Ipsum text. Just respond with "OK".

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nulla facilisi. Maecenas ac sapien sit amet eros ultricies consectetur. Integer tempor odio eu libero sodales, a venenatis ex efficitur. Suspendisse potenti. Nam tristique justo at augue pharetra, at dapibus libero consectetur. Curabitur sodales, nulla sed tincidunt pharetra, ipsum erat porttitor turpis, ac scelerisque orci lorem in lacus.

Pellentesque in odio vehicula, mollis velit id, tempus est. Aliquam erat volutpat. Nam rhoncus, arcu quis auctor gravida, tortor justo accumsan dui, sit amet ultrices libero elit eget neque. Nulla nec sollicitudin risus. Nam imperdiet diam vel elit gravida, non egestas nunc aliquet. Ut ultricies risus ac nisi molestie, ac feugiat lorem vulputate. Fusce eget diam ut turpis laoreet scelerisque non in eros.

Phasellus sollicitudin tristique nisi, nec sagittis elit varius at. Suspendisse suscipit malesuada erat, in porttitor nulla blandit a. Fusce vel turpis sit amet turpis maximus vehicula. Praesent sit amet gravida eros. Morbi et velit eu nisl lobortis finibus ac in sem. Sed fringilla ultricies felis, vel cursus odio laoreet nec. Nulla facilisi. Vivamus a magna ex.

Nam consequat facilisis felis, sed viverra justo sollicitudin sit amet. Fusce tincidunt tempor mi, ac pharetra ipsum varius eget. Integer vulputate libero a lectus scelerisque venenatis. Cras dignissim vestibulum ligula non scelerisque. Ut malesuada leo id nunc faucibus, nec posuere lectus sollicitudin. Nullam semper lorem quis tincidunt fermentum. Donec pharetra venenatis sapien eget fermentum.

Curabitur ultricies turpis vel nunc sagittis, at efficitur sapien volutpat. Nullam sit amet magna sit amet justo facilisis auctor. Quisque aliquet tortor vitae turpis scelerisque fermentum. Aenean vitae tortor ut velit fermentum dapibus vel nec est. Suspendisse rutrum gravida justo id viverra. Ut at lacinia nunc. Aenean fringilla felis ut justo ultricies, ac consequat nisl efficitur.
"""

for model_size, model in MODELS["text"].items():
    completion = get_completion(prompt, model)
    openai_token_count = completion.usage.prompt_tokens
    tiktoken_token_count = count_tokens(prompt, model=model)
    diff_token_count = openai_token_count - tiktoken_token_count
    diff_token_pct = diff_token_count / openai_token_count
    print(f"{model_size=!s} {model=!s} {openai_token_count=} {tiktoken_token_count=} {diff_token_count=} {diff_token_pct=:.0%}")

"""Output:
Packages: openai=1.45.0 tiktoken=0.7.0
model_size=deprecated model=gpt-4-0125-preview openai_token_count=576 tiktoken_token_count=569 diff_token_count=7 diff_token_pct=1%
model_size=large model=gpt-4o-2024-08-06 openai_token_count=452 tiktoken_token_count=445 diff_token_count=7 diff_token_pct=2%
model_size=large_previous model=gpt-4o-2024-05-13 openai_token_count=452 tiktoken_token_count=445 diff_token_count=7 diff_token_pct=2%
model_size=small model=gpt-4o-mini-2024-07-18 openai_token_count=452 tiktoken_token_count=445 diff_token_count=7 diff_token_pct=2%
"""
