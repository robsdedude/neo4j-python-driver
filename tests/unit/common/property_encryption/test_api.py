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

from neo4j._property_encryption import api
from neo4j.warnings import PreviewWarning

from ._preview import KeyChoice


@pytest.mark.parametrize("value", (None, "context", b"context", 42, object()))
def test_aad_choice_encryption(value: object) -> None:
    with pytest.warns(PreviewWarning, match=r"\bProperty encryption\b"):
        choice = api.AadChoiceEncryption(value)

    assert choice._value is value
    assert repr(choice) == f"AadChoiceEncryption({value!r})"


def test_aad_choice_encryption_none() -> None:
    with pytest.warns(PreviewWarning, match=r"\bProperty encryption\b"):
        choice = api.AadChoiceEncryption.none()

    assert choice._value is api.AAD_CHOICE_NONE
    assert repr(choice) == "AadChoiceEncryption.none()"


@pytest.mark.parametrize("value", (None, "context", b"context", 42, object()))
def test_aad_choice_decryption(value: object) -> None:
    with pytest.warns(PreviewWarning, match=r"\bProperty encryption\b"):
        choice = api.AadChoiceDecryption(value)

    assert choice._value is value
    assert repr(choice) == f"AadChoiceDecryption({value!r})"


def test_aad_choice_decryption_external() -> None:
    with pytest.warns(PreviewWarning, match=r"\bProperty encryption\b"):
        choice = api.AadChoiceDecryption.external()

    assert choice._value is api.AAD_CHOICE_USE_EXTERNAL
    assert repr(choice) == "AadChoiceDecryption.external()"


def test_key_choice_by_id() -> None:
    choice = KeyChoice(id="key-id")

    assert choice._id == "key-id"
    assert choice._alias is None
    assert repr(choice) == "KeyChoice(id='key-id')"


def test_key_choice_by_alias() -> None:
    choice = KeyChoice(alias="key-alias")

    assert choice._id is None
    assert choice._alias == "key-alias"
    assert repr(choice) == "KeyChoice(alias='key-alias')"


def test_key_choice_requires_id_or_alias() -> None:
    with pytest.raises(ValueError) as exc_info:
        KeyChoice()  # type: ignore[call-overload]

    assert str(exc_info.value) == "Must specify either id or alias"


def test_key_choice_rejects_id_and_alias() -> None:
    with pytest.raises(ValueError) as exc_info:
        KeyChoice(id="key-id", alias="key-alias")  # type: ignore[call-overload]

    assert str(exc_info.value) == "Cannot specify both id and alias"
