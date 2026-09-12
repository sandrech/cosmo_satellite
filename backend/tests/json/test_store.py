from __future__ import annotations

from pathlib import Path

from json_component import Err, JsonObjectCodec, JsonStore, Ok, VersionedObjectCodec
from json_component.problems import ProblemCode


def make_store():
    return JsonStore(VersionedObjectCodec(JsonObjectCodec(), "x-1"))


def test_load_missing_file_is_error(tmp_path: Path):
    result = make_store().load(tmp_path / "missing.json")
    assert isinstance(result, Err)
    assert result.error[0].code == ProblemCode.IO_READ


def test_save_and_load(tmp_path: Path):
    path = tmp_path / "project.json"
    assert make_store().save(path, {"a": 1}) == Ok(None)
    assert make_store().load(path) == Ok({"a": 1})


def test_save_does_not_create_parent(tmp_path: Path):
    path = tmp_path / "missing" / "project.json"
    result = make_store().save(path, {"a": 1})
    assert isinstance(result, Err)
    assert result.error[0].code == ProblemCode.IO_WRITE


def test_invalid_input_does_not_raise(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text('{"schema_version":"x-1",', encoding="utf-8")
    result = make_store().load(path)
    assert isinstance(result, Err)
    assert result.error[0].code == ProblemCode.JSON_SYNTAX


def test_failed_encode_does_not_overwrite_existing(tmp_path: Path):
    path = tmp_path / "project.json"
    path.write_text("old\n", encoding="utf-8")
    result = make_store().save(path, {"x": float("nan")})
    assert isinstance(result, Err)
    assert path.read_text(encoding="utf-8") == "old\n"


def test_successful_save_replaces_existing(tmp_path: Path):
    path = tmp_path / "project.json"
    path.write_text("old\n", encoding="utf-8")
    assert make_store().save(path, {"a": 1}) == Ok(None)
    assert "schema_version" in path.read_text(encoding="utf-8")
