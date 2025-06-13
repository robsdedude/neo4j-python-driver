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

"""
Vectors.

https://trello.com/c/2xcLszsC/1164-python-vector-types-design-investigation
"""

from __future__ import annotations as _

import abc as abc_
import struct as struct_
import sys as sys_

from typing as _t
from .._optional_deps import (
    np as _np,
    pa as _pa,
)


try:
    from ._rust.vector import swap_endian as _swap_endian_unchecked_rust
except ImportError:
    _swap_endian_unchecked_rust = None

if _t.TYPE_CHECKING:
    import numpy  # type: ignore[import]
    import pyarrow  # type: ignore[import]
    import typing_extensions as te


class Vector:
    """
    A class representing a Neo4j vector.

    Internally, vectors are represented as a contiguous block of memory,
    with the data type of the vector's elements in big-endian order.

    To be able to send and receive these types, the driver must be connected
    to a DBMS supporting Bolt version 6.0 or later. This corresponds to Neo4j
    2025.5 or later.

    TODO: check and update final server version above!

    :param dtype: The type of the vector.
        See :attr:`.dtype` for currently supported inner data types.
    :param data: The bytes representing the vector.
    :param byteorder: The endianness of the data.
        If ``"little"``, the bytes in data will be flipped to big-endian
        which will try to use ``neo4j-rust-ext`` or ``numpy`` to speed up the
        byte flipping if installed. Use :data:`sys.byteorder` if you want to
        use the system's native endianness.

    :raises ValueError:
      * If the dtype is not supported or data's size is not a multiple of
        dtype's size.
      * If byteorder is not one of ``"big"`` or ``"little"``.
    :raises TypeError: If the data is not of type bytes.

    .. versionadded: 6.0
    """

    __slots__ = ("__weakref__", "_inner")

    _inner: InnerVector

    def __init__(
        self,
        dtype: str,
        data: bytes,
        /,
        *,
        byteorder:
            # sphinx doesn't resolve the type alias properly :/
            # T_VectorEndian
            # so we spell it out
        VectorEndian | _t.Literal["big", "little"]
            = "big",
    ) -> None:
        type_ = get_type(dtype)
        self._inner = type_(data, byteorder=byteorder)

    def raw(self, *, byteorder: T_VectorEndian = "big") -> bytes:
        """
        Get the raw bytes of the vector.

        The data is a continuous block of memory, containing an array the
        vector's data type. The data is stored in big-endian order. You may
        pass another byte-order to this method to get the converted data.

        :param byteorder: The endianness the data should be returned in.
            If the data's byte-order needs flipping, this method tries to use
            ``neo4j-rust-ext`` or ``numpy``, if installed, to speed up the
            process. Use :data:`sys.byteorder` if you want to use the system's
            native endianness.

        :returns: The raw bytes of the vector.

        :raises ValueError:
            If byteorder is not one of ``"big"`` or ``"little"``.
        """
        match byteorder:
            case "big":
                return self._inner.data
            case "little":
                return self._inner.data_le
            case _:
                raise ValueError(
                    f"Invalid byteorder: {byteorder!r}. "
                    "Must be 'big' or 'little'."
                )

    def set_raw(
        self,
        data: bytes,
        /,
        *,
        byteorder: T_VectorEndian = "big",
    ) -> None:
        """
        Set the raw bytes of the vector.

        :param data: The new raw bytes of the vector.
        :param byteorder: The endianness of ``data``.
            The data will always be stored in big-endian order. If passed-in
            byte-order needs flipping, this method tries to use
            ``neo4j-rust-ext`` or ``numpy``, if installed, to speed up the
            process. Use :data:`sys.byteorder` if you want to use the system's
            native endianness.

        :raises ValueError:
          * If data's size is not a multiple of dtype's size.
          * If byteorder is not one of ``"big"`` or ``"little"``.
        :raises TypeError: If the data is not of type bytes.
        """
        match byteorder:
            case "big":
                self._inner.data = data
            case "little":
                self._inner.data_le = data
            case _:
                raise ValueError(
                    f"Invalid byteorder: {byteorder!r}. "
                    "Must be 'big' or 'little'."
                )

    @property
    def dtype(self) -> str:
        """
        Get the type of the vector.

        Currently supported types are:

        * ``f32``: 32-bit floating point number (single)
        * ``f64``: 64-bit floating point number (double)
        * ``i8``: 8-bit integer
        * ``i16``: 16-bit integer
        * ``i32``: 32-bit integer
        * ``i64``: 64-bit integer

        :returns: The type of the vector.
        """
        return self._inner.dtype

    def __len__(self) -> int:
        """
        Get the number of elements in the vector.

        :returns: The number of elements in the vector.
        """
        return len(self._inner)

    def __str__(self) -> str:
        return str(self._inner)

    def __repr__(self) -> str:
        return f"Vector(dtype={self.dtype!r}, data={self.raw()!r})"

    @classmethod
    @_t.overload
    def from_native(
        cls, dtype: _t.Literal["f32", "f64"], data: _t.Iterable[float]
    ) -> _t.Self: ...

    @classmethod
    @_t.overload
    def from_native(
        cls, dtype: _t.Literal["i8", "i16", "i32", "i64"], data: _t.Iterable[int]
    ) -> _t.Self: ...

    @classmethod
    def from_native(
        cls,
        dtype: _t.Literal["f32", "f64", "i8", "i16", "i32", "i64"],
        data: _t.Iterable[object],
    ) -> _t.Self:
        """
        Create a Vector instance from an iterable of values.

        :param dtype: The type of the vector.
            See also :attr:`.dtype`.
        :param data: The list, tuple, or other iterable of values to create the
            vector from.

        ``data`` must contain values that match the expected type given by
        ``dtype``:

        * ``dtype == "f32"``: :class:`float`
        * ``dtype == "f64"``: :class:`float`
        * ``dtype == "i8"``: :class:`int`
        * ``dtype == "i16"``: :class:`int`
        * ``dtype == "i32"``: :class:`int`
        * ``dtype == "i64"``: :class:`int`

        :raises ValueError: If the dtype is not supported.
        :raises TypeError: If data's elements don't match the expected type
            depending on dtype.
        :raises OverflowError: If the value is out of range for the given type.
        """
        inner = get_type(dtype).from_native(data)
        obj = cls.__new__(cls)
        obj._inner = inner
        return obj

    def to_native(self) -> list[object]:
        """
        Convert the vector to a native Python list.

        The type of the elements in the list depends on the dtype of the
        vector. See :meth:`.from_native` for details.

        :returns: A list of values representing the vector.
        """
        return self._inner.to_native()

    @classmethod
    def from_numpy(cls, data: numpy.ndarray) -> _t.Self:
        """
        Create a Vector instance from a numpy array.

        :param data: The numpy array to create the vector from.
            The array must be one-dimensional and have a dtype that is
            supported by Neo4j vectors: ``float64``, ``float32``,
            ``int64``, ``int32``, ``int16``, or ``int8``.
            See also :attr:`.dtype`.

        :raises ValueError:
          * If the dtype is not supported.
          * If the array is not one-dimensional.
        :raises ImportError: If numpy is not installed.

        :returns: A Vector instance constructed from the numpy array.
        """
        if data.ndim != 1:
            raise ValueError("Data must be one-dimensional")
        type_: type[InnerVector]
        match data.dtype.name:
            case "float64":
                type_ = VecF64
            case "float32":
                type_ = VecF32
            case "int64":
                type_ = VecI64
            case "int32":
                type_ = VecI32
            case "int16":
                type_ = VecI16
            case "int8":
                type_ = VecI8
            case _:
                raise ValueError(f"Unsupported numpy dtype: {data.dtype.name}")
        inner = type_.from_numpy(data)
        obj = cls.__new__(cls)
        obj._inner = inner
        return obj

    def to_numpy(self) -> numpy.ndarray:
        """
        Convert the vector to a numpy array.

        The array's dtype depends on the dtype of the vector. However, it will
        always be in big-endian order.

        :returns: A numpy array representing the vector.

        :raises ImportError: If numpy is not installed.
        """
        return self._inner.to_numpy()

    @classmethod
    def from_pyarrow(cls, data: pyarrow.Array) -> _t.Self:
        """
        Create a Vector instance from a pyarrow array.

        :param data: The pyarrow array to create the vector from.
            The array must have a type that is supported by Neo4j.
            See also :attr:`.dtype`.

        PyArrow stores data in little endian. Therefore, the byte-order needs
        to be swapped. If ``neo4j-rust-ext`` or ``numpy`` is installed, it will
        be used to speed up the byte flipping.

        :raises ValueError:
          * If the array's type is not supported.
          * If the array contains null values.
        :raises ImportError: If pyarrow is not installed.

        :returns: A Vector instance constructed from the pyarrow array.
        """
        import pyarrow

        type_: type[InnerVector]
        if data.type == pyarrow.float64():
            type_ = VecF64
        elif data.type == pyarrow.float32():
            type_ = VecF32
        elif data.type == pyarrow.int64():
            type_ = VecI64
        elif data.type == pyarrow.int32():
            type_ = VecI32
        elif data.type == pyarrow.int16():
            type_ = VecI16
        elif data.type == pyarrow.int8():
            type_ = VecI8
        else:
            raise ValueError(f"Unsupported pyarrow dtype: {data.type}")
        inner = type_.from_pyarrow(data)
        obj = cls.__new__(cls)
        obj._inner = inner
        return obj

    def to_pyarrow(self) -> pyarrow.Array:
        """
        Convert the vector to a pyarrow array.

        :returns: A pyarrow array representing the vector.

        :raises ImportError: If pyarrow is not installed.
        """
        return self._inner.to_pyarrow()

    # TODO: consider conversion to/from
    #   * tensorflow
    #   * pandas
    #   * polars


