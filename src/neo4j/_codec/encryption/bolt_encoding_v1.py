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
import uuid

from ... import _typing as t
from ..._sync.io._bolt._bolt6 import Bolt6x1
from ...spatial import Point
from ...time import (
    Date,
    DateTime,
    Duration,
    Time,
)
from ...vector import Vector
from ._base import (
    BoltEncodingScheme,
    SchemeMajorVersion,
    SchemeVersion,
)


class BoltEncodingSchemeV1(BoltEncodingScheme):
    SCHEME_VERSION: t.ClassVar[SchemeVersion] = SchemeVersion(1, 0)
    COMPATIBLE_SCHEME_VERSIONS: t.ClassVar[tuple[SchemeMajorVersion, ...]] = ()

    PACKER_CLS = Bolt6x1.PACKER_CLS
    UNPACKER_CLS = Bolt6x1.UNPACKER_CLS
    HYDRATION_HANDLER = Bolt6x1.HYDRATION_HANDLER_CLS()

    @classmethod
    def _decode(cls, data: bytes | bytearray, minor_version: int, /) -> object:
        hydration_scope = cls.HYDRATION_HANDLER.new_hydration_scope()
        hydration_hooks = hydration_scope.hydration_hooks
        buffer = cls.UNPACKER_CLS.new_unpackable_buffer(data)
        unpacker = cls.UNPACKER_CLS(buffer)

        return unpacker.unpack(hydration_hooks=hydration_hooks)

    @classmethod
    def _decode_compat(
        cls, data: bytes | bytearray, received_version: SchemeVersion, /
    ) -> object:
        raise NotImplementedError(
            f"No backward compatibility declared from {cls.__name__}."
        )

    _1_0_LIST_SAFE_TYPES = (
        bool,
        int,
        float,
        bytes,
        uuid.UUID,
        str,
        Time,
        Duration,
        DateTime,
        Date,
        Point,
    )
    _1_0_NON_LIST_SAFE_TYPES = (
        Vector,
        type(None),
    )

    @classmethod
    @abc.abstractmethod
    def type_baseline(cls, value: object) -> SchemeVersion:
        return cls._type_baseline(value, inside_list=False)

    @classmethod
    def _type_baseline(cls, value, inside_list=False) -> SchemeVersion:
        if isinstance(value, cls._1_0_LIST_SAFE_TYPES):
            return SchemeVersion(1, 0)
        if inside_list:
            cls._raise_for_unsupported_type(value)
        if isinstance(value, cls._1_0_NON_LIST_SAFE_TYPES):
            return SchemeVersion(1, 0)
        if isinstance(value, list):
            if not value:
                return SchemeVersion(1, 0)
            first_elem = value[0]
            first_elem_type = type(first_elem)
            if not all(type(elem) is first_elem_type for elem in value):
                cls._raise_for_mixed_list(value)
            if isinstance(first_elem, (DateTime, Time)):
                first_has_tz = first_elem.tz is not None
                if not all(
                    (elem.tz is not None) == first_has_tz for elem in value
                ):
                    cls._raise_for_mixed_list(value)
            return cls._type_baseline(first_elem, inside_list=True)
        cls._raise_for_unsupported_type(value)
        t.assert_never(value)

    @classmethod
    def _raise_for_unsupported_type(cls, value: object) -> t.Never:
        raise TypeError(f"Unsupported value type: {type(value)}")

    @classmethod
    def _raise_for_mixed_list(cls, value: object) -> t.Never:
        raise TypeError(
            f"Unsupported value type: {type(value)} "
            "containing inhomogeneous types"
        )

    @classmethod
    def _encode(cls, value: object) -> bytes | bytearray:
        hydration_scope = cls.HYDRATION_HANDLER.new_hydration_scope()
        dehydration_hooks = hydration_scope.dehydration_hooks
        buffer = cls.PACKER_CLS.new_packable_buffer()
        packer = cls.PACKER_CLS(buffer)

        packer.pack(value, dehydration_hooks=dehydration_hooks)

        return buffer.data


BoltEncodingScheme.current_scheme = BoltEncodingSchemeV1
