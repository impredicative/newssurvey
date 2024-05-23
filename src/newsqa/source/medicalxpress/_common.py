from pathlib import Path

import diskcache

from newsqa.config import DISKCACHE_ROOT_PATH, GiB


DISKCACHE = diskcache.FanoutCache(directory=str(DISKCACHE_ROOT_PATH / Path(__file__).parent.name), timeout=1, size_limit=10 * GiB)
