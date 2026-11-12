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

import mock

from neo4j import _typing as t  # noqa: TC001



class _ReturnTrackingMock(mock.Mock):
    call_return_values: list[t.Any]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.call_return_values = []

    def _get_child_mock(self, **kw):
        res = super()._get_child_mock(**kw)
        if isinstance(res, mock.AsyncMock):
            return AsyncReturnTrackingMock(**kw)
        else:
            return ReturnTrackingMock(**kw)


class ReturnTrackingMock(_ReturnTrackingMock):

    def __call__(self, *args, **kwargs):
        result = super().__call__(*args, **kwargs)
        self.call_return_values.append(result)
        return result




class AsyncReturnTrackingMock(mock.AsyncMock, _ReturnTrackingMock):
    call_return_values: list[t.Any]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.call_return_values = []

    def __call__(self, *args, **kwargs):
        super_call = super().__call__

        async def mocked_async_call(*args, **kwargs):
            result = await super_call(*args, **kwargs)
            self.call_return_values.append(result)
            return result

        return mocked_async_call(*args, **kwargs)
