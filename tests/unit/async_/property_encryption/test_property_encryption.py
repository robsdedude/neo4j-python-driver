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
from neo4j._async.config import AsyncDriverConfig
from neo4j._async.driver import AsyncDriver
from neo4j._async.property_encryption import (
    profile_envelope,
    property_encryption as property_encryption_module,
)
from neo4j._async.property_encryption.profile import (
    AsyncPropertyEncryptionProfile,
)
from neo4j._async.property_encryption.profile_envelope import (
    AsyncEncapsulatedKeyManager,
    AsyncEncapsulatedKeyRecordRepository,
    AsyncEnvelopePropertyEncryptionProfile,
    AsyncKeyEncapsulationService,
)
from neo4j._async.property_encryption.property_encryption import (
    AsyncDriverHolder,
    AsyncPropertyEncryption,
)
from neo4j._property_encryption.api import (
    AadChoiceDecryption,
    AadChoiceEncryption,
    KeyChoice,
)
from neo4j.exceptions import PropertyEncryptionError
from neo4j.warnings import PreviewWarning

from ...._async_compat import mark_async_test
from ..._mock import (
    AsyncReturnTrackingMock,
    ReturnTrackingMock,
)


if t.TYPE_CHECKING:
    from pytest_mock import MockFixture


AAD_ENCRYPTION = t.cast(AadChoiceEncryption, object())
AAD_DECRYPTION = t.cast(AadChoiceDecryption, object())
KEY_CHOICE = t.cast(KeyChoice, object())

PROFILE_NAME = "profile"
PROFILE_NAME_OTHER = "other-profile"
PROFILE_NAME_UNSUPPORTED = "unsupported"


@pytest.fixture
def async_driver(mocker: MockFixture) -> AsyncDriver:
    driver = mocker.Mock(spec=AsyncDriver)
    driver._driver_config = mocker.Mock(spec=AsyncDriverConfig)
    driver._driver_config.property_encryption_profiles = frozenset()
    return driver


@pytest.fixture
def encryption(async_driver: AsyncDriver) -> AsyncPropertyEncryption:
    return AsyncPropertyEncryption(_driver=AsyncDriverHolder(async_driver))


def _make_envelope_profile(
    name: str,
) -> AsyncEnvelopePropertyEncryptionProfile:
    service = t.cast(AsyncKeyEncapsulationService, object())
    repository = t.cast(AsyncEncapsulatedKeyRecordRepository, object())
    with pytest.warns(PreviewWarning, match=r"\bProperty encryption\b"):
        return AsyncEnvelopePropertyEncryptionProfile(
            name,
            key_encapsulation_service=service,
            key_repository=repository,
        )


@pytest.fixture
def async_profile() -> AsyncEnvelopePropertyEncryptionProfile:
    return _make_envelope_profile(PROFILE_NAME)


def _make_unsupported_profile(
    mocker: MockFixture, name: str = PROFILE_NAME_UNSUPPORTED
) -> AsyncPropertyEncryptionProfile:
    profile = mocker.Mock(spec=AsyncPropertyEncryptionProfile)
    profile.name = name
    return profile


def _set_profiles(
    driver: AsyncDriver, *profiles: AsyncPropertyEncryptionProfile
) -> None:
    driver._driver_config.property_encryption_profiles = frozenset(profiles)


@pytest.fixture
def mocked_encrypt(mocker: MockFixture) -> AsyncReturnTrackingMock:
    return mocker.patch.object(
        profile_envelope,
        "encrypt",
        new=AsyncReturnTrackingMock(return_value=b"encrypted"),
    )


@pytest.fixture
def mocked_decrypt(mocker: MockFixture) -> AsyncReturnTrackingMock:
    decrypted = object()
    return mocker.patch.object(
        profile_envelope,
        "decrypt",
        new=AsyncReturnTrackingMock(return_value=decrypted),
    )


