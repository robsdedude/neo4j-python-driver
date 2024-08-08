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
    OGMQuery,
    Part,
)


if t.TYPE_CHECKING:
    import typing_extensions as te

    from .name_registry import NameRegistry


__all__ = [
    "Entity",
    "Node",
    "Relationship",
    "Path",
    "EntityAttribute",
]


class Entity(Part, abc.ABC):
    def attr(self, name: str) -> EntityAttribute:
        return EntityAttribute(self, name)


class Node(Entity):
    labels: t.Optional[t.List[str]]
    properties: t.Optional[t.Dict[str, t.Any]]

    def __init__(
        self,
        labels: t.Optional[t.List[str]] = None,
        properties: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> None:
        self.labels = labels
        self.properties = properties

    def _to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int]
    ) -> OGMQuery:
        name = name_reg.get_or_register(self)
        labels = self.labels or ()
        escaped_labels = (f":{self._escape_literal(label, version)}"
                          for label in labels)

        properties = self.properties or {}
        param_map_entries = (
            (self._escape_literal(k, version), f"${name}_p{i}")
            for i, k in enumerate(properties.keys())
        )
        param_map = ", ".join(f"{k}: {v}" for k , v in param_map_entries)
        if param_map:
            param_map = f" {{{param_map}}}"
        return OGMQuery(
            f"({name}{''.join(escaped_labels)}{param_map})",
            {
                f"{name}_p{i}": v
                for i, v in enumerate(properties.values())
            },
        )


class Relationship(Entity):
    label: t.Optional[str]
    properties: t.Optional[t.Dict[str, t.Any]]

    def __init__(
        self,
        label: t.Optional[str] = None,
        properties: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> None:
        self.label = label
        self.properties = properties

    def _to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int]
    ) -> OGMQuery:
        raise NotImplementedError



class _Direction(enum.Enum):
    FORWARD = enum.auto()
    BACKWARD = enum.auto()


class Path(Entity):
    nodes: t.List[Node]
    relationships: t.List[t.Tuple[_Direction, Relationship]]

    def __init__(
        self,
        node: Node,
    ) -> None:
        self.nodes = [node]
        self.relationships = []

    def to(
        self,
        relationship: Relationship,
        node: Node,
    ) -> te.Self:
        self.relationships.append((_Direction.FORWARD, relationship))
        self.nodes.append(node)
        return self

    def from_(
        self,
        relationship: Relationship,
        node: Node,
    ) -> te.Self:
        self.relationships.append((_Direction.BACKWARD, relationship))
        self.nodes.append(node)
        return self

    def _to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int]
    ) -> OGMQuery:
        raise NotImplementedError


class EntityAttribute(Entity):
    _parent: Entity
    _name: str

    def __init__(self, parent: Entity, name: str) -> None:
        self._parent = parent
        self._name = name

    def _to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int]
    ) -> OGMQuery:
        this: Entity = self
        path = []
        while isinstance(this, EntityAttribute):
            path.append(self._escape_literal(self._name, version))
            this = this._parent
        path.append(name_reg.get_or_register(this))

        return OGMQuery(
            ".".join(reversed(path)),
            {}
        )
