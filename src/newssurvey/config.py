import importlib.util
from importlib.machinery import ModuleSpec
from pathlib import Path

import dotenv

dotenv.load_dotenv()


PACKAGE_PATH: Path = Path(__file__).parent
PACKAGE_NAME: str = PACKAGE_PATH.name

GiB = 1024**3
NEWS_SOURCE_NAMESPACE: str = f"{PACKAGE_NAME}.sources"
NEWS_SOURCES: dict[str, ModuleSpec] = {s.name: importlib.util.find_spec(f"{NEWS_SOURCE_NAMESPACE}.{s.name}") for s in (PACKAGE_PATH / "sources").iterdir()}  # Note: A direct import is not practicable here due to a circular import.
NUM_SECTIONS_DEFAULT: int = 100
NUM_SECTIONS_MIN: int = 10  # Applies only to the `max_sections` argument. Does not apply to LLM output.
NUM_SECTIONS_MAX: int = 100
assert NUM_SECTIONS_MIN <= NUM_SECTIONS_DEFAULT <= NUM_SECTIONS_MAX
PROMPTS: dict[str, str] = {p.stem: p.read_text().strip() for p in (PACKAGE_PATH / "prompts").glob("*.txt")}
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"}
