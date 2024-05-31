import importlib
from importlib.machinery import ModuleSpec
from pathlib import Path

import dotenv

dotenv.load_dotenv()


PACKAGE_PATH: Path = Path(__file__).parent
PACKAGE_NAME: str = PACKAGE_PATH.name

GiB = 1024**3
NEWS_SOURCES: dict[str, ModuleSpec] = {s.name: importlib.util.find_spec(f"{PACKAGE_NAME}.sources.{s.name}") for s in (PACKAGE_PATH / "sources").iterdir()}  # Note: A direct import is not practicable here due to a circular import.
PROMPTS: dict[str, str] = {p.stem: p.read_text().strip() for p in (PACKAGE_PATH / "prompts").glob("*.txt")}
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0"}
