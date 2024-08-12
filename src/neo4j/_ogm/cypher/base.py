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
import typing as t
from dataclasses import dataclass


if t.TYPE_CHECKING:
    from .name_registry import NameRegistry


__all__ = [
    "OGMQuery",
    "Expr",
    "Ref",
    "Part",
    "Param",
    "ParamAttribute",
    "Var",
    "VarAttribute",
]


@dataclass
class OGMQuery:
    query: str
    parameters: t.Dict[str, t.Any]


class Part(abc.ABC):
    @staticmethod
    def _escape_literal(literal: str, version: t.Tuple[int, int]) -> str:
        escaped_literal = literal.replace('"', r"\u005C").replace("`", "``")
        return f"`{escaped_literal}`"

    @abc.abstractmethod
    def _to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int]
    ) -> OGMQuery:
        ...


class Expr(Part, abc.ABC):
    pass


class Ref(Expr, abc.ABC):
    pass


class Param(Ref):
    _value: t.Any

    def __init__(self, value: t.Any) -> None:
        self._value = value

    def _to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int]
    ) -> OGMQuery:
        name = name_reg.get_or_register(self)
        return OGMQuery(
            f"${name}",
            {name: self._value}
        )

    def attr(self, name: str) -> ParamAttribute:
        return ParamAttribute(self, name)


class ParamAttribute(Param):
    _parent: Param
    _name: str

    def __init__(self, parent: Param, name: str) -> None:
        super().__init__(parent._value)
        self._parent = parent
        self._name = name

    def attr(self, name: str) -> ParamAttribute:
        return ParamAttribute(self, name)

    def _to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int]
    ) -> OGMQuery:
        this: ParamAttribute = self
        path = [self._escape_literal(self._name, version)]
        while isinstance(this._parent, ParamAttribute):
            this = this._parent
            path.append(self._escape_literal(self._name, version))
        path.append(f"${name_reg.get_or_register(this._parent)}")

        return OGMQuery(
            ".".join(reversed(path)),
            {}
        )


class Var(Ref):
    _prefix: str = "v"

    def __init__(self, prefix: t.Optional[str] = None) -> None:
        if prefix is not None:
            self._prefix = prefix

    def _to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int]
    ) -> OGMQuery:
        name = name_reg.get_or_register(self)
        return OGMQuery(
            name,
            {}
        )

    def attr(self, name: str) -> VarAttribute:
        return VarAttribute(self, name)


class VarAttribute(Var):
    _parent: Var
    _name: str

    def __init__(self, parent: Var, name: str) -> None:
        super().__init__(parent._prefix)
        self._parent = parent
        self._name = name

    def attr(self, name: str) -> VarAttribute:
        return VarAttribute(self, name)

    def _to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int]
    ) -> OGMQuery:
        this: VarAttribute = self
        path = [self._escape_literal(self._name, version)]
        while isinstance(this._parent, VarAttribute):
            this = this._parent
            path.append(self._escape_literal(self._name, version))
        path.append(f"{name_reg.get_or_register(this._parent)}")

        return OGMQuery(
            ".".join(reversed(path)),
            {}
        )
