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

import asyncio
import base64
import dataclasses
import time
from collections import deque
from dataclasses import dataclass
from logging import getLogger

from .... import _typing as t
from ...._async_compat.concurrency import AsyncLock
from ...._async_compat.network import (
    AsyncHTTPQueryAPI,
    HTTPQueryAPIResponse,
    HTTPVerb,
)
from ...._async_compat.util import AsyncUtil
from ...._auth_management import to_auth_dict
from ...._codec.hydration import HydrationScope
from ...._codec.hydration.http import (
    LiteralJson,
    LiteralJsonRecursive,
    v2 as hydration_v2,
    value_as_bool,
    value_as_dict,
    value_as_int,
    value_as_list,
    value_as_list_dict,
    value_as_list_list,
    value_as_list_str,
    value_as_str,
    value_dict_key,
)
from ...._deadline import Deadline
from ...._exceptions import QueryApiHttpError
from ....api import (
    READ_ACCESS,
    ServerInfo,
)
from ....exceptions import (
    ConfigurationError,
    IncompleteCommit,
    ServiceUnavailable,
    SessionExpired,
)
from ...config import AsyncPoolConfig
from ._base import AsyncHttpConnection
from ._common import ResponseHandler


if t.TYPE_CHECKING:
    from ...._addressing import Address
    from ...._api import TelemetryAPI
    from ...._auth_management import (
        AsyncAuthManager,
        AuthManager,
    )
    from ...._codec.hydration import (
        DehydrationHooks,
        T_TYPE_MAP_DICT,
    )
    from ....api import _TAuth

    _TAsyncFn = t.Callable[[], t.Awaitable[None]]
    _TState = t.TypeVar("_TState", bound="_ConnectionState")
    _TState2 = t.TypeVar("_TState2", bound="_ConnectionState")


log = getLogger("neo4j.io")


@dataclass
class _ConnectionState:
    def fail(self) -> _FailedState:
        return _FailedState()

    def reset(self) -> _InitState:
        return _InitState()


@dataclass
class _InitState(_ConnectionState):
    def begin_tx(self, tx_id: str, db: str, affinity: str | None) -> _TxState:
        return _TxState(tx_id=tx_id, db=db, affinity=affinity)

    def begin_auto_commit(
        self, result: _QueryResult, bookmark: str | None, db: str
    ) -> _AutoCommitState:
        return _AutoCommitState(bookmark=bookmark, db=db, result=result)


@dataclass
class _FailedState(_ConnectionState):
    pass


@dataclass
class _TxState(_ConnectionState):
    tx_id: str
    db: str
    affinity: str | None
    results: dict[int, _QueryResult] = dataclasses.field(default_factory=dict)
    current_qid: int | None = None

    def end_tx(self) -> _InitState:
        return _InitState()

    def commit(self) -> _InitState:
        return _InitState()

    def rollback(self) -> _InitState:
        return _InitState()


@dataclass
class _AutoCommitState(_ConnectionState):
    bookmark: str | None
    db: str
    result: _QueryResult

    def done(self) -> _InitState:
        return _InitState()


@dataclass
class _QueryResult:
    records_buffer: list[list]
    counters: dict
    notifications: list[dict] | None
    profile: dict | None
    plan: dict | None
    dehydration_hooks: DehydrationHooks
    hydration_hooks: T_TYPE_MAP_DICT

    @classmethod
    def from_body(
        cls,
        body: dict,
        dehydration_hooks: DehydrationHooks,
        hydration_hooks: T_TYPE_MAP_DICT,
    ) -> t.Self:
        data = value_as_dict(body.get("data"))
        records = value_as_list_list(data.get("values", []))
        counters = _map_counters(value_as_dict(body.get("counters", {})))
        notifications_raw = body.get("notifications", None)
        profile = value_as_dict(body.get("profiledQueryPlan", {}))
        _map_profile(profile)
        plan = value_as_dict(body.get("queryPlan", {}))
        _map_plan(plan)
        if notifications_raw is None:
            notifications = None
        else:
            notifications = value_as_list_dict(notifications_raw)

        return cls(
            records_buffer=records,
            counters=counters,
            notifications=notifications,
            profile=profile,
            plan=plan,
            dehydration_hooks=dehydration_hooks,
            hydration_hooks=hydration_hooks,
        )

    def validate_consistent_hooks(
        self,
        dehydration_hooks: DehydrationHooks,
        hydration_hooks: T_TYPE_MAP_DICT,
    ) -> None:
        if (
            self.dehydration_hooks is not dehydration_hooks
            or self.hydration_hooks is not hydration_hooks
        ):
            raise RuntimeError(
                "Inconsistent hydration/dehydration hooks used "
                "within the same result stream. "
                "This is not supported over Query API/HTTP. "
                "Please report this driver bug."
            )


