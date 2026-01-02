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

import typing as t

import mock
import pytest

from neo4j._optional_deps import (
    np,
    pa,
    pd,
)


if t.TYPE_CHECKING:
    T_Callable = t.TypeVar("T_Callable", bound=t.Callable)


class _OptionalDepsMock(mock.MagicMock):
    __optional_dep_name: str = "optional dependency"

    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        name = kwargs.get("name")
        super().__init__(*args, **kwargs)
        if isinstance(name, str):
            self.__optional_dep_name = name

    def _get_child_mock(self, **kwargs) -> t.Self:
        child = _OptionalDepsMock(**kwargs)
        child.__optional_dep_name = self.__optional_dep_name
        return child


if np is None:
    np = _OptionalDepsMock(name="numpy")
if pd is None:
    pd = _OptionalDepsMock(name="pandas")
if pa is None:
    pa = _OptionalDepsMock(name="pyarrow")

__all__ = [
    "mark_skip_without_optional_dependency",
    "np",
    "pa",
    "pd",
]

_DEP_NAME = {
    "np": "numpy",
    "pa": "pyarrow",
    "pd": "pandas",
}


def mark_skip_without_optional_dependency(
    symbol: str,
) -> t.Callable[[T_Callable], T_Callable]:
    name = _DEP_NAME.get(symbol)
    if name is None:
        raise ValueError(f"Unknown optional dependency: {name!r}")
    optional_dep = globals()[symbol]
    return pytest.mark.skipif(
        isinstance(optional_dep, mock.Mock),
        reason=f"{name} not installed",
    )


def skip_if_mocked_dependency(dep: t.Any) -> None:
    if isinstance(dep, mock.Mock):
        name_any = getattr(dep, "_OptionalDepsMock__optional_dep_name", None)
        name = name_any if isinstance(name_any, str) else "optional dependency"
        pytest.skip(f"{name} not installed")
