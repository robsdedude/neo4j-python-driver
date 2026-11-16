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
from neo4j._property_encryption.api import (
    AadChoiceDecryption,
    AadChoiceEncryption,
    KeyChoice,
)
from neo4j._sync.config import DriverConfig
from neo4j._sync.driver import Driver
from neo4j._sync.property_encryption import (
    profile_envelope,
    property_encryption as property_encryption_module,
)
from neo4j._sync.property_encryption.profile import PropertyEncryptionProfile
from neo4j._sync.property_encryption.profile_envelope import (
    EncapsulatedKeyManager,
    EncapsulatedKeyRecordRepository,
    EnvelopePropertyEncryptionProfile,
    KeyEncapsulationService,
)
from neo4j._sync.property_encryption.property_encryption import (
    DriverHolder,
    PropertyEncryption,
)
from neo4j.exceptions import PropertyEncryptionError
from neo4j.warnings import PreviewWarning

from ...._async_compat import mark_sync_test
from ..._mock import ReturnTrackingMock


if t.TYPE_CHECKING:
    from pytest_mock import MockFixture


AAD_ENCRYPTION = t.cast(AadChoiceEncryption, object())
AAD_DECRYPTION = t.cast(AadChoiceDecryption, object())
KEY_CHOICE = t.cast(KeyChoice, object())

PROFILE_NAME = "profile"
PROFILE_NAME_OTHER = "other-profile"
PROFILE_NAME_UNSUPPORTED = "unsupported"


@pytest.fixture
def driver(mocker: MockFixture) -> Driver:
    driver = mocker.Mock(spec=Driver)
    driver._driver_config = mocker.Mock(spec=DriverConfig)
    driver._driver_config.property_encryption_profiles = frozenset()
    return driver


@pytest.fixture
def encryption(driver: Driver) -> PropertyEncryption:
    return PropertyEncryption(_driver=DriverHolder(driver))


def _make_envelope_profile(
    name: str,
) -> EnvelopePropertyEncryptionProfile:
    service = t.cast(KeyEncapsulationService, object())
    repository = t.cast(EncapsulatedKeyRecordRepository, object())
    with pytest.warns(PreviewWarning, match=r"\bProperty encryption\b"):
        return EnvelopePropertyEncryptionProfile(
            name,
            key_encapsulation_service=service,
            key_repository=repository,
        )


@pytest.fixture
def profile() -> EnvelopePropertyEncryptionProfile:
    return _make_envelope_profile(PROFILE_NAME)


def _make_unsupported_profile(
    mocker: MockFixture, name: str = PROFILE_NAME_UNSUPPORTED
) -> PropertyEncryptionProfile:
    profile = mocker.Mock(spec=PropertyEncryptionProfile)
    profile.name = name
    return profile


def _set_profiles(
    driver: Driver, *profiles: PropertyEncryptionProfile
) -> None:
    driver._driver_config.property_encryption_profiles = frozenset(profiles)


@pytest.fixture
def mocked_encrypt(mocker: MockFixture) -> ReturnTrackingMock:
    return mocker.patch.object(
        profile_envelope,
        "encrypt",
        new=ReturnTrackingMock(return_value=b"encrypted"),
    )


