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

import enum
import json
from dataclasses import dataclass
from logging import getLogger

import aiohttp

from ... import _typing as t
from ..._addressing import Address
from ..._async.config import AsyncPoolConfig
from ..._deadline import Deadline
from ..._exceptions import QueryApiHttpError
from ..._meta import USER_AGENT
from ..._sync.config import PoolConfig


if t.TYPE_CHECKING:
    from ..._codec.hydration import (
        DehydrationHooks,
        T_TYPE_MAP_DICT,
    )


log = getLogger("neo4j.io")


__all__ = [
    "AsyncHTTPQueryAPI",
    "HTTPQueryAPI",
    "HTTPQueryAPIResponse",
    "HTTPVerb",
]


_default = object()


class AiohttpSessionRequestKwargs(t.TypedDict, total=False):
    data: t.NotRequired[t.Any]


@dataclass
class HTTPQueryAPIResponse:
    status: int
    reason: str | None
    cluster_affinity: str | None
    body: t.Any


class AsyncHTTPQueryAPI:
    @dataclass(frozen=True)
    class _ConfigCache:
        secure: bool
        pool_config: AsyncPoolConfig
        connector: aiohttp.TCPConnector
        default_headers: dict[str, str]

    CONNECTION_ERRORS: t.ClassVar[tuple[type[BaseException], ...]] = (
        aiohttp.ClientError,
        OSError,
    )

    _config_cache: t.ClassVar[_ConfigCache | None] = None

    _session: aiohttp.ClientSession

    def __init__(
        self,
        session: aiohttp.ClientSession,
    ) -> None:
        self._session = session
        # tcp_timeout: float | None,
        # deadline: Deadline,
        # custom_resolver: t.Callable | None,
        # ssl_context: SSLContext | None,
        # keep_alive: bool,

    @classmethod
    async def open(
        cls,
        address: Address,
        *,
        pool_config: AsyncPoolConfig,
        deadline: Deadline,
    ) -> t.Self:
        config = await cls._get_config_cache(pool_config)
        assert config.pool_config is pool_config, (
            "Driver must not support dynamic pool configuration changes"
        )
        return cls(
            aiohttp.ClientSession(
                base_url=_build_base_url(address, config.secure),
                connector=config.connector,
                connector_owner=False,
                headers=config.default_headers,
                cookie_jar=aiohttp.DummyCookieJar(),
                timeout=aiohttp.ClientTimeout(
                    connect=deadline.to_timeout(),
                    sock_connect=pool_config.connection_timeout,
                ),
            )
        )

    async def close(self) -> None:
        await self._session.close()

    @classmethod
    async def shutdown(cls) -> None:
        if cls._config_cache is None:
            return
        await cls._config_cache.connector.close()
        cls._config_cache = None

    @classmethod
    async def _get_config_cache(
        cls,
        pool_config: AsyncPoolConfig,
    ) -> _ConfigCache:
        if cls._config_cache is None:
            ssl_context = await pool_config.get_ssl_context()
            secure = ssl_context is not None
            connector = aiohttp.TCPConnector(
                ssl=False if ssl_context is None else ssl_context,
                use_dns_cache=False,
                # TODO? (it's ignored in Java)
                # resolver: Optional[AbstractResolver] = None,
                keepalive_timeout=pool_config.max_connection_lifetime,
                limit=0,
                limit_per_host=pool_config.max_connection_pool_size,
                enable_cleanup_closed=True,
            )
            user_agent = pool_config.user_agent
            if not user_agent:
                user_agent = USER_AGENT
            cls._config_cache = cls._ConfigCache(
                secure=secure,
                pool_config=pool_config,
                connector=connector,
                default_headers={
                    "User-Agent": user_agent,
                },
            )
        return cls._config_cache

    async def request(
        self,
        method: HTTPVerb,
        path: str,
        data: t.Any = _default,
        headers: dict[str, str] | None = None,
        *,
        dehydration_hooks: DehydrationHooks,
        hydration_hooks: T_TYPE_MAP_DICT,
        log_id: int,
    ) -> HTTPQueryAPIResponse:
        if headers is None:
            headers = {
                "Accept": "application/vnd.neo4j.query",
                "Content-Type": "application/vnd.neo4j.query",
            }
        else:
            headers |= {
                "Accept": "application/vnd.neo4j.query",
                "Content-Type": "application/vnd.neo4j.query",
            }
        if data is not _default:
            if dehydration_hooks is not None:
                transformer = dehydration_hooks.get_transformer(data)
                if transformer is not None:
                    data = transformer(data)

        res = await self._request(
            method,
            path,
            data,
            headers,
            log_id=log_id,
        )

        if hydration_hooks is not None:
            transformer = hydration_hooks.get(type(res.body), None)
            if transformer is not None:
                res.body = transformer(res.body)

        return res

    async def discovery(
        self,
        *,
        log_id: int,
    ) -> HTTPQueryAPIResponse:
        return await self._request(
            HTTPVerb.GET,
            "/",
            headers={"Accept": "application/json"},
            log_id=log_id,
        )

    async def _request(
        self,
        method: HTTPVerb,
        path: str,
        data: t.Any = _default,
        headers: dict[str, str] | None = None,
        *,
        log_id: int,
    ) -> HTTPQueryAPIResponse:
        kwargs: AiohttpSessionRequestKwargs = {}
        if data is not _default:
            kwargs["data"] = json.dumps(data, separators=(",", ":"))
            log.debug(
                "[#%04X]  C: %s %s %s",
                log_id,
                method.value,
                path,
                kwargs["data"],
            )
        else:
            log.debug("[#%04X]  C: %s %s", log_id, method.value, path)

        response = await self._session.request(
            method.value,
            path,
            headers=headers,
            allow_redirects=False,
            **kwargs,
        )

        raw_body = await response.text()
        log.debug("[#%04X]  S: %3d %r", log_id, response.status, raw_body)
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError as e:
            raise QueryApiHttpError("Invalid JSON response") from e

        return HTTPQueryAPIResponse(
            status=response.status,
            reason=response.reason,
            cluster_affinity=(
                response.headers.getone("neo4j-cluster-affinity", None)
            ),
            body=body,
        )


class HTTPQueryAPI:
    CONNECTION_ERRORS = (OSError,)

    @classmethod
    def open(
        cls,
        address: Address,
        *,
        pool_config: PoolConfig,
        deadline: Deadline,
    ) -> t.Self:
        raise NotImplementedError  # TODO

    def close(self) -> None:
        raise NotImplementedError  # TODO

    def request(
        self,
        method: HTTPVerb,
        path: str,
        data: t.Any = _default,
        headers: dict[str, str] | None = None,
        *,
        dehydration_hooks: DehydrationHooks,
        hydration_hooks: T_TYPE_MAP_DICT,
        log_id: int,
    ) -> HTTPQueryAPIResponse:
        raise NotImplementedError  # TODO


class HTTPVerb(enum.Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"


def _build_base_url(
    address: Address,
    secure: bool,
) -> str:
    scheme = "https" if secure else "http"
    host = address.host
    port = address.port
    return f"{scheme}://{host}:{port}/"
