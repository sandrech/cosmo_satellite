from __future__ import annotations

from dataclasses import dataclass
import math
from typing import TypeAlias

JsonScalar: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]
JsonPathPart: TypeAlias = str | int
JsonPath: TypeAlias = tuple[JsonPathPart, ...]


@dataclass(frozen=True, slots=True)
class JsonFormat:
    indent: int | None = 2
    ensure_ascii: bool = False
    sort_keys: bool = False
    trailing_newline: bool = True


def format_path(path: JsonPath) -> str:
    result = "$"
    for part in path:
        if isinstance(part, int):
            result += f"[{part}]"
        elif part.isidentifier():
            result += f".{part}"
        else:
            escaped = part.replace("\\", "\\\\").replace("'", "\\'")
            result += f"['{escaped}']"
    return result


def is_json_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and (not isinstance(value, float) or math.isfinite(value))
    )
