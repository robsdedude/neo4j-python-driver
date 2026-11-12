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

import re

import pytest

from neo4j import _typing as t
from neo4j._async.property_encryption.profile_envelope import (
    AsyncEncapsulatedKeyManager,
    ProfileWrapper,
)
from neo4j._property_encryption.profile_envelope import KeyEncapsulationOptions
from neo4j.exceptions import PropertyEncryptionError

from ....._async_compat import mark_async_test


if t.TYPE_CHECKING:
    from neo4j._property_encryption.profile_envelope import EncapsulatedKey

    from ....property_encryption._preview import EncapsulatedKeyRecord
    from .conftest import AsyncTestingEnvelopePropertyEncryptionProfile


KEY_ALIAS = "key-alias"
OLD_KEY_ALIAS = "old-key-alias"
NEW_KEY_ALIAS = "new-key-alias"


@pytest.fixture
def key_manager(
    async_profile: AsyncTestingEnvelopePropertyEncryptionProfile,
) -> AsyncEncapsulatedKeyManager:
    return AsyncEncapsulatedKeyManager(_profile=ProfileWrapper(async_profile))


def assert_key_matches_record(
    key: EncapsulatedKey, record: EncapsulatedKeyRecord
) -> None:
    assert key.id == record.id
    assert key.alias == record.alias


@pytest.mark.parametrize("alias", (None, KEY_ALIAS))
@mark_async_test
async def test_create(
    alias: str | None,
    async_profile: AsyncTestingEnvelopePropertyEncryptionProfile,
    key_manager: AsyncEncapsulatedKeyManager,
) -> None:
    encap_service = async_profile._key_encapsulation_service
    key_repo = async_profile._key_repository
    options = t.cast(KeyEncapsulationOptions, object())

    key = await key_manager.create(alias=alias, options=options)

    encap_service.encapsulate.assert_awaited_once_with(  # type: ignore[attr-defined]
        options
    )
    encapsulation_result = (
        encap_service.encapsulate.call_return_values[0]  # type: ignore[attr-defined]
    )
    key_repo.create.assert_awaited_once_with(  # type: ignore[attr-defined]
        alias,
        encapsulation_result.encapsulation,
        encapsulation_result.metadata,
    )
    key_record = key_repo.create.call_return_values[0]  # type: ignore[attr-defined]
    if alias is not None:
        assert async_profile._key_alias_cache.get(alias) == key_record.id
    assert (
        async_profile._key_cache.get(key_record.id)
        == encapsulation_result.secret_key
    )
    assert_key_matches_record(key, key_record)


@pytest.mark.parametrize("key_cache_hit", (True, False))
@pytest.mark.parametrize("alias_cache_hit", (True, False))
@mark_async_test
async def test_find_by_alias(
    key_cache_hit: bool,
    alias_cache_hit: bool,
    async_profile: AsyncTestingEnvelopePropertyEncryptionProfile,
    key_manager: AsyncEncapsulatedKeyManager,
) -> None:
    key_result, key_record = await async_profile._create_key(
        KEY_ALIAS,
        key_cache=key_cache_hit,
        alias_cache=alias_cache_hit,
    )
    async_profile._reset_mocks()
    encap_service = async_profile._key_encapsulation_service
    key_repo = async_profile._key_repository

    key = await key_manager.find_by_alias(KEY_ALIAS)

    assert key is not None
    assert_key_matches_record(key, key_record)
    if alias_cache_hit:
        key_repo.assert_not_called()
        encap_service.assert_not_called()
        expected_cached_key = key_result.secret_key if key_cache_hit else None
    else:
        key_repo.find_by_alias.assert_awaited_once_with(  # type: ignore[attr-defined]
            KEY_ALIAS
        )
        key_repo.find_by_id.assert_not_called()  # type: ignore[attr-defined]
        encap_service.decapsulate.assert_awaited_once_with(  # type: ignore[attr-defined]
            key_record.encapsulation, key_record.metadata
        )
        expected_cached_key = key_result.secret_key
    assert async_profile._key_cache.get(key_record.id) == expected_cached_key
    assert async_profile._key_alias_cache.get(KEY_ALIAS) == key_record.id


@mark_async_test
async def test_find_by_alias_not_found(
    async_profile: AsyncTestingEnvelopePropertyEncryptionProfile,
    key_manager: AsyncEncapsulatedKeyManager,
) -> None:
    encap_service = async_profile._key_encapsulation_service
    key_repo = async_profile._key_repository

    key = await key_manager.find_by_alias(KEY_ALIAS)

    assert key is None
    key_repo.find_by_alias.assert_awaited_once_with(  # type: ignore[attr-defined]
        KEY_ALIAS
    )
    encap_service.decapsulate.assert_not_called()  # type: ignore[attr-defined]
    key_repo.create.assert_not_called()  # type: ignore[attr-defined]
    assert async_profile._key_alias_cache.get(KEY_ALIAS) is None