@pytest.fixture
def mocked_decode_encrypted_struct(
    mocker: MockFixture,
) -> ReturnTrackingMock:
    struct = mocker.Mock(profile_name=PROFILE_NAME)
    return mocker.patch.object(
        property_encryption_module,
        "decode_encrypted_struct",
        new=ReturnTrackingMock(return_value=struct),
    )


def test_init_rejects_plain_driver(async_driver: AsyncDriver) -> None:
    with pytest.raises(TypeError, match=r"Expected _driver"):
        AsyncPropertyEncryption(
            _driver=async_driver,  # type: ignore[arg-type]
        )


def test_init_unwraps_driver(async_driver: AsyncDriver) -> None:
    encryption = AsyncPropertyEncryption(
        _driver=AsyncDriverHolder(async_driver)
    )
    assert encryption._driver is async_driver


@mark_async_test
async def test_encrypt_to_bytes_uses_specified_profile(
    async_driver: AsyncDriver,
    encryption: AsyncPropertyEncryption,
    async_profile: AsyncEnvelopePropertyEncryptionProfile,
    mocked_encrypt: AsyncReturnTrackingMock,
) -> None:
    other_profile = _make_envelope_profile(PROFILE_NAME_OTHER)
    _set_profiles(async_driver, async_profile, other_profile)
    value = object()

    result = await encryption.encrypt_to_bytes(
        value,
        aad=AAD_ENCRYPTION,
        profile_name=async_profile.name,
        key_choice=KEY_CHOICE,
    )

    assert len(mocked_encrypt.call_return_values) == 1
    assert result is mocked_encrypt.call_return_values[0]
    mocked_encrypt.assert_awaited_once_with(
        value, AAD_ENCRYPTION, KEY_CHOICE, async_profile
    )


@mark_async_test
async def test_encrypt_to_bytes_uses_configured_profile(
    async_driver: AsyncDriver,
    encryption: AsyncPropertyEncryption,
    async_profile: AsyncEnvelopePropertyEncryptionProfile,
    mocked_encrypt: AsyncReturnTrackingMock,
) -> None:
    _set_profiles(async_driver, async_profile)
    value = object()

    result = await encryption.encrypt_to_bytes(
        value, aad=AAD_ENCRYPTION, key_choice=KEY_CHOICE
    )

    assert len(mocked_encrypt.call_return_values) == 1
    assert result is mocked_encrypt.call_return_values[0]
    mocked_encrypt.assert_awaited_once_with(
        value, AAD_ENCRYPTION, KEY_CHOICE, async_profile
    )


@pytest.mark.parametrize("profile_count", (0, 2))
@mark_async_test
async def test_encrypt_to_bytes_requires_profile_name(
    profile_count: int,
    async_driver: AsyncDriver,
    encryption: AsyncPropertyEncryption,
    async_profile: AsyncEnvelopePropertyEncryptionProfile,
    mocked_encrypt: AsyncReturnTrackingMock,
) -> None:
    profiles: tuple[AsyncPropertyEncryptionProfile, ...] = ()
    if profile_count == 2:
        other_profile = _make_envelope_profile(PROFILE_NAME_OTHER)
        profiles = (async_profile, other_profile)
    _set_profiles(async_driver, *profiles)

    with pytest.raises(PropertyEncryptionError) as exc_info:
        await encryption.encrypt_to_bytes(
            object(), aad=AAD_ENCRYPTION, key_choice=KEY_CHOICE
        )

    assert str(exc_info.value) == "Failed to encrypt property data."
    assert isinstance(exc_info.value.__cause__, KeyError)
    assert "a profile name must be specified" in str(exc_info.value.__cause__)
    mocked_encrypt.assert_not_called()


