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

from contextlib import contextmanager

from .. import _typing as t  # noqa: TC001
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


__all__ = [
    "decode_encrypted_struct",
    "encode_encrypted_struct",
]


def encode_encrypted_struct(encrypted_struct: EncryptedStruct) -> bytes:
    packstream_struct = encrypted_struct.as_packstream_structure()
    encoded_struct = _encode_packstream_structure(packstream_struct)
    version_marker = b"\x01"
    return version_marker + encoded_struct


@contextmanager
def _wrap_decode_error(*excs: type[Exception]) -> t.Generator[None]:
    try:
        yield
    except excs as e:
        raise ValueError(
            "Failed to decode encrypted value as a packstream structure"
        ) from e


def decode_encrypted_struct(encrypted_data: bytes) -> EncryptedStruct:
    version = encrypted_data[0]
    if version != 1:
        raise ValueError(
            f"Unsupported encrypted value encoding version: {version}"
        )
    encrypted_struct_data = encrypted_data[1:]
    with _wrap_decode_error(TypeError):
        packstream_struct = _decode_packstream_structure(encrypted_struct_data)
    with _wrap_decode_error(TypeError, ValueError):
        return EncryptedStruct.from_packstream_structure(packstream_struct)


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