@pytest.mark.parametrize("old_alias", (None, OLD_KEY_ALIAS))
@mark_async_test
async def test_set_alias_by_id(
    old_alias: str | None,
    async_profile: AsyncTestingEnvelopePropertyEncryptionProfile,
    key_manager: AsyncEncapsulatedKeyManager,
) -> None:
    key_result, key_record = await async_profile._create_key(old_alias)
    async_profile._reset_mocks()
    encap_service = async_profile._key_encapsulation_service
    key_repo = async_profile._key_repository

    await key_manager.set_alias_by_id(id=key_record.id, alias=NEW_KEY_ALIAS)

    key_repo.set_alias_by_id.assert_awaited_once_with(  # type: ignore[attr-defined]
        key_record.id, NEW_KEY_ALIAS
    )
    encap_service.assert_not_called()
    assert async_profile._key_cache.get(key_record.id) == key_result.secret_key
    assert async_profile._key_alias_cache.get(OLD_KEY_ALIAS) is None
    assert async_profile._key_alias_cache.get(NEW_KEY_ALIAS) == key_record.id


@mark_async_test
async def test_set_alias_by_missing_id(
    async_profile: AsyncTestingEnvelopePropertyEncryptionProfile,
    key_manager: AsyncEncapsulatedKeyManager,
) -> None:
    key_id = "missing-key-id"
    encap_service = async_profile._key_encapsulation_service
    key_repo = async_profile._key_repository

    with pytest.raises(PropertyEncryptionError) as exc_info:
        await key_manager.set_alias_by_id(id=key_id, alias=NEW_KEY_ALIAS)

    err_str = str(exc_info.value).lower()
    assert "failed to set encapsulated key alias" in err_str
    cause = exc_info.value.__cause__
    assert isinstance(cause, KeyError)
    assert re.search(re.escape(repr(key_id)), str(cause))

    key_repo.set_alias_by_id.assert_awaited_once_with(  # type: ignore[attr-defined]
        key_id, NEW_KEY_ALIAS
    )
    encap_service.assert_not_called()
    assert async_profile._key_cache.get(key_id) is None
    assert async_profile._key_alias_cache.get(NEW_KEY_ALIAS) is None


@pytest.mark.parametrize("alias", (None, KEY_ALIAS))
@mark_async_test
async def test_delete_alias_by_id(
    alias: str | None,
    async_profile: AsyncTestingEnvelopePropertyEncryptionProfile,
    key_manager: AsyncEncapsulatedKeyManager,
) -> None:
    key_result, key_record = await async_profile._create_key(alias)
    async_profile._reset_mocks()
    encap_service = async_profile._key_encapsulation_service
    key_repo = async_profile._key_repository

    await key_manager.delete_alias_by_id(key_record.id)

    key_repo.set_alias_by_id.assert_awaited_once_with(  # type: ignore[attr-defined]
        key_record.id, None
    )
    encap_service.assert_not_called()
    assert async_profile._key_cache.get(key_record.id) == key_result.secret_key
    if alias is not None:
        assert async_profile._key_alias_cache.get(alias) is None


@mark_async_test
async def test_delete_alias_by_missing_id(
    async_profile: AsyncTestingEnvelopePropertyEncryptionProfile,
    key_manager: AsyncEncapsulatedKeyManager,
) -> None:
    key_id = "missing-key-id"
    encap_service = async_profile._key_encapsulation_service
    key_repo = async_profile._key_repository

    with pytest.raises(PropertyEncryptionError) as exc_info:
        await key_manager.delete_alias_by_id(key_id)

    err_str = str(exc_info.value).lower()
    assert "failed to delete encapsulated key alias" in err_str
    cause = exc_info.value.__cause__
    assert isinstance(cause, KeyError)
    assert re.search(re.escape(repr(key_id)), str(cause))

    key_repo.set_alias_by_id.assert_awaited_once_with(  # type: ignore[attr-defined]
        key_id, None
    )
    encap_service.assert_not_called()
    assert async_profile._key_cache.get(key_id) is None


@pytest.mark.parametrize("alias", (None, KEY_ALIAS))
@mark_async_test
async def test_delete_by_id(
    alias: str | None,
    async_profile: AsyncTestingEnvelopePropertyEncryptionProfile,
    key_manager: AsyncEncapsulatedKeyManager,
) -> None:
    _, key_record = await async_profile._create_key(alias)
    async_profile._reset_mocks()
    encap_service = async_profile._key_encapsulation_service
    key_repo = async_profile._key_repository

    await key_manager.delete_by_id(key_record.id)

    key_repo.delete_by_id.assert_awaited_once_with(  # type: ignore[attr-defined]
        key_record.id
    )
    encap_service.assert_not_called()
    assert async_profile._key_cache.get(key_record.id) is None
    if alias is not None:
        assert async_profile._key_alias_cache.get(alias) is None


@mark_async_test
async def test_delete_by_missing_id(
    async_profile: AsyncTestingEnvelopePropertyEncryptionProfile,
    key_manager: AsyncEncapsulatedKeyManager,
) -> None:
    key_id = "missing-key-id"
    encap_service = async_profile._key_encapsulation_service
    key_repo = async_profile._key_repository

    with pytest.raises(PropertyEncryptionError) as exc_info:
        await key_manager.delete_by_id(key_id)

    err_str = str(exc_info.value).lower()
    assert "failed to delete encapsulated key" in err_str
    cause = exc_info.value.__cause__
    assert isinstance(cause, KeyError)
    assert re.search(re.escape(repr(key_id)), str(cause))

    key_repo.delete_by_id.assert_awaited_once_with(  # type: ignore[attr-defined]
        key_id
    )
    encap_service.assert_not_called()
    assert async_profile._key_cache.get(key_id) is None