@dataclass
class _Request:
    handler: _TAsyncFn
    name: str


@dataclass
class _CommitRequest(_Request):
    name: str = "COMMIT"


@dataclass
class _Response:
    handler: _TAsyncFn
    name: str


#
# @dataclass
# class _Request: pass
#
# @dataclass
# class _RequestRun(_Request):
#     query: str
#     parameters: dict[str, t.Any] | None
#     mode: str
#     bookmarks: t.Iterable[str] | None
#     metadata: dict[str, t.Any] | None
#     timeout
#     db
#     imp_user
#     notifications_min_severity
#     notifications_disabled_classifications
#     dehydration_hooks
#     hydration_hooks
#     **handlers,
#
#
# @dataclass
# class _TxState(_Request):
#     tx_id: int
#
#     def end_tx(self) -> _InitState:
#         return _InitState()
#
#
# @dataclass
# class _TxRunState(_Request):
#     tx_id: int
#
#     def end_tx(self) -> _InitState:
#         return _InitState()


SHARED_HYDRATION_HANDLER = hydration_v2.HydrationHandler()


class AsyncHttpV2(AsyncHttpConnection):
    _state: _ConnectionState
    _query_api: AsyncHTTPQueryAPI | None
    _requests: deque[_Request]
    _responses: deque[_Response]
    auth_manager: AsyncAuthManager | AuthManager | None = None
    unresolved_address: Address
    server_info: ServerInfo
    _id: int
    _defunct: bool
    _server_agent_cache: t.ClassVar[_ServerAgentCache]

    def __init__(
        self,
        unresolved_address: Address,
        query_api: AsyncHTTPQueryAPI,
        auth: _TAuth,
        auth_manager: AsyncAuthManager | AuthManager | None,
        id_: int,
    ) -> None:
        self.unresolved_address = unresolved_address
        self.server_info = ServerInfo(unresolved_address, (0, 0))
        self._state = _InitState()
        self._query_api = query_api
        self._auth_header = _auth_dict_to_header(to_auth_dict(auth))
        self.auth_manager = auth_manager
        self._requests = deque()
        self._responses = deque()
        self._id = id_
        self._defunct = False

    def new_hydration_scope(self) -> HydrationScope:
        return SHARED_HYDRATION_HANDLER.new_hydration_scope()

    @property
    def ssr_enabled(self) -> bool:
        return True

    @property
    def supports_multiple_results(self) -> bool:
        return False

    @property
    def supports_multiple_databases(self) -> bool:
        return True

    @property
    def supports_re_auth(self) -> bool:
        return True

    @property
    def supports_notification_filtering(self) -> bool:
        return False

    @property
    def connection_id(self) -> int:
        return self._id

    def telemetry(
        self,
        api: TelemetryAPI,
        dehydration_hooks=None,
        hydration_hooks=None,
        **handlers,
    ) -> None:
        pass

    def run(
        self,
        query,
        parameters=None,
        mode=None,
        bookmarks=None,
        metadata=None,
        timeout=None,
        db=None,
        imp_user=None,
        notifications_min_severity=None,
        notifications_disabled_classifications=None,
        dehydration_hooks=None,
        hydration_hooks=None,
        **handlers,
    ) -> None:
        self._validate_notification_filters(
            notifications_min_severity,
            notifications_disabled_classifications,
        )
        self._validate_tx_metadata(metadata)
        self._validate_tx_timeout(timeout)
        dehydration_hooks, hydration_hooks = self._default_hydration_hooks(
            dehydration_hooks, hydration_hooks
        )

        @self._handler
        async def req_handler_run() -> None:
            handler = ResponseHandler(**handlers)
            if self._check_failure_state(handler):
                return
            state = self._validate_state(
                self._state, (_InitState, _TxState), "run a query"
            )
            if isinstance(state, _InitState):
                await req_handler_run_auto_commit(state, handler)
            elif isinstance(state, _TxState):
                await req_handler_run_tx(state, handler)
            else:
                t.assert_never(state)

        async def req_handler_run_auto_commit(
            state_: _InitState, handler: ResponseHandler
        ) -> None:
            self._validate_db(db)
            req_data: LiteralJson[dict[str, t.Any]] = LiteralJson(
                {
                    "statement": LiteralJson(str(query)),
                    "includeCounters": LiteralJson(True),
                }
            )
            if mode in {READ_ACCESS, "r"}:
                req_data.value["accessMode"] = LiteralJson("Read")
            if bookmarks:
                req_data.value["bookmarks"] = LiteralJsonRecursive(
                    list(bookmarks)
                )
            if parameters:
                req_data.value["parameters"] = LiteralJson(parameters)
            if imp_user:
                req_data.value["impersonatedUser"] = LiteralJsonRecursive(
                    imp_user
                )
            res = await self._query_api.request(
                HTTPVerb.POST,
                f"db/{db}/query/v2",
                data=req_data,
                headers=self._auth_header,
                dehydration_hooks=dehydration_hooks,
                hydration_hooks=hydration_hooks,
                log_id=self._id,
            )
            if not await self._check_res_ok(res, handler):
                return
            body = value_as_dict(res.body)
            query_result = _QueryResult.from_body(
                body, dehydration_hooks, hydration_hooks
            )
            bookmark = _extract_bookmark(body)
            data = value_as_dict(body.get("data"))
            fields = value_as_list_str(data.get("fields", []))

            async def run_success_response() -> None:
                await AsyncUtil.callback(
                    handler.on_success, {"fields": fields}
                )

            self._state = state_.begin_auto_commit(
                result=query_result,
                bookmark=bookmark,
                db=db,
            )
            self._responses.append(_Response(run_success_response, "SUCCESS"))

        async def req_handler_run_tx(
            state_: _TxState, handler: ResponseHandler
        ) -> None:
            for name, value in (
                ("mode", mode),
                ("bookmarks", bookmarks),
                ("db", db),
                ("imp_user", imp_user),
            ):
                if value is not None:
                    raise ValueError(
                        f"Driver must not set {name} on tx run requests"
                    )
            req_data: LiteralJson[dict[str, t.Any]] = LiteralJson(
                {
                    "statement": LiteralJson(str(query)),
                    "includeCounters": LiteralJson(True),
                }
            )
            if parameters:
                req_data.value["parameters"] = LiteralJson(parameters)
            headers = self._auth_header
            if state_.affinity is not None:
                headers |= {"neo4j-cluster-affinity": state_.affinity}
            res = await self._query_api.request(
                HTTPVerb.POST,
                f"db/{state_.db}/query/v2/tx/{state_.tx_id}",
                data=req_data,
                headers=headers,
                dehydration_hooks=dehydration_hooks,
                hydration_hooks=hydration_hooks,
                log_id=self._id,
            )
            if not await self._check_res_ok(res, handler):
                return
            body = value_as_dict(res.body)
            query_result = _QueryResult.from_body(
                body, dehydration_hooks, hydration_hooks
            )
            data = value_as_dict(body.get("data"))
            fields = value_as_list_str(data.get("fields", []))

            state_.current_qid = (state_.current_qid or 0) + 1
            qid = state_.current_qid
            state_.results[qid] = query_result

            async def run_success_response() -> None:
                await AsyncUtil.callback(
                    handler.on_success, {"fields": fields, "qid": qid}
                )

            self._responses.append(_Response(run_success_response, "SUCCESS"))

        self._requests.append(_Request(req_handler_run, "RUN"))

    def discard(
        self,
        n=-1,
        qid=-1,
        dehydration_hooks=None,
        hydration_hooks=None,
        **handlers,
    ) -> None:
        dehydration_hooks, hydration_hooks = self._default_hydration_hooks(
            dehydration_hooks, hydration_hooks
        )

        @self._handler
        async def req_handler_discard() -> None:
            handler = ResponseHandler(**handlers)
            if self._check_failure_state(handler):
                return
            state = self._validate_state(
                self._state, (_AutoCommitState, _TxState), "discard records"
            )
            if isinstance(state, _AutoCommitState):
                await req_handler_discard_auto_commit(state, handler)
            elif isinstance(state, _TxState):
                await req_handler_discard_tx(state, handler)
            else:
                t.assert_never(state)

        async def req_handler_discard_auto_commit(
            state_: _AutoCommitState, handler: ResponseHandler
        ) -> None:
            if qid != -1:
                self._enqueue_failure(
                    handler,
                    "Neo.ClientError.Request.InvalidFormat",
                    f"No such statement: {qid}",
                )
                return

            result = state_.result
            result.validate_consistent_hooks(
                dehydration_hooks, hydration_hooks
            )
            if n < 0:
                to_pull = len(result.records_buffer)
            else:
                to_pull = n
            result.records_buffer = result.records_buffer[to_pull:]
            has_more = bool(result.records_buffer)
            if has_more:

                async def success_response() -> None:
                    metadata = {"has_more": has_more}
                    await AsyncUtil.callback(handler.on_success, metadata)

                self._responses.append(_Response(success_response, "SUCCESS"))
            else:

                async def success_response() -> None:
                    metadata: dict[str, object] = {
                        "db": state_.db,
                        "stats": result.counters,
                    }
                    if state_.bookmark:
                        metadata["bookmark"] = state_.bookmark
                    if result.notifications is not None:
                        metadata["notifications"] = result.notifications
                    if result.plan is not None:
                        metadata["plan"] = result.plan
                    if result.profile is not None:
                        metadata["profile"] = result.profile
                    await AsyncUtil.callback(handler.on_success, metadata)

                self._responses.append(_Response(success_response, "SUCCESS"))
                self._state = state_.done()

        async def req_handler_discard_tx(
            state_: _TxState, handler: ResponseHandler
        ) -> None:
            if state_.current_qid is None:
                self._enqueue_failure(
                    handler,
                    "Neo.ClientError.Request.Invalid",
                    f"Cannot PULL without running a query first",
                )
                return
            qid_ = qid
            if qid_ == -1:
                qid_ = state_.current_qid
            result = state_.results.get(qid_)
            if result is None:
                self._enqueue_failure(
                    handler,
                    "Neo.ClientError.Request.InvalidFormat",
                    f"No such statement: {qid_}",
                )
                return
            result.validate_consistent_hooks(
                dehydration_hooks, hydration_hooks
            )
            if n < 0:
                to_pull = len(result.records_buffer)
            else:
                to_pull = n
            result.records_buffer = result.records_buffer[to_pull:]
            has_more = bool(result.records_buffer)
            if has_more:

                async def success_response() -> None:
                    metadata = {"has_more": has_more}
                    await AsyncUtil.callback(handler.on_success, metadata)

                self._responses.append(_Response(success_response, "SUCCESS"))
            else:

                async def success_response() -> None:
                    metadata: dict[str, object] = {
                        "db": state_.db,
                        "stats": result.counters,
                    }
                    if result.notifications is not None:
                        metadata["notifications"] = result.notifications
                    if result.plan is not None:
                        metadata["plan"] = result.plan
                    if result.profile is not None:
                        metadata["profile"] = result.profile
                    await AsyncUtil.callback(handler.on_success, metadata)

                self._responses.append(_Response(success_response, "SUCCESS"))
                del state_.results[qid_]

        self._requests.append(_Request(req_handler_discard, "PULL"))

    def pull(
        self,
        n=-1,
        qid=-1,
        dehydration_hooks=None,
        hydration_hooks=None,
        **handlers,
    ) -> None:
        dehydration_hooks, hydration_hooks = self._default_hydration_hooks(
            dehydration_hooks, hydration_hooks
        )

        @self._handler
        async def req_handler_pull() -> None:
            handler = ResponseHandler(**handlers)
            if self._check_failure_state(handler):
                return
            state = self._validate_state(
                self._state, (_AutoCommitState, _TxState), "pull records"
            )
            if isinstance(state, _AutoCommitState):
                await req_handler_pull_auto_commit(state, handler)
            elif isinstance(state, _TxState):
                await req_handler_pull_tx(state, handler)
            else:
                t.assert_never(state)

        async def req_handler_pull_auto_commit(
            state_: _AutoCommitState, handler: ResponseHandler
        ) -> None:
            if qid != -1:
                self._enqueue_failure(
                    handler,
                    "Neo.ClientError.Request.InvalidFormat",
                    f"No such statement: {qid}",
                )
                return

            result = state_.result
            result.validate_consistent_hooks(
                dehydration_hooks, hydration_hooks
            )
            if n < 0:
                to_pull = len(result.records_buffer)
            else:
                to_pull = n
            records = result.records_buffer[:to_pull]
            result.records_buffer = result.records_buffer[to_pull:]
            self._enqueue_records(handler, records)
            has_more = bool(result.records_buffer)
            if has_more:

                async def success_response() -> None:
                    metadata = {"has_more": has_more}
                    await AsyncUtil.callback(handler.on_success, metadata)

                self._responses.append(_Response(success_response, "SUCCESS"))
            else:

                async def success_response() -> None:
                    metadata: dict[str, object] = {
                        "db": state_.db,
                        "stats": result.counters,
                    }
                    if state_.bookmark:
                        metadata["bookmark"] = state_.bookmark
                    if result.notifications is not None:
                        metadata["notifications"] = result.notifications
                    if result.plan is not None:
                        metadata["plan"] = result.plan
                    if result.profile is not None:
                        metadata["profile"] = result.profile
                    await AsyncUtil.callback(handler.on_success, metadata)

                self._responses.append(_Response(success_response, "SUCCESS"))
                self._state = state_.done()

        async def req_handler_pull_tx(
            state_: _TxState, handler: ResponseHandler
        ) -> None:
            if state_.current_qid is None:
                self._enqueue_failure(
                    handler,
                    "Neo.ClientError.Request.Invalid",
                    f"Cannot PULL without running a query first",
                )
                return
            qid_ = qid
            if qid_ == -1:
                qid_ = state_.current_qid
            result = state_.results.get(qid_)
            if result is None:
                self._enqueue_failure(
                    handler,
                    "Neo.ClientError.Request.InvalidFormat",
                    f"No such statement: {qid_}",
                )
                return
            result.validate_consistent_hooks(
                dehydration_hooks, hydration_hooks
            )
            if n < 0:
                to_pull = len(result.records_buffer)
            else:
                to_pull = n
            records = result.records_buffer[:to_pull]
            result.records_buffer = result.records_buffer[to_pull:]
            self._enqueue_records(handler, records)
            has_more = bool(result.records_buffer)
            if has_more:

                async def success_response() -> None:
                    metadata = {"has_more": has_more}
                    await AsyncUtil.callback(handler.on_success, metadata)

                self._responses.append(_Response(success_response, "SUCCESS"))
            else:

                async def success_response() -> None:
                    metadata: dict[str, object] = {
                        "db": state_.db,
                        "stats": result.counters,
                    }
                    if result.notifications is not None:
                        metadata["notifications"] = result.notifications
                    if result.plan is not None:
                        metadata["plan"] = result.plan
                    if result.profile is not None:
                        metadata["profile"] = result.profile
                    await AsyncUtil.callback(handler.on_success, metadata)

                self._responses.append(_Response(success_response, "SUCCESS"))
                del state_.results[qid_]

        self._requests.append(_Request(req_handler_pull, "PULL"))

    def _enqueue_records(
        self,
        handler: ResponseHandler,
        records: list[list],
    ) -> None:
        async def records_response() -> None:
            await AsyncUtil.callback(handler.on_records, records)

        self._responses.append(
            _Response(
                name="RECORDS",
                handler=records_response,
            )
        )

    def begin(
        self,
        mode=None,
        bookmarks=None,
        metadata=None,
        timeout=None,
        db=None,
        imp_user=None,
        notifications_min_severity=None,
        notifications_disabled_classifications=None,
        dehydration_hooks=None,
        hydration_hooks=None,
        **handlers,
    ) -> None:
        self._validate_db(db)
        self._validate_notification_filters(
            notifications_min_severity,
            notifications_disabled_classifications,
        )
        self._validate_tx_metadata(metadata)
        self._validate_tx_timeout(timeout)
        dehydration_hooks, hydration_hooks = self._default_hydration_hooks(
            dehydration_hooks, hydration_hooks
        )

        @self._handler
        async def req_handler_begin() -> None:
            handler = ResponseHandler(**handlers)
            if self._check_failure_state(handler):
                return
            state = self._validate_state(
                self._state, _InitState, "begin a new transaction"
            )
            req_data: LiteralJson[dict[str, t.Any]] = LiteralJson({})
            if mode in {READ_ACCESS, "r"}:
                req_data.value["accessMode"] = LiteralJson("Read")
            if bookmarks:
                req_data.value["bookmarks"] = LiteralJsonRecursive(
                    list(bookmarks)
                )
            res = await self._query_api.request(
                HTTPVerb.POST,
                f"db/{db}/query/v2/tx",
                data=req_data,
                headers=self._auth_header,
                dehydration_hooks=dehydration_hooks,
                hydration_hooks=hydration_hooks,
                log_id=self._id,
            )
            if not await self._check_res_ok(res, handler):
                return

            body = value_as_dict(res.body)
            transaction = value_as_dict(body.get("transaction"))
            tx_id = value_as_str(transaction.get("id"))
            self._state = state.begin_tx(tx_id, db, res.cluster_affinity)

            async def success_response() -> None:
                await AsyncUtil.callback(handler.on_success, {})

            self._responses.append(_Response(success_response, "SUCCESS"))

        self._requests.append(_Request(req_handler_begin, "BEGIN"))

    def commit(
        self,
        dehydration_hooks=None,
        hydration_hooks=None,
        **handlers,
    ) -> None:
        dehydration_hooks, hydration_hooks = self._default_hydration_hooks(
            dehydration_hooks, hydration_hooks
        )

        @self._handler
        async def req_handler_commit() -> None:
            handler = ResponseHandler(**handlers)
            if self._check_failure_state(handler):
                return
            state = self._validate_state(
                self._state, _TxState, "commit a transaction"
            )
            headers = self._auth_header
            if state.affinity is not None:
                headers |= {"neo4j-cluster-affinity": state.affinity}
            res = await self._query_api.request(
                HTTPVerb.POST,
                f"db/{state.db}/query/v2/tx/{state.tx_id}/commit",
                headers=self._auth_header,
                dehydration_hooks=dehydration_hooks,
                hydration_hooks=hydration_hooks,
                log_id=self._id,
            )
            if not await self._check_res_ok(res, handler):
                return

            body = value_as_dict(res.body)
            bookmark = _extract_bookmark(body)

            self._state = state.commit()

            async def success_response() -> None:
                metadata = {}
                if bookmark is not None:
                    metadata["bookmark"] = bookmark
                await AsyncUtil.callback(handler.on_success, metadata)

            self._responses.append(_Response(success_response, "SUCCESS"))

        self._requests.append(_Request(req_handler_commit, "COMMIT"))

    def rollback(
        self,
        dehydration_hooks=None,
        hydration_hooks=None,
        **handlers,
    ) -> None:
        dehydration_hooks, hydration_hooks = self._default_hydration_hooks(
            dehydration_hooks, hydration_hooks
        )

        @self._handler
        async def req_handler_rollback() -> None:
            handler = ResponseHandler(**handlers)
            if self._check_failure_state(handler):
                return
            state = self._validate_state(
                self._state, _TxState, "roll back a transaction"
            )
            headers = self._auth_header
            if state.affinity is not None:
                headers |= {"neo4j-cluster-affinity": state.affinity}
            res = await self._query_api.request(
                HTTPVerb.POST,
                f"db/{state.db}/query/v2/tx/{state.tx_id}/rollback",
                headers=self._auth_header,
                dehydration_hooks=dehydration_hooks,
                hydration_hooks=hydration_hooks,
                log_id=self._id,
            )
            if not await self._check_res_ok(res, handler):
                return

            self._state = state.rollback()

            async def success_response() -> None:
                await AsyncUtil.callback(handler.on_success, {})

            self._responses.append(_Response(success_response, "SUCCESS"))

        self._requests.append(_Request(req_handler_rollback, "ROLLBACK"))
        pass

    async def reset(
        self, dehydration_hooks=None, hydration_hooks=None
    ) -> None:
        self._state = _InitState()

    async def send_all(self) -> None:
        if self.closed():
            raise ServiceUnavailable(
                "Failed to write to closed connection "
                f"{self.unresolved_address!r} ({self.server_info.address!r})"
            )
        if self.defunct():
            raise ServiceUnavailable(
                "Failed to write to defunct connection "
                f"{self.unresolved_address!r} ({self.server_info.address!r})"
            )

        while self._requests:
            req = self._requests.popleft()
            await req.handler()

    async def fetch_message(self) -> None:
        if self.closed():
            raise ServiceUnavailable(
                "Failed to read from closed connection "
                f"{self.unresolved_address!r} ({self.server_info.address!r})"
            )
        if self.defunct():
            raise ServiceUnavailable(
                "Failed to read from defunct connection "
                f"{self.unresolved_address!r} ({self.server_info.address!r})"
            )
        if not self._responses:
            return
        res = self._responses.popleft()
        await res.handler()

    async def fetch_all(self) -> None:
        while self._responses:
            await self.fetch_message()

    def defunct(self) -> bool:
        return self._defunct

    def closed(self) -> bool:
        return self._query_api is None

    async def close(self) -> None:
        if self._query_api is not None:
            await self._query_api.close()
            self._query_api = None

    @property
    def is_reset(self) -> bool:
        return isinstance(self._state, _InitState)

    @staticmethod
    def _validate_notification_filters(
        notifications_min_severity=None,
        notifications_disabled_classifications=None,
    ) -> None:
        if (
            notifications_min_severity is not None
            or notifications_disabled_classifications is not None
        ):
            raise ConfigurationError(
                "Notification filtering is not supported via the Query API/"
                "HTTP."
            )

    @staticmethod
    def _validate_db(db: str | None) -> None:
        if not db:
            raise ConfigurationError(
                "Home database resolution is not supported via the "
                "Query API/HTTP. "
                "An explicit database name must be specified."
            )

    @staticmethod
    def _validate_tx_metadata(metadata: t.Any) -> None:
        if metadata is not None:
            raise ConfigurationError(
                "Transaction metadata is not supported over Query API/HTTP."
            )

    @staticmethod
    def _validate_tx_timeout(timeout: t.Any) -> None:
        if timeout is not None:
            raise ConfigurationError(
                "Transaction timeouts are not supported over Query API/HTTP."
            )

    @staticmethod
    @t.overload
    def _validate_state(
        current_state: _ConnectionState,
        expected_state_type: type[_TState],
        action: str,
    ) -> _TState: ...

    @staticmethod
    @t.overload
    def _validate_state(
        current_state: _ConnectionState,
        expected_state_type: tuple[type[_TState], type[_TState2]],
        action: str,
    ) -> _TState | _TState2: ...

    @staticmethod
    def _validate_state(
        current_state: _ConnectionState,
        expected_state_type: type[_ConnectionState]
        | tuple[type[_ConnectionState], ...],
        action: str,
    ) -> _ConnectionState:
        if not isinstance(current_state, expected_state_type):
            AsyncHttpV2._invalid_state(current_state, action)
        return current_state

    @staticmethod
    def _invalid_state(
        current_state: _ConnectionState, action: str
    ) -> t.Never:
        raise RuntimeError(
            f"Cannot {action} in the current state {current_state!r}. "
            f"This is likely a bug in the driver, please report it."
        )

    def _default_hydration_hooks(
        self,
        dehydration_hooks: DehydrationHooks | None,
        hydration_hooks,
    ) -> tuple[DehydrationHooks, T_TYPE_MAP_DICT]:
        if dehydration_hooks is not None and hydration_hooks is not None:
            return dehydration_hooks, hydration_hooks
        hydration_scope = self.new_hydration_scope()
        if dehydration_hooks is None:
            dehydration_hooks = hydration_scope.dehydration_hooks
        if hydration_hooks is None:
            hydration_hooks = hydration_scope.hydration_hooks
        return dehydration_hooks, hydration_hooks

    def _handler(
        self,
        handler: t.Callable[[], t.Awaitable[None]],
    ) -> t.Callable[[], t.Awaitable[None]]:
        async def inner() -> None:
            try:
                await handler()
            except Exception as error:
                user_cancelled = isinstance(error, asyncio.CancelledError)
                protocol_error = isinstance(error, QueryApiHttpError)
                connection_failed = isinstance(
                    error, AsyncHTTPQueryAPI.CONNECTION_ERRORS
                )
                if not user_cancelled:
                    log_call = log.error
                else:
                    log_call = log.debug
                message = "Failed to process Query API/HTTP request"
                log_call(
                    "[#%04X]  _: Connection error: %r",
                    self._id,
                    error,
                )
                self._defunct = True
                if user_cancelled:
                    raise
                if protocol_error or not connection_failed:
                    raise
                for request in self._requests:
                    if isinstance(request, _CommitRequest):
                        raise IncompleteCommit(message) from error
                raise SessionExpired(message) from error

        return inner

    async def _check_res_ok(
        self,
        res: HTTPQueryAPIResponse,
        handler: ResponseHandler,
    ) -> bool:
        if res.status < 400:
            return True
        if not isinstance(res.body, dict):
            raise AsyncHttpV2._generic_http_error(res)
        errors = res.body.get("errors")
        if not isinstance(errors, list) or not errors:
            raise AsyncHttpV2._generic_http_error(res)
        error = errors[0]
        if not isinstance(error, dict):
            raise AsyncHttpV2._generic_http_error(res)
        code = error.get("code")
        message = error.get("message")
        if not isinstance(code, str) or not isinstance(message, str):
            raise AsyncHttpV2._generic_http_error(res)

        self._enqueue_failure(handler, code, message)
        return False

    def _enqueue_failure(
        self,
        handler: ResponseHandler,
        code: str,
        message: str,
    ) -> None:
        async def failure_response() -> None:
            self._state = _InitState()
            await AsyncUtil.callback(
                handler.on_failure,
                {"code": code, "message": message},
            )

        self._state = _FailedState()
        self._responses.append(
            _Response(
                name="FAILURE",
                handler=failure_response,
            )
        )

    def _check_failure_state(self, handler: ResponseHandler) -> bool:
        if isinstance(self._state, _FailedState):

            async def ignored_response() -> None:
                await AsyncUtil.callback(handler.on_ignored)

            self._responses.append(
                _Response(
                    name="IGNORED",
                    handler=ignored_response,
                )
            )
            return True
        return False

    @staticmethod
    def _generic_http_error(res: HTTPQueryAPIResponse) -> RuntimeError:
        msg = f"HTTP error {res.status}: {res.body}"
        if res.reason is not None:
            msg += f" - ({res.reason})"
        return RuntimeError(msg)

    class _ServerAgentCache:
        _value: str | None = None
        _last_fetch: float = float("-inf")
        _lock = AsyncLock()

        async def get(self, http: AsyncHttpV2) -> str | None:
            age = time.monotonic() - self._last_fetch
            if self._value is not None and age <= 60:
                return self._value
            async with self._lock:
                # check if value has been update while waiting for the lock
                age = time.monotonic() - self._last_fetch
                if self._value is not None and age <= 60:
                    return self._value
                await self._update(http)
                return self._value

        async def _update(self, http: AsyncHttpV2) -> None:
            try:
                res = await http._query_api.discovery(log_id=http._id)
                if res.status >= 400:
                    raise AsyncHttpV2._generic_http_error(res)
                version = res.body["neo4j_version"]
                if not isinstance(version, str):
                    raise TypeError(
                        "Expected 'neo4j_version' to be str, "
                        f"got {type(version)}"
                    )
                self._value = f"Neo4j/{version}"
            except Exception as e:
                log.warning(
                    "[#%04X]  _: Could not fetch server agent: %r",
                    http._id,
                    e,
                )
            finally:
                self._last_fetch = time.monotonic()

    _server_agent_cache = _ServerAgentCache()


