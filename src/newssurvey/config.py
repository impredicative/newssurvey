import datetime
import importlib.util
from importlib.machinery import ModuleSpec
from pathlib import Path
import re

from newssurvey.util.dotenv_ import load_dotenv

load_dotenv()

CWD: Path = Path.cwd()
PACKAGE_PATH: Path = Path(__file__).parent
PACKAGE_NAME: str = PACKAGE_PATH.name

CACHE_EXPIRATION_BY_TAG: dict[str, int] = {tag: datetime.timedelta(weeks=weeks).total_seconds() for tag, weeks in {"get_search_response": 1, "get_article_response": 52, "get_completion": 52, "get_embedding": 52}.items()}
CACHE_SIZES_GiB: dict[str, int] = {"small": 1, "medium": 5, "large": 10}
CITATION_OPEN_CHAR, CITATION_CLOSE_CHAR = "〚〛"  # Defined in the corresponding LLM prompt.
CITATION_GROUP_PATTERN = re.compile(CITATION_OPEN_CHAR + r"(.*?)" + CITATION_CLOSE_CHAR)
GiB = 1024**3
NEWS_SOURCE_NAMESPACE: str = f"{PACKAGE_NAME}.sources"
NEWS_SOURCES: dict[str, ModuleSpec] = {s.name: importlib.util.find_spec(f"{NEWS_SOURCE_NAMESPACE}.{s.name}") for s in (PACKAGE_PATH / "sources").iterdir()}  # Note: A direct import is not practicable here due to a circular import.
NUM_SECTIONS_DEFAULT: int = 100
NUM_SECTIONS_MIN: int = 5  # Applies only to the `max_sections` argument. Does not apply to LLM output.
NUM_SECTIONS_MAX: int = 100
assert NUM_SECTIONS_MIN <= NUM_SECTIONS_DEFAULT <= NUM_SECTIONS_MAX
OUTPUT_FORMAT_DEFAULT: str = "txt"
PROMPTS: dict[str, str] = {p.stem: p.read_text().strip() for p in (PACKAGE_PATH / "prompts").glob("*.txt")}
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"}
