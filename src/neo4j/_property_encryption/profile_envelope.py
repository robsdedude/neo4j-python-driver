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

from .. import _typing as t  # noqa: TC001
from .._warnings import preview


__all__ = [
    "EncapsulatedKey",
    "EncapsulatedKeyRecord",
    "KeyEncapsulationOptions",
    "KeyEncapsulationResult",
]


class KeyEncapsulationOptions(abc.ABC):
    """
    Options used by a ``KeyEncapsulationService`` to encapsulate a key.

    Implementations of :class:`.KeyEncapsulationService` (or
    :class:`.AsyncKeyEncapsulationService`) are expected to define a dedicated
    subtype of this abstract base class containing the options required by the
    particular key encapsulation mechanism.

    The metadata returned by :meth:`.as_dict()` is stored alongside the
    encapsulated key in the :class:`.EncapsulatedKeyRepository` (or
    :class:`.AsyncEncapsulatedKeyRepository`) and is provided as ``metadata``
    to :meth:`.KeyEncapsulationService.decapsulate()` (or
    :meth:`.AsyncKeyEncapsulationService.decapsulate()`) when the key is
    retrieved form the repository and needs to be decapsulated.

    **Property Encryption is a preview**.
    It might be changed without following the deprecation policy.
    See also https://github.com/neo4j/neo4j-python-driver/wiki/preview-features

    .. versionadded:: 6.5

    .. seealso:: :class:`.KeyEncapsulationResult`
    """

    @abc.abstractmethod
    def as_dict(self) -> t.Mapping[str, str]:
        """
        Return the options as a mapping.

        The serialization logic will turn the mapping into a :class:`dict`.
        """


@preview("Property encryption is a preview feature.")
@dataclasses.dataclass
class KeyEncapsulationResult:
    """
    The result of a key encapsulation operation.

    Contains the encapsulated key, the metadata required to decapsulate it,
    and the key itself.

    **Property Encryption is a preview**.
    It might be changed without following the deprecation policy.
    See also https://github.com/neo4j/neo4j-python-driver/wiki/preview-features

    .. versionadded:: 6.5

    .. seealso::
        :meth:`.AsyncKeyEncapsulationService.encapsulate`,
        :meth:`.KeyEncapsulationService.encapsulate`
    """

    encapsulation: bytes
    """The encapsulated key."""

    metadata: t.Mapping[str, str]
    """
    The metadata associated with the encapsulated key.

    The metadata is provided to the :class:`.KeyEncapsulationService` when
    the key is decapsulated.
    """

    secret_key: bytes
    """
    The secret key that was encapsulated.

    This must be a valid AES-256 key, i.e. 32 bytes in length.
    """


@preview("Property encryption is a preview feature.")
@dataclasses.dataclass
class EncapsulatedKey:
    """
    A reference to an encapsulated key.

    Contains the key's globally unique id and, if assigned, its alias.

    **Property Encryption is a preview**.
    It might be changed without following the deprecation policy.
    See also https://github.com/neo4j/neo4j-python-driver/wiki/preview-features

    .. versionadded:: 6.5
    """

    id: str
    """The globally unique key id."""

    alias: str | None
    """The key alias, or :data:`None` if no alias is assigned."""


@preview("Property encryption is a preview feature.")
@dataclasses.dataclass
class EncapsulatedKeyRecord(EncapsulatedKey):
    """
    An encapsulated key with the data required to decapsulate it.

    Extends :class:`.EncapsulatedKey` with the key encapsulation and associated
    metadata required by a :class:`.KeyEncapsulationService` to decapsulate the
    key.

    **Property Encryption is a preview**.
    It might be changed without following the deprecation policy.
    See also https://github.com/neo4j/neo4j-python-driver/wiki/preview-features

    .. versionadded:: 6.5
    """

    encapsulation: bytes
    """The encapsulated key."""

    metadata: t.Mapping[str, str]
    """
    The key metadata.

    The metadata is stored along side the key via
    :meth:`.EncapsulatedKeyRecordRepository.create()` (or
    :meth:`.AsyncEncapsulatedKeyRecordRepository.create()`) when creating a
    key and passed to :meth:`.KeyEncapsulationService.decapsulate()` (or
    :meth:`.AsyncKeyEncapsulationService.decapsulate()`) when decapsulating a
    key after fetching it.
    """
