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
import sys
from dataclasses import dataclass
from logging import getLogger
from socket import (
    SO_KEEPALIVE,
    socket,
    SOL_SOCKET,
)

import aiohttp
import urllib3

from ... import _typing as t
from ..._async_compat.concurrency import (
    AsyncLock,
    Lock,
)
from ..._exceptions import QueryApiHttpError
from ..._meta import USER_AGENT
from ...exceptions import ServiceUnavailable


if t.TYPE_CHECKING:
    from aiohappyeyeballs import AddrInfoType

    from ..._addressing import Address
    from ..._async.config import AsyncPoolConfig
    from ..._sync.config import PoolConfig


log = getLogger("neo4j.io")


__all__ = [
    "NO_DATA",
    "AsyncHTTPQueryAPI",
    "AsyncHTTPQueryAPIFactory",
    "HTTPQueryAPI",
    "HTTPQueryAPIFactory",
    "HTTPQueryAPIResponse",
    "HTTPVerb",
]


NO_DATA = object()
ENABLE_CLEANUP_CLOSED = (
    sys.version_info < (3, 12)
    or (3, 12) <= sys.version_info < (3, 12, 8)
    or (3, 13) <= sys.version_info < (3, 13, 1)
)


class AiohttpSessionRequestKwargs(t.TypedDict, total=False):
    data: t.NotRequired[t.Any]


class Urllib3RequestKwargs(t.TypedDict, total=False):
    body: t.NotRequired[str]


@dataclass
class HTTPQueryAPIResponse:
    status: int
    reason: str | None
    cluster_affinity: str | None
    body: t.Any


class AsyncHTTPQueryAPIFactory:
    @dataclass(frozen=True)
    class _ConfigCache:
        secure: bool
        pool_config: AsyncPoolConfig
        connector: aiohttp.TCPConnector

    CONNECTION_ERRORS: t.ClassVar[tuple[type[BaseException], ...]] = (
        aiohttp.ClientError,
        OSError,
    )

    _config_cache: _ConfigCache | None = None
    _config_cache_lock: AsyncLock
    _closed: bool = False

    def __init__(self) -> None:
        self._config_cache_lock = AsyncLock()

    async def new_http_query_api(
        self,
        address: Address,
        *,
        pool_config: AsyncPoolConfig,
    ) -> AsyncHTTPQueryAPI:
        config = await self._get_config_cache(pool_config)
        timeout = aiohttp.ClientTimeout(
            total=5 * 60,
            sock_connect=pool_config.connection_timeout,
        )
        return AsyncHTTPQueryAPI(
            aiohttp.ClientSession(
                base_url=_build_base_url(address, config.secure),
                connector=config.connector,
                connector_owner=False,
                cookie_jar=aiohttp.DummyCookieJar(),
                timeout=timeout,
            )
        )

    async def _get_config_cache(
        self,
        pool_config: AsyncPoolConfig,
    ) -> _ConfigCache:
        async with self._config_cache_lock:
            if self._config_cache is None:
                if self._closed:
                    raise OSError(
                        "Cannot open HTTP connection: session already closed"
                    )
                self._config_cache = await self._new_config_cache(pool_config)
            else:
                assert self._config_cache.pool_config is pool_config, (
                    "Driver must not support dynamic pool configuration "
                    "changes"
                )
            return self._config_cache

    async def _new_config_cache(
        self, pool_config: AsyncPoolConfig
    ) -> _ConfigCache:
        def socket_factory(addr_info: AddrInfoType) -> socket:
            family, type_, proto, _, _ = addr_info
            sock = socket(family=family, type=type_, proto=proto)
            keep_alive = 1 if pool_config.keep_alive else 0
            sock.setsockopt(SOL_SOCKET, SO_KEEPALIVE, keep_alive)
            return sock

        ssl_context = await pool_config.get_ssl_context()
        secure = ssl_context is not None
        connector = aiohttp.TCPConnector(
            ssl=False if ssl_context is None else ssl_context,
            use_dns_cache=False,
            # TODO? (it's ignored in Java)
            # resolver: Optional[AbstractResolver] = None,
            keepalive_timeout=pool_config.max_connection_lifetime,
            limit=0,
            enable_cleanup_closed=ENABLE_CLEANUP_CLOSED,
            socket_factory=socket_factory,
        )
        user_agent = pool_config.user_agent
        if not user_agent:
            user_agent = USER_AGENT
        return self._ConfigCache(
            secure=secure,
            pool_config=pool_config,
            connector=connector,
        )

    async def shutdown(self) -> None:
        async with self._config_cache_lock:
            self._closed = True
            self._config_cache, config_cache = None, self._config_cache
        if config_cache is None:
            return
        await config_cache.connector.close()


class AsyncHTTPQueryAPI:
    CONNECTION_ERRORS: t.ClassVar[tuple[type[BaseException], ...]] = (
        aiohttp.ClientError,
        OSError,
    )

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

    async def close(self) -> None:
        await self._session.close()

    def closed(self) -> bool:
        return self._session.closed

    async def request(
        self,
        method: HTTPVerb,
        path: str,
        data: t.Any = NO_DATA,
        headers: dict[str, str] | None = None,
        *,
        log_id: int,
    ) -> HTTPQueryAPIResponse:
        kwargs: AiohttpSessionRequestKwargs = {}
        if data is not NO_DATA:
            kwargs["data"] = json.dumps(data, separators=(",", ":"))
            log.debug(
                "[#%04X]  C: %s %s %s (%s)",
                log_id,
                method.value,
                path,
                kwargs["data"],
                _HeaderLogFormatter(headers),
            )
        else:
            log.debug(
                "[#%04X]  C: %s %s (%s)",
                log_id,
                method.value,
                path,
                _HeaderLogFormatter(headers),
            )

        try:
            response = await self._session.request(
                method.value,
                path,
                headers=headers,
                allow_redirects=False,
                **kwargs,
            )
        except aiohttp.ClientError as e:
            raise ServiceUnavailable(str(e)) from e

        raw_body = await response.text()
        log.debug(
            "[#%04X]  S: %3d %r (%s)",
            log_id,
            response.status,
            raw_body,
            response.headers,
        )
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


