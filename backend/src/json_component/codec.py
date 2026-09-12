from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, Protocol, TypeVar

from .problems import Problem, ProblemCode, Problems
from .result import Err, Ok, Result
from .types import JsonObject, JsonValue

T = TypeVar("T")
StorageT = TypeVar("StorageT")


class Codec(Protocol[T]):
    def decode(self, value: JsonValue) -> Result[T, Problems]: ...
    def encode(self, value: T) -> Result[JsonValue, Problems]: ...


@dataclass(frozen=True, slots=True)
class FunctionCodec(Generic[T]):
    decoder: Callable[[JsonValue], Result[T, Problems]]
    encoder: Callable[[T], Result[JsonValue, Problems]]

    def decode(self, value: JsonValue) -> Result[T, Problems]:
        return self.decoder(value)

    def encode(self, value: T) -> Result[JsonValue, Problems]:
        return self.encoder(value)


@dataclass(frozen=True, slots=True)
class MappedCodec(Generic[T, StorageT]):
    storage: Codec[StorageT]
    from_storage: Callable[[StorageT], Result[T, Problems]]
    to_storage: Callable[[T], Result[StorageT, Problems]]

    def decode(self, value: JsonValue) -> Result[T, Problems]:
        decoded = self.storage.decode(value)
        if isinstance(decoded, Err):
            return decoded
        return self.from_storage(decoded.value)

    def encode(self, value: T) -> Result[JsonValue, Problems]:
        mapped = self.to_storage(value)
        if isinstance(mapped, Err):
            return mapped
        return self.storage.encode(mapped.value)


@dataclass(frozen=True, slots=True)
class JsonObjectCodec:
    def decode(self, value: JsonValue) -> Result[JsonObject, Problems]:
        if not isinstance(value, dict):
            return Err((Problem(
                ProblemCode.DECODE_TYPE,
                "expected a JSON object",
                details=(("actual", type(value).__name__),),
            ),))
        return Ok(value)

    def encode(self, value: JsonObject) -> Result[JsonValue, Problems]:
        return Ok(value)
