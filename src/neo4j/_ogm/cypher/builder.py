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
from dataclasses import dataclass

from .base import (
    OGMQuery,
    Part,
)
from .clause import (
    Clause,
    RootClause,
)
from .entity import (
    Entity,
    Node,
    Path,
    Relationship,
)
from .name_registry import NameRegistry


if t.TYPE_CHECKING:
    import typing_extensions as te


__all__ = [
    "CypherBuilder",
]


class CypherBuilder:
    _cypher_version: t.Tuple[int, int]

    def __init__(self, cypher_version: t.Tuple[int, int]) -> None:
        self._cypher_version = cypher_version

    def build(self, root: RootClause) -> OGMQuery:
        return root._to_cypher(NameRegistry(), self._cypher_version)
