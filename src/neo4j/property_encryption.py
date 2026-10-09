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
TODO: docs.

**Property Encryption is a preview**.
It might be changed without following the deprecation policy.
See also https://github.com/neo4j/neo4j-python-driver/wiki/preview-features

TODO: explain AAD normalization is user responsibility
> Drivers MUST document that users may want to consider normalizing STRING
> values using something like NFC before providing them to the driver when both
> encrypting and decrypting values.
"""


from __future__ import annotations

from ._warnings import preview_warn
from ._async.property_encryption import (
    AsyncEnvelopePropertyEncryptionProfile,
    AsyncPropertyEncryptionProfile,
    AsyncKeyEncapsulationService,
    AsyncEncapsulatedKeyRecordRepository,
)
from ._sync.property_encryption import (
    EnvelopePropertyEncryptionProfile,
    PropertyEncryptionProfile,
    KeyEncapsulationService,
    EncapsulatedKeyRecordRepository,
)
from ._property_encryption.profile_envelope import (
    KeyEncapsulationOptions,
    KeyEncapsulationResult,
)

__all__ = [
    "AsyncEncapsulatedKeyRecordRepository",
    "AsyncEnvelopePropertyEncryptionProfile",
    "AsyncKeyEncapsulationService",
    "AsyncPropertyEncryptionProfile",
    "EncapsulatedKeyRecordRepository",
    "EnvelopePropertyEncryptionProfile",
    "KeyEncapsulationOptions",
    "KeyEncapsulationResult",
    "KeyEncapsulationService",
    "PropertyEncryptionProfile",
]

preview_warn("Property encryption is a preview feature.", stack_level=2)
