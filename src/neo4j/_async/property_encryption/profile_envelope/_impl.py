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

from .... import _typing as t
from ...._property_encryption import profile_envelope_impl
from ...._property_encryption.impl import (
    decode_encrypted_struct,
    encode_encrypted_struct,
)


if t.TYPE_CHECKING:
    from ...._property_encryption.api import (
        AadChoiceDecryption,
        AadChoiceEncryption,
        KeyChoice,
    )
    from ...._property_encryption.profile_envelope import EncapsulatedKeyRecord
    from ._profile import AsyncEnvelopePropertyEncryptionProfile


__all__ = [
    "decrypt",
    "encrypt",
]


async def encrypt(
    value: object,
    aad: AadChoiceEncryption,
    key_choice: KeyChoice,
    profile: AsyncEnvelopePropertyEncryptionProfile,
) -> bytes:
    key = await _get_key(profile, key_choice)
    struct = profile_envelope_impl.encrypt(value, aad, key, profile.name)
    return encode_encrypted_struct(struct)


async def decrypt(
    value: bytes,
    aad: AadChoiceDecryption,
    profile: AsyncEnvelopePropertyEncryptionProfile,
) -> t.Any:
    struct = decode_encrypted_struct(value)
    metadata = profile_envelope_impl.load_metadata(struct.metadata)
    key = await _get_key_by_id(profile, metadata["key_id"])
    return profile_envelope_impl.decrypt(
        struct, metadata, aad, profile.name, key
    )


async def _get_key(
    profile: AsyncEnvelopePropertyEncryptionProfile, key_choice: KeyChoice
) -> bytes:
    if key_choice._alias is not None:
        return await _get_key_by_alias(profile, key_choice._alias)
    assert key_choice._id is not None
    return await _get_key_by_id(profile, key_choice._id)


async def _get_key_by_id(
    profile: AsyncEnvelopePropertyEncryptionProfile, key_id: str
) -> bytes:
    decap_key = profile._key_cache.get(key_id)
    if decap_key is not None:
        return decap_key
    return await _load_key_by_id(profile, key_id)


async def _get_key_by_alias(
    profile: AsyncEnvelopePropertyEncryptionProfile, alias: str
) -> bytes:
    key_id = profile._key_alias_cache.get(alias)
    if key_id is not None:
        return await _load_key_by_id(profile, key_id)
    else:
        return await _load_key_by_alias(profile, alias)


async def _load_key_by_id(
    profile: AsyncEnvelopePropertyEncryptionProfile, key_id: str
) -> bytes:
    key_repository = profile._key_repository
    encap_key = await key_repository.find_by_id(key_id)
    if encap_key is None:
        profile._key_cache.forget(key_id)
        profile._key_alias_cache.forget_value(key_id)
        raise KeyError(f"Key not found by id {key_id!r}.")
    return await _decapsulate_key(profile, encap_key)


async def _load_key_by_alias(
    profile: AsyncEnvelopePropertyEncryptionProfile, alias: str
) -> bytes:
    key_repository = profile._key_repository
    encap_key = await key_repository.find_by_alias(alias)
    if encap_key is None:
        profile._key_alias_cache.forget(alias)
        raise KeyError(f"Key not found by alias {alias!r}.")
    return await _decapsulate_key(profile, encap_key)


async def _decapsulate_key(
    profile: AsyncEnvelopePropertyEncryptionProfile, key: EncapsulatedKeyRecord
) -> bytes:
    if key.alias is not None:
        profile._key_alias_cache.set(key.alias, key.id)
    service = profile._key_encapsulation_service
    decap_key = await service.decapsulate(key.encapsulation, key.metadata)
    profile._key_cache.set(key.id, decap_key)
    return decap_key
