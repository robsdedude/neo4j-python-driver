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

import collections
import itertools
import typing as t

from ..._api import RoutingControl
from ..._data import Record
from ..._ogm import cypher as cy
from ..._ogm.cypher import expr as cy_x
from ..._ogm.log import log
from ..._ogm.model import (
    clean_node_dump,
    Direction,
    Node,
)
from ...api import WRITE_ACCESS
from .dbms_meta import DBMSMetaProvider


if t.TYPE_CHECKING:
    import typing_extensions as te
    LiteralString = te.LiteralString

    from ..._ogm.cmp import _Cmp
    from ..._ogm.cypher.clause import (
        Clause,
        RootClause,
    )
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
        log.info("Executing query:\n%s\n%r", query, parameters)
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

    @staticmethod
    def _make_set_pk_processor(
        model: t.Union[Node, t.List[Node]],
        key: t.Optional[str] = None,
    ) -> t.Callable[[t.Optional[Record]], None]:
        def set_pk_processor(record: t.Optional[Record]) -> None:
            if not model:
                assert key is None
            if not isinstance(model, list):
                pk = None
                if key is not None:
                    assert record is not None
                    pk = record.get(key)
                model.__ogm_obj__.pk._load(model, pk)
            else:
                if key is None:
                    pks = itertools.repeat(None)
                else:
                    assert record is not None
                    pks = record.get(key)
                for m, pk in zip(model, pks):
                    m.__ogm_obj__.pk._load(m, pk)

        return set_pk_processor

    def save(
        self,
        model: Node,
        relationships: t.Union[bool, t.Sequence[str]] = False,
    ) -> None:
        if not isinstance(relationships, bool):
            for rel in relationships:
                if rel not in model.__ogm_cls__.rels:
                    raise ValueError(
                        f"Model {model} has no relationship {rel}"
                    )
        else:
            if relationships:
                relationships = tuple(model.__ogm_cls__.rels.keys())
            else:
                relationships = ()

        properties = clean_node_dump(model)

        meta = self._DBMSMetaProvider.get()

        record_processors = []
        return_vars: t.List[cy.ReturnArg] = []

        if model.pk is None:
            n = cy.Node(
                labels=model.__ogm_cls__.labels,
                properties=properties,
            )
            query = cy.Create(n)
            pk_return = model.__ogm_cls__.pk._cy_return(n)
            if pk_return is not None:
                return_vars.append(cy.ReturnArg(pk_return).as_("pk"))
                record_processors.append(
                    self._make_set_pk_processor(model, key="pk")
                )
            else:
                record_processors.append(
                    self._make_set_pk_processor(model)
                )

        else:
            n = cy.Node(labels=model.__ogm_cls__.labels)
            query = (cy
                .Match(n)
                .where(
                    model.__ogm_cls__.pk._cy_filter(model.__ogm_obj__.pk, n)
                )
                .set(cy.SetArg(n.ref(), cy.Param(properties)))
            )
        with_vars: t.List[cy.Expr] = [n.ref()]
        next_with = cy.With(tuple(map(cy.ReturnArg, with_vars)))

        # rels_creation: t.Dict[str, Clause] = {}
        # rels_creation_collection: t.Dict[str, cy.Var] = {}
        # rels_update: t.Dict[str, Clause] = {}
        # rel_vars: t.List[cy.Expr]  = []
        for i, rel in enumerate(relationships):
            rel_vars: t.List[cy.Expr] = []
            rel_model_cls = model.__ogm_cls__.rels[rel].target
            rel_label = model.__ogm_cls__.rels[rel].label
            rel_node_labels = rel_model_cls.__ogm_cls__.labels
            rel_nodes = t.cast(t.List[Node], getattr(model, rel))
            rel_new_models: t.List[Node] = []
            rel_update_models: t.List[Node] = []
            for rel_model in rel_nodes:
                if rel_model.pk is None:
                    rel_new_models.append(rel_model)
                else:
                    rel_update_models.append(rel_model)

            del_rel = cy.Relationship(
                label=rel_label,
            )
            del_node = cy.Node(
                labels=rel_node_labels,
            )
            rel_direction = model.__ogm_cls__.rels[rel].direction
            if rel_direction == Direction.INCOMING:
                del_rel.start_node = del_node
                del_rel.end_node = n.ref()
            elif rel_direction == Direction.OUTGOING:
                del_rel.start_node = n.ref()
                del_rel.end_node = del_node
            elif rel_direction == Direction.BOTH:
                del_rel.start_node = del_node
                del_rel.end_node = n.ref()
                del_rel.directed = False
            else:
                raise ValueError(f"Unhandled direction {rel_direction}")

            if rel_new_models:
                dumps = [clean_node_dump(n) for n in rel_new_models]
                unwind_var = cy.Var("rel_new_prop")
                collection_var = cy.Var(f"rel_new{i + 1}")
                collection_var_pk_raw = f"rel_new_pk{i + 1}"
                collection_var_pk = cy.Var(collection_var_pk_raw)
                rel_node = cy.Node(
                    labels=rel_node_labels,
                )
                new_rel = cy.Relationship(
                    label=rel_label,
                )
                if rel_direction == Direction.INCOMING:
                    new_rel.start_node = rel_node
                    new_rel.end_node = n.ref()
                else:
                    new_rel.start_node = n.ref()
                    new_rel.end_node = rel_node
                query = (query
                    .extend(next_with)
                    .unwind(
                        cy.ReturnArg(cy.Param(dumps)).as_(unwind_var),
                    )
                    .create(new_rel)
                    .set(cy.SetArg(rel_node.ref(), unwind_var))
                )
                with_args = [
                    *map(cy.ReturnArg, with_vars),
                    *map(cy.ReturnArg, rel_vars),
                    cy.ReturnArg(
                        cy.Func("collect", rel_node.ref())
                    ).as_(collection_var),
                ]
                rel_vars.append(collection_var)
                rel_pk_return = \
                    rel_model_cls.__ogm_cls__.pk._cy_return(rel_node)
                if rel_pk_return is not None:
                    with_args.append(
                        cy.ReturnArg(
                            cy.Func("collect", rel_pk_return)
                        ).as_(collection_var_pk),
                    )
                    with_vars.append(collection_var_pk)
                    return_vars.append(
                        cy.ReturnArg(
                            collection_var_pk
                        ).as_(collection_var_pk_raw)
                    )
                    record_processors.append(
                        self._make_set_pk_processor(rel_new_models,
                                                    key=collection_var_pk_raw)
                    )
                else:
                    record_processors.append(
                        self._make_set_pk_processor(rel_new_models)
                    )
                next_with = cy.With(with_args)

            if rel_update_models:
                rel_node = cy.Node(
                    labels=rel_node_labels,
                )
                rel_update_data = [
                    {
                        "data": clean_node_dump(model),
                        "pk": model.__ogm_obj__.pk._value,
                    }
                    for model in rel_update_models
                ]
                unwind_var = cy.Var("rel_update_data")
                collection_var = cy.Var(f"rel_update{i + 1}")
                query = (query
                    .extend(next_with)
                    .unwind(
                        cy.ReturnArg(cy.Param(rel_update_data)).as_(unwind_var)
                    )
                    .match(
                        rel_node
                    )
                    .where(
                        rel_model_cls.__ogm_cls__.pk._cy_var_filter(
                            unwind_var.attr("pk"), rel_node
                        )
                    )
                    .merge(del_rel)
                    .set(
                        cy.SetArg(
                            rel_node.ref(),
                            unwind_var.attr("data")
                        )
                    )
                )
                next_with = cy.With((
                    *map(cy.ReturnArg, rel_vars),
                    *map(cy.ReturnArg, with_vars),
                    cy.ReturnArg(
                        cy.Func("collect", rel_node.ref())
                    ).as_(collection_var),
                ))
                rel_vars.append(collection_var)

            if rel_vars:
                rels_expr = cy_x.ExprChain(
                    cy_x.BinaryOp.PLUS,
                    tuple(var for var in rel_vars)
                )
                query = (query
                    .extend(next_with)
                    .match(del_rel)
                    .where(
                        cy_x.UnaryExpr(
                            cy_x.UnaryOp.NOT,
                            cy_x.BinaryExpr(
                                cy_x.ExprLiteral(del_node.ref()),
                                cy_x.BinaryOp.IN,
                                rels_expr,
                            )
                        )
                    )
                    .delete(del_rel.ref())
                )
            else:
                query = (query
                    .extend(next_with)
                    .match(del_rel)
                    .delete(del_rel.ref())
                )
            next_with = cy.With(tuple(map(cy.ReturnArg, with_vars)))

        if return_vars:
            query = query.extend(next_with).return_(*return_vars)
        built_query = cy.CypherBuilder(meta.version).build(query)
        records = self._query(built_query.query, built_query.parameters)
        if not return_vars:
            assert not records
            for record_processor in record_processors:
                record_processor(None)
            return
        assert len(records) == 1
        record = records[0]
        for record_processor in record_processors:
            record_processor(record)


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
        where = cy_x.ExprChain(
            cy_x.BinaryOp.AND,
            tuple(
                v.to_filter(n.attr(k))
                for k, v in kw_filters.items()
            )
        )
        return_args: t.List[cy.ReturnArg] = [
            cy.ReturnArg(
                n.ref(),
                project_flat=("*",),
            ).as_("n")
        ]
        pk_return = model_cls.__ogm_cls__.pk._cy_return(n)
        if pk_return is not None:
            return_args.append(cy.ReturnArg(pk_return).as_("pk"))
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
