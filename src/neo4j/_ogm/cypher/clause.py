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

from .base import (
    OGMQuery,
    Part,
    Var,
)
from .entity import (
    Entity,
    EntityAttribute,
)


if t.TYPE_CHECKING:
    import typing_extensions as te

    from .filters import Filter
    from .name_registry import NameRegistry


__all__ = [
    "Clause",
    "RootClause",
    "Create",
    "Match",
    "ReturnArg",
    "ReturnEntityArg",
    "SetArg",
]


class Clause(Part, abc.ABC):
    pass

class RootClause(Clause, abc.ABC):
    _clauses: t.List[Clause]

    def __init__(self) -> None:
        super().__init__()
        self._clauses = []

    @abc.abstractmethod
    def _root_to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int]
    ) -> OGMQuery:
        ...

    def _to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int]
    ) -> OGMQuery:
        root = self._root_to_cypher(name_reg, version)
        clauses = [root.query]
        parameters = root.parameters
        for clause in self._clauses:
            clause_query = clause._to_cypher(name_reg, version)
            clauses.append(clause_query.query)
            parameters.update(clause_query.parameters)
        return OGMQuery("\n".join(clauses), parameters)

    def append(
        self,
        clause: Clause
    ) -> te.Self:
        self._clauses.append(clause)
        return self

    def create(
        self,
        entity: t.Union[Entity, str]
    ) -> te.Self:
        self._clauses.append(Create(entity))
        return self

    def match(
        self,
        entity: t.Union[Entity, str]
    ) -> te.Self:
        self._clauses.append(Match(entity))
        return self

    def merge(
        self,
        entity: t.Union[Entity, str]
    ) -> te.Self:
        self._clauses.append(Merge(entity))
        return self

    def where(
        self,
        filter_: Filter
    ) -> te.Self:
        self._clauses.append(_Where(filter_))
        return self

    def set(
        self,
        *sets: t.Union[SetArg, str]
    ) -> te.Self:
        self._clauses.append(_Set(sets))
        return self

    def return_(
        self,
        *returns: t.Union[ReturnArg, str],
    ) -> te.Self:
        self._clauses.append(_Return(returns))
        return self


class _EntityRootClause(RootClause, abc.ABC):
    _entity: t.Union[Entity, str]

    def __init__(
        self,
        entity: t.Union[Entity, str]
    ) -> None:
        super().__init__()
        self._entity = entity

    def _root_to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int]
    ) -> OGMQuery:
        if isinstance(self._entity, str):
            entity_str, entity_params = self._entity, {}
        else:
            entity_query = self._entity._to_cypher(name_reg, version)
            entity_str = entity_query.query
            entity_params = entity_query.parameters
        clause_str = self._get_clause_str(version)
        return OGMQuery(
            f"{clause_str} {entity_str}",
            entity_params,
        )

    @classmethod
    @abc.abstractmethod
    def _get_clause_str(cls, version: t.Tuple[int, int]) -> str:
        ...


class Create(_EntityRootClause):
    _entity: t.Union[Entity, str]

    @classmethod
    def _get_clause_str(cls, version: t.Tuple[int, int]) -> str:
        return "CREATE"


class Match(_EntityRootClause):
    @classmethod
    def _get_clause_str(cls, version: t.Tuple[int, int]) -> str:
        return "MATCH"


class Merge(_EntityRootClause):
    _on_create: t.Optional[_Set]
    _on_match: t.Optional[_Set]

    @classmethod
    def _get_clause_str(cls, version: t.Tuple[int, int]) -> str:
        return "MERGE"

    def on_create(
        self,
        args: t.Optional[t.Sequence[t.Union[SetArg, str]]]
    ) -> te.Self:
        if args is None:
            self._on_create = None
        else:
            self._on_create = _Set(args)
        return self

    def on_match(
        self,
        args: t.Optional[t.Sequence[t.Union[SetArg, str]]]
    ) -> te.Self:
        if args is None:
            self._on_match = None
        else:
            self._on_match = _Set(args)
        return self

    def _root_to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int]
    ) -> OGMQuery:
        query = super()._root_to_cypher(name_reg, version)
        if self._on_create is None and self._on_match is None:
            return query
        parts = [query.query]
        parameters = query.parameters
        if self._on_create is not None:
            on_create_query = self._on_create._to_cypher(name_reg, version)
            parts.append(f"ON CREATE {on_create_query.query}")
            parameters.update(on_create_query.parameters)
        if self._on_match is not None:
            on_match_query = self._on_match._to_cypher(name_reg, version)
            parts.append(f"ON MATCH {on_match_query.query}")
            parameters.update(on_match_query.parameters)
        return OGMQuery("\n  ".join(parts), parameters)


