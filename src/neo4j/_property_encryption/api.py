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

from .. import _typing as t
from .._warnings import preview


__all__ = [
    "AadChoiceDecryption",
    "AadChoiceEncryption",
    "KeyChoice",
]


class _AadChoice:
    _value: object

    def __init__(self, value: object) -> None:
        self._value = value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._value!r})"


@preview("Property encryption is a preview feature.")
class AadChoiceEncryption(_AadChoice):
    """
    Represents a choice of additional authenticated data (AAD) for encryption.

    The AAD helps to ensure the integrity of the encrypted data and can be used
    to bind the encrypted data to a specific context or purpose.
    The AAD can either be a specific value (``AadChoiceEncryption(value)``) or
    to be absent (i.e., no AAD is being used—:meth:`.none()`).

    .. important::
        Using no AAD means that an attacker is able to swap encrypted values
        between different entities even without being able to decrypt it.

        Using the stored AAD, while providing some level of integrity, does not
        protect against the previous case either.

        Using an explicit AAD value provides the highest level of integrity
        check.

    **Property Encryption is a preview**.
    It might be changed without following the deprecation policy.
    See also https://github.com/neo4j/neo4j-python-driver/wiki/preview-features

    .. versionadded:: 6.5
    """

    _value: object

    def __init__(self, value: object) -> None:
        """Use the give ``value`` as the AAD."""
        super().__init__(value)

    @classmethod
    def none(cls) -> t.Self:
        """Use no AAD."""
        return cls(AAD_CHOICE_NONE)

    def __repr__(self) -> str:
        if self._value is AAD_CHOICE_NONE:
            return f"{self.__class__.__name__}.none()"
        return super().__repr__()


@preview("Property encryption is a preview feature.")
class AadChoiceDecryption(_AadChoice):
    """
    Represents a choice of additional authenticated data (AAD) for decryption.

    The AAD helps to ensure the integrity of the encrypted data and can be used
    to bind the encrypted data to a specific context or purpose.
    The AAD can either be a specific value (``AadChoiceDecryption(value)``) or
    the AAD stored alongside the encrypted value may be used
    (:meth:`.external()`).

    .. important::
        Using the stored AAD, while providing some level of integrity, means
        that an attacker is able to swap encrypted values between different
        entities even without being able to decrypt it.

        Using an explicit AAD value provides the highest level of integrity
        check.

    **Property Encryption is a preview**.
    It might be changed without following the deprecation policy.
    See also https://github.com/neo4j/neo4j-python-driver/wiki/preview-features

    .. versionadded:: 6.5
    """

    _value: object

    def __init__(self, value: object) -> None:
        """Use the give ``value`` as the AAD."""
        super().__init__(value)

    @classmethod
    def external(cls) -> t.Self:
        """Use the AAD stored alongside the encrypted value."""
        return cls(AAD_CHOICE_USE_EXTERNAL)

    def __repr__(self) -> str:
        if self._value is AAD_CHOICE_USE_EXTERNAL:
            return f"{self.__class__.__name__}.external()"
        return super().__repr__()


# TODO: when dropping support for Python 3.14, use sentinel
AAD_CHOICE_NONE = object()
AAD_CHOICE_USE_EXTERNAL = object()


@preview("Property encryption is a preview feature.")
class KeyChoice:
    """
    Represents a key choice to be used for encryption/decyrption.

    A key may either be selected by its id, or by its alias.
    Exactly one of these must be specified when creating a :class:`.KeyChoice`
    instance.

    :raises ValueError: if not exactly one of ``id`` or ``alias`` is specified.

    **Property Encryption is a preview**.
    It might be changed without following the deprecation policy.
    See also https://github.com/neo4j/neo4j-python-driver/wiki/preview-features

    .. versionadded:: 6.5

    .. seealso::
        :meth:`.PropertyEncryption.encrypt_to_bytes`,
        :meth:`.AsyncPropertyEncryption.encrypt_to_bytes`
    """

    _id: str | None
    _alias: str | None

    @t.overload
    def __init__(
        self, *, id: str | None = None, alias: None = None
    ) -> None: ...
    @t.overload
    def __init__(
        self, *, id: None = None, alias: str | None = None
    ) -> None: ...
    def __init__(
        self, *, id: str | None = None, alias: str | None = None
    ) -> None:
        if id is not None and alias is not None:
            raise ValueError("Cannot specify both id and alias")
        if id is None and alias is None:
            raise ValueError("Must specify either id or alias")
        self._id = id
        self._alias = alias

    def __repr__(self) -> str:
        if self._id is not None:
            return f"{self.__class__.__name__}(id={self._id!r})"
        return f"{self.__class__.__name__}(alias={self._alias!r})"
