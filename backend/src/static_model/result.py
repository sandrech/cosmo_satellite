from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeAlias, TypeVar

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True, slots=True)
class Ok(Generic[T]):
    value: T


@dataclass(frozen=True, slots=True)
class Err(Generic[E]):
    error: E


Result: TypeAlias = Ok[T] | Err[E]


class StaticProblemCode(StrEnum):
    DUPLICATE_NODE = "duplicate_node"
    UNKNOWN_NODE = "unknown_node"
    INVALID_LINK = "invalid_link"
    DUPLICATE_LINK = "duplicate_link"
    INVALID_NUMBER = "invalid_number"
    INVALID_QUERY = "invalid_query"
    INVALID_PLAN = "invalid_plan"
    INVALID_VISIBILITY = "invalid_visibility"


@dataclass(frozen=True, slots=True)
class StaticProblem:
    code: StaticProblemCode
    message: str
    path: tuple[str | int, ...] = ()

    def __str__(self) -> str:
        where = "$"
        for item in self.path:
            where += f"[{item}]" if isinstance(item, int) else f".{item}"
        return f"{self.code}: {where}: {self.message}"


StaticProblems: TypeAlias = tuple[StaticProblem, ...]
