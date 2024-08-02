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


if t.TYPE_CHECKING:
    import typing_extensions as te


__all__ = [
    "VERSION_QUERY",
    "Node",
    "Relationship",
    "Path",
    "CypherBuilder",
    "Clause",
    "RootClause",
    "Entity",
]


VERSION_QUERY: te.LiteralString = \
    "CALL dbms.components() YIELD versions RETURN versions[0] AS version"


class _NameRegistry:
    _counters: t.Dict[str, int]
    _names: t.Dict[int, str]

    def __init__(self) -> None:
        self._counters = {"n": 0, "r": 0, "p": 0}
        self._names = {}

    def get(self, obj: Entity) -> t.Optional[str]:
        return self._names.get(id(obj))

    def _generate_name(self, obj: Entity) -> str:
        if isinstance(obj, Node):
            prefix = "n"
        elif isinstance(obj, Relationship):
            prefix = "r"
        elif isinstance(obj, Path):
            prefix = "p"
        else:
            raise NotImplementedError(f"Unsupported entity type: {type(obj)}")
        self._counters[prefix] += 1
        return f"{prefix}{self._counters[prefix]}"

    def register(self, obj: Entity) -> str:
        if obj in self._names:
            raise ValueError(f"Entity {obj} is already registered.")
        name = self._generate_name(obj)
        self._names[id(obj)] = name
        return name

    def get_or_register(self, obj: Entity) -> str:
        name = self.get(obj)
        if name is None:
            name = self.register(obj)
        return name


@dataclass
class OGMQuery:
    query: str
    parameters: t.Dict[str, t.Any]



class _Part(abc.ABC):
    @staticmethod
    def _escape_literal(literal: str, version: t.Tuple[int, int]) -> str:
        escaped_literal = literal.replace('"', r"\u005C").replace("`", "``")
        return f"`{escaped_literal}`"


class Entity(_Part, abc.ABC):
    @abc.abstractmethod
    def _to_cypher(self, name: str, version: t.Tuple[int, int]) -> OGMQuery:
        ...


class Clause(_Part, abc.ABC):
    @abc.abstractmethod
    def _to_cypher(
        self,
        name_reg: _NameRegistry,
        version: t.Tuple[int, int]
    ) -> OGMQuery:
        ...


class RootClause(Clause, abc.ABC):
    pass


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

    def _to_cypher(self, name: str, version: t.Tuple[int, int]) -> OGMQuery:
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

    def _to_cypher(self, name: str, version: t.Tuple[int, int]) -> OGMQuery:
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

    def _to_cypher(self, name: str, version: t.Tuple[int, int]) -> OGMQuery:
        raise NotImplementedError


class Create(RootClause):
    _entity: t.Union[Entity, str]

    def __init__(
        self,
        entity: t.Union[Entity, str]
    ) -> None:
        self._entity = entity

    def _to_cypher(
        self,
        name_reg: _NameRegistry,
        version: t.Tuple[int, int]
    ) -> OGMQuery:
        if isinstance(self._entity, str):
            entity_str, entity_params = self._entity, {}
        else:
            name = name_reg.get_or_register(self._entity)
            entity_query = self._entity._to_cypher(name, version)
            entity_str = entity_query.query
            entity_params = entity_query.parameters
        return OGMQuery(
            f"CREATE {entity_str}",
            entity_params,
        )


class CypherBuilder:
    _cypher_version: t.Tuple[int, int]

    def __init__(self, cypher_version: t.Tuple[int, int]) -> None:
        self._cypher_version = cypher_version

    def build(self, root: RootClause) -> OGMQuery:
        return root._to_cypher(_NameRegistry(), self._cypher_version)


if __name__ == '__main__':
    def main():
        bob = Node(labels=["Person"], properties={"name": "Bob"})
        person = Node(labels=["Person"])
        # Match(person).where(person.name == "Alice").return_(person)
        # Create(bob).where(bob.name == "Bob").return_(bob)
        print(CypherBuilder((5, 0)).build(Create(bob)))

    main()
