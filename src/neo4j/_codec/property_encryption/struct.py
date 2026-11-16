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

import dataclasses

from ... import _typing as t  # noqa: TC001
from ..packstream import Structure as PackstreamStructure


__all__ = [
    "EncryptedStruct",
]


@dataclasses.dataclass
class EncryptedStruct:
    profile_type: str
    profile_version: int
    profile_name: str
    cipher_output: bytes
    type_name: str
    type_encoding_scheme_major: int
    type_encoding_scheme_minor: int
    metadata: dict[str, object]

    def __post_init__(self) -> None:
        sorted_metadata = {}
        keys = sorted(self.metadata.keys(), key=lambda x: x.encode("utf-8"))
        for key in keys:
            sorted_metadata[key] = self.metadata[key]
        self.metadata = sorted_metadata

    def as_packstream_structure(self) -> PackstreamStructure:
        return PackstreamStructure(
            b"e",
            self.profile_type,
            self.profile_version,
            self.profile_name,
            self.cipher_output,
            self.type_name,
            self.type_encoding_scheme_major,
            self.type_encoding_scheme_minor,
            self.metadata,
        )

    @classmethod
    def from_packstream_structure(
        cls, structure: PackstreamStructure
    ) -> t.Self:
        if structure.tag != b"e":
            hex_tag = structure.tag.hex().upper()
            raise ValueError(f"Invalid structure tag: {hex_tag}")
        if len(structure) != 8:
            raise ValueError(f"Invalid structure length: {len(structure)}")
        (
            profile_type,
            profile_version,
            profile_name,
            cipher_output,
            type_name,
            type_encoding_scheme_major,
            type_encoding_scheme_minor,
            metadata,
        ) = structure.fields
        if not isinstance(profile_type, str):
            raise TypeError(f"Invalid profile_type: {profile_type}")
        if not isinstance(profile_version, int):
            raise TypeError(f"Invalid profile_version: {profile_version}")
        if not isinstance(profile_name, str):
            raise TypeError(f"Invalid profile_name: {profile_name}")
        if not isinstance(cipher_output, bytes):
            raise TypeError(f"Invalid cipher_output: {cipher_output}")
        if not isinstance(type_name, str):
            raise TypeError(f"Invalid type_name: {type_name}")
        if not isinstance(type_encoding_scheme_major, int):
            raise TypeError(
                "Invalid type_encoding_scheme_major: "
                f"{type_encoding_scheme_major}"
            )
        if not isinstance(type_encoding_scheme_minor, int):
            raise TypeError(
                "Invalid type_encoding_scheme_minor: "
                f"{type_encoding_scheme_minor}"
            )
        if not isinstance(metadata, dict):
            raise TypeError(f"Invalid metadata: {metadata}")
        if not all(isinstance(k, str) for k in metadata):
            raise TypeError(f"Invalid metadata: {metadata}")
        return cls(
            profile_type,
            profile_version,
            profile_name,
            cipher_output,
            type_name,
            type_encoding_scheme_major,
            type_encoding_scheme_minor,
            metadata,
        )