@mark_async_test
async def test_decrypt_uses_specified_profile(
    async_driver: AsyncDriver,
    encryption: AsyncPropertyEncryption,
    async_profile: AsyncEnvelopePropertyEncryptionProfile,
    mocked_decrypt: AsyncReturnTrackingMock,
    mocked_decode_encrypted_struct: ReturnTrackingMock,
) -> None:
    other_profile = _make_envelope_profile(PROFILE_NAME_OTHER)
    _set_profiles(async_driver, async_profile, other_profile)
    struct = mocked_decode_encrypted_struct.return_value
    struct.profile_name = async_profile.name
    value = b"encrypted"

    result = await encryption.decrypt(value, aad=AAD_DECRYPTION)

    mocked_decode_encrypted_struct.assert_called_once_with(value)
    assert len(mocked_decrypt.call_return_values) == 1
    assert result is mocked_decrypt.call_return_values[0]
    mocked_decrypt.assert_awaited_once_with(
        struct, AAD_DECRYPTION, async_profile
    )


@pytest.mark.parametrize("any_profile", (True, False))
@mark_async_test
async def test_encrypt_to_bytes_rejects_missing_profile(
    any_profile: bool,
    async_driver: AsyncDriver,
    encryption: AsyncPropertyEncryption,
    async_profile: AsyncEnvelopePropertyEncryptionProfile,
    mocked_encrypt: AsyncReturnTrackingMock,
) -> None:
    if any_profile:
        _set_profiles(async_driver, async_profile)

    with pytest.raises(PropertyEncryptionError) as exc_info:
        await encryption.encrypt_to_bytes(
            object(),
            aad=AAD_ENCRYPTION,
            profile_name=PROFILE_NAME_OTHER,
            key_choice=KEY_CHOICE,
        )

    assert str(exc_info.value) == "Failed to encrypt property data."
    assert isinstance(exc_info.value.__cause__, KeyError)
    assert PROFILE_NAME_OTHER in str(exc_info.value.__cause__)
    mocked_encrypt.assert_not_called()


@pytest.mark.parametrize("any_profile", (True, False))
@mark_async_test
async def test_decrypt_rejects_missing_profile(
    any_profile: bool,
    async_driver: AsyncDriver,
    encryption: AsyncPropertyEncryption,
    async_profile: AsyncEnvelopePropertyEncryptionProfile,
    mocked_decrypt: AsyncReturnTrackingMock,
    mocked_decode_encrypted_struct: ReturnTrackingMock,
) -> None:
    if any_profile:
        _set_profiles(async_driver, async_profile)
    mocked_decode_encrypted_struct.return_value.profile_name = (
        PROFILE_NAME_OTHER
    )

    with pytest.raises(PropertyEncryptionError) as exc_info:
        await encryption.decrypt(b"encrypted", aad=AAD_DECRYPTION)

    assert str(exc_info.value) == "Failed to decrypt property data."
    assert isinstance(exc_info.value.__cause__, KeyError)
    assert PROFILE_NAME_OTHER in str(exc_info.value.__cause__)
    mocked_decrypt.assert_not_called()


@mark_async_test
async def test_encrypt_to_bytes_rejects_unsupported_profile(
    async_driver: AsyncDriver,
    encryption: AsyncPropertyEncryption,
    mocker: MockFixture,
    mocked_encrypt: AsyncReturnTrackingMock,
) -> None:
    profile = _make_unsupported_profile(mocker)
    _set_profiles(async_driver, profile)

    with pytest.raises(PropertyEncryptionError) as exc_info:
        await encryption.encrypt_to_bytes(
            object(),
            aad=AAD_ENCRYPTION,
            profile_name=profile.name,
            key_choice=KEY_CHOICE,
        )

    assert str(exc_info.value) == "Failed to encrypt property data."
    assert isinstance(exc_info.value.__cause__, TypeError)
    assert "Unsupported property encryption profile type" in str(
        exc_info.value.__cause__
    )
    mocked_encrypt.assert_not_called()


