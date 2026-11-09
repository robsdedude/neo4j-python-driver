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

import pytest

from neo4j import _typing as t
from neo4j._sync.property_encryption.profile_envelope import (
    decrypt,
    encrypt,
)

from ....._async_compat import mark_sync_test
from ....property_encryption._preview import (
    AadChoiceDecryption,
    AadChoiceEncryption,
    KeyChoice,
)


if t.TYPE_CHECKING:
    from ...._mock import ReturnTrackingMock
    from .conftest import TestingEnvelopePropertyEncryptionProfile


KEY_ALIAS = "key-alias"


@pytest.mark.parametrize("by_alias", (True, False))
@pytest.mark.parametrize("key_cache_hit", (True, False))
@pytest.mark.parametrize("alias_cache_hit", (True, False))
@mark_sync_test
def test_encrypt(
    by_alias: bool,
    key_cache_hit: bool,
    alias_cache_hit: bool,
    profile: TestingEnvelopePropertyEncryptionProfile,
    mocked_encrypt_primitive: ReturnTrackingMock,
    mocked_struct_encode: ReturnTrackingMock,
) -> None:
    encap_service = profile._key_encapsulation_service
    key_repo = profile._key_repository
    key, key_record = profile._create_key(
        KEY_ALIAS if by_alias else None,
        key_cache=key_cache_hit,
        alias_cache=alias_cache_hit,
    )
    profile._reset_mocks()

    value = object()
    aad = t.cast(AadChoiceEncryption, object())
    key_choice = (
        KeyChoice(alias=KEY_ALIAS) if by_alias else KeyChoice(id=key_record.id)
    )
    encypted = encrypt(value, aad, key_choice, profile)

    mocked_encrypt_primitive.assert_called_once_with(
        value, aad, key.secret_key, profile.name
    )
    struct = mocked_encrypt_primitive.call_return_values[0]
    mocked_struct_encode.assert_called_once_with(struct)
    assert encypted is mocked_struct_encode.call_return_values[0]
    expect_key_from_cache = alias_cache_hit if by_alias else key_cache_hit
    if expect_key_from_cache:
        encap_service.assert_not_called()
        key_repo.assert_not_called()
    else:
        if by_alias:
            key_repo.find_by_alias.assert_called_once_with(KEY_ALIAS)  # type: ignore[attr-defined]
        else:
            key_repo.find_by_id.assert_called_once_with(key_record.id)  # type: ignore[attr-defined]
        encap_service.decapsulate.assert_called_once_with(  # type: ignore[attr-defined]
            key.encapsulation, key.metadata
        )


@pytest.mark.parametrize("key_cache_hit", (True, False))
@pytest.mark.parametrize("alias_cache_hit", (True, False))
@mark_sync_test
def test_decrypt(
    key_cache_hit: bool,
    alias_cache_hit: bool,
    profile: TestingEnvelopePropertyEncryptionProfile,
    mocked_decrypt_primitive: ReturnTrackingMock,
    mocked_struct_decode: ReturnTrackingMock,
    mocked_load_metadata: ReturnTrackingMock,
) -> None:
    encap_service = profile._key_encapsulation_service
    key_repo = profile._key_repository
    key, key_record = profile._create_key(
        KEY_ALIAS,
        key_cache=key_cache_hit,
        alias_cache=alias_cache_hit,
    )
    mocked_load_metadata.return_value["key_id"] = key_record.id
    profile._reset_mocks()

    value = t.cast(bytes, object())
    aad = t.cast(AadChoiceDecryption, object())
    decrypted = decrypt(value, aad, profile)

    assert decrypted is mocked_decrypt_primitive.call_return_values[0]
    mocked_struct_decode.assert_called_once_with(value)
    decoded_struct = mocked_struct_decode.call_return_values[0]
    mocked_load_metadata.assert_called_once_with(decoded_struct.metadata)
    metadata = mocked_load_metadata.call_return_values[0]
    if key_cache_hit:
        encap_service.assert_not_called()
        key_repo.assert_not_called()
    else:
        key_repo.find_by_id.assert_called_once_with(metadata["key_id"])  # type: ignore[attr-defined]
        encap_service.decapsulate.assert_called_once_with(  # type: ignore[attr-defined]
            key.encapsulation, key.metadata
        )
    mocked_decrypt_primitive.assert_called_once_with(
        decoded_struct, metadata, aad, profile.name, key.secret_key
    )


# TODO:
#  * Test encrypt using non-existing key id
#  * Test encrypt using non-existing key alias
#  * Test decrypt using non-existing key id
