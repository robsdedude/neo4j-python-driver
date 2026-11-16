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
from neo4j._sync.property_encryption.caching import (
    KeyAliasCache,
    KeyCache,
)
from neo4j._sync.property_encryption.profile_envelope._profile import (
    EnvelopePropertyEncryptionProfile,
)
from neo4j.warnings import PreviewWarning


if t.TYPE_CHECKING:
    from neo4j._sync.property_encryption.profile_envelope._repository import (
        EncapsulatedKeyRecordRepository,
    )
    from neo4j._sync.property_encryption.profile_envelope._service import (
        KeyEncapsulationService,
    )


if t.TYPE_CHECKING:
    import typing_extensions as te

    DEFAULT = te.sentinel("DEFAULT")
else:
    DEFAULT = object()


class EnvelopePropertyEncryptionProfileKwargs(t.TypedDict):
    key_cache_max_size: t.NotRequired[int]
    key_cache_ttl: t.NotRequired[float]
    key_alias_cache_max_size: t.NotRequired[int]
    key_alias_cache_ttl: t.NotRequired[float]


def _make_profile(
    service: KeyEncapsulationService,
    repository: EncapsulatedKeyRecordRepository,
    /,
    *,
    key_cache_max_size: int | DEFAULT = DEFAULT,
    key_cache_ttl: float | DEFAULT = DEFAULT,
    key_alias_cache_max_size: int | DEFAULT = DEFAULT,
    key_alias_cache_ttl: float | DEFAULT = DEFAULT,
) -> EnvelopePropertyEncryptionProfile:
    profile_class: type[EnvelopePropertyEncryptionProfile] = (
        EnvelopePropertyEncryptionProfile._without_warning  # type: ignore[attr-defined]
    )
    kwargs: EnvelopePropertyEncryptionProfileKwargs = {}
    if key_cache_max_size is not DEFAULT:
        kwargs["key_cache_max_size"] = key_cache_max_size
    if key_cache_ttl is not DEFAULT:
        kwargs["key_cache_ttl"] = key_cache_ttl
    if key_alias_cache_max_size is not DEFAULT:
        kwargs["key_alias_cache_max_size"] = key_alias_cache_max_size
    if key_alias_cache_ttl is not DEFAULT:
        kwargs["key_alias_cache_ttl"] = key_alias_cache_ttl

    return profile_class(
        "profile",
        key_encapsulation_service=service,
        key_repository=repository,
        **kwargs,
    )


def test_init(
    encapsulation_service: KeyEncapsulationService,
    repository: EncapsulatedKeyRecordRepository,
) -> None:
    with pytest.warns(PreviewWarning, match=r"\bProperty encryption\b"):
        profile = EnvelopePropertyEncryptionProfile(
            "profile-name",
            key_encapsulation_service=encapsulation_service,
            key_repository=repository,
        )

    assert profile.name == "profile-name"
    assert profile._key_encapsulation_service is encapsulation_service
    assert profile._key_repository is repository


def test_default_cache_configuration(
    encapsulation_service: KeyEncapsulationService,
    repository: EncapsulatedKeyRecordRepository,
) -> None:
    profile = _make_profile(encapsulation_service, repository)

    assert isinstance(profile._key_cache, KeyCache)
    assert profile._key_cache._ttl == 15 * 60.0
    assert profile._key_cache._size == 100
    assert isinstance(profile._key_alias_cache, KeyAliasCache)
    assert profile._key_alias_cache._ttl == 15.0
    assert profile._key_alias_cache._size == 100


def test_custom_cache_configuration(
    encapsulation_service: KeyEncapsulationService,
    repository: EncapsulatedKeyRecordRepository,
) -> None:
    profile = _make_profile(
        encapsulation_service,
        repository,
        key_cache_max_size=1,
        key_cache_ttl=2.0,
        key_alias_cache_max_size=3,
        key_alias_cache_ttl=4.0,
    )

    assert profile._key_cache._ttl == 2.0
    assert profile._key_cache._size == 1
    assert profile._key_alias_cache._ttl == 4.0
    assert profile._key_alias_cache._size == 3


def test_disabled_key_cache_disables_alias_cache(
    encapsulation_service: KeyEncapsulationService,
    repository: EncapsulatedKeyRecordRepository,
) -> None:
    profile = _make_profile(
        encapsulation_service,
        repository,
        key_cache_max_size=0,
        key_alias_cache_max_size=100,
    )

    assert profile._key_cache.is_disabled()
    assert profile._key_alias_cache.is_disabled()
