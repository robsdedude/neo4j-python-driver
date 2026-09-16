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

from . import _typing as t


__all__ = [
    "MajorVersion",
    "VersionTuple",
]


T = t.TypeVar("T", bound=tuple[int, ...])


class _VersionBase(t.Generic[T]):
    version: T
    part_names: t.ClassVar[tuple[str, ...]]

    def __init__(self, version_parts: T) -> None:
        super().__init__()
        self.version = version_parts
        self._check_positive_version()

    def __init_subclass__(cls, *kwargs) -> None:
        version_type = t.get_type_hints(cls).get("version")
        if version_type is None:
            raise TypeError(
                f"Subclass {cls.__name__} must specify a type for the "
                "'version' attribute."
            )
        if t.get_origin(version_type) is not tuple:
            raise TypeError(
                f"Subclass {cls.__name__} must specify a tuple type for the "
                f"'version' attribute, found {version_type}."
            )
        args = t.get_args(t.get_type_hints(cls)["version"])
        if any(arg is Ellipsis for arg in args):
            raise TypeError(
                f"Subclass {cls.__name__} must specify a concrete type for "
                f"the 'version' attribute, found {version_type}."
            )
        if len(args) != len(cls.part_names):
            raise TypeError(
                f"Subclass {cls.__name__} must specify a 'version' attribute "
                "matching the length of 'part_names' "
                f"({len(cls.part_names)}), found {version_type}."
            )
        return super().__init_subclass__()

    def _check_positive_version(self) -> None:
        version = self.version
        for i, part in enumerate(version):
            if part < 0:
                name = self.part_names[i]
                raise ValueError(
                    f"{self.__class__.__name__} version parts must be "
                    f"non-negative integers, found {name} {part} in {version}."
                )

    def __hash__(self) -> int:
        return hash(self.version)

    def __iter__(self) -> t.Iterator[int]:
        return iter(self.version)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, _VersionBase):
            return self.version == other.version
        if isinstance(other, tuple):
            return self.version == other
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        if isinstance(other, _VersionBase):
            return self.version != other.version
        if isinstance(other, tuple):
            return self.version != other
        return NotImplemented

    def __lt__(self, other: t.Self | tuple) -> bool:
        if isinstance(other, type(self)):
            return self.version < other.version
        if isinstance(other, tuple):
            return self.version < other
        return NotImplemented

    def __le__(self, other: t.Self | tuple) -> bool:
        if isinstance(other, type(self)):
            return self.version <= other.version
        if isinstance(other, tuple):
            return self.version <= other
        return NotImplemented

    def __gt__(self, other: t.Self | tuple) -> bool:
        if isinstance(other, type(self)):
            return self.version > other.version
        if isinstance(other, tuple):
            return self.version > other
        return NotImplemented

    def __ge__(self, other: t.Self | tuple) -> bool:
        if isinstance(other, type(self)):
            return self.version >= other.version
        if isinstance(other, tuple):
            return self.version >= other
        return NotImplemented

    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        args = ", ".join(map(str, self.version))
        return f"{cls_name}({args})"

    def __str__(self) -> str:
        return ".".join(map(str, self.version))


class MajorVersion(_VersionBase):
    version: tuple[int]
    part_names = ("major",)

    def __init__(self, major: int, /) -> None:
        super().__init__((major,))

    @property
    def major(self) -> int:
        return self.version[0]


class VersionTuple(_VersionBase):
    version: tuple[int, int]
    part_names = ("major", "minor")

    def __init__(self, major: int, minor: int, /) -> None:
        super().__init__((major, minor))

    @property
    def major(self) -> int:
        return self.version[0]

    @property
    def minor(self) -> int:
        return self.version[1]
