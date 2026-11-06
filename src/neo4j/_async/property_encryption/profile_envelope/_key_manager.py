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
from ...._property_encryption.error_wrapper import (
    property_encryption_error_wrapper,
)
from ...._property_encryption.profile_envelope import (
    EncapsulatedKey,
    KeyEncapsulationOptions,
)


if t.TYPE_CHECKING:
    from ._profile import AsyncEnvelopePropertyEncryptionProfile


__all__ = ["AsyncEncapsulatedKeyManager", "ProfileWrapper"]


class ProfileWrapper(t.NamedTuple):
    # Indirection to indicate that AsyncEncapsulatedKeyManager is not meant to
    # be instantiated by users.
    profile: AsyncEnvelopePropertyEncryptionProfile


class AsyncEncapsulatedKeyManager:
    """
    A manager for encapsulated keys.

    This class is not supposed to be instantiated externally. Use
    :meth:`AsyncPropertyEncryption.key_manager` instead.

    A :class:`.AsyncEnvelopePropertyEncryptionProfile` requires data keys to
    exist before they can be used for encryption. This manager provides
    operations for creating and managing such keys.

    When creating a key, the manager uses the configured
    :class:`.AsyncKeyEncapsulationService` to generate and encapsulate a new
    data key and registers the resulting :class:`.EncapsulatedKeyRecord`
    with the configured :class:`.AsyncEncapsulatedKeyRecordRepository`.

    .. versionadded:: 6.5
    """

    _profile: AsyncEnvelopePropertyEncryptionProfile

    def __init__(self, /, *, _profile: ProfileWrapper) -> None:
        if not isinstance(_profile, ProfileWrapper):
            raise TypeError(
                f"Expected key_repository to be of type {ProfileWrapper}, "
                f"got {type(_profile)}."
            )
        self._profile = _profile.profile

    @property_encryption_error_wrapper("Failed to create encapsulated key.")
    async def create(
        self,
        /,
        *,
        alias: str | None = None,
        options: KeyEncapsulationOptions | None = None,
    ) -> EncapsulatedKey:
        """
        Create a new encapsulated key.

        :param alias: the key alias to assign or :data:`None` to create a key
            without an alias.
        :return: the created encapsulated key
        """
        encapsulation_result = (
            await self._profile._key_encapsulation_service.encapsulate(options)
        )
        key_record = await self._profile._key_repository.create(
            alias,
            encapsulation_result.encapsulation,
            encapsulation_result.metadata,
        )
        self._profile._key_cache.set(key_record.id, key_record.encapsulation)
        if alias is not None:
            self._profile._key_alias_cache.set(alias, key_record.id)
        return EncapsulatedKey(id=key_record.id, alias=key_record.alias)

    @property_encryption_error_wrapper("Failed encapsulated key alias lookup.")
    async def find_by_alias(self, alias: str, /) -> EncapsulatedKey | None:
        """
        Find an encapsulated key by its alias.

        :param alias: the key alias to look up.
        :return: the found encapsulated key or :data:`None` if no key with the
            given alias exists.
        """
        key_id = self._profile._key_alias_cache.get(alias)
        if key_id is not None:
            return EncapsulatedKey(id=key_id, alias=alias)
        key_record = await self._profile._key_repository.find_by_alias(alias)
        if key_record is None:
            return None
        self._profile._key_cache.set(key_record.id, key_record.encapsulation)
        self._profile._key_alias_cache.set(alias, key_record.id)
        return EncapsulatedKey(id=key_record.id, alias=key_record.alias)

    @property_encryption_error_wrapper("Failed to set encapsulated key alias.")
    async def set_alias_by_id(self, /, *, id: str, alias: str) -> None:
        """
        Set the alias of an encapsulated key by its id.

        The alias must not be used by another key. To assign an alias currently
        used by another key, it must first be deleted from that key.

        :param id: the key id to set the alias for.
        :param alias: the new key alias to assign.
        """
        await self._profile._key_repository.set_alias_by_id(id, alias)
        self._profile._key_alias_cache.set(alias, id)

    @property_encryption_error_wrapper(
        "Failed to delete encapsulated key alias."
    )
    async def delete_alias_by_id(self, id: str, /) -> None:
        """
        Delete the alias of an encapsulated key by its id.

        :param id: the key id to delete the alias for.
        """
        await self._profile._key_repository.set_alias_by_id(id, None)
        self._profile._key_alias_cache.forget_value(id)

    @property_encryption_error_wrapper("Failed to delete encapsulated key.")
    async def delete_by_id(self, id: str, /) -> None:
        """
        Delete an encapsulated key by its id.

        :param id: the key id to delete.
        """
        await self._profile._key_repository.delete_by_id(id)
        self._profile._key_cache.forget(id)
        self._profile._key_alias_cache.forget_value(id)
