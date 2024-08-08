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

import enum
import typing as t
from dataclasses import dataclass

from . import cypher as cy
from .cypher import filters as cy_f


if t.TYPE_CHECKING:
    import typing_extensions as te


__all__ = [
    # TODO: implement more filters (see cy_f.UnaryOp, .BinaryOp)
    "eq",
    "ge",
    "contains",
]


@dataclass
class _Cmp:
    _to_filter: t.Callable[[cy.EntityAttribute, t.Any], cy_f.Filter]
    _value: t.Any

    def to_filter(self, e: cy.EntityAttribute) -> cy_f.Filter:
        return self._to_filter(e, self._value)


def _eq_to_filter(e: cy.EntityAttribute, value: t.Any) -> cy_f.Filter:
    return cy_f.BinaryFilter(
        cy_f.FilterLiteral(e),
        cy_f.BinaryOp.EQ,
        cy_f.FilterLiteral(cy.Var(value))
    )


def eq(value: t.Any) -> _Cmp:
    return _Cmp(_eq_to_filter, value)


def _ge_to_filter(e: cy.EntityAttribute, value: t.Any) -> cy_f.Filter:
    return cy_f.BinaryFilter(
        cy_f.FilterLiteral(e),
        cy_f.BinaryOp.GE,
        cy_f.FilterLiteral(cy.Var(value))
    )


def ge(value: t.Any) -> _Cmp:
    return _Cmp(_ge_to_filter, value)


def _contains_to_filter(e: cy.EntityAttribute, value: t.Any) -> cy_f.Filter:
    return cy_f.BinaryFilter(
        cy_f.FilterLiteral(e),
        cy_f.BinaryOp.CONTAINS,
        cy_f.FilterLiteral(cy.Var(value))
    )


def contains(value: t.Any) -> _Cmp:
    return _Cmp(_contains_to_filter, value)
