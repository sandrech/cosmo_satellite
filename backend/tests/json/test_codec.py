from __future__ import annotations

from dataclasses import dataclass

from json_component import Err, JsonObjectCodec, MappedCodec, Ok
from json_component.problems import Problem, ProblemCode


@dataclass(frozen=True)
class Name:
    value: str


def from_storage(value):
    raw = value.get("name")
    if not isinstance(raw, str) or not raw:
        return Err((Problem(ProblemCode.DECODE_VALIDATION, "name required", ("name",)),))
    return Ok(Name(raw))


def to_storage(value):
    return Ok({"name": value.value})


def test_mapped_codec_decode():
    codec = MappedCodec(JsonObjectCodec(), from_storage, to_storage)
    assert codec.decode({"name": "demo"}) == Ok(Name("demo"))


def test_mapped_codec_encode():
    codec = MappedCodec(JsonObjectCodec(), from_storage, to_storage)
    assert codec.encode(Name("demo")) == Ok({"name": "demo"})


def test_mapped_codec_propagates_decode_error():
    codec = MappedCodec(JsonObjectCodec(), from_storage, to_storage)
    result = codec.decode({"name": ""})
    assert isinstance(result, Err)


def test_object_codec_rejects_array():
    result = JsonObjectCodec().decode([])
    assert isinstance(result, Err)
    assert result.error[0].code == ProblemCode.DECODE_TYPE
