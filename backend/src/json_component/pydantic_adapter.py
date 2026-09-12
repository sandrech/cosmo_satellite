from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import TypeAdapter, ValidationError
from pydantic_core import PydanticSerializationError

from .problems import Problem, ProblemCode, Problems
from .result import Err, Ok, Result
from .types import JsonValue
from .validation import validate_json_value

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class PydanticCodec(Generic[T]):
    adapter: TypeAdapter[T]

    @classmethod
    def for_type(cls, value_type: type[T]) -> "PydanticCodec[T]":
        return cls(TypeAdapter(value_type))

    def decode(self, value: JsonValue) -> Result[T, Problems]:
        try:
            return Ok(self.adapter.validate_python(value, strict=True))
        except ValidationError as exc:
            problems = tuple(
                Problem(
                    ProblemCode.DECODE_VALIDATION,
                    error["msg"],
                    tuple(error["loc"]),
                    (("kind", error["type"]),),
                )
                for error in exc.errors(include_url=False, include_context=False, include_input=False)
            )
            return Err(problems)

    def encode(self, value: T) -> Result[JsonValue, Problems]:
        try:
            dumped = self.adapter.dump_python(value, mode="json", warnings="error")
        except (PydanticSerializationError, ValueError, TypeError) as exc:
            return Err((Problem(ProblemCode.ENCODE, str(exc)),))
        return validate_json_value(dumped)
