"""Short-lived in-memory store: uploads are never written to disk."""
from __future__ import annotations

import threading
import time


class SessionStore:
    def __init__(self, ttl_seconds: int, max_items: int = 50):
        self.ttl, self.max_items = ttl_seconds, max_items
        self._items: dict[str, tuple[float, dict]] = {}
        self._lock = threading.Lock()

    def _purge(self) -> None:
        now = time.monotonic()
        for key in [k for k, (ts, _) in self._items.items() if now - ts > self.ttl]:
            del self._items[key]
        while len(self._items) >= self.max_items:
            del self._items[min(self._items, key=lambda k: self._items[k][0])]

    def put(self, key: str, value: dict) -> None:
        with self._lock:
            self._purge()
            self._items[key] = (time.monotonic(), value)

    def get(self, key: str) -> dict | None:
        with self._lock:
            item = self._items.get(key)
            if item is None or time.monotonic() - item[0] > self.ttl:
                return None
            self._items[key] = (time.monotonic(), item[1])
            return item[1]
