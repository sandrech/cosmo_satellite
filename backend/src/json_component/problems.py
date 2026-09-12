from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TypeAlias

from .types import JsonPath, JsonPathPart, format_path


class ProblemCode(StrEnum):
    IO_READ = "io.read"
    IO_WRITE = "io.write"
    JSON_SYNTAX = "json.syntax"
    JSON_DUPLICATE_KEY = "json.duplicate_key"
    JSON_NON_FINITE = "json.non_finite"
    JSON_INVALID_VALUE = "json.invalid_value"
    DECODE_TYPE = "decode.type"
    DECODE_VALIDATION = "decode.validation"
    ENCODE = "encode.failure"
    SCHEMA_MISSING_VERSION = "schema.missing_version"
    SCHEMA_INVALID_VERSION = "schema.invalid_version"
    SCHEMA_UNSUPPORTED_VERSION = "schema.unsupported_version"
    SCHEMA_RESERVED_FIELD = "schema.reserved_field"
    MIGRATION = "schema.migration"
    MIGRATION_CYCLE = "schema.migration_cycle"
    MIGRATION_AMBIGUOUS_PATH = "schema.migration_ambiguous_path"


@dataclass(frozen=True, slots=True)
class Problem:
    code: ProblemCode
    message: str
    path: JsonPath = ()
    details: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def prefixed(self, *parts: JsonPathPart) -> "Problem":
        return Problem(self.code, self.message, (*parts, *self.path), self.details)

    def __str__(self) -> str:
        location = format_path(self.path)
        if not self.details:
            return f"{self.code} at {location}: {self.message}"
        details = ", ".join(f"{key}={value}" for key, value in self.details)
        return f"{self.code} at {location}: {self.message} ({details})"


Problems: TypeAlias = tuple[Problem, ...]


def one(problem: Problem) -> Problems:
    return (problem,)
