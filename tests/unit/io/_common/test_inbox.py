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
# limitations under the License.import asyncio


import pytest

from neo4j._exceptions import SocketDeadlineExceeded
from neo4j.io._common import Inbox
from neo4j.packstream import Unpacker


def _on_error_side_effect(e):
    raise e


class InboxMockHolder:
    def __init__(self, mocker):
        self.socket_mock = mocker.Mock()
        self.socket_mock.getsockname.return_value = ("host", 1234)
        self.on_error = mocker.MagicMock()
        self.on_error.side_effect = _on_error_side_effect
        self.inbox = Inbox(self.socket_mock, self.on_error)
        self.unpacker = None
        self._unpacker_failure = None
        mocker.patch(
            "neo4j.io._common.Unpacker",
            new=self._make_unpacker,
        )
        self.inbox._unpacker = self.unpacker
        # plenty of nonsense messages to read
        self.mock_set_data(b"\x00\x01\xff\x00\x00" * 1000)
        self._mocker = mocker

    def _make_unpacker(self, buffer):
        if self.unpacker is not None:
            pytest.fail("Unexpected 2nd instantiation of Unpacker")
        self.unpacker = self._mocker.Mock(wraps=Unpacker(buffer))
        if self._unpacker_failure is not None:
            self.mock_unpack_failure(self._unpacker_failure)
        return self.unpacker

    def mock_set_data(self, data):
        def side_effect(buffer, n):
            nonlocal data

            if not data:
                pytest.fail("Read more data than mocked")

            n = min(len(data), len(buffer), n)
            buffer[:n] = data[:n]
            data = data[n:]
            return n

        self.socket_mock.recv_into.side_effect = side_effect

    def assert_no_error(self):
        self.on_error.assert_not_called()
        assert next(self.inbox, None) is not None

    def mock_receive_failure(self, exception):
        self.socket_mock.recv_into.side_effect = exception

    def mock_unpack_failure(self, exception):
        self._unpacker_failure = exception
        if self.unpacker is not None:
            self.unpacker.unpack_structure_header.side_effect = exception


@pytest.mark.parametrize(
    "error",
    (
        SocketDeadlineExceeded("test"),
        OSError("test"),
    ),
)
def test_inbox_receive_failure_error_handler(mocker, error):
    mocks = InboxMockHolder(mocker)
    mocks.mock_receive_failure(error)
    inbox = mocks.inbox

    with pytest.raises(type(error)) as exc:
        next(inbox)

    assert exc.value is error
    mocks.on_error.assert_called_once_with(error)


@pytest.mark.parametrize(
    "error",
    (
        SocketDeadlineExceeded("test"),
        OSError("test"),
        RecursionError("2deep4u"),
        RuntimeError("something funny happened"),
    ),
)
def test_inbox_unpack_failure(mocker, error):
    mocks = InboxMockHolder(mocker)
    mocks.mock_unpack_failure(error)
    inbox = mocks.inbox

    with pytest.raises(type(error)) as exc:
        next(inbox)

    assert exc.value is error
    mocks.on_error.assert_called_once_with(error)
