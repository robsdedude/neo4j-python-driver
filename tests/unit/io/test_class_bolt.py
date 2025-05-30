#!/usr/bin/env python
# -*- encoding: utf-8 -*-

# Copyright (c) "Neo4j"
# Neo4j Sweden AB [http://neo4j.com]
#
# This file is part of Neo4j.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import random
from socket import socket

import pytest

import neo4j
from neo4j._exceptions import SocketDeadlineExceeded
from neo4j.io import (
    Bolt,
    BoltPool,
    IOPool,
    Neo4jPool,
)
from neo4j.io._bolt4 import Bolt4x4
from neo4j.io._common import (
    CommitResponse,
    ResetResponse,
    Response,
)
from neo4j.exceptions import (
    IncompleteCommit,
    ServiceUnavailable,
    SessionExpired,
)


# python -m pytest tests/unit/io/test_class_bolt.py -s -v


def test_class_method_protocol_handlers():
    # python -m pytest tests/unit/io/test_class_bolt.py -s -v -k test_class_method_protocol_handlers
    protocol_handlers = Bolt.protocol_handlers()
    assert len(protocol_handlers) == 6


@pytest.mark.parametrize(
    "test_input, expected",
    [
        ((0, 0), 0),
        ((4, 0), 1),
    ]
)
def test_class_method_protocol_handlers_with_protocol_version(test_input, expected):
    # python -m pytest tests/unit/io/test_class_bolt.py -s -v -k test_class_method_protocol_handlers_with_protocol_version
    protocol_handlers = Bolt.protocol_handlers(protocol_version=test_input)
    assert len(protocol_handlers) == expected


def test_class_method_protocol_handlers_with_invalid_protocol_version():
    # python -m pytest tests/unit/io/test_class_bolt.py -s -v -k test_class_method_protocol_handlers_with_invalid_protocol_version
    with pytest.raises(TypeError):
        Bolt.protocol_handlers(protocol_version=2)


def test_class_method_get_handshake():
    # python -m pytest tests/unit/io/test_class_bolt.py -s -v -k test_class_method_get_handshake
    handshake = Bolt.get_handshake()
    assert handshake == b"\x00\x02\x04\x04\x00\x00\x01\x04\x00\x00\x00\x04\x00\x00\x00\x03"


def test_magic_preamble():
    # python -m pytest tests/unit/io/test_class_bolt.py -s -v -k test_magic_preamble
    preamble = 0x6060B017
    preamble_bytes = preamble.to_bytes(4, byteorder="big")
    assert Bolt.MAGIC_PREAMBLE == preamble_bytes

@pytest.mark.parametrize("mode", ("r", "w"))
@pytest.mark.parametrize(
    "error",
    (
        RuntimeError("test error"),
        RecursionError("How deep is your ~~love~~ recursion?"),
    ),
)
@pytest.mark.parametrize("queued_commit", (None, 0, 1, 10))
def test_error_handler_bubbling(
    mocker, fake_socket, mode, error, queued_commit
):
    mocks = ErrorHandlerTestMockHolder(mocker)
    if queued_commit is not None:
        mocks.queue_commit_message_at(queued_commit)

    connection = mocks.connection
    handler = mocks.get_error_handler(mode)

    with pytest.raises(type(error)) as exc:
        handler(error)
    assert exc.value is error

    connection.socket.close.assert_called_once()

    assert connection.closed()
    assert connection.defunct()


@pytest.mark.parametrize("mode", ("r", "w"))
@pytest.mark.parametrize(
    "error",
    (
        OSError("computer says no! *cough*"),
        SocketDeadlineExceeded("too late, too little"),
        ServiceUnavailable("borked connection"),
        SessionExpired("nobody at home"),
    ),
)
@pytest.mark.parametrize("routing", (True, False))
@pytest.mark.parametrize("queued_commit", (None, 0, 1, 10))
def test_error_handler_rewritten(
    mocker, fake_socket, mode, error, routing, queued_commit
):
    mocks = ErrorHandlerTestMockHolder(mocker)
    mocks.mock_driver_routing(routing)
    if queued_commit is not None:
        mocks.queue_commit_message_at(queued_commit)

    connection = mocks.connection
    handler = mocks.get_error_handler(mode)

    if queued_commit is not None:
        expected_error = IncompleteCommit
    elif routing:
        expected_error = SessionExpired
    else:
        expected_error = ServiceUnavailable

    print(expected_error)
    with pytest.raises(expected_error) as exc:
        handler(error)
    assert exc.value.__cause__ is error
    connection.socket.close.assert_called_once()

    assert connection.closed()
    assert connection.defunct()


def make_pool_mock_cls(mocker, routing):
    class PoolMock(mocker.MagicMock):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def __getattribute__(self, item):
            if item == "__class__":
                if routing:
                    return Neo4jPool
                return BoltPool
            return super().__getattribute__(item)

        def __setattr__(self, key, value):
            print(key)
            if key == "_PoolMock__routing":
                nonlocal routing
                routing = value
                return
            super().__setattr__(key, value)

    return PoolMock


class ErrorHandlerTestMockHolder:
    def __init__(self, mocker):
        self.address = neo4j.Address(("127.0.0.1", 7687))
        self.socket_mock = mocker.MagicMock(spec=socket)
        self.socket_mock.getpeername.return_value = self.address
        self.connection = Bolt4x4(self.address, self.socket_mock, 108000)
        self.pool = make_pool_mock_cls(mocker, False)()
        self.connection.pool = self.pool

    def mock_driver_routing(self, routing):
        print("++++++ SETTING +++++++")
        self.pool._PoolMock__routing = routing

    def queue_random_non_commit_response(self):
        resp_cls = random.choice((ResetResponse, Response))
        resp = resp_cls(self.connection, "MESSAGE")
        self.connection.responses.append(resp)

    def queue_commit_message(self):
        resp = CommitResponse(self.connection, "MESSAGE")
        self.connection.responses.append(resp)

    def queue_commit_message_at(self, position):
        self.connection.responses.clear()
        for _ in range(position - 1):
            self.queue_random_non_commit_response()
        self.queue_commit_message()
        self.queue_random_non_commit_response()

    def get_error_handler(self, mode):
        if mode == "r":
            return self.connection._set_defunct_read
        elif mode == "w":
            return self.connection._set_defunct_write
        else:
            raise ValueError(f"Invalid handler mode {mode!r}")


def test_configures_inbox_error_handler(mocker):
    inbox_cls_mock = mocker.patch(
        "neo4j.io.Inbox", autospec=True
    )
    mocks = ErrorHandlerTestMockHolder(mocker)
    inbox_cls_mock.assert_called_once()
    call_args = inbox_cls_mock.call_args
    assert call_args.kwargs["on_error"] == mocks.connection._set_defunct_read
