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


"""
Functionality to encrypt and decrypt property values on the client side.

**Property Encryption is a preview**.
It might be changed without following the deprecation policy.
See also https://github.com/neo4j/neo4j-python-driver/wiki/preview-features

.. note::

    To be able to use this feature, the optional dependencies ``encryption``
    need to be installed. For example::

        pip install neo4j[encryption]

The main entry-point for encryption and decryption is
:meth:`.Driver.property_encryption` and
:meth:`.AsyncDriver.property_encryption` respectively.

TODO: explain AAD normalization is user responsibility
> Drivers MUST document that users may want to consider normalizing STRING
> values using something like NFC before providing them to the driver when both
> encrypting and decrypting values.


General Workflow
^^^^^^^^^^^^^^^^

TODO: how does on even?


FIPS Compliance
^^^^^^^^^^^^^^^

TODO: explain FIPS compliance
 * requires ``os.random`` to be FIPS compliant
 * requires Python to be linked against OpenSSL in FIPS mode

.. versionadded:: 6.5
"""

from __future__ import annotations

from ._async.property_encryption import (
    AsyncEncapsulatedKeyRecordRepository,
    AsyncEnvelopePropertyEncryptionProfile,
    AsyncKeyEncapsulationService,
    AsyncPropertyEncryption,
    AsyncPropertyEncryptionProfile,
)
from ._property_encryption.api import (
    AadChoiceDecryption,
    AadChoiceEncryption,
    KeyChoice,
)
from ._property_encryption.profile_envelope import (
    EncapsulatedKeyRecord,
    KeyEncapsulationOptions,
    KeyEncapsulationResult,
)
from ._sync.property_encryption import (
    EncapsulatedKeyRecordRepository,
    EnvelopePropertyEncryptionProfile,
    KeyEncapsulationService,
    PropertyEncryption,
    PropertyEncryptionProfile,
)
from ._warnings import preview_warn


__all__ = [
    "AadChoiceDecryption",
    "AadChoiceEncryption",
    "AsyncEncapsulatedKeyRecordRepository",
    "AsyncEnvelopePropertyEncryptionProfile",
    "AsyncKeyEncapsulationService",
    "AsyncPropertyEncryption",
    "AsyncPropertyEncryptionProfile",
    "EncapsulatedKeyRecord",
    "EncapsulatedKeyRecordRepository",
    "EnvelopePropertyEncryptionProfile",
    "KeyChoice",
    "KeyEncapsulationOptions",
    "KeyEncapsulationResult",
    "KeyEncapsulationService",
    "PropertyEncryption",
    "PropertyEncryptionProfile",
]

preview_warn("Property encryption is a preview feature.", stack_level=2)
