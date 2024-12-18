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


import inspect
import typing as t


if t.TYPE_CHECKING:
    import typing_extensions as te

    from .._addressing import Address

    TAddrLike: te.TypeAlias = t.Union[Address, str]
    TAddrLikeIter: te.TypeAlias = t.Iterable[TAddrLike]
    TAsyncAddressProvider: te.TypeAlias = t.Callable[
        [],
        t.Union[
            t.Iterable[TAddrLike],
            t.Awaitable[t.Iterable[TAddrLike]],
            t.AsyncIterable[TAddrLike],
        ],
    ]
    TAddressProvider: te.TypeAlias = t.Callable[[], t.Iterable[TAddrLike]]


class AsyncAddressUtil:
    @staticmethod
    async def resolve_address_provider(
        addresses: TAddrLikeIter | TAsyncAddressProvider,
    ) -> t.Iterable[TAddrLike]:
        if not callable(addresses):
            return addresses
        addresses_called = addresses()
        addresses_iter: t.Iterable[TAddrLike]
        if inspect.isawaitable(addresses_called):
            addresses_iter = await addresses_called
        elif isinstance(addresses_called, t.AsyncIterable):
            addresses_iter = [addr async for addr in addresses_called]
        else:
            addresses_iter = addresses_called
        return addresses_iter


class AddressUtil:
    @staticmethod
    def resolve_address_provider(
        addresses: TAddrLikeIter | TAddressProvider,
    ) -> t.Iterable[TAddrLike]:
        if not callable(addresses):
            return addresses
        return addresses()
