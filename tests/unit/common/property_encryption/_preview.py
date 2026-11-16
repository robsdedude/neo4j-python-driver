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
from neo4j.warnings import PreviewWarning


with pytest.warns(PreviewWarning, match=r"\bProperty encryption\b"):
    from neo4j.property_encryption import (
        AadChoiceDecryption as _AadChoiceDecryption,
        AadChoiceEncryption as _AadChoiceEncryption,
        EncapsulatedKeyRecord as _EncapsulatedKeyRecord,
        KeyChoice as _KeyChoice,
        KeyEncapsulationResult as _KeyEncapsulationResult,
    )

if t.TYPE_CHECKING:
    from neo4j.property_encryption import (
        AadChoiceDecryption,
        AadChoiceEncryption,
        EncapsulatedKeyRecord,
        KeyChoice,
        KeyEncapsulationResult,
    )

else:

    def AadChoiceDecryption(*args, **kwargs):  # noqa: N802
        with pytest.warns(PreviewWarning, match=r"\bProperty encryption\b"):
            return _AadChoiceDecryption(*args, **kwargs)

    def AadChoiceEncryption(*args, **kwargs):  # noqa: N802
        with pytest.warns(PreviewWarning, match=r"\bProperty encryption\b"):
            return _AadChoiceEncryption(*args, **kwargs)

    def EncapsulatedKeyRecord(*args, **kwargs):  # noqa: N802
        with pytest.warns(PreviewWarning, match=r"\bProperty encryption\b"):
            return _EncapsulatedKeyRecord(*args, **kwargs)

    def KeyChoice(*args, **kwargs):  # noqa: N802
        with pytest.warns(PreviewWarning, match=r"\bProperty encryption\b"):
            return _KeyChoice(*args, **kwargs)

    def KeyEncapsulationResult(*args, **kwargs):  # noqa: N802
        with pytest.warns(PreviewWarning, match=r"\bProperty encryption\b"):
            return _KeyEncapsulationResult(*args, **kwargs)
