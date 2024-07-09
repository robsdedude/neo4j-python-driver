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

import importlib
import os
import sys
import traceback
import typing as t


if t.TYPE_CHECKING:
    import typing_extensions as te

import pytest

from neo4j._codec.hydration import DehydrationHooks
from neo4j._codec.packstream import Structure
from neo4j._codec.packstream.v1 import (
    PackableBuffer,
    Packer,
    UnpackableBuffer,
    Unpacker,
)
from neo4j._optional_deps import rust_available


_T_PACKER_FIXTURE: te.TypeAlias = t.Tuple[Packer, PackableBuffer]
_T_UNPACKER_FIXTURE: te.TypeAlias = t.Tuple[Unpacker, UnpackableBuffer]

rust_exclusive = pytest.mark.skipif(
    not rust_available, reason="Rust extensions are not available"
)
py_exclusive = pytest.mark.skipif(
    rust_available, reason="Rust extensions are available"
)

EXPECT_OWN_EXTENSIONS: t.Optional[bool] = None
if os.getenv("TEST_NEO4J_EXPECT_OWN_EXTENSIONS", "").lower() in (
    "yes", "y", "1", "on", "true"
):
    EXPECT_OWN_EXTENSIONS = True
elif os.getenv("TEST_NEO4J_EXPECT_OWN_EXTENSIONS", "").lower() in (
    "no", "n", "0", "off", "false"
):
    EXPECT_OWN_EXTENSIONS = False
EXPECT_EXTERNAL_EXTENSIONS: t.Optional[bool] = None
if os.getenv("TEST_NEO4J_EXPECT_EXTERNAL_EXTENSIONS", "").lower() in (
    "yes", "y", "1", "on", "true"
):
    EXPECT_EXTERNAL_EXTENSIONS = True
elif os.getenv("TEST_NEO4J_EXPECT_EXTERNAL_EXTENSIONS", "").lower() in (
    "no", "n", "0", "off", "false"
):
    EXPECT_EXTERNAL_EXTENSIONS = False


@pytest.fixture
def packer_with_buffer() -> _T_PACKER_FIXTURE:
    packable_buffer = Packer.new_packable_buffer()
    return Packer(packable_buffer), packable_buffer


@pytest.fixture
def unpacker_with_buffer() -> _T_UNPACKER_FIXTURE:
    unpackable_buffer = Unpacker.new_unpackable_buffer()
    return Unpacker(unpackable_buffer), unpackable_buffer


@pytest.mark.skipif(
    not (EXPECT_OWN_EXTENSIONS or EXPECT_EXTERNAL_EXTENSIONS),
    reason=(
        "Native extensions are not expected to be available "
        "(set TEST_NEO4J_EXPECT_OWN_EXTENSIONS or "
        "TEST_NEO4J_EXPECT_EXTERNAL_EXTENSIONS to '1' to run this test)"
    )
)
def test_available() -> None:
    assert rust_available


@pytest.mark.skipif(
    not(
        EXPECT_OWN_EXTENSIONS is False and EXPECT_EXTERNAL_EXTENSIONS is False
    ),
    reason=(
        "Native extensions are not expected to be unavailable "
        "(set TEST_NEO4J_EXPECT_OWN_EXTENSIONS and "
        "TEST_NEO4J_EXPECT_EXTERNAL_EXTENSIONS to '0' to run this test)"
    )
)
def test_not_available() -> None:
    assert not rust_available


def test_pack_injection_works(packer_with_buffer: _T_PACKER_FIXTURE) -> None:
    class TestClass:
        pass

    class TestException(Exception):
        pass

    def raise_test_exception(*args, **kwargs):
        raise TestException()

    dehydration_hooks = DehydrationHooks(
        exact_types={TestClass: raise_test_exception},
        subtypes={},
    )
    test_object = TestClass()
    packer, _ = packer_with_buffer

    with pytest.raises(TestException) as exc:
        packer.pack(test_object, dehydration_hooks=dehydration_hooks)

    # printing the traceback to stdout to make it easier to debug
    traceback.print_exception(exc.type, exc.value, exc.tb, file=sys.stdout)

    if rust_available:
        assert any("_rust_pack" in str(entry.statement)
                   for entry in exc.traceback)
        assert not any("_py_pack" in str(entry.statement)
                       for entry in exc.traceback)
    else:
        assert any("_py_pack" in str(entry.statement)
                   for entry in exc.traceback)
        assert not any("_rust_pack " in str(entry.statement)
                       for entry in exc.traceback)


@rust_exclusive
def test_unpack_injection_works(
    unpacker_with_buffer: _T_UNPACKER_FIXTURE
) -> None:
    class TestException(Exception):
        pass

    def raise_test_exception(*args, **kwargs) -> None:
        raise TestException()

    hydration_hooks = {Structure: raise_test_exception}
    unpacker, buffer = unpacker_with_buffer

    buffer.reset()
    buffer.data = bytearray(b"\xB0\xFF")

    with pytest.raises(TestException) as exc:
        unpacker.unpack(hydration_hooks)

    # printing the traceback to stdout to make it easier to debug
    traceback.print_exception(exc.type, exc.value, exc.tb, file=sys.stdout)

    assert any("_rust_unpack" in str(entry.statement)
               for entry in exc.traceback)
    assert not any("_py_unpack" in str(entry.statement)
                   for entry in exc.traceback)


import_base_names = []
if EXPECT_OWN_EXTENSIONS is True:
    import_base_names.append("neo4j")
if EXPECT_EXTERNAL_EXTENSIONS is True:
    import_base_names.append("neo4j_rust_ext")


@pytest.mark.parametrize(
    ("name", "package_names"), (
        (name, package_names)
        for import_base_name in import_base_names
        for name, package_names in (
            (f"{import_base_name}._rust.codec.packstream.v1", ()),
            (f"{import_base_name}._rust.codec.packstream", ("v1",)),
            (f"{import_base_name}._rust.codec", ("packstream",)),
            (f"{import_base_name}._rust", ("codec",)),
            (f"{import_base_name}", ("_rust",)),
        )
    )
)
@rust_exclusive
def test_import_module(name, package_names) -> None:
    module = importlib.import_module(name)

    assert module.__name__ == name

    for package_name in package_names:
        package = getattr(module, package_name)
        assert package.__name__ == f"{name}.{package_name}"
