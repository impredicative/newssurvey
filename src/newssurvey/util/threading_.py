import threading
import time
from typing import Optional, Self


class CooldownLock:
    """A lock mechanism that also enforces a cooldown period between releases and subsequent acquisitions.

    This is useful in scenarios where it's also necessary to limit the frequency of lock acquisition,
    such as for managing access to a shared resource in a way that prevents excessively rapid consecutive uses.

    Ref: https://stackoverflow.com/a/78591650/
    """

    def __init__(self, cooldown: float = 1, name: Optional[str] = None):
        """Initialize with a specified cooldown period.

        Args:
            cooldown: The cooldown period in seconds after releasing the lock before it can be acquired again.
            name: Optional name of lock used in log messages.
        """
        self._cooldown_period = cooldown
        self._name = f"{name} lock" if name else "lock"

        self._earliest_use_time = 0
        self._lock = threading.Lock()

    def acquire(self) -> bool:
        self._lock.acquire()
        wait_time = self._earliest_use_time - time.monotonic()
        if wait_time > 0:
            print(f"Sleeping for {wait_time:.1f}s to acquire {self._name}.")
            time.sleep(wait_time)
        return True

    def release(self):
        if self.locked():
            self._earliest_use_time = time.monotonic() + self._cooldown_period
        self._lock.release()

    def locked(self) -> bool:
        return self._lock.locked()

    def __enter__(self) -> Self:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