async def _get_auth_dict(
    auth_manager: AsyncAuthManager | AuthManager | None,
) -> dict[str, str]:
    if auth_manager is None:
        return {}
    auth = await AsyncUtil.callback(auth_manager.get_auth)
    auth_dict = to_auth_dict(auth)
    return auth_dict


def _auth_dict_to_header(
    auth_dict: dict[str, str],
) -> dict[str, str]:
    scheme = auth_dict.pop("scheme", None)
    if scheme == "basic":
        user = str(auth_dict.pop("principal", ""))
        if ":" in user:
            raise ConfigurationError(
                "The username over Query API/HTTP cannot contain a colon "
                "(':')."
            )
        password = str(auth_dict.pop("credentials", ""))
        for k, v in auth_dict.items():
            if v is None:
                continue
            raise ConfigurationError(
                f"The parameter '{k}' is not supported for 'basic' auth "
                "over Query API/HTTP."
            )
        token = base64.b64encode(f"{user}:{password}".encode()).decode("ascii")
        return {"Authorization": f"Basic {token}"}
    if scheme == "bearer":
        token = str(auth_dict.pop("credentials", ""))
        for k, v in auth_dict.items():
            if v is None:
                continue
            raise ConfigurationError(
                f"The parameter '{k}' is not supported for 'bearer' auth "
                "over Query API/HTTP."
            )
        return {"Authorization": f"Bearer {token}"}
    raise ConfigurationError(
        f"The auth scheme '{scheme}' is not supported over Query API/HTTP."
    )


