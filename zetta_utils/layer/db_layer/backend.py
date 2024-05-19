# pylint: disable=missing-docstring # pragma: no cover
from __future__ import annotations

from abc import abstractmethod
from typing import MutableMapping, Sequence, Union

from .. import Backend
from . import DBIndex

DBScalarValueT = Union[bool, int, float, str]
DBArrayValueT = list[DBScalarValueT]
DBValueT = Union[DBScalarValueT, DBArrayValueT]
DBRowDataT = MutableMapping[str, DBValueT]
DBDataT = Sequence[DBRowDataT]


class DBBackend(Backend[DBIndex, DBDataT, DBDataT]):  # pylint: disable=too-few-public-methods
    @abstractmethod
    def __contains__(self, idx: str) -> bool:
        ...

    @abstractmethod
    def __len__(self) -> int:
        ...

    @abstractmethod
    def read(self, idx: DBIndex) -> DBDataT:
        ...

    @abstractmethod
    def write(self, idx: DBIndex, data: DBDataT):
        ...

    @abstractmethod
    def clear(self, idx: DBIndex | None = None) -> None:
        ...

    @abstractmethod
    def keys(self, column_filter: dict[str, list] | None = None) -> list[str]:
        ...

    @abstractmethod
    def query(
        self,
        column_filter: dict[str, list] | None = None,
    ) -> dict[str, DBRowDataT]:
        ...