def swap_endian(type_size: int, data: bytes) -> bytes:
    """Swap from big endian to little endian."""
    if type_size == 1:
        return data
    if type_size not in {2, 4, 8}:
        raise ValueError(f"Unsupported type size: {type_size}")
    if len(data) % type_size != 0:
        raise ValueError(
            f"Data length {len(data)} is not a multiple of {type_size}"
        )
    return _swap_endian_unchecked(type_size, data)


def _swap_endian_unchecked_np(type_size: int, data: bytes) -> bytes:
    match type_size:
        case 2:
            dtype = _np.dtype("<i2")
        case 4:
            dtype = _np.dtype("<i4")
        case 8:
            dtype = _np.dtype("<i8")
        case _:
            raise ValueError(f"Unsupported type size: {type_size}")
    return _np.frombuffer(data, dtype=dtype).byteswap().tobytes()


def _swap_endian_unchecked_py(type_size: int, data: bytes) -> bytes:
    return bytes(
        byte
        for i in range(0, len(data), type_size)
        for byte in data[i : i + type_size][::-1]
    )


if _swap_endian_unchecked_rust is not None:
    _swap_endian_unchecked = _swap_endian_unchecked_rust
elif _np is not None:
    _swap_endian_unchecked = _swap_endian_unchecked_np