class HTTPQueryAPIFactory:
    @dataclass(frozen=True)
    class _ConfigCache:
        pool: urllib3.HTTPConnectionPool
        pool_config: PoolConfig
        address: Address

    _config_cache: _ConfigCache | None = None
    _config_cache_lock: Lock
    _closed: bool = False

    def __init__(self) -> None:
        self._config_cache_lock = Lock()

    def new_http_query_api(
        self,
        address: Address,
        *,
        pool_config: PoolConfig,
    ) -> HTTPQueryAPI:
        config = self._get_config_cache(address, pool_config)
        return HTTPQueryAPI(config.pool)

    def _get_config_cache(
        self,
        address: Address,
        pool_config: PoolConfig,
    ) -> _ConfigCache:
        with self._config_cache_lock:
            if self._config_cache is None:
                if self._closed:
                    raise OSError(
                        "Cannot open HTTP connection: session already closed"
                    )
                self._config_cache = self._new_config_cache(
                    address, pool_config
                )
            else:
                assert self._config_cache.pool_config is pool_config, (
                    "Driver must not support dynamic pool configuration "
                    "changes"
                )
                assert self._config_cache.address is address, (
                    "Query API/HTTP pool must always point to the same address"
                )
            return self._config_cache

    def _new_config_cache(
        self, address: Address, pool_config: PoolConfig
    ) -> _ConfigCache:
        pool = self._new_pool(address, pool_config)
        return self._ConfigCache(
            pool=pool,
            pool_config=pool_config,
            address=address,
        )

    def _new_pool(
        self,
        address: Address,
        pool_config: PoolConfig,
    ) -> urllib3.HTTPConnectionPool:
        # TODO: pool_config.max_connection_lifetime
        #       urllib3 doesn't seem to support this :/

        extra_kwargs = {}
        ssl_context = pool_config.get_ssl_context()
        secure = ssl_context is not None
        if secure:
            extra_kwargs["ssl_context"] = ssl_context
        keep_alive = 1 if pool_config.keep_alive else 0
        return urllib3.connectionpool.connection_from_url(
            _build_base_url(address, secure),
            maxsize=0,
            socket_options=[
                (SOL_SOCKET, SO_KEEPALIVE, keep_alive),
            ],
            timeout=urllib3.Timeout(
                total=5 * 60,
                connect=pool_config.connection_timeout,
            ),
            **extra_kwargs,
        )

    def shutdown(self) -> None:
        with self._config_cache_lock:
            self._closed = True
            self._config_cache, config_cache = None, self._config_cache
        if config_cache is None:
            return
        config_cache.pool.close()


class HTTPQueryAPI:
    CONNECTION_ERRORS = (OSError,)

    _pool: urllib3.HTTPConnectionPool

    _closed: bool = False

    def __init__(self, pool: urllib3.HTTPConnectionPool) -> None:
        self._pool = pool

    def close(self) -> None:
        self._closed = True

    def request(
        self,
        method: HTTPVerb,
        path: str,
        data: t.Any = NO_DATA,
        headers: dict[str, str] | None = None,
        *,
        log_id: int,
    ) -> HTTPQueryAPIResponse:
        kwargs: Urllib3RequestKwargs = {}
        if data is not NO_DATA:
            kwargs["body"] = json.dumps(data, separators=(",", ":"))
            log.debug(
                "[#%04X]  C: %s %s %s (%s)",
                log_id,
                method.value,
                path,
                kwargs["body"],
                _HeaderLogFormatter(headers),
            )
        else:
            log.debug(
                "[#%04X]  C: %s %s (%s)",
                log_id,
                method.value,
                path,
                _HeaderLogFormatter(headers),
            )

        try:
            response = self._pool.request(
                method.value,
                path,
                headers=headers,
                redirect=False,
                **kwargs,
            )
        except urllib3.exceptions.HTTPError as e:
            raise ServiceUnavailable(str(e)) from e

        raw_body = response.data.decode("utf-8")
        log.debug(
            "[#%04X]  S: %3d %r (%s)",
            log_id,
            response.status,
            raw_body,
            response.headers,
        )
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError as e:
            raise QueryApiHttpError("Invalid JSON response") from e

        return HTTPQueryAPIResponse(
            status=response.status,
            reason=response.reason,
            cluster_affinity=(
                response.headers.get("neo4j-cluster-affinity", None)
            ),
            body=body,
        )

    def closed(self) -> bool:
        return self._closed


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


class _HeaderLogFormatter:
    _REDACTED_HEADERS = frozenset(("authorization", "cookie"))

    _headers: dict[str, str] | None
    _cleaned: bool = False

    def __init__(self, headers: dict[str, str] | None) -> None:
        self._headers = headers

    def __repr__(self) -> str:
        if self._headers is None:
            return repr({})
        if not self._cleaned:
            self._clean_headers()
        return repr(self._headers)

    def _clean_headers(self) -> None:
        self._cleaned = True
        if self._headers is None:
            return
        if not any(
            redacted_header in self._headers
            for redacted_header in self._REDACTED_HEADERS
        ):
            return
        self._headers = dict(self._headers)
        for redacted_header in self._REDACTED_HEADERS:
            self._headers[redacted_header] = "*******"
