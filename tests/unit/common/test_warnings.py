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

import re
import warnings

import pytest

from neo4j._warnings import preview
from neo4j.warnings import PreviewWarning


MSG = "This is a preview feature... testing, testing!"


class BaseWithInit:
    _base_new_with: type
    _base_init_with: type

    def __new__(cls, *args, **kwargs):
        obj = super().__new__(cls, *args, **kwargs)
        obj._base_new_with = type(obj)
        return obj

    def __init__(self):
        self._base_init_with = type(self)
        super().__init__()

    @classmethod
    def factory(cls):
        return cls()


@preview(MSG)
class FooWithInit(BaseWithInit):
    _foo_new_with: type
    _foo_init_with: type

    def __new__(cls, *args, **kwargs):
        obj = super().__new__(cls, *args, **kwargs)
        obj._foo_new_with = type(obj)
        return obj

    def __init__(self):
        self._foo_init_with = type(self)
        super().__init__()

    @classmethod
    def factory_fwd(cls):
        return super().factory()

    @classmethod
    def factory(cls):
        return cls()


def test_preview_decorator_class() -> None:
    with pytest.warns(PreviewWarning, match=f"^{re.escape(MSG)}"):
        foo = FooWithInit()

    assert isinstance(foo, FooWithInit)
    assert foo._base_new_with is FooWithInit
    assert foo._base_init_with is FooWithInit
    assert foo._foo_new_with is FooWithInit
    assert foo._foo_init_with is FooWithInit


@pytest.mark.parametrize("factory_method", ("factory", "factory_fwd"))
def test_preview_decorator_class_factory(factory_method: str) -> None:
    factory = getattr(FooWithInit, factory_method)
    with pytest.warns(PreviewWarning, match=f"^{re.escape(MSG)}"):
        foo = factory()

    assert isinstance(foo, FooWithInit)
    assert foo._base_new_with is FooWithInit
    assert foo._base_init_with is FooWithInit
    assert foo._foo_new_with is FooWithInit
    assert foo._foo_init_with is FooWithInit


def test_preview_decorator_class_without_warning() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")

        foo = FooWithInit._without_warning()  # type: ignore[attr-defined]
    assert isinstance(foo, FooWithInit)


@pytest.mark.parametrize("factory_method", ("factory", "factory_fwd"))
def test_preview_decorator_class_factory_without_warning(
    factory_method: str,
) -> None:
    factory = getattr(
        FooWithInit._without_warning,  # type: ignore[attr-defined]
        factory_method,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")

        foo = factory()
    assert isinstance(foo, FooWithInit)


class BaseWithoutInit:
    @classmethod
    def factory(cls):
        return cls()


@preview(MSG)
class FooWithoutInit(BaseWithoutInit):
    @classmethod
    def factory_fwd(cls):
        return super().factory()

    @classmethod
    def factory(cls):
        return cls()


def test_preview_decorator_class_without_init() -> None:
    with pytest.warns(PreviewWarning, match=f"^{re.escape(MSG)}"):
        foo = FooWithoutInit()

    assert isinstance(foo, FooWithoutInit)


@pytest.mark.parametrize("factory_method", ("factory", "factory_fwd"))
def test_preview_decorator_class_factory_without_init(
    factory_method: str,
) -> None:
    factory = getattr(FooWithoutInit, factory_method)
    with pytest.warns(PreviewWarning, match=f"^{re.escape(MSG)}"):
        foo = factory()

    assert isinstance(foo, FooWithoutInit)


def test_preview_decorator_class_without_init_without_warning() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")

        foo = FooWithoutInit._without_warning()  # type: ignore[attr-defined]
    assert isinstance(foo, FooWithoutInit)


@pytest.mark.parametrize("factory_method", ("factory", "factory_fwd"))
def test_preview_decorator_class_factory_without_init_without_warning(
    factory_method: str,
) -> None:
    factory = getattr(
        FooWithoutInit._without_warning,  # type: ignore[attr-defined]
        factory_method,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")

        foo = factory()
    assert isinstance(foo, FooWithoutInit)
