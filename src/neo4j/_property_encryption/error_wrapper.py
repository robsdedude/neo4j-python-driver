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


from functools import wraps

from ..exceptions import (
    DriverError,
    Neo4jError,
    PropertyEncryptionError,
)


__all__ = [
    "property_encryption_error_wrapper",
]


def property_encryption_error_wrapper(message):
    def decorator(func):
        @wraps(func)
        def inner(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except (DriverError, Neo4jError):
                raise
            except Exception as e:
                raise PropertyEncryptionError(message) from e

        return inner

    return decorator
