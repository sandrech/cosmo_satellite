from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

from .codec import Codec
from .migration import MigrationGraph, SchemaVersion, is_schema_version
from .problems import Problem, ProblemCode, Problems
from .result import Err, Ok, Result
from .types import JsonObject, JsonValue

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class VersionedObjectCodec(Generic[T]):
    payload: Codec[T]
    current_version: SchemaVersion
    migrations: MigrationGraph = field(default_factory=MigrationGraph)
    version_field: str = "schema_version"

    def __post_init__(self) -> None:
        if not is_schema_version(self.current_version):
            raise ValueError("current_version must be a non-empty, non-whitespace string")
        if not isinstance(self.version_field, str) or not self.version_field.strip():
            raise ValueError("version_field must be a non-empty, non-whitespace string")

    def decode(self, value: JsonValue) -> Result[T, Problems]:
        if not isinstance(value, dict):
            return Err((Problem(ProblemCode.DECODE_TYPE, "versioned document must be a JSON object"),))

        if self.version_field not in value:
            return Err((Problem(
                ProblemCode.SCHEMA_MISSING_VERSION,
                f"missing required {self.version_field!r}",
                (self.version_field,),
            ),))
        raw_version = value[self.version_field]
        if not is_schema_version(raw_version):
            return Err((Problem(
                ProblemCode.SCHEMA_INVALID_VERSION,
                f"{self.version_field!r} must be a non-empty, non-whitespace string",
                (self.version_field,),
            ),))

        payload: JsonObject = dict(value)
        del payload[self.version_field]

        migrated = self.migrations.upgrade(payload, raw_version, self.current_version)
        if isinstance(migrated, Err):
            return migrated
        return self.payload.decode(migrated.value)

    def encode(self, value: T) -> Result[JsonValue, Problems]:
        encoded = self.payload.encode(value)
        if isinstance(encoded, Err):
            return encoded
        if not isinstance(encoded.value, dict):
            return Err((Problem(
                ProblemCode.ENCODE,
                "payload codec for a versioned object must encode to a JSON object",
            ),))
        if self.version_field in encoded.value:
            return Err((Problem(
                ProblemCode.SCHEMA_RESERVED_FIELD,
                f"payload must not define reserved field {self.version_field!r}",
                (self.version_field,),
            ),))

        return Ok({self.version_field: self.current_version, **encoded.value})
