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

from .... import _typing as t


if t.TYPE_CHECKING:
    from ...._property_encryption.profile_envelope import EncapsulatedKeyRecord


__all__ = [
    "EncapsulatedKeyRecordRepository",
]


class EncapsulatedKeyRecordRepository(abc.ABC):
    """
    A repository for :class:`.EncapsulatedKeyRecord` data.

    Implementations of this abstract base class represent some persistent
    storage for encapsulated keys. Encapsulation and decapsulation of keys
    before storage and after retrieval respectively is handled by a
    :class:`.KeyEncapsulationService` implementation.

    Any implementation of this abstract base class must be thread-safe.

    **Property Encryption is a preview**.
    It might be changed without following the deprecation policy.
    See also https://github.com/neo4j/neo4j-python-driver/wiki/preview-features

    .. versionadded:: 6.5
    """

    @abc.abstractmethod
    def find_by_id(self, id: str) -> EncapsulatedKeyRecord | None:
        """
        Find and return an :class:`.EncapsulatedKeyRecord` by its id.

        :param id: the id by which to look up the key.

        :returns: the key, or :data:`None` if no key with the given id exists.
        """
        ...

    @abc.abstractmethod
    def find_by_alias(self, alias: str) -> EncapsulatedKeyRecord | None:
        """
        Find and return an :class:`.EncapsulatedKeyRecord` by its alias.

        :param alias: the alias by which to look up the key.

        :returns: the key, or :data:`None` if no key with the given alias
            exists.
        """
        ...

    @abc.abstractmethod
    def create(
        self,
        alias: str | None,
        encapsulation: bytes,
        metadata: t.Mapping[str, str],
    ) -> EncapsulatedKeyRecord:
        """
        Create a new encapsulated key and assign a globally unique id.

        Wraps the given encapsulation and metadata in an
        :class:`.EncapsulatedKeyRecord` and stores it in the repository.

        The generated id **must** be globally unique and immutable.
        Implementations **should** use a mechanism designed to generate
        globally unique identifiers, such as UUIDs.

        :param alias: the alias to assign to the key, or :data:`None` if no
            alias should be assigned.
        :param encapsulation: the key encapsulation.
        :param metadata: the key metadata.

        :returns: the created key.
        """
        ...

    @abc.abstractmethod
    def set_alias_by_id(self, id: str, alias: str | None) -> None:
        """
        Set the alias of an encapsulated key by id.

        The alias **must not** be used by another key. To assign an alias
        currently used by another key, it must first be deleted from that key.

        Implementers are advised to raise an error if the id cannot be found in
        the repository or if the alias is already in use by another key.

        :param id: the id of the key for which to set the alias.
        :param alias: the alias to assign to the key, or :data:`None` to remove
            the alias.
        """
        ...

    @abc.abstractmethod
    def delete_by_id(self, id: str) -> None:
        """
        Delete a key by id.

        Implementers are advised to raise an error if the id cannot be found in
        the repository.

        :param id: the id of the key to delete.
        """
        ...