class _Where(Clause):
    _filter: Filter
    def __init__(self, filter_: Filter) -> None:
        self._filter = filter_

    def _to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int]
    ) -> OGMQuery:
        filter_query = self._filter._to_cypher(name_reg, version)
        return OGMQuery(
            f"WHERE {filter_query.query}",
            filter_query.parameters
        )


class _Return(Clause):
    _args: t.Sequence[t.Union[ReturnArg, str]]

    def __init__(
        self,
        args: t.Sequence[t.Union[ReturnArg, str]]
    ) -> None:
        if not args:
            raise ValueError("At least one return argument is required.")
        self._args = args

    def _to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int]
    ) -> OGMQuery:
        arg_strs = []
        parameters = {}
        for arg in self._args:
            if isinstance(arg, str):
                arg_strs.append(arg)
                continue
            arg_query = arg._to_cypher(name_reg, version)
            arg_strs.append(arg_query.query)
            parameters.update(arg_query.parameters)
        arg_str = ", ".join(arg_strs)
        return OGMQuery(
            f"RETURN {arg_str}",
            parameters,
        )


class ReturnArg(Part, abc.ABC):
    _as: t.Optional[str] = None

    def as_(self, alias: t.Optional[str]) -> te.Self:
        self._as = alias
        return self

    def _as_to_cypher(
        self,
        query: str,
        version: t.Tuple[int, int],
    ) -> str:
        if self._as is not None:
            return f"{query} AS {self._as}"
        return query


class ReturnEntityArg(ReturnArg):
    _entity: t.Union[Entity, str]
    _map_project: bool

    def __init__(
        self,
        entity: t.Union[Entity, str],
        map_project: bool = False,
    ) -> None:
        if map_project and not isinstance(entity, Entity):
            raise ValueError("Mapping projection requires an entity.")
        self._entity = entity
        self._map_project = map_project

    def _to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int],
    ) -> OGMQuery:
        if isinstance(self._entity, str):
            entity_str = self._entity
        else:
            entity_str = name_reg.get_or_register(self._entity)
        if self._map_project:
            entity_str += "{.*}"
        return OGMQuery(
            self._as_to_cypher(entity_str, version),
            {},
        )

class _Set(Clause):
    _args: t.Sequence[t.Union[SetArg, str]]

    def __init__(
        self,
        args: t.Sequence[t.Union[SetArg, str]]
    ) -> None:
        if not args:
            raise ValueError("At least one set argument is required.")
        self._args = args

    def _to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int],
    ) -> OGMQuery:
        arg_strs = []
        parameters = {}
        for arg in self._args:
            if isinstance(arg, str):
                arg_strs.append(arg)
                continue
            arg_query = arg._to_cypher(name_reg, version)
            arg_strs.append(arg_query.query)
            parameters.update(arg_query.parameters)
        arg_str = ", ".join(arg_strs)
        return OGMQuery(
            f"SET {arg_str}",
            parameters,
        )


class SetArg(Part, abc.ABC):
    _target: t.Union[Entity, str]
    _value: t.Union[Var, str]

    def __init__(
        self,
        target: t.Union[Entity, str],
        value: t.Union[Var, str],
    ) -> None:
        self._target = target
        self._value = value

    def _to_cypher(
        self,
        name_reg: NameRegistry,
        version: t.Tuple[int, int],
    ) -> OGMQuery:
        if isinstance(self._target, str):
            target_str = self._target
            params = {}
        elif isinstance(self._target, EntityAttribute):
            target_query = self._target._to_cypher(name_reg, version)
            target_str = target_query.query
            params = target_query.parameters
        else:
            assert isinstance(self._target, Entity)
            target_str = name_reg.get_or_register(self._target)
            params = {}
        if isinstance(self._value, str):
            value_str = self._value
        else:
            value_query = self._value._to_cypher(name_reg, version)
            value_str = value_query.query
            params.update(value_query.parameters)
        return OGMQuery(
            f"{target_str} = {value_str}",
            params,
        )
