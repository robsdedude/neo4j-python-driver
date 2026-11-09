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
import profile

import pytest

from neo4j import _typing as t
from neo4j._async.property_encryption.profile_envelope import (
    AsyncEncapsulatedKeyRecordRepository,
    AsyncEnvelopePropertyEncryptionProfile,
    AsyncKeyEncapsulationService,
    decrypt,
    encrypt,
)


if t.TYPE_CHECKING:
    from pytest_mock import MockFixture

    from neo4j.property_encryption import (
        AadChoiceDecryption,
        AadChoiceEncryption,
        KeyChoice,
    )

    from .conftest import AsyncTestingEnvelopePropertyEncryptionProfile


KEY_ID = "key-id"
KEY_ALIAS = "key-alias"


@pytest.mark.parametrize(
    "key_choice", (KeyChoice(id=KEY_ID), KeyChoice(alias=KEY_ALIAS))
)
@pytest.mark.parametrize("key_cache_hit", (True, False))
@pytest.mark.parametrize("alias_cache_hit", (True, False))
def test_encrypt(
    key_choice: KeyChoice,
    key_cache_hit: bool,
    alias_cache_hit: bool,
    async_profile: AsyncTestingEnvelopePropertyEncryptionProfile,
) -> None:
    key = async_profile._create_key(
        alias=KEY_ALIAS,
        key_cache=key_cache_hit,
        alias_cache=alias_cache_hit,
    )
    value = object()
    aad = t.cast(AadChoiceEncryption, object())
    # mock encryption primitive
    encypted = encrypt(value, aad, key_choice, async_profile)
    assert False, "TODO"
