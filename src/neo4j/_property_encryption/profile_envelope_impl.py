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
from contextlib import contextmanager
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .. import _typing as t
from .._codec.encryption import (
    BoltEncodingScheme,
    SchemeVersion,
)
from .._codec.encryption.struct import EncryptedStruct
from .._codec.packstream import (
    PackableBuffer,
    Structure as PackstreamStructure,
    UnpackableBuffer,
)
from .._codec.packstream.v2 import (
    Packer as PackStreamV2Packer,
    Unpacker as PackStreamV2Unpacker,
)
from .api import (
    AAD_CHOICE_NONE,
    AAD_CHOICE_USE_EXTERNAL,
    AadChoiceDecryption,
    AadChoiceEncryption,
)


if t.TYPE_CHECKING:
    T = t.TypeVar("T")


PROFILE_NAME = "ENVELOPE"
PROFILE_VERSION = 1


__all__ = [
    "MetaData",
    "decrypt",
    "encrypt",
    "load_metadata",
]


class MetaData(t.TypedDict):
    key_id: str
    iv: bytes
    aad: bytes
    aad_encoding_scheme_major: int
    aad_encoding_scheme_minor: int


def load_metadata(data: dict[str, object]) -> MetaData:
    key_id = _get_meta(str, data, "key_id")
    iv = _get_meta(bytes, data, "iv")
    aad = _get_meta(bytes, data, "aad")
    if (
        "aad_encoding_scheme_major" in data
        or "aad_encoding_scheme_minor" in data
    ):
        aad_encoding_scheme_major = _get_meta(
            int, data, "aad_encoding_scheme_major"
        )
        aad_encoding_scheme_minor = _get_meta(
            int, data, "aad_encoding_scheme_minor"
        )
    else:
        current = BoltEncodingScheme.current_scheme.SCHEME_VERSION
        aad_encoding_scheme_major = current.major
        aad_encoding_scheme_minor = current.minor
    return MetaData(
        key_id=key_id,
        iv=iv,
        aad=aad,
        aad_encoding_scheme_major=aad_encoding_scheme_major,
        aad_encoding_scheme_minor=aad_encoding_scheme_minor,
    )


def _get_meta(typ: type[T], metadata: dict[str, object], key: str) -> T:
    if key not in metadata:
        raise ValueError(f"Encrypted value does not contain {key!r} metadata.")
    value = metadata[key]
    if not isinstance(value, typ):
        raise TypeError(
            f"Encrypted value contains invalid {key!r} metadata: "
            f"{type(value)} (expected {typ})."
        )
    return value


def encrypt(
    value: object,
    aad: AadChoiceEncryption,
    key: bytes,
    profile_name: str,
) -> EncryptedStruct:
    value_enc, value_enc_ver, type_name = BoltEncodingScheme.encode(value)
    metadata: dict[str, object] = {}
    encdoed_aad = b""
    if aad._value != AAD_CHOICE_NONE:
        encdoed_aad, add_enc_ver = BoltEncodingScheme.encode_add(aad._value)
        metadata["aad"] = encdoed_aad
        metadata["aad_encoding_scheme_major"] = add_enc_ver.major
        metadata["aad_encoding_scheme_minor"] = add_enc_ver.minor
    encryption_res = _encrypt_encoded_value(value_enc, key, encdoed_aad)
    return EncryptedStruct(
        profile_type=PROFILE_NAME,
        profile_version=PROFILE_VERSION,
        profile_name=profile_name,
        cipher_output=encryption_res.cipher_output,
        type_name=type_name,
        type_encoding_scheme_major=value_enc_ver.major,
        type_encoding_scheme_minor=value_enc_ver.minor,
        metadata=metadata,
    )


@contextmanager
def _wrap_decode_error(*excs: type[Exception]) -> t.Generator[None]:
    try:
        yield
    except excs as e:
        raise ValueError(
            "Failed to decode encrypted value as a packstream structure"
        ) from e


def decrypt(
    encrypted_struct: EncryptedStruct,
    metadata: MetaData,
    aad_choice: AadChoiceDecryption,
    profile_name: str,
    key: bytes,
) -> t.Any:
    if encrypted_struct.profile_type != PROFILE_NAME:
        raise ValueError(
            "Unsupported property encryption profile type: "
            f"{encrypted_struct.profile_type!r} (expected {PROFILE_NAME!r})."
        )
    if encrypted_struct.profile_version != PROFILE_VERSION:
        raise ValueError(
            "Unsupported property encryption profile version: "
            f"{encrypted_struct.profile_version}."
        )
    if encrypted_struct.profile_name != profile_name:
        raise ValueError(
            "Encrypted value was encrypted with a different property "
            f"encryption profile: {encrypted_struct.profile_name!r} "
            f"(user expected {profile_name!r})."
        )
    iv = metadata["iv"]
    aad = _recreate_aad(aad_choice, metadata)
    encrypted_value = encrypted_struct.cipher_output
    encoded_value = _decrypt_encoded_value(encrypted_value, iv, key, aad)
    received_version = SchemeVersion(
        encrypted_struct.type_encoding_scheme_major,
        encrypted_struct.type_encoding_scheme_minor,
    )
    received_type_name = encrypted_struct.type_name
    return BoltEncodingScheme.decode(
        encoded_value,
        received_version,
        received_type_name=received_type_name,
    )


@dataclass
class _EncryptionResult:
    cipher_output: bytes
    iv: bytes


def _encrypt_encoded_value(
    data: bytes, key: bytes, aad: bytes | None
) -> _EncryptionResult:
    if len(key) != 256:
        raise ValueError(f"Invalid key length: {len(key)} (must be 256).")
    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    cipher_output = aesgcm.encrypt(iv, data, aad)
    return _EncryptionResult(cipher_output=cipher_output, iv=iv)


def _decrypt_encoded_value(
    cipher_output: bytes, iv: bytes, key: bytes, aad: bytes | None
) -> bytes:
    if len(key) != 256:
        raise ValueError(f"Invalid key length: {len(key)} (must be 256).")
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(iv, cipher_output, aad)


def _encode_packstream_structure(structure: PackstreamStructure) -> bytes:
    buffer = PackableBuffer()
    packer = PackStreamV2Packer(buffer)
    packer.pack(structure)
    return bytes(buffer.data)


def _decode_packstream_structure(data: bytes) -> PackstreamStructure:
    buffer = UnpackableBuffer(data)
    unpacker = PackStreamV2Unpacker(buffer)
    struct = unpacker.unpack()
    if not isinstance(struct, PackstreamStructure):
        raise TypeError(
            f"Decoded value is not a packstream structure: {type(struct)}"
        )
    return struct


def _recreate_aad(
    aad_choice: AadChoiceDecryption, metadata: MetaData
) -> bytes | None:
    meta_aad = metadata["aad"]
    if aad_choice._value == AAD_CHOICE_USE_EXTERNAL:
        return meta_aad
    aad_version = SchemeVersion(
        metadata.get("aad_encoding_scheme_major"),
        metadata.get("aad_encoding_scheme_minor"),
    )
    return BoltEncodingScheme.recreate_encoded_add(meta_aad, aad_version)
