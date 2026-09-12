from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeAlias, TypeVar

T = TypeVar("T")
U = TypeVar("U")
E = TypeVar("E")


@dataclass(frozen=True, slots=True)
class Ok(Generic[T]):
    value: T


@dataclass(frozen=True, slots=True)
class Err(Generic[E]):
    error: E


Result: TypeAlias = Ok[T] | Err[E]


def map_ok(result: Result[T, E], function: Callable[[T], U]) -> Result[U, E]:
    if isinstance(result, Err):
        return result
    return Ok(function(result.value))
