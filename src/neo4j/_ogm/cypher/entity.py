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
    Ref,
)


if t.TYPE_CHECKING:
    import typing_extensions as te

    from .name_registry import NameRegistry


__all__ = [
    "Entity",
    "Node",
    "Relationship",
    "Path",
    "EntityRef",
    "EntityAttribute",
]


class Entity(Part, abc.ABC):
    def attr(self, name: str) -> EntityAttribute:
        return _EntityAttribute(self, name)

    def ref(self) -> EntityRef:
        return _EntityRef(self)

    def _encode_labels(
        self,
        labels: t.Optional[t.Sequence[str]],
        version: t.Tuple[int, int],
    ) -> str:
        if not labels:
            return ""
        escaped_labels = (f":{self._escape_literal(label, version)}"
                          for label in labels)
        return "".join(escaped_labels)

    def _encode_properties(
        self,
        name_space: str,
        properties: t.Optional[t.Dict[str, t.Any]],
        version: t.Tuple[int, int],
    ) -> OGMQuery:
        if not properties:
            return OGMQuery("", {})
        param_map_entries = (
            (self._escape_literal(k, version), f"${name_space}_p{i}")
            for i, k in enumerate(properties.keys())
        )
        param_map = ", ".join(f"{k}: {v}" for k , v in param_map_entries)
        return OGMQuery(
            f" {{{param_map}}}",
            {
                f"{name_space}_p{i}": v
                for i, v in enumerate(properties.values())
            },
        )


class Node(Entity):
    labels: t.Optional[t.Sequence[str]]
    properties: t.Optional[t.Dict[str, t.Any]]

    def __init__(
        self,
        labels: t.Optional[t.Sequence[str]] = None,
        properties: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> None:
        self.labels = labels
        self.properties = properties

    def _to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int],
    ) -> OGMQuery:
        name = name_reg.get_or_register(self)
        escaped_labels = self._encode_labels(self.labels, version)
        param_query = self._encode_properties(name, self.properties, version)
        return OGMQuery(
            f"({name}{''.join(escaped_labels)}{param_query.query})",
            param_query.parameters
        )

    def ref(self) -> NodeRef:
        return _NodeRef(self)


class Relationship(Entity):
    label: t.Optional[str]
    properties: t.Optional[t.Dict[str, t.Any]]
    start_node: t.Union[Entity, NodeRef, str, None]
    end_node: t.Union[Entity, NodeRef, str, None]
    directed: bool

    def __init__(
        self,
        label: t.Optional[str] = None,
        properties: t.Optional[t.Dict[str, t.Any]] = None,
        start_node: t.Union[Entity, NodeRef, str, None] = None,
        end_node: t.Union[Entity, NodeRef, str, None] = None,
        directed: bool = True,
    ) -> None:
        self.label = label
        self.properties = properties
        self.start_node = start_node
        self.end_node = end_node
        self.directed = directed

    @staticmethod
    def _encode_node(
        node: t.Union[Entity, NodeRef, str, None],
        name_reg: NameRegistry,
        version: t.Tuple[int, int],
    ) -> OGMQuery:
        if node is None:
            return OGMQuery("()", {})
        if isinstance(node, str):
            return OGMQuery(node, {})
        if isinstance(node, NodeRef):
            q = node._to_cypher(name_reg, version)
            return OGMQuery(f"({q.query})", q.parameters)
        return node._to_cypher(name_reg, version)

    def _to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int],
    ) -> OGMQuery:
        name = name_reg.get_or_register(self)
        labels = () if self.label is None else (self.label,)
        escaped_label = self._encode_labels(labels, version)
        param_query = self._encode_properties(name, self.properties, version)
        params = param_query.parameters
        start_q = self._encode_node(self.start_node, name_reg, version)
        params.update(start_q.parameters)
        end_q = self._encode_node(self.end_node, name_reg, version)
        params.update(end_q.parameters)
        directed = ">" if self.directed else ""
        return OGMQuery(
            (
                f"{start_q.query}"
                f"-[{name}{escaped_label}{param_query.query}]-{directed}"
                f"{end_q.query}"
            ),
            params
        )


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
        version: t.Tuple[int, int],
    ) -> OGMQuery:
        raise NotImplementedError


class EntityRef(Ref, abc.ABC):
    pass


class NodeRef(EntityRef, abc.ABC):
    pass


class _EntityRef(EntityRef):
    _entity: Entity

    def __init__(self, entity: Entity) -> None:
        self._entity = entity

    def _to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int],
    ) -> OGMQuery:
        return OGMQuery(
            name_reg.get_or_register(self._entity),
            {}
        )


class _NodeRef(_EntityRef, NodeRef, abc.ABC):
    _entity: Node

    def __init__(self, entity: Node) -> None:
        self._entity = entity


class EntityAttribute(EntityRef, abc.ABC):
    pass


class _EntityAttribute(EntityAttribute):
    _parent: t.Union[Entity, EntityRef]
    _name: str

    def __init__(self, parent: t.Union[Entity, EntityRef], name: str) -> None:
        self._parent = parent
        self._name = name

    def attr(self, name: str) -> EntityAttribute:
        return _EntityAttribute(self, name)

    def _to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int],
    ) -> OGMQuery:
        this: _EntityAttribute = self
        path = [self._escape_literal(self._name, version)]
        while isinstance(this._parent, _EntityAttribute):
            path.append(self._escape_literal(self._name, version))
            this = this._parent
        assert isinstance(this._parent, Entity)
        path.append(name_reg.get_or_register(this._parent))

        return OGMQuery(
            ".".join(reversed(path)),
            {}
        )
