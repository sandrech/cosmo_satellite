from __future__ import annotations

import math
import pytest

from json_component import Err, JsonFormat, Ok, dumps, loads
from json_component.problems import ProblemCode


@pytest.mark.parametrize("text, expected", [
    ("null", None),
    ("true", True),
    ("false", False),
    ("0", 0),
    ("-15", -15),
    ("1.25", 1.25),
    ('"hello"', "hello"),
    ("[]", []),
    ("{}", {}),
    ('{"a":[1,true,null]}', {"a": [1, True, None]}),
])
def test_loads_valid(text, expected):
    assert loads(text) == Ok(expected)


@pytest.mark.parametrize("text", [
    "{",
    "[1,",
    '{"a":}',
    "tru",
    "'single quotes'",
])
def test_loads_syntax_error(text):
    result = loads(text)
    assert isinstance(result, Err)
    assert result.error[0].code == ProblemCode.JSON_SYNTAX


@pytest.mark.parametrize("text", ["NaN", "Infinity", "-Infinity", "1e99999"])
def test_loads_rejects_non_finite(text):
    result = loads(text)
    assert isinstance(result, Err)
    assert result.error[0].code == ProblemCode.JSON_NON_FINITE


def test_loads_rejects_duplicate_key():
    result = loads('{"a":1,"a":2}')
    assert isinstance(result, Err)
    assert result.error[0].code == ProblemCode.JSON_DUPLICATE_KEY


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_dumps_rejects_non_finite(value):
    result = dumps({"x": value})
    assert isinstance(result, Err)
    assert result.error[0].code == ProblemCode.JSON_NON_FINITE
    assert result.error[0].path == ("x",)


def test_dumps_rejects_non_string_key():
    result = dumps({1: "x"})  # type: ignore[dict-item]
    assert isinstance(result, Err)
    assert result.error[0].code == ProblemCode.JSON_INVALID_VALUE


def test_dumps_rejects_cycle():
    value = []
    value.append(value)
    result = dumps(value)  # type: ignore[arg-type]
    assert isinstance(result, Err)
    assert result.error[0].code == ProblemCode.JSON_INVALID_VALUE


def test_dumps_format_options():
    result = dumps({"β": 1, "a": 2}, JsonFormat(indent=None, ensure_ascii=False, sort_keys=True, trailing_newline=False))
    assert result == Ok('{"a": 2, "β": 1}')
