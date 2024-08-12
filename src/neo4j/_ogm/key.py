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

from pydantic import GetCoreSchemaHandler
from pydantic_core import (
    core_schema,
    CoreSchema,
)

from . import cypher as cy
from .cypher import expr as cy_x


if t.TYPE_CHECKING:
    import typing_extensions as te

    from .model import Node


T = t.TypeVar("T")


__all__ = [
    "PK",
    "PKField",
]


class PK(abc.ABC, t.Generic[T]):
    _value: t.Optional[T] = None

    @property
    def value(self) -> t.Optional[T]:
        return self._value

    @abc.abstractmethod
    def _validate_model(self, model: t.Type[Node]) -> None:
        ...

    @abc.abstractmethod
    def _new_with_value(self, value: T) -> te.Self:
        ...

    @abc.abstractmethod
    def _cy_return(self, node: cy.Node) -> t.Optional[cy_x.Expr]:
        ...

    @abc.abstractmethod
    def _load(self, model: Node, cy_return: t.Optional[t.Any]) -> None:
        ...

    # @abc.abstractmethod
    # def _load_return(self, value: t.Any) -> te.Self:
    #     ...

    @abc.abstractmethod
    def _cy_filter(self, value: te.Self, node: cy.Node) -> cy_x.Expr:
        ...

    @abc.abstractmethod
    def _cy_var_filter(self, var: cy.Var, node: cy.Node) -> cy_x.Expr:
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.value!r})"

    def __eq__(self, other: t.Any) -> bool:
        if not isinstance(other, PK):
            return False
        return (
            type(self.value) == type(other.value)
            and self.value == other.value
        )

    def __hash__(self) -> int:
        return hash(self.value)

    # @property
    # @abc.abstractmethod
    # def _implicit(self) -> bool:
    #     ...


class PKField(PK[tuple]):
    _fields: t.Tuple[str, ...]

    def __init__(self, *fields: str) -> None:
        self._fields = fields

    def _new_with_value(self, value: tuple) -> te.Self:
        obj = self.__class__(*self._fields)
        obj._value = value
        return obj

    def _validate_model(self, model: t.Type[Node]) -> None:
        for field in self._fields:
            if field not in model.model_fields:
                raise ValueError(f"Field `{field}` not found in model {model}")

    def _cy_return(self, node: cy.Node) -> t.Optional[cy_x.Expr]:
        return None

    def _load(self, model: Node, cy_return: t.Optional[t.Any]) -> None:
        self._value = tuple(
            getattr(model, field)
            for field in self._fields
        )

    def _cy_filter(self, value: te.Self, node: cy.Node) -> cy_x.Expr:
        assert value._value is not None
        attr_filters = tuple(
            cy_x.BinaryExpr(
                cy_x.ExprLiteral(node.attr(self._fields[i])),
                cy_x.BinaryOp.EQ,
                cy_x.ExprLiteral(cy.Param(value._value[i]))
            )
            for i in range(len(self._fields))
        )
        return cy_x.ExprChain(
            cy_x.BinaryOp.AND,
            attr_filters
        )

    def _cy_var_filter(self, var: cy.Var, node: cy.Node) -> cy_x.Expr:
        attr_filters = tuple(
            cy_x.BinaryExpr(
                cy_x.ExprLiteral(node.attr(self._fields[i])),
                cy_x.BinaryOp.EQ,
                cy_x.ExprLiteral(var.attr(self._fields[i]))
            )
            for i in range(len(self._fields))
        )
        return cy_x.ExprChain(
            cy_x.BinaryOp.AND,
            attr_filters
        )

    # @classmethod
    # def __get_pydantic_core_schema__(
    #     cls, source_type: t.Any, handler: GetCoreSchemaHandler
    # ) -> CoreSchema:
    #     serialization = core_schema.plain_serializer_function_ser_schema(
    #         lambda x: x.value
    #     )
    #     return core_schema.any_schema(
    #         serialization=serialization,
    #     )
        # return core_schema.model_field(
        #     handler(
        #         core_schema.with_default_schema(
        #             core_schema.any_schema(),
        #             default=PKField(),
        #             serialization=serialization,
        #         ),
        #     ),
        #     serialization_alias="__ogm_pk_cls__",
        # )
        # core_schema.with_default_schema(
        #     core_schema.with_info_after_validator_function(
        #         cls._load,
        #         handler(t.List[t.Any]),
        #         serialization=core_schema.plain_serializer_function_ser_schema(
        #             lambda x: None,
        #             when_used="unless-none",
        #         )
        #     ),
        #
        # )
        # return schema

# class PKStrategy(abc.ABC):
#     def _model_init(self, model: t.Type[Node]) -> None:
#         pass
#
#     @abc.abstractmethod
#     def _pk_get(self, model: Node) -> t.Optional[PK]:
#         ...
#
#     @abc.abstractmethod
#     def _pk_set(self, model: Node, value: t.Optional[PK]) -> None:
#         ...
#
#
# class PKField(PKStrategy):
#     _fields: t.Tuple[str, ...]
#
#     def __init__(self, *fields: str) -> None:
#         self._fields = tuple(fields)
#
#     def _model_init(self, model: t.Type[Node]) -> None:
#         for field in self._fields:
#             if field not in model.model_fields:
#                 raise ValueError(f"Field `{field}` not found in model {model}")
#
#     def _pk_get(self, model: Node) -> t.Optional[PK]:
#         if
#
#     def _pk_set(self, model: Node, value: t.Optional[PK]) -> None:
#         ...
