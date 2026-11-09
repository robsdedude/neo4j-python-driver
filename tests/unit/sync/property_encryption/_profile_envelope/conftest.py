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
import struct

import pytest

from neo4j import _typing as t
from neo4j._sync.property_encryption.profile_envelope import (
    EncapsulatedKeyRecordRepository,
    EnvelopePropertyEncryptionProfile,
    KeyEncapsulationService,
)
from neo4j.property_encryption import (
    EncapsulatedKeyRecord,
    KeyEncapsulationResult,
)


if t.TYPE_CHECKING:
    from pytest_mock import MockFixture

    from neo4j.property_encryption import (
        AadChoiceDecryption,
        AadChoiceEncryption,
        KeyChoice,
        KeyEncapsulationOptions,
    )


class TestingEnvelopePropertyEncryptionProfile(
    EnvelopePropertyEncryptionProfile, abc.ABC
):
    @abc.abstractmethod
    def _create_key(
        self,
        alias: str | None = None,
        key_cache: bool = True,
        alias_cache: bool = True,
    ) -> EncapsulatedKeyRecord: ...


@pytest.fixture
def encapsulation_service(
    mocker: MockFixture,
) -> KeyEncapsulationService:
    fixed_meta = {"meta": "data"}

    class FakeService(KeyEncapsulationService):
        _last_key: int

        def __init__(self):
            super().__init__()
            self._last_key = 0

        def encapsulate(
            self, options: KeyEncapsulationOptions | None
        ) -> KeyEncapsulationResult:
            key = b"\x00" * 248 + struct.pack(">Q", self._last_key)
            encapsulation = b"enc-" + struct.pack(">Q", self._last_key)
            self._last_key += 1
            return KeyEncapsulationResult(
                encapsulation=encapsulation,
                metadata=fixed_meta,
                secret_key=key,
            )

        def decapsulate(
            self, encapsulation: bytes, metadata: t.Mapping[str, str]
        ) -> bytes:
            assert encapsulation.startswith(b"enc-")
            assert metadata == fixed_meta
            key = encapsulation[4:]
            assert len(key) == 8
            return b"\x00" * 248 + key

    return mocker.Mock(warps=FakeService())


@pytest.fixture
def repository(
    mocker: MockFixture,
) -> EncapsulatedKeyRecordRepository:
    class FakeRepository(EncapsulatedKeyRecordRepository):
        _records: dict[str, EncapsulatedKeyRecord]
        _alias_map: dict[str, str]
        _next_id: int

        def __init__(self):
            super().__init__()
            self._records = {}
            self._alias_map = {}
            self._next_id = 1

        def find_by_id(self, id: str) -> EncapsulatedKeyRecord | None:
            return self._records.get(id)

        def find_by_alias(
            self, alias: str
        ) -> EncapsulatedKeyRecord | None:
            id = self._alias_map.get(alias)
            if id is None:
                return None
            return self._records.get(id)

        def create(
            self,
            alias: str | None,
            encapsulation: bytes,
            metadata: t.Mapping[str, str],
        ) -> EncapsulatedKeyRecord:
            id_ = f"key-{self._next_id:04d}"
            record = EncapsulatedKeyRecord(
                id=id_,
                alias=alias,
                encapsulation=encapsulation,
                metadata=metadata,
            )
            self._records[id_] = record
            if alias is not None:
                self._alias_map[alias] = id_
            return record

        def set_alias_by_id(self, id: str, alias: str | None) -> None:
            record = self._records.get(id)
            if record is None:
                raise KeyError(f"Key not found by id {id!r}.")
            if alias is not None:
                if alias in self._alias_map:
                    raise ValueError(f"Alias {alias!r} already in use.")
                self._alias_map[alias] = id
            if record.alias is not None:
                del self._alias_map[record.alias]
            record.alias = alias

        def delete_by_id(self, id: str) -> None:
            record = self._records.pop(id, None)
            if record is None:
                raise KeyError(f"Key not found by id {id!r}.")
            if record.alias is not None:
                del self._alias_map[record.alias]

    return mocker.Mock(wraps=FakeRepository())


@pytest.fixture
def profile(
    encapsulation_service: KeyEncapsulationService,
    repository: EncapsulatedKeyRecordRepository,
) -> TestingEnvelopePropertyEncryptionProfile:
    class Profile(TestingEnvelopePropertyEncryptionProfile):
        def _create_key(
            self,
            alias: str | None = None,
            key_cache: bool = True,
            alias_cache: bool = True,
        ) -> EncapsulatedKeyRecord:
            key = self._key_encapsulation_service.encapsulate(None)
            record = self._key_repository.create(
                alias=alias,
                encapsulation=key.encapsulation,
                metadata=key.metadata,
            )
            if alias_cache and alias is not None:
                self._key_alias_cache.set(alias, record.id)
            if key_cache:
                self._key_cache.set(record.id, key.secret_key)
            return record

    return Profile(
        "profile",
        key_encapsulation_service=encapsulation_service,
        key_repository=repository,
    )
