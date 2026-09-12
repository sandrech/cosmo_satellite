from __future__ import annotations

import math

from .problems import Problem, ProblemCode, Problems
from .result import Err, Ok, Result
from .types import JsonPath, JsonValue


def validate_json_value(value: object) -> Result[JsonValue, Problems]:
    problem = _find_invalid(value, (), set())
    if problem is not None:
        return Err((problem,))
    return Ok(value)  # type: ignore[arg-type]


def _find_invalid(value: object, path: JsonPath, active: set[int]) -> Problem | None:
    if value is None or isinstance(value, (bool, str)):
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return None
    if isinstance(value, float):
        if math.isfinite(value):
            return None
        return Problem(ProblemCode.JSON_NON_FINITE, "JSON numbers must be finite", path)

    if isinstance(value, list):
        identity = id(value)
        if identity in active:
            return Problem(ProblemCode.JSON_INVALID_VALUE, "cyclic list is not representable as JSON", path)
        active.add(identity)
        try:
            for index, item in enumerate(value):
                problem = _find_invalid(item, (*path, index), active)
                if problem is not None:
                    return problem
            return None
        finally:
            active.remove(identity)

    if isinstance(value, dict):
        identity = id(value)
        if identity in active:
            return Problem(ProblemCode.JSON_INVALID_VALUE, "cyclic object is not representable as JSON", path)
        active.add(identity)
        try:
            for key, item in value.items():
                if not isinstance(key, str):
                    return Problem(
                        ProblemCode.JSON_INVALID_VALUE,
                        "JSON object keys must be strings",
                        path,
                        (("key_type", type(key).__name__),),
                    )
                problem = _find_invalid(item, (*path, key), active)
                if problem is not None:
                    return problem
            return None
        finally:
            active.remove(identity)

    return Problem(
        ProblemCode.JSON_INVALID_VALUE,
        "value is not representable as JSON",
        path,
        (("type", type(value).__name__),),
    )
