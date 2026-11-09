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

import abc
import math
import random
import string
import sys

import freezegun
import pytest

from neo4j import _typing as t
from neo4j._sync.property_encryption.caching import (
    _BijectiveCache,
    _Cache,
    KeyAliasCache,
    KeyCache,
)


T_V = t.TypeVar("T_V", bound=t.Hashable)


class _CacheFactory(t.Generic[T_V], abc.ABC):
    @abc.abstractmethod
    def __call__(self, /, *, ttl: float, size: int) -> _Cache[T_V]: ...
    @abc.abstractmethod
    def next_value(self) -> T_V: ...


class KeyCacheFactory(_CacheFactory[bytes]):
    def __init__(self) -> None:
        self._next_value = 1
        self._rigged_value = "RIGGED"

    def __call__(self, /, *, ttl: float, size: int) -> KeyCache:
        return KeyCache(ttl, size)

    def next_value(self) -> bytes:
        if random.random() < 0.5:
            # Doesn't have to be a bijective mapping
            return self._rigged_value.encode("ascii")
        value = self._next_value
        self._next_value += 1
        pool = string.ascii_letters + string.digits
        pre = random.choices(pool, k=4)
        post = random.choices(pool, k=4)
        return f"{pre}-{value:04d}-{post}".encode("ascii")


@pytest.fixture
def key_cache_factory() -> KeyCacheFactory:
    return KeyCacheFactory()


if t.TYPE_CHECKING:
    T_key_cache_factory: t.TypeAlias = KeyCacheFactory


class KeyAliasCacheFactory(_CacheFactory[str]):
    def __init__(self) -> None:
        self._next_value = 1

    def __call__(self, /, *, ttl: float, size: int) -> KeyAliasCache:
        return KeyAliasCache(ttl, size)

    def next_value(self) -> str:
        value = self._next_value
        self._next_value += 1
        pool = string.ascii_letters + string.digits
        pre = random.choices(pool, k=4)
        post = random.choices(pool, k=4)
        return f"{pre}-{value:04d}-{post}"


@pytest.fixture
def alias_cache_factory() -> KeyAliasCacheFactory:
    return KeyAliasCacheFactory()


if t.TYPE_CHECKING:
    T_alias_cache_factory: t.TypeAlias = KeyAliasCacheFactory


@pytest.fixture(params=[True, False], ids=["key_cache", "alias_cache"])
def cache_factory(request) -> KeyCacheFactory | KeyAliasCacheFactory:
    if request.param:
        return KeyCacheFactory()
    else:
        return KeyAliasCacheFactory()


if t.TYPE_CHECKING:
    T_cache_factory: t.TypeAlias = _CacheFactory[T_V]


def _make_keys(n: int) -> list[str]:
    keys: dict[str, None] = {}
    key_len = math.ceil(math.log(n, len(string.ascii_letters))) + 7
    while len(keys) < n:
        key = "".join(random.choices(string.ascii_letters, k=key_len))
        if key not in keys:
            keys[key] = None
    return list(keys)


def _set_values(
    cache: _Cache[T_V], keys: t.Sequence[str], factory: _CacheFactory[T_V]
) -> list[T_V]:
    values = []
    for key in keys:
        value = factory.next_value()
        values.append(value)
        cache.set(key, value)
    return values


def _assert_cache_contains(
    cache: _Cache[T_V],
    expected_keys: t.Sequence[str],
    expected_values: t.Sequence[T_V] | None,
) -> None:
    if expected_values is not None and len(expected_keys) != len(
        expected_values
    ):
        raise ValueError("expected_keys must not contain duplicates")
    for i, key in enumerate(expected_keys):
        value = cache.get(key)
        if expected_values is not None:
            assert value is expected_values[i]


def _assert_cache_does_not_contain(
    cache: _Cache[T_V], absent_keys: t.Sequence[str]
) -> None:
    for key in absent_keys:
        assert cache.get(key) is None


def _assert_cache_internal_keys(
    cache: _Cache[T_V] | _BijectiveCache[T_V], expected_keys: t.Sequence[str]
) -> None:
    assert sorted(cache._cache) == sorted(expected_keys)
    if isinstance(cache, _BijectiveCache):
        assert cache._inv_cache is not None
        assert sorted(cache._inv_cache.values()) == sorted(expected_keys)


@freezegun.freeze_time()
def test_stores_entry(cache_factory: T_cache_factory[T_V]) -> None:
    key = "foo"
    cache = cache_factory(ttl=0.001, size=1)

    (value,) = _set_values(cache, (key,), cache_factory)

    assert cache.get(key) is value


@freezegun.freeze_time()
def test_key_miss(cache_factory: T_cache_factory[T_V]) -> None:
    key = "foo"
    cache = cache_factory(ttl=0.001, size=1)

    _assert_cache_does_not_contain(cache, ("bar",))
    assert cache.get("bar") is None

    _set_values(cache, (key,), cache_factory)

    _assert_cache_does_not_contain(cache, ("bar",))


