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

from pydantic import (
    BaseModel,
    computed_field,
    GetCoreSchemaHandler,
)
from pydantic_core import (
    core_schema,
    CoreSchema,
)

from .key import PK


if t.TYPE_CHECKING:
    import typing_extensions as te


T = t.TypeVar('T')


__all__ = [
    "Node",
    "Relationship",
    "Related",
]


class _CmpField:
    ...


class _NodeMeta(type(BaseModel)):  # type: ignore[misc]
    def __new__(
        cls,
        cls_name: str,
        bases: tuple[type[t.Any], ...],
        namespace: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> type:
        if bases == (BaseModel, abc.ABC) and cls_name == "Node":
            # no special treatment for our own `Node` base class
            return super().__new__(cls, cls_name, bases, namespace, **kwargs)
        for field in ("__ogm_cls__", "__ogm_obj__"):
            if field in namespace:
                raise TypeError(
                    f"Node subclasses must not have a `{field}` attribute"
                )

        # TODO: make extraction work with subclasses by walking the bases
        pk = namespace.pop("pk", None)
        namespace.get("__annotations__", {}).pop("pk", None)
        if pk is None:
            raise TypeError("Node subclasses must have a `pk` class attribute")
        if not isinstance(pk, PK):
            raise TypeError("`pk` must be an instance of `PK`")

        rels = {}
        for k, v in namespace.items():
            if isinstance(v, _Related):
                rels[k] = v

        namespace["__ogm_cls__"] = _OGMClsData(
            pk=pk,
            rels=rels,
        )

        kls = super().__new__(cls, cls_name, bases, namespace, **kwargs)
        # for field in kls.model_fields.keys():
        #     setattr(kls, field, f"Hello, {field}")
        assert issubclass(kls, Node)

        pk._validate_model(kls)
        # pk_strategy = getattr(kls, "__ogm_pk_strategy__", None)
        # if not isinstance(pk_strategy, PKStrategy):
        #     raise TypeError(
        #         f"Class {kls.__name} must have a valid "
        #         f"`__ogm_pk_strategy__` attribute"
        #     )
        # pk_strategy._model_init(kls)
        return kls


@dataclass
class _OGMClsData:
    pk: PK
    rels: t.Dict[str, _Related]


@dataclass
class _OGMObjData:
    pk: PK


class Node(BaseModel, abc.ABC, metaclass=_NodeMeta):
    __ogm_cls__: t.ClassVar[_OGMClsData]
    __ogm_obj__: _OGMObjData

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.__ogm_obj__ = _OGMObjData(
            pk=self.__ogm_cls__.pk._new_with_value(None),
        )

    # @property
    # def pk(self) -> t.Optional[PK]:
    #     return self.__ogm_pk_strategy__._pk_get(self)
    #
    # @pk.setter
    # def pk(self, value: t.Optional[PK]) -> None:
    #     self.__ogm_pk_strategy__._pk_set(self, value)
    #
    # # def __init_subclass__(cls, **kwargs):
    # #     super().__init_subclass__(**kwargs)
    # #     pk_strategy = getattr(cls, "__ogm_pk_strategy__", None)
    # #     if not isinstance(pk_strategy, PKStrategy):
    # #         raise TypeError(
    # #             f"Class {cls.__name__} must have a valid "
    # #             f"`__ogm_pk_strategy__` attribute"
    # #         )
    # #     pk_strategy._model_verification(cls)
    #
    # @property
    # @abc.abstractmethod
    # def __ogm_pk_strategy__(self) -> PKStrategy:
    #     ...

    if t.TYPE_CHECKING:
        @property
        @abc.abstractmethod
        def pk(self) -> PK:
            ...
    else:
        @computed_field
        def pk(self) -> t.Optional[object]:
            return self.__ogm_obj__.pk.value


class Relationship(BaseModel, t.Generic[T]):
    ...
    # def __iter__(self) -> t.Iterable[T]:
    #     ...


class Direction(str, enum.Enum):
    OUTGOING = "->"
    INCOMING = "<-"
    BOTH = "--"


@dataclass
class _Related:
    direction: Direction
    label: str


def Related(
    direction: t.Union[te.Literal["->", "<-", "--"], Direction],
    label: str,
) -> t.Any:
    if not isinstance(direction, Direction):
        direction_enum = Direction(direction)
    else:
        direction_enum = direction
    return _Related(direction_enum, label)
