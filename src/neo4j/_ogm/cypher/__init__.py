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
    Part,
    Var,
)
from .builder import CypherBuilder
from .clause import (
    Create,
    Match,
    ReturnArg,
    ReturnEntityArg,
    SetArg,
)
from .entity import (
    Entity,
    EntityAttribute,
    Node,
    Path,
    Relationship,
)
from .name_registry import NameRegistry


if t.TYPE_CHECKING:
    import typing_extensions as te


__all__ = [
    "VERSION_QUERY",
    "Entity",
    "EntityAttribute",
    "Node",
    "Relationship",
    "Path",
    "CypherBuilder",
    "Create",
    "Match",
    "Part",
    "NameRegistry",
    "ReturnArg",
    "ReturnEntityArg",
    "SetArg",
    "Var",
]


VERSION_QUERY: te.LiteralString = \
    "CALL dbms.components() YIELD versions RETURN versions[0] AS version"
