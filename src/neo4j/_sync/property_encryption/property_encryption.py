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
from ..._property_encryption._all import (
    AadChoice,
    KeyChoice,
)


"""

/**
 * Provides Neo4j Property Encryption functions.
 *
 * @see org.neo4j.driver.property_encryption.async.PropertyEncryption
 * @see org.neo4j.driver.property_encryption.reactive.ReactivePropertyEncryption
 * @see org.neo4j.driver.property_encryption.reactivestreams.ReactivePropertyEncryption
 * @since 6.3.0
 */
@Preview(name = "Property Encryption")
public interface PropertyEncryption extends BasePropertyEncryption {
    /**
     * Encrypts the value according to the provided {@link PropertyEncryptionRequest}.
     *
     * @param encryptRequest the encryption request, must not be {@literal null}
     * @return the encrypted bytes
     */
    byte[] encryptToBytes(PropertyEncryptionRequest encryptRequest);

    /**
     * Decrypts the value according to the provided {@link PropertyDecryptionRequest}.
     *
     * @param decryptRequest the decryption request, must not be {@literal null}
     * @return the decrypted value
     */
    Value decrypt(PropertyDecryptionRequest decryptRequest);

    /**
     * Returns the key manager.
     * <p>
     * If this instance has been configured with a single property encryption profile, the key manager for that
     * profile is returned.
     *
     * @return the key manager
     * @throws IllegalStateException if key management is not supported by the specified profile
     */
    default EncapsulatedKeyManager keyManager() {
        return keyManager(null);
    }

    /**
     * Returns the key manager for the specified property encryption profile.
     *
     * @param profileName the profile name, may be {@literal null} when only a single profile is configured
     * @return the key manager, or {@literal null} if the specified profile does not exist
     * @throws IllegalStateException if key management is not supported by the specified profile
     */
    EncapsulatedKeyManager keyManager(String profileName);
}
"""


class PropertyEncryption:
    """
    Provides Neo4j property encryption functions.

    This class bundles access to property encryption and decryption
    functionality.
    It is not supposed to be instantiated directly, but rather accessed via
    :meth:`.Driver.property_encryption()`.

    .. versionadded:: 6.4
    """

    def encrypt_to_bytes(
        self,
        value: object,
        /,
        *,
        aad: AadChoice = AadChoice.none(),
        profile_name: str | None = None,
        key_choice: KeyChoice | None,
    ) -> bytes:
        """
        Encrypts the value according to the provided :class:`.PropertyEncryptionRequest`.

        :param encrypt_request: the encryption request, must not be :data:`None`
        :return: the encrypted bytes
        """
        ...

    def decrypt(
        self,
        value: bytes,
        /,
        *,
        aad: AadChoice = AadChoice.none(),
        todo: ... = ...,
    ):
        ...
