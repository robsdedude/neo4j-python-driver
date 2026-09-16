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

from ... import _typing as t  # noqa: TC001
from ..._version import (
    MajorVersion,
    VersionTuple,
)
from ...types import UnsupportedType


# class BoltEncodingSchemeMeta(abc.ABC, type):
#     @property
#     @abc.abstractmethod
#     def version(self) -> :


class SchemeVersion(VersionTuple):
    pass


class SchemeMajorVersion(MajorVersion):
    pass


class BoltEncodingScheme(abc.ABC):
    known_schemes: t.ClassVar[
        dict[SchemeMajorVersion, type[BoltEncodingScheme]]
    ] = {}
    back_compat_schemes: t.ClassVar[
        dict[SchemeMajorVersion, type[BoltEncodingScheme]]
    ] = {}
    max_supported_major: t.ClassVar[SchemeMajorVersion] = SchemeMajorVersion(0)
    current_scheme: t.ClassVar[type[BoltEncodingScheme]]

    SCHEME_VERSION: t.ClassVar[SchemeVersion] = None  # type: ignore[assignment]
    COMPATIBLE_SCHEME_VERSIONS: t.ClassVar[tuple[SchemeMajorVersion, ...]] = ()

    def __init_subclass__(cls: type[t.Self], **kwargs: t.Any) -> None:
        scheme_ver = cls.SCHEME_VERSION
        scheme_major_ver = SchemeMajorVersion(scheme_ver.major)
        if not isinstance(scheme_ver, SchemeVersion):
            raise TypeError(
                "PROTOCOL_VERSION must be a SchemeVersion, found "
                f"{scheme_ver!r} for {cls.__name__}"
            )
        if scheme_major_ver in BoltEncodingScheme.known_schemes:
            cls_conflict = BoltEncodingScheme.known_schemes[scheme_major_ver]
            raise TypeError(
                f"Multiple classes for the same scheme version "
                f"{scheme_ver}: {cls}, {cls_conflict}"
            )
        BoltEncodingScheme.max_supported_major = max(
            BoltEncodingScheme.max_supported_major, scheme_major_ver
        )
        compatible_scheme_vers = cls.COMPATIBLE_SCHEME_VERSIONS
        if not isinstance(compatible_scheme_vers, tuple) or not all(
            isinstance(v, SchemeMajorVersion) for v in compatible_scheme_vers
        ):
            raise TypeError(
                "COMPATIBLE_SCHEME_VERSIONS must be a "
                "tuple[SchemeMajorVersion, ...], found "
                f"{compatible_scheme_vers!r} for {cls.__name__}"
            )
        for compatible_ver in compatible_scheme_vers:
            if compatible_ver.major >= scheme_ver.major:
                raise ValueError(
                    f"Compatible scheme version {compatible_ver} must be "
                    f"older than scheme version {scheme_ver}. {cls.__name__} "
                    "does not fulfill this requirement."
                )
            found_compat_scheme = cls.back_compat_schemes.get(compatible_ver)
            if found_compat_scheme is None:
                BoltEncodingScheme.back_compat_schemes[compatible_ver] = cls
                continue
            if scheme_ver < found_compat_scheme.SCHEME_VERSION:
                # oldest scheme wins
                BoltEncodingScheme.back_compat_schemes[compatible_ver] = cls
        BoltEncodingScheme.known_schemes[scheme_major_ver] = cls
        super().__init_subclass__(**kwargs)

    @staticmethod
    def decode(
        data: bytes | bytearray, received_version: SchemeVersion, /
    ) -> object:
        cls = BoltEncodingScheme
        received_major_ver = SchemeMajorVersion(received_version.major)
        if received_major_ver > cls.max_supported_major:
            # TODO: Properly fill fields!
            return UnsupportedType._new("TODO", (0, 0), "TODO")
        scheme = cls.known_schemes.get(received_major_ver)
        if scheme is not None:
            if scheme.SCHEME_VERSION.minor < received_version.minor:
                # TODO: Properly fill fields!
                return UnsupportedType._new("TODO", (0, 0), "TODO")
            value = scheme._decode(data, received_version.minor)
        else:
            scheme = cls.back_compat_schemes.get(received_major_ver)
        if scheme is not None:
            value = scheme._decode_compat(data, received_version)
        else:
            # TODO: Properly fill fields!
            return UnsupportedType._new("TODO", (0, 0), "TODO")
        type_baseline = scheme.type_baseline(value)
        if type_baseline > received_version:
            # TODO: Properly fill fields!
            return UnsupportedType._new("TODO", (0, 0), "TODO")
        return value

    @classmethod
    @abc.abstractmethod
    def _decode(
        cls, data: bytes | bytearray, minor_version: int, /
    ) -> object: ...

    @classmethod
    @abc.abstractmethod
    def _decode_compat(
        cls, data: bytes | bytearray, received_version: SchemeVersion, /
    ) -> object: ...

    @classmethod
    @abc.abstractmethod
    def type_baseline(cls, value: object, /) -> SchemeVersion:
        """
        Compute the required scheme version for the given type.

        The passed ``value`` is normalized. I.e., it's guaranteed to have been
        encoded and decoded.
        """
        ...

    @staticmethod
    def encode(value: object, /) -> tuple[bytes, SchemeVersion]:
        data = BoltEncodingScheme.current_scheme._encode(value)
        normalized_value = BoltEncodingScheme.current_scheme._decode(
            data, BoltEncodingScheme.current_scheme.SCHEME_VERSION.minor
        )
        baseline = BoltEncodingScheme.current_scheme.type_baseline(
            normalized_value
        )
        return bytes(data), baseline

    @classmethod
    @abc.abstractmethod
    def _encode(cls, value: object, /) -> bytes | bytearray: ...
