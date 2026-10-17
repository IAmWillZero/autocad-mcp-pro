"""Cache TTL minima con invalidacion por clave y por prefijo."""

from __future__ import annotations

import time
from typing import Any


class TTLCache:
    """Cache TTL con desalojo FIFO cuando se supera ``maxsize``."""

    def __init__(self, ttl: float, maxsize: int = 128) -> None:
        self.ttl = ttl
        self.maxsize = maxsize
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.time() > expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        if len(self._store) >= self.maxsize and key not in self._store:
            self._store.pop(next(iter(self._store)))
        self._store[key] = (time.time() + self.ttl, value)

    def invalidate(self, key: str) -> None:
        """Elimina una clave concreta."""
        self._store.pop(key, None)

    def invalidate_prefix(self, prefix: str) -> None:
        """Elimina todas las claves que empiezan por ``prefix``."""
        for key in [k for k in self._store if k.startswith(prefix)]:
            self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()