else:
    _swap_endian_unchecked = _swap_endian_unchecked_py


def get_type(dtype: str) -> type[InnerVector]:
    if dtype not in _TYPES:
        raise ValueError(f"Unsupported vector type: {dtype}")
    return _TYPES[dtype]


_TYPES: dict[str, type[InnerVector]] = {}


class InnerVector(abc_.ABC):
    __slots__ = ("_data", "_data_le")

    dtype: _t.ClassVar[str]
    size: _t.ClassVar[int]
    _data: bytes
    _data_le: None | bytes

    def __init__(
        self, data: bytes, /, *, byteorder: _t.Literal["big", "little"] = "big"
    ) -> None:
        super().__init__()
        if self.__class__ == InnerVector:
            raise TypeError("Cannot instantiate abstract class InnerVector")
        match byteorder:
            case "big":
                self.data = data
                self._data_le = None
            case "little":
                self.data = swap_endian(self.size, data)
                self._data_le = data
            case _:
                raise ValueError(
                    f"Invalid byteorder: {byteorder!r}. "
                    "Must be 'big' or 'little'."
                )

    @property
    def data(self) -> bytes:
        return self._data

    @data.setter
    def data(self, data: bytes) -> None:
        if not isinstance(data, bytes):
            raise TypeError("Data must be of type bytes")
        if not len(data) % self.size == 0:
            raise ValueError(
                f"Data length {len(data)} is not a multiple of {self.size}"
            )
        self._data = data

    @property
    def data_le(self) -> bytes:
        if self._data_le is None:
            self._data_le = swap_endian(self.size, self.data)
        return self._data_le

    @data_le.setter
    def data_le(self, data: bytes) -> None:
        self.data = swap_endian(self.size, data)
        self._data_le = data

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        dtype = getattr(cls, "dtype", None)
        if not isinstance(dtype, str):
            raise TypeError(
                f"Class {cls.__name__} must have a str attribute 'dtype'"
            )
        if not isinstance(getattr(cls, "size", None), int):
            raise TypeError(
                f"Class {cls.__name__} must have a str attribute 'size'"
            )
        if cls.size not in {1, 2, 4, 8}:
            # Either change the sub-type's size if it was a typo or add support
            # for the new size in the swap_endian function.
            raise ValueError(
                f"Class {cls.__name__} has an unhandled size {cls.size}"
            )
        if dtype in _TYPES:
            raise ValueError(
                f"Class {cls.__name__} has a duplicate type '{dtype}'"
            )
        _TYPES[dtype] = cls

    def __len__(self) -> int:
        return len(self.data) // self.size

    def __str__(self) -> str:
        size = len(self)
        return f"Vec[{self.dtype}; {size}]"

    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        return f"{cls_name}({self.data!r})"

    @classmethod
    @abc_.abstractmethod
    def from_native(cls, data: _t.Iterable[object]) -> _t.Self: ...

    @abc_.abstractmethod
    def to_native(self) -> list[object]: ...

    @classmethod
    def from_numpy(cls, data: numpy.ndarray) -> _t.Self:
        if data.dtype.byteorder == "<" or (
            data.dtype.byteorder == "=" and sys_.byteorder == "little"
        ):
            data = data.byteswap()
        return cls(data.tobytes())

    @abc_.abstractmethod
    def to_numpy(self) -> numpy.ndarray: ...

    @classmethod
    def from_pyarrow(cls, data: pyarrow.Array) -> _t.Self:
        width = data.type.byte_width
        assert cls.size == width
        if _pa.compute.count(data, mode="only_null").as_py():
            raise ValueError("PyArrow array must not contain any null values.")
        _, buffer = data.buffers()
        buffer = buffer[
            data.offset * width : (data.offset + len(data)) * width
        ]
        return cls(bytes(buffer), byteorder=sys_.byteorder)

    @abc_.abstractmethod
    def to_pyarrow(self) -> pyarrow.Array: ...


