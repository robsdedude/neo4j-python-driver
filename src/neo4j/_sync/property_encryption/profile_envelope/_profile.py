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
from ...._warnings import preview
from ..caching import (
    KeyAliasCache,
    KeyCache,
)
from ..profile import (
    internal_implementer,
    PropertyEncryptionProfile,
)


if t.TYPE_CHECKING:
    from ._repository import EncapsulatedKeyRecordRepository
    from ._service import KeyEncapsulationService


__all__ = [
    "EnvelopePropertyEncryptionProfile",
]


@preview("Property encryption is a preview feature.")
class EnvelopePropertyEncryptionProfile(PropertyEncryptionProfile):
    __permitted_implementer = internal_implementer

    _name: str
    _key_encapsulation_service: KeyEncapsulationService
    _key_repository: EncapsulatedKeyRecordRepository
    _key_cache: KeyCache
    _key_alias_cache: KeyAliasCache

    def __init__(
        self,
        name: str,
        /,
        *,
        key_encapsulation_service: KeyEncapsulationService,
        key_repository: EncapsulatedKeyRecordRepository,
        key_cache_max_size: int = 100,
        key_cache_ttl: float = 15 * 60.0,
        key_alias_cache_max_size: int = 100,
        key_alias_cache_ttl: float = 15.0,
    ) -> None:
        """
        Use envelope encryption for encrypting and decrypting properties.

        This means that a private key used for data encryption, called a data
        encryption key (DEK), is being encrypted using a second (usually
        symmetric) key, called the key encryption key (KEK). This technique is
        also know as key encapsulation.

        The profile contains two caches:

        1. A cache resolving key ids to decapsulated DEKs.
           This safes network operations when using remote/cloud key
           encapsulation services as well as cryptographic operations for
           decapsulating DEKs.
        2. A cache resolving key aliases to key ids.
           This safes network operations when using remote/cloud key
           repositories.

        Both come at the cost of potentially using outdated keys temporarily.
        The ``ttl``s might be adjusted to lessen the effect or the cache's size
        might be reduced or set to ``0`` to disable caching completely.

        :param name: the name of the profile (see remarks under
            :attr:`.PropertyEncryptionProfile.name`).
        :param key_encapsulation_service: the service responsible for
            encapsulating and decapsulating keys.
        :param key_repository: the repository responsible for storing and
            retrieving encapsulated keys (DEKs).
        :param key_cache_max_size: the maximum number of keys to cache in
            memory. If set to 0, caching is disabled.
        :param key_cache_ttl:
            for how many seconds a cache entry should be valid.
        :param key_alias_cache_max_size: the maximum number of key aliases to
            cache in memory. If set to 0, caching is disabled.
        :param key_alias_cache_ttl:
            for how many seconds a cache entry should be valid.

        :raises ValueError:
            * if any cache size is negative.
            * if any cache ttl ``<= 0`` or ``nan``.

        **Property Encryption is a preview**.
        It might be changed without following the deprecation policy.
        See also https://github.com/neo4j/neo4j-python-driver/wiki/preview-features

        .. versionadded:: 6.5
        """
        self._name = name
        self._key_encapsulation_service = key_encapsulation_service
        self._key_repository = key_repository
        self._key_cache = KeyCache(
            ttl=key_cache_ttl, size=key_cache_max_size
        )
        if self._key_cache.is_disabled():
            key_alias_cache_max_size = 0
        self._key_alias_cache = KeyAliasCache(
            ttl=key_alias_cache_ttl, size=key_alias_cache_max_size
        )

    @property
    def name(self) -> str:
        return self._name
