from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from json_component import Err, Ok
from json_component.problems import ProblemCode
from json_component.pydantic_adapter import PydanticCodec


class Child(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    count: int


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str
    child: Child


def test_pydantic_decode():
    codec = PydanticCodec.for_type(Model)
    result = codec.decode({"name": "x", "child": {"count": 2}})
    assert result == Ok(Model(name="x", child=Child(count=2)))


def test_pydantic_strict_type_error_has_path():
    codec = PydanticCodec.for_type(Model)
    result = codec.decode({"name": "x", "child": {"count": "2"}})
    assert isinstance(result, Err)
    assert result.error[0].code == ProblemCode.DECODE_VALIDATION
    assert result.error[0].path == ("child", "count")


def test_pydantic_extra_field_rejected():
    codec = PydanticCodec.for_type(Model)
    result = codec.decode({"name": "x", "child": {"count": 2}, "unknown": 1})
    assert isinstance(result, Err)
    assert result.error[0].path == ("unknown",)


def test_pydantic_encode():
    codec = PydanticCodec.for_type(Model)
    result = codec.encode(Model(name="x", child=Child(count=2)))
    assert result == Ok({"name": "x", "child": {"count": 2}})