class VecF64(InnerVector):
    __slots__ = ()

    dtype = "f64"
    size = 8

    @classmethod
    def from_native(cls, data: _t.Iterable[object]) -> _t.Self:
        bytes_ = bytearray()
        for item in data:
            if not isinstance(item, float):
                raise TypeError(
                    f"Cannot build f64 vector from {type(item).__name__}, "
                    "expected float."
                )
            bytes_.extend(struct_.pack(">d", item))
        return cls(bytes(bytes_))

    def to_native(self) -> list[object]:
        return [
            struct_.unpack(">d", self.data[i: i + self.size])[0]
            for i in range(0, len(self.data), self.size)
        ]

    def to_numpy(self) -> numpy.ndarray:
        import numpy

        return numpy.frombuffer(self.data, dtype=numpy.dtype(">f8"))

    def to_pyarrow(self) -> pyarrow.Array:
        import pyarrow

        buffer = pyarrow.py_buffer(self.data_le)
        return pyarrow.Array.from_buffers(
            pyarrow.float64(), len(self), [None, buffer], 0
        )


class VecF32(InnerVector):
    __slots__ = ()

    dtype = "f32"
    size = 4

    @classmethod
    def from_native(cls, data: _t.Iterable[object]) -> _t.Self:
        bytes_ = bytearray()
        for item in data:
            if not isinstance(item, float):
                raise TypeError(
                    f"Cannot build f32 vector from {type(item).__name__}, "
                    "expected float."
                )
            bytes_.extend(struct_.pack(">f", item))
        return cls(bytes(bytes_))

    def to_native(self) -> list[object]:
        return [
            struct_.unpack(">f", self.data[i: i + self.size])[0]
            for i in range(0, len(self.data), self.size)
        ]

    def to_numpy(self) -> numpy.ndarray:
        import numpy

        return numpy.frombuffer(self.data, dtype=numpy.dtype(">f4"))

    def to_pyarrow(self) -> pyarrow.Array:
        import pyarrow

        buffer = pyarrow.py_buffer(self.data_le)
        return pyarrow.Array.from_buffers(
            pyarrow.float32(), len(self), [None, buffer], 0
        )


class _VecI(abc_.ABC):
    __slots__ = ()

    MAX: int
    MIN: int


