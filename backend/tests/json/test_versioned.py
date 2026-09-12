from __future__ import annotations

import pytest

from json_component import Err, JsonObjectCodec, Migration, MigrationGraph, Ok, VersionedObjectCodec
from json_component.problems import Problem, ProblemCode


def test_current_version_decodes_without_migration():
    codec = VersionedObjectCodec(JsonObjectCodec(), "x-2")
    assert codec.decode({"schema_version": "x-2", "a": 1}) == Ok({"a": 1})


def test_encode_inserts_version_first():
    codec = VersionedObjectCodec(JsonObjectCodec(), "x-2")
    result = codec.encode({"a": 1})
    assert result == Ok({"schema_version": "x-2", "a": 1})
    assert list(result.value) == ["schema_version", "a"]


def test_missing_version_is_error():
    result = VersionedObjectCodec(JsonObjectCodec(), "x-2").decode({"a": 1})
    assert isinstance(result, Err)
    assert result.error[0].code == ProblemCode.SCHEMA_MISSING_VERSION


@pytest.mark.parametrize("version", [2, "", "   "])
def test_invalid_document_version_is_error(version):
    result = VersionedObjectCodec(JsonObjectCodec(), "x-2").decode({"schema_version": version})
    assert isinstance(result, Err)
    assert result.error[0].code == ProblemCode.SCHEMA_INVALID_VERSION


def test_invalid_current_version_is_programmer_error():
    with pytest.raises(ValueError, match="current_version"):
        VersionedObjectCodec(JsonObjectCodec(), "   ")


def test_root_must_be_object():
    result = VersionedObjectCodec(JsonObjectCodec(), "x-2").decode([])
    assert isinstance(result, Err)
    assert result.error[0].code == ProblemCode.DECODE_TYPE


def test_reserved_field_from_payload_is_error():
    codec = VersionedObjectCodec(JsonObjectCodec(), "x-2")
    result = codec.encode({"schema_version": "bad"})
    assert isinstance(result, Err)
    assert result.error[0].code == ProblemCode.SCHEMA_RESERVED_FIELD


def test_migration_graph_upgrades_multiple_steps():
    def one_to_two(payload):
        return Ok({**payload, "b": payload["a"]})

    def two_to_three(payload):
        result = dict(payload)
        result["c"] = result.pop("b")
        return Ok(result)

    codec = VersionedObjectCodec(
        JsonObjectCodec(),
        "x-3",
        MigrationGraph([
            Migration("x-1", "x-2", one_to_two),
            Migration("x-2", "x-3", two_to_three),
        ]),
    )
    assert codec.decode({"schema_version": "x-1", "a": 7}) == Ok({"a": 7, "c": 7})


def test_unknown_old_version_is_error():
    codec = VersionedObjectCodec(JsonObjectCodec(), "x-3")
    result = codec.decode({"schema_version": "x-1", "a": 7})
    assert isinstance(result, Err)
    assert result.error[0].code == ProblemCode.SCHEMA_UNSUPPORTED_VERSION


def test_migration_failure_is_prefixed_and_identifies_edge():
    def fail(payload):
        return Err((Problem(ProblemCode.MIGRATION, "nope", ("field",)),))

    codec = VersionedObjectCodec(
        JsonObjectCodec(), "x-2", MigrationGraph([Migration("x-1", "x-2", fail)])
    )
    result = codec.decode({"schema_version": "x-1", "a": 7})
    assert isinstance(result, Err)
    assert result.error[0].path == ("<migration>", "field")
    assert ("source", "x-1") in result.error[0].details
    assert ("target", "x-2") in result.error[0].details


def test_ambiguous_partial_order_path_is_reported_as_value():
    keep = lambda payload: Ok(payload)
    codec = VersionedObjectCodec(
        JsonObjectCodec(),
        "x-4",
        MigrationGraph([
            Migration("x-1", "x-2a", keep),
            Migration("x-1", "x-2b", keep),
            Migration("x-2a", "x-4", keep),
            Migration("x-2b", "x-4", keep),
        ]),
    )
    result = codec.decode({"schema_version": "x-1", "a": 7})
    assert isinstance(result, Err)
    assert result.error[0].code == ProblemCode.MIGRATION_AMBIGUOUS_PATH
