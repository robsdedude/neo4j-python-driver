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

from .base import (
    Expr,
    OGMQuery,
)
from .name_registry import NameRegistry


__all__ = [
    "Func",
]


class Func(Expr):
    _name: str
    _args: t.Sequence[Expr]

    def __init__(self, name: str, *args: Expr) -> None:
        self._name = name
        self._args = args

    def _to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int],
    ) -> OGMQuery:
        args = []
        params = {}
        for arg in self._args:
            args_query = arg._to_cypher(name_reg, version)
            args.append(args_query.query)
            params.update(args_query.parameters)
        args_str = ", ".join(args)
        return OGMQuery(
            f"{self._name}({args_str})",
            params
        )
