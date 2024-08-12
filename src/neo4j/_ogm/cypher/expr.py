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
import enum
import typing as t

from .base import (
    Expr,
    OGMQuery,
    Param,
    Part,
    Ref,
)


if t.TYPE_CHECKING:
    import typing_extensions as te

    from .entity import (
        Entity,
        EntityAttribute,
    )
    from .name_registry import NameRegistry


__all__ = [
    "UnaryOp",
    "BinaryOp",
    "ExprLiteral",
    "UnaryExpr",
    "BinaryExpr",
    "ExprChain",
]



class UnaryOp(enum.Enum):
    NOT = "NOT"
    IS_NULL = "IS_NULL"
    IS_NOT_NULL = "IS_NOT_NULL"

    _TRANSLATION: t.ClassVar[t.Dict[UnaryOp, str]]

    @classmethod
    def _translation(cls, version: t.Tuple[int, int]) -> t.Dict[UnaryOp, str]:
        translation = getattr(cls, "_TRANSLATION", None)
        if translation is None:
            cls._TRANSLATION = {
                cls.NOT: "NOT",
                cls.IS_NULL: "IS NULL",
                cls.IS_NOT_NULL: "IS NOT NULL",
            }
        return cls._TRANSLATION  # type: ignore[return-value]

    def _to_cypher(self, version: t.Tuple[int, int]) -> str:
        return self._translation(version)[self]


class BinaryOp(enum.Enum):
    EQ = "EQ"
    NE = "NE"
    LT = "LT"
    LE = "LE"
    GT = "GT"
    GE = "GE"
    STARTS_WITH = "STARTS_WITH"
    ENDS_WITH = "ENDS_WITH"
    CONTAINS = "CONTAINS"
    IN = "IN"
    REGEX = "REGEX"
    AND = "AND"
    OR = "OR"
    XOR = "XOR"
    PLUS = "+"

    _TRANSLATION: t.ClassVar[t.Dict[BinaryOp, str]]

    @classmethod
    def _translation(cls, version: t.Tuple[int, int]) -> t.Dict[BinaryOp, str]:
        translation = getattr(cls, "_TRANSLATION", None)
        if translation is None:
            cls._TRANSLATION = {
                cls.EQ: "=",
                cls.NE: "<>",
                cls.LT: "<",
                cls.LE: "<=",
                cls.GT: ">",
                cls.GE: ">=",
                cls.STARTS_WITH: "STARTS WITH",
                cls.ENDS_WITH: "ENDS WITH",
                cls.CONTAINS: "CONTAINS",
                cls.IN: "IN",
                cls.REGEX: "=~",
                cls.AND: "AND",
                cls.OR: "OR",
                cls.XOR: "XOR",
                cls.PLUS: "+",
            }
        return cls._TRANSLATION  # type: ignore[return-value]

    def _to_cypher(self, version: t.Tuple[int, int]) -> str:
        return self._translation(version)[self]


class ExprLiteral(Expr):
    _literal: t.Union[Ref, str]

    def __init__(self, literal: t.Union[Ref, str]) -> None:
        self._literal = literal

    def _to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int],
    ) -> OGMQuery:
        if isinstance(self._literal, str):
            return OGMQuery(self._literal, {})
        return self._literal._to_cypher(name_reg, version)


class UnaryExpr(Expr):
    _op: UnaryOp
    _target: Expr

    def __init__(
        self,
        op: UnaryOp,
        target: Expr
    ) -> None:
        self._op = op
        self._target = target

    def _to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int],
    ) -> OGMQuery:
        op = self._op._to_cypher(version)
        target = self._target._to_cypher(name_reg, version)
        if self._op == UnaryOp.NOT:
            return OGMQuery(
                f"({op} {target.query})",
                target.parameters
            )
        else:
            return OGMQuery(
                f"({target.query} {op})",
                target.parameters
            )


class BinaryExpr(Expr):
    _op: BinaryOp
    _left: Expr
    _right: Expr

    def __init__(self, left: Expr, op: BinaryOp, right: Expr) -> None:
        self._op = op
        self._left = left
        self._right = right

    def _to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int],
    ) -> OGMQuery:
        left = self._left._to_cypher(name_reg, version)
        right = self._right._to_cypher(name_reg, version)
        op = self._op._to_cypher(version)

        parameters = left.parameters
        parameters.update(right.parameters)

        return OGMQuery(
            f"({left.query} {op} {right.query})",
            parameters
        )


class ExprChain(Expr):
    _op: BinaryOp
    _targets: t.Sequence[Expr]

    def __init__(self, op: BinaryOp, targets: t.Sequence[Expr]) -> None:
        if len(targets) < 1:
            raise ValueError("FilterChain must have at least one target")
        self._op = op
        self._targets = targets

    def _to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int],
    ) -> OGMQuery:
        if len(self._targets) == 1:
            return self._targets[0]._to_cypher(name_reg, version)

        targets = (target._to_cypher(name_reg, version)
                   for target in self._targets)
        op = self._op._to_cypher(version)

        queries = []
        parameters = {}
        for target in targets:
            queries.append(target.query)
            parameters.update(target.parameters)

        query = f" {op} ".join(queries)
        return OGMQuery(f"({query})", parameters)
