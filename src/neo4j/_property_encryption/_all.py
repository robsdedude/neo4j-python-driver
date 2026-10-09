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

import os
from dataclasses import dataclass
from contextlib import contextmanager

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .. import _typing as t  # noqa: TC001
from .._warnings import preview
from .._codec.encryption import BoltEncodingScheme
from .._codec.encryption.struct import EncryptedStruct
from .._codec.packstream import (
    PackableBuffer,
    UnpackableBuffer,
    Structure as PackstreamStructure,
)
from .._codec.packstream.v2 import (Packer as PackStreamV2Packer, Unpacker as PackStreamV2Unpacker)


def encrypt(value: t.Any, key: bytes, aad: bytes | None) -> bytes:
    encoded_value, encoding_ver, type_name = BoltEncodingScheme.encode(value)
    cipher_output = encrypt_encoded_value(encoded_value, key, aad)
    encrypted_struct = EncryptedStruct(
        profile_type="TODO",
        profile_version=1,  # TODO
        profile_name="TODO",
        cipher_output=cipher_output,
        type_name=type_name,
        type_encoding_scheme_major=encoding_ver.major,
        type_encoding_scheme_minor=encoding_ver.minor,
        metadata={
            "iv": "TODO",
            "aad": "TODO",
        }
    )
    packstream_struct = encrypted_struct.as_packstream_structure()
    encoded_struct = encode_packstream_structure(packstream_struct)
    version_marker = b"\x01"
    return version_marker + encoded_struct


@preview("Property encryption is a preview feature.")
class AadChoice:
    """
    Represents a choice of additional authenticated data (AAD).

    The AAD helps to ensure the integrity of the encrypted data and can be used
    to bind the encrypted data to a specific context or purpose.
    The AAD can either be a specific value (``Aad(value)``), be absent
    (i.e., no AAD is being used—:meth:`.Aad.none()`), or the AAD stored
    alongside the encrypted value may be used (:meth:`.Aad.external()`).

    .. important::
        Using no AAD means that an attacker is able to swap encrypted values
        between different entities even without being able to decrypt it.

        Using the stored AAD, while providing some level of integrity, does not
        protect against the previous case either.

        Using an explicit AAD value provides the highest level of integrity
        check.

    **Property Encryption is a preview**.
    It might be changed without following the deprecation policy.
    See also https://github.com/neo4j/neo4j-python-driver/wiki/preview-features

    .. versionadded:: 6.4
    """

    _value: object

    def __init__(self, value: object) -> None:
        """Use the give ``value`` as the AAD."""
        self._value = value

    @classmethod
    def none(cls) -> t.Self:
        """Use no AAD."""
        return cls(AAD_CHOICE_NONE)

    @classmethod
    def external(cls) -> t.Self:
        """Use the AAD stored alongside the encrypted value."""
        return cls(AAD_CHOICE_USE_EXTERNAL)

    def __repr__(self) -> str:
        if self._value is AAD_CHOICE_NONE:
            return f"{self.__class__.__name__}.none()"
        if self._value is AAD_CHOICE_USE_EXTERNAL:
            return f"{self.__class__.__name__}.external()"
        return f"{self.__class__.__name__}({self._value!r})"


# TODO: when dropping support for Python 3.14, use sentinel
AAD_CHOICE_NONE = object()
AAD_CHOICE_USE_EXTERNAL = object()


@preview("Property encryption is a preview feature.")
class KeyChoice:
    """
    Represents a key choice to be used for encryption/decyrption.

    A key may either be selected by its id, or by its alias.
    Exactly one of these must be specified when creating a :class:`.KeyChoice`
    instance.

    This class is not meant to be instantiated directly, but rather through the
    provided class methods.

    :raises ValueError: if not exactly one of ``id`` or ``alias`` is specified.

    **Property Encryption is a preview**.
    It might be changed without following the deprecation policy.
    See also https://github.com/neo4j/neo4j-python-driver/wiki/preview-features

    .. versionadded:: 6.4
    """

    _id: str | None
    _alias: str | None

    @t.overload
    def __init__(self, *, id: str | None = None, alias: None = None) -> None: ...
    @t.overload
    def __init__(self, *, id: None = None, alias: str | None = None) -> None: ...
    def __init__(self, *, id: str | None = None, alias: str | None = None) -> None:
        if id is not None and alias is not None:
            raise ValueError("Cannot specify both id and alias")
        if id is None and alias is None:
            raise ValueError("Must specify either id or alias")
        self._id = id
        self._alias = alias


@contextmanager
def _wrap_decode_error(*excs: type[Exception]) -> t.Generator[None]:
    try:
        yield
    except excs as e:
        raise ValueError(
            "Failed to decode encrypted value as a packstream structure"
        ) from e


def decrypt(encrypted_data: bytes, key: bytes, aad: AadChoice) -> t.Any:
    version = encrypted_data[0]
    if version != 1:
        raise ValueError(
            f"Unsupported encrypted value encoding version: {version}"
        )
    encrypted_struct_data = encrypted_data[1:]
    with _wrap_decode_error(TypeError):
        packstream_struct = decode_packstream_structure(encrypted_struct_data)
    with _wrap_decode_error(TypeError, ValueError):
        encrypted_struct = EncryptedStruct.from_packstream_structure(packstream_struct)


def encrypt_encoded_value(data: bytes, key: bytes, aad: t.Any) -> bytes:
    assert len(key) == 256
    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    return aesgcm.encrypt(iv, data, aad)


def decrypt_encoded_value(cipher_output: bytes, iv: bytes, key: bytes, aad: bytes | None) -> bytes:
    assert len(key) == 256
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(iv, cipher_output, aad)


def encode_packstream_structure(structure: PackstreamStructure) -> bytes:
    buffer = PackableBuffer()
    packer = PackStreamV2Packer(buffer)
    packer.pack(structure)
    return bytes(buffer.data)


def decode_packstream_structure(data: bytes) -> PackstreamStructure:
    buffer = UnpackableBuffer(data)
    unpacker = PackStreamV2Unpacker(buffer)
    struct = unpacker.unpack()
    if not isinstance(struct, PackstreamStructure):
        raise TypeError(
            f"Decoded value is not a packstream structure: {type(struct)}"
        )
    return struct
