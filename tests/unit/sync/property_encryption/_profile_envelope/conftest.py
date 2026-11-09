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

import neo4j._sync.property_encryption.profile_envelope._impl
from neo4j import _typing as t
from neo4j._codec.encryption.struct import EncryptedStruct
from neo4j._property_encryption import profile_envelope_impl
from neo4j._property_encryption.profile_envelope_impl import MetaData
from neo4j._sync.property_encryption.profile import internal_implementer
from neo4j._sync.property_encryption.profile_envelope import (
    EncapsulatedKeyRecordRepository,
    EnvelopePropertyEncryptionProfile,
    KeyEncapsulationService,
)

from ...._mock import ReturnTrackingMock
from ....property_encryption._preview import (
    EncapsulatedKeyRecord,
    KeyEncapsulationResult,
)


if t.TYPE_CHECKING:
    import mock
    from pytest_mock import MockFixture

    from neo4j.property_encryption import (
        AadChoiceEncryption,
        KeyEncapsulationOptions,
    )


if t.TYPE_CHECKING:

    class KeyEncapsulationServiceMock(
        KeyEncapsulationService, mock.MagicMock
    ): ...


@pytest.fixture
def encapsulation_service(
    mocker: MockFixture,
) -> KeyEncapsulationServiceMock:
    fixed_meta = {"meta": "data"}

    class FakeService(KeyEncapsulationService):
        _last_key: int

        def __init__(self):
            super(KeyEncapsulationService, self).__init__()
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

    return mocker.MagicMock(wraps=FakeService())


if t.TYPE_CHECKING:

    class EncapsulatedKeyRecordRepositoryMock(
        EncapsulatedKeyRecordRepository, mock.MagicMock
    ): ...


@pytest.fixture
def repository(
    mocker: MockFixture,
) -> EncapsulatedKeyRecordRepositoryMock:
    class FakeRepository(EncapsulatedKeyRecordRepository):
        _records: dict[str, EncapsulatedKeyRecord]
        _alias_map: dict[str, str]
        _next_id: int

        def __init__(self):
            super(EncapsulatedKeyRecordRepository, self).__init__()
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

    return mocker.MagicMock(wraps=FakeRepository())


class TestingEnvelopePropertyEncryptionProfile(
    EnvelopePropertyEncryptionProfile, abc.ABC
):
    __permitted_implementer = internal_implementer
    _key_encapsulation_service: KeyEncapsulationServiceMock
    _key_repository: EncapsulatedKeyRecordRepositoryMock

    @abc.abstractmethod
    def _create_key(
        self,
        alias: str | None = None,
        /,
        *,
        key_cache: bool = True,
        alias_cache: bool = True,
    ) -> tuple[KeyEncapsulationResult, EncapsulatedKeyRecord]: ...

    @abc.abstractmethod
    def _reset_mocks(self) -> None: ...


@pytest.fixture
def profile(
    encapsulation_service: KeyEncapsulationService,
    repository: EncapsulatedKeyRecordRepository,
) -> TestingEnvelopePropertyEncryptionProfile:
    class Profile(TestingEnvelopePropertyEncryptionProfile):
        __permitted_implementer = internal_implementer

        def __init__(self, *args, **kwargs) -> None:
            if t.TYPE_CHECKING:
                super_init = (
                    TestingEnvelopePropertyEncryptionProfile.__init__
                )
            else:
                super_init = super()._without_warning.__init__
            super_init(self, *args, **kwargs)

        def _create_key(
            self,
            alias: str | None = None,
            /,
            *,
            key_cache: bool = True,
            alias_cache: bool = True,
        ) -> tuple[KeyEncapsulationResult, EncapsulatedKeyRecord]:
            key = self._key_encapsulation_service.encapsulate(None)
            record = self._key_repository.create(
                alias=alias,
                encapsulation=key.encapsulation,
                metadata=key.metadata,
            )
            if key_cache:
                self._key_cache.set(record.id, key.secret_key)
            if alias_cache and alias is not None:
                self._key_alias_cache.set(alias, record.id)
            return key, record

        def _reset_mocks(self) -> None:
            self._key_encapsulation_service.reset_mock()
            self._key_repository.reset_mock()

    return Profile(
        "profile",
        key_encapsulation_service=encapsulation_service,
        key_repository=repository,
    )


def mocked_encrypt(
    value: object,
    aad: AadChoiceEncryption,
    key: bytes,
    profile_name: str,
) -> EncryptedStruct:
    return EncryptedStruct(
        profile_type="MOCKED",
        profile_version=3,
        profile_name=profile_name,
        cipher_output=b"super secret",
        type_name=str(type(value)),
        type_encoding_scheme_major=7,
        type_encoding_scheme_minor=13,
        metadata={"encryption meta": object()},
    )


@pytest.fixture
def mocked_encrypt_primitive(mocker: MockFixture) -> ReturnTrackingMock:
    mod = profile_envelope_impl
    attr_name = "encrypt"
    attr = getattr(mod, attr_name)

    mocked = mocker.patch.object(
        mod, attr_name, new=ReturnTrackingMock(spec=attr)
    )
    mocked.side_effect = mocked_encrypt
    return mocked


@pytest.fixture
def mocked_struct_encode(mocker: MockFixture) -> ReturnTrackingMock:
    n = 0

    def call(*args, **kwargs) -> bytes:
        nonlocal n
        n += 1
        return f"encoded-{n}".encode("ascii")

    mod = neo4j._sync.property_encryption.profile_envelope._impl
    attr_name = "encode_encrypted_struct"
    attr = getattr(mod, attr_name)

    mocked = mocker.patch.object(
        mod, attr_name, new=ReturnTrackingMock(spec=attr)
    )
    mocked.side_effect = call
    return mocked


@pytest.fixture
def mocked_decrypt_primitive(mocker: MockFixture) -> ReturnTrackingMock:
    mod = profile_envelope_impl
    attr_name = "decrypt"
    attr = getattr(mod, attr_name)

    return mocker.patch.object(
        mod, attr_name, new=ReturnTrackingMock(spec=attr)
    )


@pytest.fixture
def mocked_struct_decode(mocker: MockFixture) -> ReturnTrackingMock:
    n = 0

    def call(*args, **kwargs) -> EncryptedStruct:
        nonlocal n
        n += 1
        return EncryptedStruct(
            profile_type="MOCKED",
            profile_version=3,
            profile_name="profile name",
            cipher_output=f"super secret {n}".encode("ascii"),
            type_name="mockeroony",
            type_encoding_scheme_major=7,
            type_encoding_scheme_minor=13,
            metadata={"decryption meta": object()},
        )

    mod = neo4j._sync.property_encryption.profile_envelope._impl
    attr_name = "decode_encrypted_struct"
    attr = getattr(mod, attr_name)

    mocked = mocker.patch.object(
        mod, attr_name, new=ReturnTrackingMock(spec=attr)
    )
    mocked.side_effect = call
    return mocked


@pytest.fixture
def mocked_load_metadata(mocker: MockFixture) -> ReturnTrackingMock:
    mod = profile_envelope_impl
    attr_name = "load_metadata"
    attr = getattr(mod, attr_name)

    mocked = mocker.patch.object(
        mod, attr_name, new=ReturnTrackingMock(spec=attr)
    )
    mocked.return_value = MetaData(
        key_id="key_id",
        iv=b"iv",
        aad=b"aad",
        aad_encoding_scheme_major=4,
        aad_encoding_scheme_minor=6,
    )
    return mocked
