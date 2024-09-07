from functools import cache
from pathlib import Path

import diskcache

from newsqa.config import GiB, PACKAGE_PATH


DISKCACHE_ROOT_PATH = PACKAGE_PATH / ".diskcache"


@cache
def get_diskcache(file_path: str, *, size_gib: int = 1) -> diskcache.FanoutCache:
    """Return a diskcache object for the given file path.

    `file_path` should typically be `__file__`.
    """
    path = Path(file_path)  # Ex: /home/user/projects/newsqa/src/newsqa/sources/medicalxpress/article.py
    assert path.is_relative_to(PACKAGE_PATH), path
    path = path.relative_to(PACKAGE_PATH)  # Ex: sources/medicalxpress/article.py
    path = path.with_suffix("")  # Ex: sources/medicalxpress/article
    path = DISKCACHE_ROOT_PATH / path  # Ex: /home/user/projects/newsqa/src/newsqa/.diskcache/sources/medicalxpress/article
    print(f"Using diskcache path: {path}")
    return diskcache.FanoutCache(directory=str(path), timeout=10, size_limit=size_gib * GiB)
