from pathlib import Path

import diskcache

PACKAGE_PATH: Path = Path(__file__).parent
REPO_PATH: Path = PACKAGE_PATH.parent.parent

GiB = 1024**3
DISKCACHE_PATH = REPO_PATH / ".diskcache"
DISKCACHE_SIZE_LIMIT = 10 * GiB
DISKCACHE = diskcache.FanoutCache(directory=str(DISKCACHE_PATH), timeout=1, size_limit=DISKCACHE_SIZE_LIMIT)
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0"}