class VecI64(InnerVector):
    __slots__ = ()

    dtype = "i64"
    size = 8

    @classmethod
    def from_native(cls, data: _t.Iterable[object]) -> _t.Self:
        bytes_ = bytearray()
        for item in data:
            if not isinstance(item, int):
                raise TypeError(
                    f"Cannot build i64 vector from {type(item).__name__}, "
                    "expected int."
                )
            if not -9223372036854775808 <= item <= 9223372036854775807:
                raise OverflowError(
                    f"Value {item} is out of range for i64: "
                    "[-9223372036854775808, 9223372036854775807]"
                )
            bytes_.extend(struct_.pack(">q", item))
        return cls(bytes(bytes_))

    def to_native(self) -> list[object]:
        return [
            struct_.unpack(">q", self.data[i: i + self.size])[0]
            for i in range(0, len(self.data), self.size)
        ]

    def to_numpy(self) -> numpy.ndarray:
        import numpy

        return numpy.frombuffer(self.data, dtype=numpy.dtype(">i8"))

    def to_pyarrow(self) -> pyarrow.Array:
        import pyarrow

        buffer = pyarrow.py_buffer(self.data_le)
        return pyarrow.Array.from_buffers(
            pyarrow.int64(), len(self), [None, buffer], 0
        )


class VecI32(InnerVector):
    __slots__ = ()

    dtype = "i32"
    size = 4

    @classmethod
    def from_native(cls, data: _t.Iterable[object]) -> _t.Self:
        bytes_ = bytearray()
        for item in data:
            if not isinstance(item, int):
                raise TypeError(
                    f"Cannot build i32 vector from {type(item).__name__}, "
                    "expected int."
                )
            if not -2147483648 <= item <= 2147483647:
                raise OverflowError(
                    f"Value {item} is out of range for i32: "
                    "[-2147483648, 2147483647]"
                )
            bytes_.extend(struct_.pack(">i", item))
        return cls(bytes(bytes_))

    def to_native(self) -> list[object]:
        return [
            struct_.unpack(">i", self.data[i: i + self.size])[0]
            for i in range(0, len(self.data), self.size)
        ]

    def to_numpy(self) -> numpy.ndarray:
        import numpy

        return numpy.frombuffer(self.data, dtype=numpy.dtype(">i4"))

    def to_pyarrow(self) -> pyarrow.Array:
        import pyarrow

        buffer = pyarrow.py_buffer(self.data_le)
        return pyarrow.Array.from_buffers(
            pyarrow.int32(), len(self), [None, buffer], 0
        )


class VecI16(InnerVector):
    __slots__ = ()

    dtype = "i16"
    size = 2

    @classmethod
    def from_native(cls, data: _t.Iterable[object]) -> _t.Self:
        bytes_ = bytearray()
        for item in data:
            if not isinstance(item, int):
                raise TypeError(
                    f"Cannot build i16 vector from {type(item).__name__}, "
                    "expected int."
                )
            if not -32768 <= item <= 32767:
                raise OverflowError(
                    f"Value {item} is out of range for i16: [-32768, 32767]"
                )
            bytes_.extend(struct_.pack(">h", item))
        return cls(bytes(bytes_))

    def to_native(self) -> list[object]:
        return [
            struct_.unpack(">h", self.data[i: i + self.size])[0]
            for i in range(0, len(self.data), self.size)
        ]

    def to_numpy(self) -> numpy.ndarray:
        import numpy

        return numpy.frombuffer(self.data, dtype=numpy.dtype(">i2"))

    def to_pyarrow(self) -> pyarrow.Array:
        import pyarrow

        buffer = pyarrow.py_buffer(self.data_le)
        return pyarrow.Array.from_buffers(
            pyarrow.int16(), len(self), [None, buffer], 0
        )


class VecI8(InnerVector):
    __slots__ = ()

    dtype = "i8"
    size = 1

    @classmethod
    def from_native(cls, data: _t.Iterable[object]) -> _t.Self:
        bytes_ = bytearray()
        for item in data:
            if not isinstance(item, int):
                raise TypeError(
                    f"Cannot build i8 vector from {type(item).__name__}, "
                    "expected int."
                )
            if not -128 <= item <= 127:
                raise OverflowError(
                    f"Value {item} is out of range for i8: [-128, 127]"
                )
            bytes_.extend(struct_.pack(">b", item))
        return cls(bytes(bytes_))

    def to_native(self) -> list[object]:
        return [
            struct_.unpack(">b", self.data[i: i + self.size])[0]
            for i in range(0, len(self.data), self.size)
        ]

    def to_numpy(self) -> numpy.ndarray:
        import numpy

        return numpy.frombuffer(self.data, dtype=numpy.dtype(">i1"))

    def to_pyarrow(self) -> pyarrow.Array:
        import pyarrow

        buffer = pyarrow.py_buffer(self.data_le)
        return pyarrow.Array.from_buffers(
            pyarrow.int8(), len(self), [None, buffer], 0
        )
