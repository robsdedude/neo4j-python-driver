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
from ..._data import Record
from ..._ogm import cypher as cy
from ..._ogm.cypher import filters as cy_f
from ..._ogm.log import log
from ...api import WRITE_ACCESS
from .dbms_meta import DBMSMetaProvider


if t.TYPE_CHECKING:
    import typing_extensions as te
    LiteralString = te.LiteralString

    from ..._ogm.cmp import _Cmp
    from ..._ogm.model import Node
    from ..driver import Driver

    _M = t.TypeVar("_M", bound=Node)
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

    def register(self, *models: t.Type[Node]) -> t.Any:
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

    def _query(
        self,
        query: str,
        parameters: t.Dict[str, t.Any],
    ) -> t.List[Record]:
        # await self._driver.execute_query(
        #     t.cast(LiteralString, query.query),
        #     parameters_=query.parameters,
        #     routing_=RoutingControl.WRITE,
        #     # TODO: make database configurable
        #     database_="neo4j",
        # )
        log.info("Executing query: %r %r", query, parameters)
        with self._driver.session(
            # TODO: make database configurable
            database="neo4j",
            default_access_mode=WRITE_ACCESS,
        ) as session:
            with session.begin_transaction() as tx:
                result = tx.run(
                    t.cast(LiteralString, query),
                    parameters=parameters
                )
                records = [rec for rec in result]
                tx.commit()
        return records

    def save(
        self,
        model: Node,
        # relationships: bool = True
    ) -> None:
        properties = model.model_dump()
        del properties["pk"]

        meta = self._DBMSMetaProvider.get()

        if model.pk is None:
            n = cy.Node(
                labels=[type(model).__name__],
                properties=properties,
            )
            create = cy.Create(n)
            pk_return = model.__ogm_cls__.pk._cy_return(n)
            if pk_return is not None:
                create.return_(pk_return.as_("pk"))
            query = cy.CypherBuilder(meta.version).build(create)
            records = self._query(query.query, query.parameters)
            pk_value = None
            if pk_return is not None:
                pk_value = records[0]["pk"]
            model.__ogm_obj__.pk._load(model, pk_value)
        else:
            n = cy.Node(labels=[type(model).__name__])
            match = (cy
                .Match(n)
                .where(
                    model.__ogm_cls__.pk._cy_filter(model.__ogm_obj__.pk, n)
                )
                .set(cy.SetArg(n, cy.Var(properties)))
            )
            query = cy.CypherBuilder(meta.version).build(match)
            self._query(query.query, query.parameters)

    def find(
        self,
        model_cls: t.Type[_M],
        *,
        # eager_load: t.Sequence[str] = (),
        filters: t.Optional[t.Dict[str, _Cmp]] = None,
        **kw_filters: _Cmp,
    ) -> t.List[_M]:
        if filters is not None:
            kw_filters.update(filters)
        n = cy.Node(
            labels=[model_cls.__name__],
        )
        where = cy_f.FilterChain(
            cy_f.BinaryOp.AND,
            tuple(
                v.to_filter(n.attr(k))
                for k, v in kw_filters.items()
            )
        )
        return_args: t.List[cy.ReturnArg] = [
            cy.ReturnEntityArg(n, map_project=True).as_("n")
        ]
        pk_return = model_cls.__ogm_cls__.pk._cy_return(n)
        if pk_return is not None:
            return_args.append(pk_return.as_("pk"))
        match = (cy
            .Match(n)
            .where(where)
            .return_(*return_args)
        )
        meta = self._DBMSMetaProvider.get()
        query = cy.CypherBuilder(meta.version).build(match)
        records = self._query(query.query, query.parameters)
        models = [model_cls(**rec["n"]) for rec in records]
        for model, rec in zip(models, records):
            model.__ogm_obj__.pk._load(model, rec.get("pk"))
        return models
