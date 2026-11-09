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


__all__ = [
    "PropertyEncryptionProfile",
    "internal_implementer",
]


internal_implementer = object()


class PropertyEncryptionProfile(abc.ABC):
    """
    A collection of mechanisms for encrypting and decrypting properties.

    This class is not meant to be subclassed by user-code. Instead, users
    should use the implementation(s) provided by the driver:

    * :class:`.EnvelopePropertyEncryptionProfile`

    **Property Encryption is a preview**.
    It might be changed without following the deprecation policy.
    See also https://github.com/neo4j/neo4j-python-driver/wiki/preview-features

    .. versionadded:: 6.5
    """

    def __init_subclass__(cls) -> None:
        attr = f"_{cls.__name__}__permitted_implementer"
        if getattr(cls, attr, None) is not internal_implementer:
            raise TypeError(
                "Subclassing PropertyEncryptionProfile is not supported "
                f"({cls.__name__})."
            )

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """
        The name of the profile.

        The profile's name is used by the driver as a look-up key when deciding
        what cryptographic mechanisms to use for encrypting and decrypting
        properties.

        For encryption, user-code provides the name
        (:meth:`.PropertyEncryption.decode`).
        For decryption, the name of the used profile is stored alongside the
        encrypted data. Therefore, when using multiple drivers to exchange
        encrypted data, the used profile names must be the same across all
        drivers.
        """
