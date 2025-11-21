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

# inspired by:
# https://stackoverflow.com/questions/23831510/abstract-attribute-not-property

from __future__ import annotations

from abc import (
    ABC as _ABC,
    ABCMeta as _ABCMeta,
    abstractmethod,
)

from . import _typing as t


__all__ = ["ABC", "abstractattribute", "abstractmethod"]


_R = t.TypeVar("_R")


class _AbstractAttribute(t.Any):
    __is_abstract_attribute__ = True

    def __call__(self, _: t.Callable[[t.Any], _R]) -> _R:
        return t.cast(_R, abstractattribute)


abstractattribute = _AbstractAttribute()


# def abstract_attribute(_: t.Callable[[], _R] | None = None) -> _R:
#     return t.cast(_R, _abstract_attribute)


class ABCMeta(_ABCMeta):
    """"""

    def __call__(cls, *args, **kwargs):
        obj = super().__call__(*args, **kwargs)
        for name in dir(obj):
            attr = getattr(obj, name)
            if attr is abstractattribute:
                raise NotImplementedError(
                    "Can't instantiate abstract class"
                    f"{cls.__name__} "
                    f"with abstract attribute {name!r}"
                )
        return obj


class ABC(_ABC, metaclass=ABCMeta):
    __slots__ = ()
