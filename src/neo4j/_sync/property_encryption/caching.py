# Copyright (c) "Neo4j"
# Neo4j Sweden AB [https://neo4j.com]
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from __future__ import annotations

import math
from time import monotonic

from ... import _typing as t
from ..._async_compat.concurrency import CooperativeLock


T = t.TypeVar("T")


__all__ = [
    "KeyAliasCache",
    "KeyCache",
]


class _Cache(t.Generic[T]):
    _ttl: float
    _size: int
    _cache: dict[str, _Entry[T]]
    _lock: CooperativeLock

    def __init__(self, ttl: float, size: int) -> None:
        if math.isnan(ttl) or ttl <= 0:
            raise ValueError(
                f"{type(self)} ttl must be a number > 0, got {ttl}"
            )
        if size < 0:
            raise ValueError(
                f"{type(self)} size must be a number >= 0, got {size}"
            )
        self._ttl = ttl
        self._size = size
        self._cache = {}
        self._lock = CooperativeLock()

    def set(self, key: str, value: T) -> None:
        if self.is_disabled():
            return
        with self._lock:
            self._clear_expired_locked()
            if len(self._cache) >= self._size:
                self._evict_lru_locked()
            self._cache[key] = _Entry(value, monotonic())

    def get(self, key: str) -> T | None:
        if self.is_disabled():
            return None
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if entry.age() > self._ttl:
                del self._cache[key]
                return None
            self._cache[key] = _Entry(entry.id, monotonic())
            return entry.id

    def forget(self, key: str) -> None:
        if self.is_disabled():
            return
        with self._lock:
            self._cache.pop(key, None)

    def is_disabled(self) -> bool:
        return self._size == 0

    def _clear_expired_locked(self) -> None:
        expired = tuple(
            key
            for key, entry in self._cache.items()
            if entry.age() > self._ttl
        )
        for key in expired:
            del self._cache[key]

    def _evict_lru_locked(self) -> None:
        oldest_key = min(
            self._cache, key=lambda key: self._cache[key].last_used
        )
        del self._cache[oldest_key]


if t.TYPE_CHECKING:

    class _Entry(t.NamedTuple, t.Generic[T]):
        id: T
        last_used: float

        def age(self) -> float: ...
else:
    # Python 3.10 does not support generic `NamedTuple`s
    class _Entry(t.NamedTuple):
        id: T
        last_used: float

        def age(self) -> float:
            return monotonic() - self.last_used


class KeyAliasCache(_Cache[str]):
    pass


class KeyCache(_Cache[bytes]):
    pass
