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
from functools import wraps

from ... import _typing as t
from ..._version import (
    MajorVersion,
    VersionTuple,
)
from ...types import UnsupportedType


if t.TYPE_CHECKING:
    P = t.ParamSpec("P")
    T = t.TypeVar("T")


__all__ = [
    "BoltEncodingScheme",
    "SchemeMajorVersion",
    "SchemeVersion",
]


class SchemeVersion(VersionTuple):
    pass


class SchemeMajorVersion(MajorVersion):
    pass


def _wrap_encoding(
    value_name: str,
) -> t.Callable[[t.Callable[P, T]], t.Callable[P, T]]:
    def decorator(func: t.Callable[P, T]) -> t.Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except (ValueError, TypeError, OverflowError) as e:
                raise type(e)(
                    f"Failed to encode {value_name} {args[0]!r}: {e}"
                ) from e

        return wrapper

    return decorator


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
        data: bytes | bytearray,
        received_version: SchemeVersion,
        /,
        *,
        received_type_name: str,
    ) -> object:
        def unsupported(msg: str) -> UnsupportedType:
            return UnsupportedType._new(
                received_type_name, received_version.version, msg
            )

        cls = BoltEncodingScheme
        received_major_ver = SchemeMajorVersion(received_version.major)
        if received_major_ver > cls.max_supported_major:
            return unsupported(
                "found future value encoding version "
                "(consider updating the driver)"
            )
        scheme = cls.known_schemes.get(received_major_ver)
        if scheme is not None:
            if scheme.SCHEME_VERSION.minor < received_version.minor:
                return unsupported(
                    "found future value encoding version "
                    "(consider updating the driver)"
                )
            value = scheme._decode(data, received_version.minor)
        else:
            scheme = cls.back_compat_schemes.get(received_major_ver)
            if scheme is not None:
                value = scheme._decode_compat(data, received_version)
            else:
                return unsupported(
                    "found unknown value encoding version "
                    "(an older driver can help to re-encrypt the value)"
                )

        type_baseline = scheme.type_baseline(value)[0]
        if type_baseline > received_version:
            return unsupported(
                "unable to decode value; the value was encoded using "
                "an older driver but this encoding version has been dropped "
                "from this driver"
                "(an older driver can help to re-encode the value)"
            )
        if type_baseline < received_version:
            return unsupported(
                "unable to decode value; the value was encoded using "
                "a newer driver but this encoding version is not supported by "
                "this driver (consider updating the driver)"
            )
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
    def type_baseline(cls, value: object, /) -> tuple[SchemeVersion, str]:
        """
        Compute the min. scheme version for ``value`` and its type name.

        The passed ``value`` is normalized. I.e., it's guaranteed to have been
        encoded and decoded.

        This is also the place where implementations may choose to reject
        certain types even when their :meth:`.encode` or :meth:`.decode`
        methods can handle them just fine.
        """
        ...

    @classmethod
    @abc.abstractmethod
    def type_baseline_aad(cls, value: object, /) -> SchemeVersion:
        """
        Compute the min. scheme version for a given aad ``value``.

        Similar to :meth:`.type_baseline`, but for AAD values.
        Implementations may choose to apply further constraints compared to
        :meth:`.type_baseline` for AAD values, e.g., to reject certain types
        that are otherwise allowed for regular values.
        """
        ...

    @staticmethod
    @_wrap_encoding("value")
    def encode(value: object, /) -> tuple[bytes, SchemeVersion, str]:
        scheme = BoltEncodingScheme.current_scheme
        data = scheme._encode(value)
        normalized_value = scheme._decode(data, scheme.SCHEME_VERSION.minor)
        baseline, type_name = scheme.type_baseline(normalized_value)
        return bytes(data), baseline, type_name

    @staticmethod
    def encode_add(value: object, /) -> tuple[bytes, SchemeVersion]:
        cls = BoltEncodingScheme
        return cls.__encode_add(value, cls.current_scheme)

    @staticmethod
    def recreate_encoded_add(
        value: object, received_version: SchemeVersion, /
    ) -> bytes:
        cls = BoltEncodingScheme
        received_major_ver = SchemeMajorVersion(received_version.major)
        if received_major_ver > cls.max_supported_major:
            cls.__raise_for_unsupported_aad_version(
                f"found future AAD encoding version {received_version} "
                "(consider updating the driver)"
            )
        scheme = cls.known_schemes.get(received_major_ver)
        if scheme is not None:
            if scheme.SCHEME_VERSION.minor < received_version.minor:
                cls.__raise_for_unsupported_aad_version(
                    f"found too old AAD encoding version {received_version} "
                    "(an older driver can help to re-encrypt the value)"
                )
        else:
            scheme = cls.back_compat_schemes.get(received_major_ver)
            if scheme is None:
                cls.__raise_for_unsupported_aad_version(
                    f"found unknown AAD encoding version {received_version} "
                    "(an older driver can help to re-encrypt the value)"
                )
        data, baseline = cls.__encode_add(value, scheme)
        if baseline > received_version:
            cls.__raise_for_unsupported_aad_version(
                "unable to recreate AAD encoding; the AAD was encoded using "
                "an older driver but this encoding version has been dropped "
                "from this driver (stored encoding version: "
                f"{received_version}, recreated encoding version: {baseline}, "
                f"value {value!r}; an older driver can help to re-encode the "
                "value)"
            )
        if baseline < received_version:
            cls.__raise_for_unsupported_aad_version(
                "unable to recreate AAD encoding; the AAD was encoded using "
                "a newer driver but this encoding version is not supported by "
                "this driver (stored encoding version: "
                f"{received_version}, recreated encoding version: {baseline}, "
                f"value {value!r}; consider updating the driver)"
            )
        return data

    @staticmethod
    @_wrap_encoding("AAD value")
    def __encode_add(
        value: object, scheme: type[BoltEncodingScheme], /
    ) -> tuple[bytes, SchemeVersion]:
        data = scheme._encode(value)
        normalized_value = scheme._decode(data, scheme.SCHEME_VERSION.minor)
        baseline = scheme.type_baseline_aad(normalized_value)
        return bytes(data), baseline

    @staticmethod
    def __raise_for_unsupported_aad_version(extra: str = "") -> t.Never:
        raise ValueError(
            "Cannot use external AAD value as it was stored with an "
            f"incompatible encoding{f': {extra}' if extra else ''}."
        )

    @classmethod
    @abc.abstractmethod
    def _encode(cls, value: object, /) -> bytes | bytearray: ...
