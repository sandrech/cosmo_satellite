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


class ComparisonProblemCode(StrEnum):
    TOO_FEW_VARIANTS = "comparison.too_few_variants"
    DUPLICATE_VARIANT_ID = "comparison.duplicate_variant_id"
    UNKNOWN_BASELINE = "comparison.unknown_baseline"
    GRID_MISMATCH = "comparison.grid_mismatch"
    DUPLICATE_PARAMETER = "comparison.duplicate_parameter"
    INCONSISTENT_ANALYSIS = "comparison.inconsistent_analysis"


@dataclass(frozen=True, slots=True)
class ComparisonProblem:
    code: ComparisonProblemCode
    message: str
    path: tuple[str | int, ...] = ()


ComparisonProblems: TypeAlias = tuple[ComparisonProblem, ...]