@mark_async_test
async def test_decrypt_rejects_unsupported_profile(
    async_driver: AsyncDriver,
    encryption: AsyncPropertyEncryption,
    mocker: MockFixture,
    mocked_decrypt: AsyncReturnTrackingMock,
    mocked_decode_encrypted_struct: ReturnTrackingMock,
) -> None:
    profile = _make_unsupported_profile(mocker)
    _set_profiles(async_driver, profile)
    mocked_decode_encrypted_struct.return_value.profile_name = profile.name

    with pytest.raises(PropertyEncryptionError) as exc_info:
        await encryption.decrypt(b"encrypted", aad=AAD_DECRYPTION)

    assert str(exc_info.value) == "Failed to decrypt property data."
    assert isinstance(exc_info.value.__cause__, TypeError)
    assert "Unsupported property encryption profile type" in str(
        exc_info.value.__cause__
    )
    mocked_decrypt.assert_not_called()


def test_key_manager_uses_specified_profile(
    async_driver: AsyncDriver,
    encryption: AsyncPropertyEncryption,
    async_profile: AsyncEnvelopePropertyEncryptionProfile,
) -> None:
    other_profile = _make_envelope_profile(PROFILE_NAME_OTHER)
    _set_profiles(async_driver, async_profile, other_profile)

    key_manager = encryption.key_manager(async_profile.name)

    assert isinstance(key_manager, AsyncEncapsulatedKeyManager)
    assert key_manager._profile is async_profile


def test_key_manager_uses_configured_profile(
    async_driver: AsyncDriver,
    encryption: AsyncPropertyEncryption,
    async_profile: AsyncEnvelopePropertyEncryptionProfile,
) -> None:
    _set_profiles(async_driver, async_profile)

    key_manager = encryption.key_manager()

    assert isinstance(key_manager, AsyncEncapsulatedKeyManager)
    assert key_manager._profile is async_profile


@pytest.mark.parametrize("profile_count", (0, 2))
def test_key_manager_requires_profile_name(
    profile_count: int,
    async_driver: AsyncDriver,
    encryption: AsyncPropertyEncryption,
    async_profile: AsyncEnvelopePropertyEncryptionProfile,
) -> None:
    profiles: tuple[AsyncPropertyEncryptionProfile, ...] = ()
    if profile_count == 2:
        other_profile = _make_envelope_profile(PROFILE_NAME_OTHER)
        profiles = (async_profile, other_profile)
    _set_profiles(async_driver, *profiles)

    with pytest.raises(PropertyEncryptionError) as exc_info:
        encryption.key_manager()

    assert str(exc_info.value) == "Failed to retrieve the key manager."
    assert isinstance(exc_info.value.__cause__, KeyError)
    assert "a profile name must be specified" in str(exc_info.value.__cause__)


@pytest.mark.parametrize("any_profile", (True, False))
def test_key_manager_rejects_missing_profile(
    any_profile: bool,
    async_driver: AsyncDriver,
    encryption: AsyncPropertyEncryption,
    async_profile: AsyncEnvelopePropertyEncryptionProfile,
) -> None:
    if any_profile:
        _set_profiles(async_driver, async_profile)

    with pytest.raises(PropertyEncryptionError) as exc_info:
        encryption.key_manager(PROFILE_NAME_OTHER)

    assert str(exc_info.value) == "Failed to retrieve the key manager."
    assert isinstance(exc_info.value.__cause__, KeyError)
    assert PROFILE_NAME_OTHER in str(exc_info.value.__cause__)


def test_key_manager_rejects_unsupported_profile(
    async_driver: AsyncDriver,
    encryption: AsyncPropertyEncryption,
    mocker: MockFixture,
) -> None:
    profile = _make_unsupported_profile(mocker)
    _set_profiles(async_driver, profile)

    with pytest.raises(PropertyEncryptionError) as exc_info:
        encryption.key_manager(profile.name)

    assert str(exc_info.value) == "Failed to retrieve the key manager."
    assert isinstance(exc_info.value.__cause__, TypeError)
    assert "does not support encapsulated keys" in str(
        exc_info.value.__cause__
    )
