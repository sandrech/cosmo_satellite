from __future__ import annotations

import pytest

from json_component import (
    Err,
    Migration,
    MigrationGraph,
    Ok,
    VersionRelation,
)
from json_component.problems import ProblemCode


def identity(payload):
    return Ok(payload)


def test_reachability_defines_partial_order():
    graph = MigrationGraph([
        Migration("a", "b", identity),
        Migration("a", "c", identity),
        Migration("b", "d", identity),
        Migration("c", "d", identity),
    ])

    assert graph.relation("a", "d") is VersionRelation.BEFORE
    assert graph.relation("d", "a") is VersionRelation.AFTER
    assert graph.relation("b", "b") is VersionRelation.EQUAL
    assert graph.relation("b", "c") is VersionRelation.INCOMPARABLE
    assert graph.precedes("a", "d")
    assert not graph.comparable("b", "c")


def test_branch_is_allowed_when_only_one_branch_reaches_target():
    def a_to_b(payload):
        return Ok({**payload, "route": ["b"]})

    def b_to_d(payload):
        return Ok({**payload, "route": [*payload["route"], "d"]})

    graph = MigrationGraph([
        Migration("a", "b", a_to_b),
        Migration("a", "c", identity),
        Migration("b", "d", b_to_d),
    ])

    assert graph.upgrade({}, "a", "d") == Ok({"route": ["b", "d"]})


def test_diamond_is_valid_partial_order_but_ambiguous_for_data_migration():
    graph = MigrationGraph([
        Migration("a", "b", identity),
        Migration("a", "c", identity),
        Migration("b", "d", identity),
        Migration("c", "d", identity),
    ])

    result = graph.upgrade({}, "a", "d")
    assert isinstance(result, Err)
    assert result.error[0].code is ProblemCode.MIGRATION_AMBIGUOUS_PATH


def test_incomparable_versions_cannot_be_upgraded():
    graph = MigrationGraph([
        Migration("a", "b", identity),
        Migration("x", "y", identity),
    ])

    result = graph.upgrade({}, "a", "y")
    assert isinstance(result, Err)
    assert result.error[0].code is ProblemCode.SCHEMA_UNSUPPORTED_VERSION
    assert ("relation", "incomparable") in result.error[0].details


def test_downgrade_is_rejected_by_partial_order():
    graph = MigrationGraph([Migration("a", "b", identity)])

    result = graph.upgrade({}, "b", "a")
    assert isinstance(result, Err)
    assert result.error[0].code is ProblemCode.SCHEMA_UNSUPPORTED_VERSION
    assert ("relation", "after") in result.error[0].details


def test_cycle_is_rejected_when_graph_is_constructed():
    with pytest.raises(ValueError, match="acyclic"):
        MigrationGraph([
            Migration("a", "b", identity),
            Migration("b", "c", identity),
            Migration("c", "a", identity),
        ])


def test_duplicate_edge_is_rejected():
    with pytest.raises(ValueError, match="duplicate migration edge"):
        MigrationGraph([
            Migration("a", "b", identity),
            Migration("a", "b", identity),
        ])


def test_migration_rejects_reflexive_edge():
    with pytest.raises(ValueError, match="must differ"):
        Migration("a", "a", identity)


@pytest.mark.parametrize("version", ["", "   "])
def test_migration_rejects_invalid_version_identifier(version):
    with pytest.raises(ValueError, match="non-empty"):
        Migration(version, "b", identity)
