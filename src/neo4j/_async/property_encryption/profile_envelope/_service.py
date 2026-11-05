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
import base64
import os

from cryptography.hazmat.primitives.ciphers import (
    Cipher,
    modes,
)
from cryptography.hazmat.primitives.ciphers.algorithms import AES256

from .... import _typing as t  # noqa: TC001
from ...._property_encryption.profile_envelope import (
    KeyEncapsulationOptions,
    KeyEncapsulationResult,
)
from ...._warnings import preview


__all__ = [
    "AsyncKeyEncapsulationService",
    "AsyncKeyEncapsulationServices",
]


class AsyncKeyEncapsulationService(abc.ABC):
    """
    A service responsible for encapsulating and decapsulating keys.

    This means that a private key used for data encryption, called a data
    encryption key (DEK), is being encrypted using a second (usually symmetric)
    key, called the key encryption key (KEK). This technique is also know as
    key encapsulation.

    Implementations of this abstract base class are provided through
    :class:`.AsyncKeyEncapsulationServices`.

    .. versionadded:: 6.5
    """

    @abc.abstractmethod
    async def encapsulate(
        self, options: KeyEncapsulationOptions | None
    ) -> KeyEncapsulationResult:
        """
        Create a new key, encapsulates it and return the result.

        :param options: the encapsulation options.

        :returns: the encapsulation result
        """
        ...

    @abc.abstractmethod
    async def decapsulate(
        self, encapsulation: bytes, matadata: t.Mapping[str, str]
    ) -> bytes:
        """
        Decapsulate an encapsulated key.

        :param encapsulation: the encapsulated key.
        :param metadata: the key metadata.

        :returns: the decapsulated key
        """
        ...


class AsyncKeyEncapsulationServices:
    """
    A factory for :class:`.AsyncKeyEncapsulationService` instances.

    Implementations are not limited to those provided by this factory.

    .. versionadded:: 6.5
    """

    @staticmethod
    @preview("Property encryption is a preview feature.")
    def local(master_key: bytes) -> AsyncKeyEncapsulationService:
        """
        Build a key encapsulation service using a local AES-256 master key.

        Return a new :class:`.AsyncKeyEncapsulationService` implementation that
        uses a locally generated AES-256 key as a master key for encapsulating
        and decapsulating data keys.

        This implementation does not accept any
        :class:`.KeyEncapsulationOptions` and will raise a :class:`.ValueError`
        if any are provided.

        :returns: the class:`.AsyncKeyEncapsulationService` implementation
        """
        return _AsyncLocalKeyEncapsulationService(master_key)


class _AsyncLocalKeyEncapsulationService(AsyncKeyEncapsulationService):
    def __init__(self, master_key: bytes) -> None:
        self._algo = AES256(master_key)

    async def encapsulate(
        self, options: KeyEncapsulationOptions | None
    ) -> KeyEncapsulationResult:
        if options is not None:
            raise ValueError(
                "Local key encapsulation service does not accept options."
            )

        iv = os.urandom(16)
        mode = modes.CBC(iv)
        cipher = Cipher(self._algo, mode)
        secret_key = os.urandom(32)  # new random AES-256 key
        encryptor = cipher.encryptor()
        encapsulation = encryptor.update(secret_key) + encryptor.finalize()
        metadata = {"iv": base64.b64encode(iv).decode("utf-8")}
        return KeyEncapsulationResult(
            encapsulation=encapsulation,
            metadata=metadata,
            secret_key=secret_key,
        )

    async def decapsulate(
        self, encapsulation: bytes, matadata: t.Mapping[str, str]
    ) -> bytes:
        try:
            iv_base64 = matadata["iv"]
        except KeyError as e:
            raise ValueError(
                "Metadata for decapsulation must contain 'iv'."
            ) from e
        if len(matadata) != 1:
            raise ValueError(
                "Metadata for decapsulation must only contain 'iv'."
            )
        try:
            iv = base64.b64decode(iv_base64)
        except Exception as e:
            raise ValueError(
                "Metadata for decapsulation must contain a valid "
                "base64-encoded 'iv'."
            ) from e
        if len(iv) != 16:
            raise ValueError(
                "Metadata for decapsulation must contain a valid 16-byte 'iv'."
            )
        mode = modes.CBC(iv)
        cipher = Cipher(self._algo, mode)
        decryptor = cipher.decryptor()
        try:
            secret_key = decryptor.update(encapsulation) + decryptor.finalize()
        except Exception as e:
            raise ValueError("Failed to decapsulate the key.") from e
        return secret_key
