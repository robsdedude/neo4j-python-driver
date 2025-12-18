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
from ...._addressing import Address
from ...._async_compat.concurrency import AsyncCooperativeLock
from ...._async_compat.network import AsyncHTTPQueryAPI
from ...._async_compat.util import AsyncUtil
from ...config import AsyncPoolConfig
from .._connection import AsyncConnection


if t.TYPE_CHECKING:
    from ...._addressing import Address
    from ...._auth_management import (
        AsyncAuthManager,
        AuthManager,
    )
    from ...._deadline import Deadline


class IdGenerator:
    _next_id: int
    _lock: AsyncCooperativeLock

    def __init__(self) -> None:
        self._next_id = 1
        self._lock = AsyncCooperativeLock()

    async def next_id(self) -> int:
        async with self._lock:
            current_id = self._next_id
            self._next_id += 1
        return current_id


class AsyncHttpConnection(AsyncConnection, abc.ABC):
    _id_generator: t.ClassVar[IdGenerator] = IdGenerator()

    @classmethod
    async def open(
        cls,
        address: Address,
        *,
        auth_manager: AsyncAuthManager | AuthManager,
        deadline: Deadline,
        routing_context: dict[str, str] | None,
        pool_config: AsyncPoolConfig | None,
    ) -> AsyncHttpConnection:
        assert routing_context is None, "Found routing context over HTTP"
        if pool_config is None:
            pool_config = AsyncPoolConfig()
        auth = await AsyncUtil.callback(auth_manager.get_auth)
        query_api = await AsyncHTTPQueryAPI.open(
            address,
            pool_config=pool_config,
            deadline=deadline,
        )
        id_ = await cls._id_generator.next_id()

        from ._http2 import AsyncHttpV2

        http_cls = AsyncHttpV2

        connection = http_cls(
            address,
            query_api=query_api,
            auth=auth,
            auth_manager=auth_manager,
            id_=id_,
        )

        connection.server_info.update(
            {
                "protocol_version": "0.0",
                "connection_id": str(id_),
                "server": await http_cls._server_agent_cache.get(connection),
            }
        )

        return connection

    @abc.abstractmethod
    async def close(self) -> None:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def connection_id(self) -> int:
        raise NotImplementedError

    @classmethod
    async def shutdown(cls) -> None:
        await AsyncHTTPQueryAPI.shutdown()
