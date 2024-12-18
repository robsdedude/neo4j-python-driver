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

import typing as t
from types import MappingProxyType
from urllib.parse import urlparse

from .. import _api
from .._addressing import Address
from .._async_compat.address import AsyncAddressUtil
from .._meta import preview
from ..exceptions import ConfigurationError


if t.TYPE_CHECKING:
    from urllib.parse import ParseResult

    import typing_extensions as te

    TAddrLike: te.TypeAlias = t.Union[Address, str]
    TAddrLikeIter: te.TypeAlias = t.Iterable[TAddrLike]
    TAddressProvider: te.TypeAlias = t.Callable[
        [],
        t.Union[
            TAddrLikeIter,
            t.Awaitable[TAddrLikeIter],
            t.AsyncIterable[TAddrLike],
        ],
    ]

__all__ = [
    "AsyncMultiAddress",
    "_AsyncMultiAddress",
]


class _AsyncMultiAddress:
    """
    TODO write these docs.

    .. note:: for direct driver all addresses are assumed to belong to the
        same server

    :param scheme: TODO
    :param addresses: TODO
    :param routing_context: TODO
    """

    _scheme: str
    _driver_type: str
    _security_type: str
    _addresses: tuple[Address, ...] | TAddressProvider
    _routing_context: dict[str, str]

    __slots__ = (  # noqa: RUF023 - in order of definition above
        "_scheme",
        "_driver_type",
        "_security_type",
        "_addresses",
        "_routing_context",
    )

    def __init__(
        self,
        scheme: str,
        addresses: TAddrLikeIter | TAddressProvider,
        routing_context: t.Mapping[str, str] | None = None,
    ) -> None:
        self._scheme = scheme
        self._driver_type, self._security_type = _api.parse_uri_scheme(scheme)
        if not callable(addresses):
            self._addresses = self._collect_addresses(addresses)
        else:
            self._addresses = addresses
        self._routing_context = dict(routing_context or {})

        if self._driver_type == _api.DRIVER_BOLT and self._routing_context:
            raise ConfigurationError(
                "Direct drivers (bolt[+s[sc]] scheme) don't support "
                "having a routing context"
            )
        if "address" in self._routing_context:
            raise ConfigurationError(
                "The key 'address' is reserved for routing context."
            )

    def __repr__(self):
        if not callable(self._addresses):
            return (
                f"{self.__class__.__name__}("
                f"scheme={self._scheme!r}, "
                f"addresses={self._addresses!r}, "
                f"routing_context={self._routing_context!r})"
            )
        return (
            f"<{self.__class__.__name__} "
            f"scheme={self._scheme!r}, "
            f"addresses={self._addresses!r}, "
            f"routing_context={self._routing_context!r} "
            f"at {hex(id(self))}>"
        )

    @staticmethod
    def _collect_addresses(
        addresses: TAddrLikeIter,
    ) -> tuple[Address, ...]:
        # (ab)using dict keys as sorted set
        consolidated_addresses = {
            AsyncMultiAddress._consolidate_address(address): None
            for address in addresses
        }
        return tuple(consolidated_addresses.keys())

    @staticmethod
    def _consolidate_address(address: str | Address) -> Address:
        if isinstance(address, Address):
            return address
        return Address.parse(
            address,
            default_host="localhost",
            default_port=7687,
        )

    def __eq__(self, other):
        if not isinstance(other, AsyncMultiAddress):
            return NotImplemented
        return (
            self._scheme == other._scheme
            and self._addresses == other._addresses
            and self._routing_context == other._routing_context
        )

    @property
    def scheme(self) -> str:
        return self._scheme

    async def addresses(self) -> t.Sequence[Address]:
        if not callable(self._addresses):
            return self._addresses
        return self._collect_addresses(
            await AsyncAddressUtil.resolve_address_provider(self._addresses)
        )

    @property
    def routing_context(self) -> t.Mapping[str, t.Any]:
        return MappingProxyType(self._routing_context)

    @classmethod
    def _from_url(cls, url: str | ParseResult) -> te.Self:
        if isinstance(url, str):
            url = urlparse(url)

        if url.username:
            raise ConfigurationError("Username is not supported in the URI")
        if url.password:
            raise ConfigurationError("Password is not supported in the URI")

        routing_context = _api.parse_routing_context(url.query)
        return cls(url.scheme, (url.netloc,), routing_context)


@preview("MultiAddress support is a preview feature")
class AsyncMultiAddress(_AsyncMultiAddress):
    pass
