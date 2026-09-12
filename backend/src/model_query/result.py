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


class QueryProblemCode(StrEnum):
    INVALID_RANGE = "query.invalid_range"
    INVALID_PLAN = "query.invalid_plan"
    SPATIAL_SNAPSHOT = "query.spatial_snapshot"
    STATIC_MODEL = "query.static_model"


@dataclass(frozen=True, slots=True)
class QueryProblem:
    code: QueryProblemCode
    message: str
    path: tuple[str | int, ...] = ()


QueryProblems: TypeAlias = tuple[QueryProblem, ...]