@pytest.fixture
def mocked_decrypt(mocker: MockFixture) -> ReturnTrackingMock:
    decrypted = object()
    return mocker.patch.object(
        profile_envelope,
        "decrypt",
        new=ReturnTrackingMock(return_value=decrypted),
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


def test_init_rejects_plain_driver(driver: Driver) -> None:
    with pytest.raises(TypeError, match=r"Expected _driver"):
        PropertyEncryption(
            _driver=driver,  # type: ignore[arg-type]
        )


def test_init_unwraps_driver(driver: Driver) -> None:
    encryption = PropertyEncryption(
        _driver=DriverHolder(driver)
    )
    assert encryption._driver is driver


@mark_sync_test
def test_encrypt_to_bytes_uses_specified_profile(
    driver: Driver,
    encryption: PropertyEncryption,
    profile: EnvelopePropertyEncryptionProfile,
    mocked_encrypt: ReturnTrackingMock,
) -> None:
    other_profile = _make_envelope_profile(PROFILE_NAME_OTHER)
    _set_profiles(driver, profile, other_profile)
    value = object()

    result = encryption.encrypt_to_bytes(
        value,
        aad=AAD_ENCRYPTION,
        profile_name=profile.name,
        key_choice=KEY_CHOICE,
    )

    assert len(mocked_encrypt.call_return_values) == 1
    assert result is mocked_encrypt.call_return_values[0]
    mocked_encrypt.assert_called_once_with(
        value, AAD_ENCRYPTION, KEY_CHOICE, profile
    )


@mark_sync_test
def test_encrypt_to_bytes_uses_configured_profile(
    driver: Driver,
    encryption: PropertyEncryption,
    profile: EnvelopePropertyEncryptionProfile,
    mocked_encrypt: ReturnTrackingMock,
) -> None:
    _set_profiles(driver, profile)
    value = object()

    result = encryption.encrypt_to_bytes(
        value, aad=AAD_ENCRYPTION, key_choice=KEY_CHOICE
    )

    assert len(mocked_encrypt.call_return_values) == 1
    assert result is mocked_encrypt.call_return_values[0]
    mocked_encrypt.assert_called_once_with(
        value, AAD_ENCRYPTION, KEY_CHOICE, profile
    )


@pytest.mark.parametrize("profile_count", (0, 2))
@mark_sync_test
def test_encrypt_to_bytes_requires_profile_name(
    profile_count: int,
    driver: Driver,
    encryption: PropertyEncryption,
    profile: EnvelopePropertyEncryptionProfile,
    mocked_encrypt: ReturnTrackingMock,
) -> None:
    profiles: tuple[PropertyEncryptionProfile, ...] = ()
    if profile_count == 2:
        other_profile = _make_envelope_profile(PROFILE_NAME_OTHER)
        profiles = (profile, other_profile)
    _set_profiles(driver, *profiles)

    with pytest.raises(PropertyEncryptionError) as exc_info:
        encryption.encrypt_to_bytes(
            object(), aad=AAD_ENCRYPTION, key_choice=KEY_CHOICE
        )

    assert str(exc_info.value) == "Failed to encrypt property data."
    assert isinstance(exc_info.value.__cause__, KeyError)
    assert "a profile name must be specified" in str(exc_info.value.__cause__)
    mocked_encrypt.assert_not_called()


@mark_sync_test
def test_decrypt_uses_specified_profile(
    driver: Driver,
    encryption: PropertyEncryption,
    profile: EnvelopePropertyEncryptionProfile,
    mocked_decrypt: ReturnTrackingMock,
    mocked_decode_encrypted_struct: ReturnTrackingMock,
) -> None:
    other_profile = _make_envelope_profile(PROFILE_NAME_OTHER)
    _set_profiles(driver, profile, other_profile)
    struct = mocked_decode_encrypted_struct.return_value
    struct.profile_name = profile.name
    value = b"encrypted"

    result = encryption.decrypt(value, aad=AAD_DECRYPTION)

    mocked_decode_encrypted_struct.assert_called_once_with(value)
    assert len(mocked_decrypt.call_return_values) == 1
    assert result is mocked_decrypt.call_return_values[0]
    mocked_decrypt.assert_called_once_with(
        struct, AAD_DECRYPTION, profile
    )


@pytest.mark.parametrize("any_profile", (True, False))
@mark_sync_test
def test_encrypt_to_bytes_rejects_missing_profile(
    any_profile: bool,
    driver: Driver,
    encryption: PropertyEncryption,
    profile: EnvelopePropertyEncryptionProfile,
    mocked_encrypt: ReturnTrackingMock,
) -> None:
    if any_profile:
        _set_profiles(driver, profile)

    with pytest.raises(PropertyEncryptionError) as exc_info:
        encryption.encrypt_to_bytes(
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
@mark_sync_test
def test_decrypt_rejects_missing_profile(
    any_profile: bool,
    driver: Driver,
    encryption: PropertyEncryption,
    profile: EnvelopePropertyEncryptionProfile,
    mocked_decrypt: ReturnTrackingMock,
    mocked_decode_encrypted_struct: ReturnTrackingMock,
) -> None:
    if any_profile:
        _set_profiles(driver, profile)
    mocked_decode_encrypted_struct.return_value.profile_name = (
        PROFILE_NAME_OTHER
    )

    with pytest.raises(PropertyEncryptionError) as exc_info:
        encryption.decrypt(b"encrypted", aad=AAD_DECRYPTION)

    assert str(exc_info.value) == "Failed to decrypt property data."
    assert isinstance(exc_info.value.__cause__, KeyError)
    assert PROFILE_NAME_OTHER in str(exc_info.value.__cause__)
    mocked_decrypt.assert_not_called()


@mark_sync_test
def test_encrypt_to_bytes_rejects_unsupported_profile(
    driver: Driver,
    encryption: PropertyEncryption,
    mocker: MockFixture,
    mocked_encrypt: ReturnTrackingMock,
) -> None:
    profile = _make_unsupported_profile(mocker)
    _set_profiles(driver, profile)

    with pytest.raises(PropertyEncryptionError) as exc_info:
        encryption.encrypt_to_bytes(
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


@mark_sync_test
def test_decrypt_rejects_unsupported_profile(
    driver: Driver,
    encryption: PropertyEncryption,
    mocker: MockFixture,
    mocked_decrypt: ReturnTrackingMock,
    mocked_decode_encrypted_struct: ReturnTrackingMock,
) -> None:
    profile = _make_unsupported_profile(mocker)
    _set_profiles(driver, profile)
    mocked_decode_encrypted_struct.return_value.profile_name = profile.name

    with pytest.raises(PropertyEncryptionError) as exc_info:
        encryption.decrypt(b"encrypted", aad=AAD_DECRYPTION)

    assert str(exc_info.value) == "Failed to decrypt property data."
    assert isinstance(exc_info.value.__cause__, TypeError)
    assert "Unsupported property encryption profile type" in str(
        exc_info.value.__cause__
    )
    mocked_decrypt.assert_not_called()


def test_key_manager_uses_specified_profile(
    driver: Driver,
    encryption: PropertyEncryption,
    profile: EnvelopePropertyEncryptionProfile,
) -> None:
    other_profile = _make_envelope_profile(PROFILE_NAME_OTHER)
    _set_profiles(driver, profile, other_profile)

    key_manager = encryption.key_manager(profile.name)

    assert isinstance(key_manager, EncapsulatedKeyManager)
    assert key_manager._profile is profile


def test_key_manager_uses_configured_profile(
    driver: Driver,
    encryption: PropertyEncryption,
    profile: EnvelopePropertyEncryptionProfile,
) -> None:
    _set_profiles(driver, profile)

    key_manager = encryption.key_manager()

    assert isinstance(key_manager, EncapsulatedKeyManager)
    assert key_manager._profile is profile


@pytest.mark.parametrize("profile_count", (0, 2))
def test_key_manager_requires_profile_name(
    profile_count: int,
    driver: Driver,
    encryption: PropertyEncryption,
    profile: EnvelopePropertyEncryptionProfile,
) -> None:
    profiles: tuple[PropertyEncryptionProfile, ...] = ()
    if profile_count == 2:
        other_profile = _make_envelope_profile(PROFILE_NAME_OTHER)
        profiles = (profile, other_profile)
    _set_profiles(driver, *profiles)

    with pytest.raises(PropertyEncryptionError) as exc_info:
        encryption.key_manager()

    assert str(exc_info.value) == "Failed to retrieve the key manager."
    assert isinstance(exc_info.value.__cause__, KeyError)
    assert "a profile name must be specified" in str(exc_info.value.__cause__)


@pytest.mark.parametrize("any_profile", (True, False))
def test_key_manager_rejects_missing_profile(
    any_profile: bool,
    driver: Driver,
    encryption: PropertyEncryption,
    profile: EnvelopePropertyEncryptionProfile,
) -> None:
    if any_profile:
        _set_profiles(driver, profile)

    with pytest.raises(PropertyEncryptionError) as exc_info:
        encryption.key_manager(PROFILE_NAME_OTHER)

    assert str(exc_info.value) == "Failed to retrieve the key manager."
    assert isinstance(exc_info.value.__cause__, KeyError)
    assert PROFILE_NAME_OTHER in str(exc_info.value.__cause__)


def test_key_manager_rejects_unsupported_profile(
    driver: Driver,
    encryption: PropertyEncryption,
    mocker: MockFixture,
) -> None:
    profile = _make_unsupported_profile(mocker)
    _set_profiles(driver, profile)

    with pytest.raises(PropertyEncryptionError) as exc_info:
        encryption.key_manager(profile.name)

    assert str(exc_info.value) == "Failed to retrieve the key manager."
    assert isinstance(exc_info.value.__cause__, TypeError)
    assert "does not support encapsulated keys" in str(
        exc_info.value.__cause__
    )
