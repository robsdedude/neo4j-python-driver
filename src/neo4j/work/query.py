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

# TODO: 6.0 - remove this file


from .._warnings import deprecation_warn as _deprecation_warn
from .._work import (
    Query,
    unit_of_work,
)


__all__ = [
    "unit_of_work",
    "Query",
]

_deprecation_warn(
    "The module `neo4j.work.summary` was made internal and will "
    "no longer be available for import in future versions. "
    "Everything from there should be imported directly from `neo4j`.",
    stack_level=2
)
