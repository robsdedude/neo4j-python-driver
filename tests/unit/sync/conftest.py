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


# necessary for pytest to discover the fixtures
from .fixtures import (
    fake_connection,
    fake_connection_generator,
    fake_pool,
    scripted_connection,
    scripted_connection_generator,
)


__all__ = [
    "fake_connection",
    "fake_connection_generator",
    "fake_pool",
    "scripted_connection",
    "scripted_connection_generator",
]

TRUE_ENV_VALUES = {"1", "y", "yes", "true", "t", "on"}


# TODO: explain
def pytest_asyncio_loop_factories(config, item):
    import asyncio
    import os
    import sys
    import time

    is_win = sys.platform in {"win32", "cygwin"}
    is_gha = os.environ.get("GITHUB_ACTION", "").lower() in TRUE_ENV_VALUES

    if is_win and is_gha:
        last_call = time.monotonic()

        def throttled_new_event_loop():
            nonlocal last_call

            now = time.monotonic()
            since_last_call = now - last_call
            last_call = now
            if since_last_call < 0.001:
                time.sleep(0.001 - since_last_call)
            return asyncio.new_event_loop()

        return {"throttled": throttled_new_event_loop}

    return {"default": asyncio.new_event_loop}
