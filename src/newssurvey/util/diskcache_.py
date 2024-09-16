from functools import cache
from pathlib import Path

import diskcache

from newssurvey.config import CACHE_SIZES_GiB, GiB, PACKAGE_PATH

_SHARDS = 16  # Note: A heuristic for this value is to use the number of OpenAI workers. Changing this value can invalidate the cache.
DISKCACHE_ROOT_PATH = PACKAGE_PATH / ".diskcache"


@cache
def get_diskcache(file_path: str, *, size_gib: int = CACHE_SIZES_GiB["small"]) -> diskcache.FanoutCache:
    """Return a diskcache object for the given file path.

    `file_path` should typically be `__file__`.
    """
    path = Path(file_path)  # Ex: /workspaces/newssurvey/src/newssurvey/sources/medicalxpress/article.py
    assert path.is_relative_to(PACKAGE_PATH), path
    path = path.relative_to(PACKAGE_PATH)  # Ex: sources/medicalxpress/article.py
    path = path.with_suffix("")  # Ex: sources/medicalxpress/article
    path = DISKCACHE_ROOT_PATH / path  # Ex: /workspaces/newssurvey/src/newssurvey/.diskcache/sources/medicalxpress/article
    print(f"Using diskcache path: {path}")
    return diskcache.FanoutCache(directory=str(path), shards=_SHARDS, timeout=10, size_limit=size_gib * GiB)
