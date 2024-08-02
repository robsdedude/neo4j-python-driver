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

import time
import typing as t

from ..._api import RoutingControl
from ..._async_compat.concurrency import (
    CooperativeLock,
    Lock,
)
from ..._ogm.cypher import VERSION_QUERY
from ...api import READ_ACCESS
from ...exceptions import (
    DriverError,
    Neo4jError,
)
from ..work.session import retry_delay_generator


if t.TYPE_CHECKING:
    import typing_extensions as te

    from ..driver import Driver


__all__ = [
    "DBMSMeta",
    "DBMSMetaProvider",
]


# TODO: replace all t.Any


STALE_AFTER: float = 3600.0


class DBMSMeta:
    _checked_at: float
    version: t.Tuple[int, int]

    def _parse_version(self, version: t.Any) -> t.Tuple[int, int]:
        if not isinstance(version, str):
            raise TypeError(
                f"DBMS version: expected str, got {type(version).__name__}"
            )
        try:
            version = tuple(map(int, version.split(".")))
        except (ValueError, TypeError) as e:
            raise type(e)("Failed to parse DBMS version:") from e
        if len(version) < 2:
            raise ValueError("DBMS version: expected at least 2 components")
        return version[0], version[1]

    @classmethod
    def load(cls, driver: Driver, *, retry: bool) -> te.Self:
        if retry:
            record = driver.execute_query(
                VERSION_QUERY,
                database_="system",
                routing_=RoutingControl.READ,
                result_transformer_=lambda r: r.single(strict=True),
            )
        else:
            with driver.session(
                database="system",
                default_access_mode=READ_ACCESS
            ) as session:
                result = session.run(VERSION_QUERY)
                record = result.single(strict=True)

        version = record["version"]
        obj = cls()
        obj._checked_at = time.time()
        obj.version = obj._parse_version(version)
        return obj

    def _stale(self) -> bool:
        return time.time() - self._checked_at > STALE_AFTER

    def _extend_lifetime(self, delay: float) -> None:
        self._checked_at += delay


class DBMSMetaProvider:
    _current: t.Optional[DBMSMeta] = None
    _refresh_lock: Lock
    _retry_lock: CooperativeLock
    _fail_delay: t.Generator[float, None, None]

    def __init__(self, driver: Driver) -> None:
        self._driver = driver
        self._refresh_lock = Lock()
        self._retry_lock = CooperativeLock()
        self._reset_retry()

    def _reset_retry(self) -> None:
        self._fail_delay = retry_delay_generator(1, 2, 0.2)

    def get(self) -> DBMSMeta:
        if self._current is not None and not self._current._stale():
            return self._current
        with self._refresh_lock:
            # check if another task has updated the metadata while we were
            # waiting for the lock
            if self._current is not None and not self._current._stale():
                return self._current

            if self._current is None:
                self._current = DBMSMeta.load(
                    self._driver, retry=True
                )
                return self._current

            try:
                self._current = DBMSMeta.load(
                    self._driver, retry=False
                )
                self._reset_retry()
            except (DriverError, Neo4jError) as e:
                if not e.is_retryable():
                    raise
                delay = max(next(self._fail_delay), STALE_AFTER)
                self._current._extend_lifetime(delay)

            return self._current
