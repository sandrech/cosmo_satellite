from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tempfile
from typing import Generic, TypeVar

from .codec import Codec
from .problems import Problem, ProblemCode, Problems
from .result import Err, Ok, Result
from .syntax import dumps, loads
from .types import JsonFormat

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class JsonStore(Generic[T]):
    codec: Codec[T]
    format: JsonFormat = JsonFormat()

    def loads(self, text: str) -> Result[T, Problems]:
        parsed = loads(text)
        if isinstance(parsed, Err):
            return parsed
        return self.codec.decode(parsed.value)

    def dumps(self, value: T) -> Result[str, Problems]:
        encoded = self.codec.encode(value)
        if isinstance(encoded, Err):
            return encoded
        return dumps(encoded.value, self.format)

    def load(self, path: str | Path) -> Result[T, Problems]:
        source = Path(path)
        try:
            text = source.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            return Err((Problem(
                ProblemCode.IO_READ,
                str(exc),
                details=(("path", str(source)),),
            ),))
        return self.loads(text)

    def save(self, path: str | Path, value: T) -> Result[None, Problems]:
        destination = Path(path)
        rendered = self.dumps(value)
        if isinstance(rendered, Err):
            return rendered

        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                stream.write(rendered.value)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
            temporary = None
        except (OSError, UnicodeError) as exc:
            return Err((Problem(
                ProblemCode.IO_WRITE,
                str(exc),
                details=(("path", str(destination)),),
            ),))
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

        return Ok(None)
