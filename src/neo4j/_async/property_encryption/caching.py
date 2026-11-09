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
from ..._async_compat.concurrency import AsyncCooperativeLock


T = t.TypeVar("T", bound=t.Hashable)


__all__ = [
    "AsyncKeyAliasCache",
    "AsyncKeyCache",
]


class _Entry(t.NamedTuple, t.Generic[T]):
    id: T
    last_used: float

    def age(self) -> float:
        return monotonic() - self.last_used


class _Cache(t.Generic[T]):
    _ttl: float
    _size: int
    _cache: dict[str, _Entry[T]]
    _inv_cache: dict[T, str] | None
    _lock: AsyncCooperativeLock

    def __init__(self, ttl: float, size: int, bijective: bool = False) -> None:
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
        self._inv_cache = {} if bijective else None
        self._lock = AsyncCooperativeLock()

    def set(self, key: str, value: T) -> None:
        if self.is_disabled():
            return
        with self._lock:
            self._clear_expired_locked()
            if len(self._cache) >= self._size:
                self._evict_lru_locked()
            self._cache[key] = _Entry(value, monotonic())
            self._set_bijective_locked(key, value)

    def _set_bijective_locked(self, key: str, value: T) -> None:
        if self._inv_cache is None:
            return
        old_key = self._inv_cache.get(value)
        if old_key is not None and old_key != key:
            del self._cache[old_key]
        self._inv_cache[value] = key

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
            value = self._cache.pop(key, None)
            self._forget_bijective_locked(value)

    def _forget_bijective_locked(self, value: _Entry[T] | None) -> None:
        if self._inv_cache is None or value is None:
            return
        del self._inv_cache[value.id]

    def is_disabled(self) -> bool:
        return self._size == 0

    def _clear_expired_locked(self) -> None:
        expired = tuple(
            (key, entry)
            for (key, entry) in self._cache.items()
            if entry.age() > self._ttl
        )
        for key, entry in expired:
            del self._cache[key]
            if self._inv_cache is not None:
                del self._inv_cache[entry.id]

    def _evict_lru_locked(self) -> None:
        oldest_key = min(
            self._cache.items(), key=lambda item: item[1].last_used
        )
        del self._cache[oldest_key[0]]
        if self._inv_cache is not None:
            del self._inv_cache[oldest_key[1].id]


class _BijectiveCache(_Cache[T]):
    def __init__(self, ttl: float, size: int) -> None:
        super().__init__(ttl, size, bijective=True)

    def forget_value(self, value: T) -> None:
        if self.is_disabled():
            return
        with self._lock:
            assert self._inv_cache is not None
            key = self._inv_cache.get(value)
            if key is not None:
                del self._cache[key]
                del self._inv_cache[value]


class AsyncKeyAliasCache(_BijectiveCache[str]):
    """Caches key alias -> key id."""


class AsyncKeyCache(_Cache[bytes]):
    """Caches key id -> decapsulated key."""

    def __init__(self, ttl: float, size: int) -> None:
        super().__init__(ttl, size)
