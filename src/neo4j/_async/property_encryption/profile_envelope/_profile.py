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
import dataclasses

from ..caching import AsyncKeyAliasCache, AsyncKeyCache
from ..profile import AsyncPropertyEncryptionProfile, internal_implementer
from ...._warnings import preview
from .... import _typing as t
from ...._property_encryption.profile_envelope import KeyEncapsulationOptions, KeyEncapsulationResult, EncapsulatedKey, EncapsulatedKeyRecord

if t.TYPE_CHECKING:
    from ._service import AsyncKeyEncapsulationService
    from ._repository import AsyncEncapsulatedKeyRecordRepository


T_o = t.TypeVar("T_o", bound=KeyEncapsulationOptions)


@preview("Property encryption is a preview feature.")
class AsyncEnvelopePropertyEncryptionProfile(AsyncPropertyEncryptionProfile):
    """
    TODO: docs.

    **Property Encryption is a preview**.
    It might be changed without following the deprecation policy.
    See also https://github.com/neo4j/neo4j-python-driver/wiki/preview-features
    """

    __permitted_implementer = internal_implementer

    _name: str
    _key_encapsulation_service: AsyncKeyEncapsulationService
    _key_repository: AsyncEncapsulatedKeyRecordRepository
    _key_cache: AsyncKeyCache
    _key_alias_cache: AsyncKeyAliasCache

    def __init__(
        self,
        name: str,
        /,
        *,
        key_encapsulation_service: AsyncKeyEncapsulationService,
        key_repository: AsyncEncapsulatedKeyRecordRepository,
        key_cache_max_size: int = 100,
        key_cache_ttl: float = 15 * 60.0,
        key_alias_cache_max_size: int = 100,
        key_alias_cache_ttl: float = 15.0,
    ) -> None:
        self._name = name
        self._key_encapsulation_service = key_encapsulation_service
        self._key_repository = key_repository
        self._key_cache = AsyncKeyCache(ttl=key_cache_ttl, size=key_cache_max_size)
        if self._key_cache.is_disabled():
            key_alias_cache_max_size = 0
        self._key_alias_cache = AsyncKeyAliasCache(ttl=key_alias_cache_ttl, size=key_alias_cache_max_size)

    @property
    def name(self) -> str:
        return self._name
