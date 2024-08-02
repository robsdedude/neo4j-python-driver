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

from ..._api import RoutingControl
from ..._ogm import cypher as cy
from .dbms_meta import DBMSMetaProvider


if t.TYPE_CHECKING:
    import typing_extensions as te
    LiteralString = te.LiteralString

    from ..._ogm.model import Model
    from ..driver import Driver
else:
    LiteralString = t.Any


__all__ = [
    "OGM",
    "OGMRegistry",
]


# TODO: replace all t.Any

class OGMRegistry:
    _nodes: t.Any
    _relationships: t.Any

    def register(self, *models: Model) -> t.Any:
        # TODO: implement
        if len(models) == 1:
            return models[0]


class OGM:
    _driver: Driver
    _registry: OGMRegistry
    _DBMSMetaProvider: DBMSMetaProvider

    @classmethod
    def _new(cls, driver: Driver, registry: OGMRegistry) -> te.Self:
        instance = cls()
        instance._driver = driver
        instance._registry = registry
        instance._DBMSMetaProvider = DBMSMetaProvider(driver)
        return instance

    def save(self, model: Model):
        n = cy.Node(
            labels=[type(model).__name__],
            properties=model.model_dump()
        )
        create = cy.Create(n)
        meta = self._DBMSMetaProvider.get()
        query = cy.CypherBuilder(meta.version).build(create)
        self._driver.execute_query(
            t.cast(LiteralString, query.query),
            parameters_=query.parameters,
            routing_=RoutingControl.WRITE,
            # TODO: make database configurable
            database_="neo4j",
        )
