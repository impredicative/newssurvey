from pathlib import Path

import dotenv

dotenv.load_dotenv()


PACKAGE_PATH: Path = Path(__file__).parent
REPO_PATH: Path = PACKAGE_PATH.parent.parent

GiB = 1024**3
DISKCACHE_ROOT_PATH = REPO_PATH / ".diskcache"
PROMPTS: dict[str, str] = {p.stem: p.read_text().strip() for p in (REPO_PATH / "prompts").glob("*.txt")}
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0"}
