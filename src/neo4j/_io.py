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

import dataclasses
import math
import re

from ._version import VersionTuple
from . import _typing as t
from .api import ServerInfo


if t.TYPE_CHECKING:
    from .addressing import Address

__all__ = [
    "BoltProtocolVersion",
]


class BoltProtocolVersion(VersionTuple):
    pass


_VERSION_RE = re.compile(r"^(\d+)\.(\d+)")


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class HTTPServerInfo:
    neo4j_version: str
    parsed_neo4j_version: tuple[int, int] | None = dataclasses.field(
        init=False, default=None
    )
    server_agent: str = dataclasses.field(init=False)
    bolt_version: str | None
    parsed_bolt_version: BoltProtocolVersion | None = dataclasses.field(
        init=False, default=None
    )

    def __post_init__(self):
        match = _VERSION_RE.match(self.neo4j_version)
        if match is not None:
            parsed_version = tuple(map(int, match.groups()))
            object.__setattr__(self, "parsed_neo4j_version", parsed_version)
        if self.bolt_version is not None:
            match = _VERSION_RE.match(self.bolt_version)
            if match is not None:
                parsed_version = BoltProtocolVersion(*map(int, match.groups()))
                object.__setattr__(self, "parsed_bolt_version", parsed_version)
        server_agent = f"Neo4j/{self.neo4j_version}"
        object.__setattr__(self, "server_agent", server_agent)

    def as_server_info(
        self, address: Address, connection_id: str
    ) -> ServerInfo:
        protocol_version = (0, 0)
        if self.parsed_bolt_version is not None:
            protocol_version = self.parsed_bolt_version.version
        server_info = ServerInfo(address, protocol_version=protocol_version)
        server_info.update(
            {
                "protocol_version": ".".join(map(str, protocol_version)),
                "connection_id": connection_id,
                "server": self.server_agent,
            }
        )
        return server_info


def min_timeout(*timeouts: float | None) -> float | None:
    """Return the minimum timeout from an iterable of timeouts."""
    return min(
        (
            to
            for to in timeouts
            if to is not None and not math.isnan(to) and to >= 0
        ),
        default=None,
    )
