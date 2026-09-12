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


class SpatialProblemCode(StrEnum):
    INVALID_NUMBER = "spatial.invalid_number"
    INVALID_RANGE = "spatial.invalid_range"
    DUPLICATE_ID = "spatial.duplicate_id"
    INVALID_ROLE = "spatial.invalid_role"
    INVALID_INTERVAL = "spatial.invalid_interval"
    INVALID_REFERENCE = "spatial.invalid_reference"
    INVALID_TRAJECTORY = "spatial.invalid_trajectory"
    TRAJECTORY_BINDING = "spatial.trajectory_binding"


@dataclass(frozen=True, slots=True)
class SpatialProblem:
    code: SpatialProblemCode
    message: str
    path: tuple[str | int, ...] = ()


SpatialProblems: TypeAlias = tuple[SpatialProblem, ...]
