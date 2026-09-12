from __future__ import annotations

import json

from .problems import Problem, ProblemCode, Problems
from .result import Err, Ok, Result
from .types import JsonFormat, JsonValue
from .validation import validate_json_value


class _DuplicateKey(ValueError):
    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(key)


class _NonFiniteNumber(ValueError):
    pass


def _object_without_duplicates(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey(key)
        result[key] = value
    return result


def _parse_float(text: str) -> float:
    value = float(text)
    if not __import__("math").isfinite(value):
        raise _NonFiniteNumber(text)
    return value


def _reject_constant(text: str) -> float:
    raise _NonFiniteNumber(text)


def loads(text: str) -> Result[JsonValue, Problems]:
    try:
        value = json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_float=_parse_float,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        return Err((Problem(
            ProblemCode.JSON_SYNTAX,
            exc.msg,
            details=(("line", str(exc.lineno)), ("column", str(exc.colno)), ("position", str(exc.pos))),
        ),))
    except _DuplicateKey as exc:
        return Err((Problem(
            ProblemCode.JSON_DUPLICATE_KEY,
            f"duplicate object key: {exc.key!r}",
            details=(("key", exc.key),),
        ),))
    except _NonFiniteNumber as exc:
        return Err((Problem(
            ProblemCode.JSON_NON_FINITE,
            f"non-finite number is not valid JSON: {exc}",
        ),))

    return validate_json_value(value)


def dumps(value: JsonValue, format: JsonFormat = JsonFormat()) -> Result[str, Problems]:
    valid = validate_json_value(value)
    if isinstance(valid, Err):
        return valid

    try:
        text = json.dumps(
            value,
            ensure_ascii=format.ensure_ascii,
            indent=format.indent,
            sort_keys=format.sort_keys,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        return Err((Problem(ProblemCode.ENCODE, str(exc)),))

    if format.trailing_newline:
        text += "\n"
    return Ok(text)
