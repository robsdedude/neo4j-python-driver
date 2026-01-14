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

from contextlib import suppress

import mock
import pytest

from ...._optional_deps import (
    np,
    pd,
    pa,
    skip_if_mocked_dependency,
)


@pytest.fixture(params=(True, False))
def np_float_overflow_as_error(request):
    should_raise = request.param
    if should_raise:
        old_err = np.seterr(over="raise")
    else:
        old_err = np.seterr(over="ignore")
    yield
    np.seterr(**old_err)


@pytest.fixture(
    params=(
        int,
        np.int8,
        np.int16,
        np.int32,
        np.int64,
        np.longlong,
        np.uint8,
        np.uint16,
        np.uint32,
        np.uint64,
        np.ulonglong,
    )
)
def int_type(request):
    skip_if_mocked_dependency(request.param)

    if not isinstance(np, mock.Mock) and issubclass(request.param, np.number):

        def _int_type(value):
            # this avoids deprecation warning from NEP50 and forces
            # c-style wrapping of the value
            return np.array(value).astype(request.param).item()

        return _int_type
    else:
        return request.param


@pytest.fixture(
    params=(float, np.float16, np.float32, np.float64, np.longdouble)
)
def float_type(request, np_float_overflow_as_error):
    skip_if_mocked_dependency(request.param)
    return request.param


@pytest.fixture(params=(bool, np.bool_))
def bool_type(request):
    skip_if_mocked_dependency(request.param)
    return request.param


@pytest.fixture(params=(bytes, bytearray, np.bytes_))
def bytes_type(request):
    skip_if_mocked_dependency(request.param)
    return request.param


@pytest.fixture(params=(str, np.str_))
def str_type(request):
    skip_if_mocked_dependency(request.param)
    return request.param


@pytest.fixture(
    params=(
        list,
        tuple,
        np.array,
        pd.Series,
        pd.array,
        pd.arrays.SparseArray,
        pd.arrays.NumpyExtensionArray,
        pd.arrays.ArrowExtensionArray,
    ),
    ids=(
        "list",
        "tuple",
        "np.array",
        "pd.Series",
        "pd.array",
        "pd.arrays.SparseArray",
        "pd.arrays.NumpyExtensionArray",
        "pd.arrays.ArrowExtensionArray",
    ),
)
def sequence_type(request):
    skip_if_mocked_dependency(request.param)

    if not isinstance(pd, mock.Mock) and request.param is pd.Series:

        def constructor(value):
            if not value:
                return pd.Series(dtype=object)
            return pd.Series(value)

    elif request.param is pd.array and pd.__version__ >= "3":

        def constructor(value):
            with suppress(ValueError):
                return pd.array(value)
            return pd.array(value, dtype=object)

    elif request.param is pd.arrays.NumpyExtensionArray:

        def constructor(value):
            return pd.arrays.NumpyExtensionArray(np.array(value))

    elif request.param is pd.arrays.ArrowExtensionArray:

        def constructor(value):
            def _map_value(v):
                if isinstance(v, pd.arrays.ArrowExtensionArray):
                    v = pa.array(v)
                if isinstance(v, pa.Array):
                    v = v.to_pylist()
                return v

            value = map(_map_value, value)
            return pd.arrays.ArrowExtensionArray(pa.array(value))

    else:
        constructor = request.param

    return constructor