_COUNTERS_MAPPING = {
    "nodesCreated": "nodes_created",
    "nodesDeleted": "nodes-deleted",
    "relationshipsCreated": "relationships-created",
    "relationshipsDeleted": "relationships-deleted",
    "propertiesSet": "properties-set",
    "labelsAdded": "labels-added",
    "labelsRemoved": "labels-removed",
    "indexesAdded": "indexes-added",
    "indexesRemoved": "indexes-removed",
    "constraintsAdded": "constraints-added",
    "constraintsRemoved": "constraints-removed",
    "systemUpdates": "system-updates",
    "containsUpdates": "contains-updates",
    "containsSystemUpdates": "contains-system-updates",
}

_COUNTERS_TYPE_GETTER = {
    "nodesCreated": value_as_int,
    "nodesDeleted": value_as_int,
    "relationshipsCreated": value_as_int,
    "relationshipsDeleted": value_as_int,
    "propertiesSet": value_as_int,
    "labelsAdded": value_as_int,
    "labelsRemoved": value_as_int,
    "indexesAdded": value_as_int,
    "indexesRemoved": value_as_int,
    "constraintsAdded": value_as_int,
    "constraintsRemoved": value_as_int,
    "systemUpdates": value_as_int,
    "containsUpdates": value_as_bool,
    "containsSystemUpdates": value_as_bool,
}


