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


class DynamicProblemCode(StrEnum):
    INVALID_GRID = "dynamic.invalid_grid"
    INVALID_TARGET = "dynamic.invalid_target"
    INVALID_PLAN = "dynamic.invalid_plan"
    SPATIAL_SNAPSHOT = "dynamic.spatial_snapshot"
    STATIC_MODEL = "dynamic.static_model"
    INCONSISTENT_ANALYSIS = "dynamic.inconsistent_analysis"


@dataclass(frozen=True, slots=True)
class DynamicProblem:
    code: DynamicProblemCode
    message: str
    path: tuple[str | int, ...] = ()


DynamicProblems: TypeAlias = tuple[DynamicProblem, ...]
