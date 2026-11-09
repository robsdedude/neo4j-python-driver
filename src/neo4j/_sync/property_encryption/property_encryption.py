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

from ... import _typing as t
from ..._property_encryption.api import (
    AadChoiceDecryption,
    AadChoiceEncryption,
    KeyChoice,
)
from ..._property_encryption.error_wrapper import (
    property_encryption_error_wrapper,
)
from . import profile_envelope
from .profile_envelope import EnvelopePropertyEncryptionProfile


if t.TYPE_CHECKING:
    from ..config import DriverConfig
    from ..driver import Driver
    from .profile import PropertyEncryptionProfile
    from .profile_envelope import EncapsulatedKeyManager


__all__ = [
    "DriverHolder",
    "PropertyEncryption",
]


AAD_CHOICE_ENCRYPTION_NONE = t.cast(
    AadChoiceEncryption,
    AadChoiceEncryption._without_warning,  # type: ignore[attr-defined]
).none()


class DriverHolder(t.NamedTuple):
    # Indirection to indicate that AsyncPropertyEncryption is not meant to
    # be instantiated by users.
    driver: Driver


class PropertyEncryption:
    """
    Provides Neo4j property encryption functions.

    This class bundles access to property encryption and decryption
    functionality.
    It is not supposed to be instantiated directly, but rather accessed via
    :meth:`.Driver.property_encryption()`.

    The class is not supposed to be instantiated directly, but rather accessed
    via :meth:`.Driver.property_encryption()`.

    **Property Encryption is a preview**.
    It might be changed without following the deprecation policy.
    See also https://github.com/neo4j/neo4j-python-driver/wiki/preview-features

    .. versionadded:: 6.5
    """

    _driver: Driver

    def __init__(self, /, *, _driver: DriverHolder) -> None:
        if not isinstance(_driver, DriverHolder):
            raise TypeError(
                f"Expected _driver to be of type {DriverHolder}, "
                f"got {type(_driver)}."
            )
        self._driver = _driver.driver

    @property_encryption_error_wrapper("Failed to encrypt property data.")
    def encrypt_to_bytes(
        self,
        value: object,
        /,
        *,
        aad: AadChoiceEncryption = AAD_CHOICE_ENCRYPTION_NONE,
        profile_name: str | None = None,
        key_choice: KeyChoice,
    ) -> bytes:
        """
        Encrypt a property value.

        :param value: the value to encrypt.
        :param aad: the additional authenticated data to use for encryption,
            defaults to :meth:`.AadChoiceEncryption.none()`
        :param profile_name: the name of the property encryption profile to
            use. The profile must have been configured on the driver. If
            exactly one profile has been configured, this parameter may be
            omitted.
        :param key_choice: the key to use for encryption.
        :return: the encrypted bytes
        """
        profile = _get_profile(self._driver, profile_name)
        if type(profile) is EnvelopePropertyEncryptionProfile:
            return profile_envelope.encrypt(
                value, aad, key_choice, profile
            )
        raise TypeError(
            f"Unsupported property encryption profile type: {type(profile)}."
        )

    @property_encryption_error_wrapper("Failed to decrypt property data.")
    def decrypt(
        self,
        value: bytes,
        /,
        *,
        aad: AadChoiceDecryption,
    ) -> t.Any:
        """
        Decrypt a property value.

        A :class:`.UnsupportedType` value will be returned if the value was
        encrypted using a driver newer or older driver version that encoded the
        value with a non-supported scheme.

        :param value: the value to decrypt.
        :param aad: the additional authenticated data to use for decryption.
        :return: the decrypted value
        """
        profile = _get_profile(self._driver, None)
        if type(profile) is EnvelopePropertyEncryptionProfile:
            return profile_envelope.decrypt(value, aad, profile)
        raise TypeError(
            f"Unsupported property encryption profile type: {type(profile)}."
        )

    @property_encryption_error_wrapper("Failed to retrieve the key manager.")
    def key_manager(
        self, profile_name: str | None = None
    ) -> EncapsulatedKeyManager:
        """
        Provide access to manage encapsulated keys.

        The retrieved profile must be a
        :class:`.EnvelopePropertyEncryptionProfile` instance.

        :param profile_name: the name of the property encryption profile to
            use. The profile must have been configured on the driver. If
            exactly one profile has been configured, this parameter may be
            omitted.
        :return: a key manager instance
        """
        profile = _get_profile(self._driver, profile_name)
        if type(profile) is not EnvelopePropertyEncryptionProfile:
            raise TypeError(
                f"Profile with name {profile_name!r} does not support "
                f"encapsulated keys (type {type(profile)})."
            )
        return profile_envelope.EncapsulatedKeyManager(
            _profile=profile_envelope.ProfileWrapper(profile)
        )


def _get_profile(
    driver: Driver, profile_name: str | None
) -> PropertyEncryptionProfile:
    config: DriverConfig = driver._driver_config
    profiles = config.property_encryption_profiles
    if profile_name is None:
        if len(profiles) == 1:
            return next(iter(profiles))
        else:
            raise KeyError(
                "Multiple property encryption profiles are configured, "
                "a profile name must be specified."
            )
    for profile in profiles:
        if profile.name == profile_name:
            return profile
    raise KeyError(
        f"Property encryption profile '{profile_name}' is not configured."
    )