@freezegun.freeze_time()
def test_stores_values(cache_factory: T_cache_factory[T_V]) -> None:
    keys = _make_keys(10)
    keys = list(keys)
    cache = cache_factory(ttl=0.001, size=len(keys))
    values = _set_values(cache, keys, cache_factory)

    _assert_cache_contains(cache, keys, values)
    _assert_cache_contains(
        cache, tuple(reversed(keys)), tuple(reversed(values))
    )


@freezegun.freeze_time()
def test_overflow_drops_least_recently_used_entry(
    cache_factory: T_cache_factory[T_V],
) -> None:
    cache = cache_factory(ttl=0.001, size=3)
    keys = _make_keys(4)

    _set_values(cache, keys[:3], cache_factory)
    cache.get(keys[0])  # keys[1] is now the most recently used

    _assert_cache_does_not_contain(cache, keys[1])
    _assert_cache_contains(cache, (keys[0], *keys[2:]), None)


def test_get_respects_ttl(cache_factory: T_cache_factory[T_V]) -> None:
    ttl = 1
    tick = ttl + 0.001
    with freezegun.freeze_time() as frozen_time:
        cache = cache_factory(ttl=ttl, size=10)
        keys = _make_keys(2)

        values = _set_values(cache, keys, cache_factory)
        _assert_cache_contains(cache, keys, values)

        frozen_time.tick(tick)

        # Public access does not return expired entry.
        # The cache may or may not actually delete the entry
        _assert_cache_does_not_contain(cache, keys[:1])
        # However, the cache must not alter any other entries
        assert cache._cache.get(keys[1]) is not None


def test_set_clears_expired_entries(
    cache_factory: T_cache_factory[T_V],
) -> None:
    ttl = 1
    tick = ttl / 2 + 0.001
    with freezegun.freeze_time() as frozen_time:
        cache = cache_factory(ttl=ttl, size=10)
        keys1 = _make_keys(2)
        _set_values(cache, keys1, cache_factory)
        frozen_time.tick(tick)
        keys2 = _make_keys(1)
        _set_values(cache, keys2, cache_factory)

        frozen_time.tick(tick)

        keys3 = _make_keys(1)
        _set_values(cache, keys3, cache_factory)

        _assert_cache_internal_keys(cache, (*keys2, *keys3))


@pytest.mark.parametrize("size", [0, 1, 2**64 - 1])
@pytest.mark.parametrize(
    "ttl", [sys.float_info.min, sys.float_info.max, float("inf")]
)
def test_is_disabled(
    cache_factory: T_cache_factory[T_V], ttl: float, size: int
) -> None:
    cache = cache_factory(ttl=ttl, size=size)
    assert cache.is_disabled() is (size == 0)


@pytest.mark.parametrize(
    "ttl",
    [
        0,
        -1,
        float("NaN"),
        float("-inf"),
        -sys.float_info.min,
        -sys.float_info.max,
        -0,
    ],
)
def test_invalid_ttl_raises(
    cache_factory: T_cache_factory[T_V], ttl: float
) -> None:
    with pytest.raises(ValueError, match=r"\bttl\b"):
        cache_factory(ttl=ttl, size=1)


@pytest.mark.parametrize("size", [-1])
def test_invalid_size_raises(
    cache_factory: T_cache_factory[T_V], size: int
) -> None:
    with pytest.raises(ValueError, match=r"\bsize\b"):
        cache_factory(ttl=1, size=size)


def test_forget(cache_factory: T_cache_factory[T_V]) -> None:
    cache = cache_factory(ttl=0.001, size=10)
    keys = _make_keys(3)
    values = _set_values(cache, keys, cache_factory)

    cache.forget(keys[1])

    left_keys, left_values = keys[:1] + keys[2:], values[:1] + values[2:]
    _assert_cache_contains(cache, left_keys, left_values)
    _assert_cache_does_not_contain(cache, (keys[1],))


def test_forget_missing_key(cache_factory: T_cache_factory[T_V]) -> None:
    cache = cache_factory(ttl=0.001, size=10)
    keys = _make_keys(4)
    values = _set_values(cache, keys[:-1], cache_factory)

    cache.forget(keys[-1])

    _assert_cache_contains(cache, keys[:-1], values)


def test_forget_value(alias_cache_factory: KeyAliasCacheFactory) -> None:
    cache = alias_cache_factory(ttl=0.001, size=10)
    keys = _make_keys(3)
    values = _set_values(cache, keys, alias_cache_factory)

    cache.forget_value(values[1])

    left_keys, left_values = keys[:1] + keys[2:], values[:1] + values[2:]
    _assert_cache_contains(cache, left_keys, left_values)
    _assert_cache_does_not_contain(cache, (keys[1],))


def test_forget_value_missing_value(
    alias_cache_factory: KeyAliasCacheFactory,
) -> None:
    cache = alias_cache_factory(ttl=0.001, size=10)
    keys = _make_keys(4)
    values = _set_values(cache, keys[:-1], alias_cache_factory)

    cache.forget(values[-1])

    _assert_cache_contains(cache, keys[:-1], values)