def _map_counters(counters_dict: dict) -> dict:
    try:
        return {
            _COUNTERS_MAPPING[key]: _COUNTERS_TYPE_GETTER[key](value)
            for key, value in counters_dict.items()
        }
    except KeyError as e:
        raise QueryApiHttpError(
            f"Unexpected counter key in Query API/HTTP response"
        ) from e


def _map_profile(profile: dict) -> None:
    if "arguments" in profile:
        profile["args"] = profile.pop("arguments")
    if "hasPageCacheStats" in profile:
        del profile["hasPageCacheStats"]
    if "records" in profile:
        profile["rows"] = profile.pop("records")
    children = profile.get("children")
    if isinstance(children, list):
        for child in children:
            _map_profile(child)


def _map_plan(plan: dict) -> None:
    if "arguments" in plan:
        plan["args"] = plan.pop("arguments")
    children = plan.get("children")
    if isinstance(children, list):
        for child in children:
            _map_plan(child)


def _extract_bookmark(body: dict) -> str | None:
    bookmarks = value_as_list_str(body.get("bookmarks", []))
    if not bookmarks:
        return None
    if len(bookmarks) != 1:
        raise QueryApiHttpError(
            "Multiple bookmarks returned from Query API/HTTP, "
            "but only a single bookmark is supported."
        )
    return bookmarks[0]
