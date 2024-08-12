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
from collections import defaultdict

from .base import (
    Param,
    Var,
)
from .entity import (
    Entity,
    Node,
    Path,
    Relationship,
)
from .expr import Expr


if t.TYPE_CHECKING:
    import typing_extensions as te


__all__ = [
    "NameRegistry",
]


_TReg: te.TypeAlias = t.Union[Entity, Param, Var]


class NameRegistry:
    _counters: t.Dict[str, int]
    _names: t.Dict[int, str]

    def __init__(self) -> None:
        self._counters = defaultdict(int)
        self._names = {}

    def get(self, obj: _TReg) -> t.Optional[str]:
        return self._names.get(id(obj))

    def _generate_name(self, obj: _TReg) -> str:
        if isinstance(obj, Node):
            prefix = "n"
        elif isinstance(obj, Relationship):
            prefix = "r"
        elif isinstance(obj, Path):
            prefix = "p"
        elif isinstance(obj, Param):
            prefix = "in"
        elif isinstance(obj, Var):
            prefix = f"_{obj._prefix}"
        else:
            raise NotImplementedError(f"Unsupported entity type: {type(obj)}")
        self._counters[prefix] += 1
        if self._counters[prefix] == 1:
            return prefix
        return f"{prefix}{self._counters[prefix]}"

    def register(self, obj: _TReg) -> str:
        if obj in self._names:
            raise ValueError(f"Entity {obj} is already registered.")
        name = self._generate_name(obj)
        self._names[id(obj)] = name
        return name

    def get_or_register(self, obj: _TReg) -> str:
        name = self.get(obj)
        if name is None:
            name = self.register(obj)
        return name
