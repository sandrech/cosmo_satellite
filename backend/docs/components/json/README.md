# JSON component

A persistence boundary, not a satellite-model package.

The component has four deliberately separate layers:

1. **JSON syntax** (`syntax.py`, `types.py`) — parse/render RFC-style JSON values, reject duplicate keys and non-finite numbers.
2. **Typed conversion** (`codec.py`, optional `pydantic_adapter.py`) — convert `JsonValue` to a component-owned/application-owned type and back.
3. **Schema evolution** (`migration.py`, `versioned.py`) — keep `schema_version` outside the domain object, migrate old JSON payloads explicitly, always write the current version.
4. **Storage** (`store.py`) — UTF-8 file IO and atomic replace; expected input/IO errors are returned as `Err`, not thrown.

The satellite/static/dynamic/3D/UI components depend only on `Codec[T]` / `JsonStore[T]`. The JSON package does not import any of them.

## Why the version is outside the model

The case files have this shape:

```json
{
  "schema_version": "cosmo-A-1.0",
  "meta": {},
  "environment": {},
  "design": {}
}
```

`VersionedObjectCodec` removes the version field before handing the payload to the application codec and inserts the current version on save. This prevents persistence metadata from leaking into the static model while preserving the case format.

## Errors as values

Public operations return:

```python
Ok(value)
Err((Problem(...), ...))
```

Expected failures include malformed JSON, duplicate keys, non-finite numbers, validation errors, unsupported schema versions, migration failures and file IO errors. Programmer errors (for example a broken migration callback violating its contract) are not broadly swallowed.

Each `Problem` has a stable `ProblemCode`, a JSON path and optional details. UI code can render it, translate it, group it, or attach it to a field without parsing exception strings.

## Schema evolution

Versions are opaque identifiers. There is no hidden assumption that `1.10 > 1.9` or that every project uses semantic versioning. `MigrationGraph` is a DAG, and graph reachability defines a **partial order** over schema versions:

```text
a < b  iff a directed migration path exists from a to b
a = b  iff the version identifiers are equal
a || b when neither version reaches the other
```

This permits branches and merges instead of imposing a false total order:

```text
              feature-a
             /         \
cosmo-A-1.0              cosmo-A-2.0
             \         /
              feature-b
```

Cycles are rejected when the graph is constructed, which gives antisymmetry. Reflexive migration edges and duplicate edges are rejected as programmer configuration errors. Version identifiers must be non-empty, non-whitespace strings.

Loading may only move upward in the partial order. Equal versions need no migration; incomparable versions and attempted downgrades return `Err(SCHEMA_UNSUPPORTED_VERSION)`. A DAG can contain several distinct chains between the same ordered pair. That is a valid partial order but an ambiguous data transformation, so `upgrade()` returns `Err(MIGRATION_AMBIGUOUS_PATH)` rather than selecting a path by iteration order.

For a deterministic history:

```python
Migration("cosmo-A-1.0", "cosmo-A-1.1", migrate_1_0_to_1_1)
Migration("cosmo-A-1.1", "cosmo-A-2.0", migrate_1_1_to_2_0)
```

Loading upgrades in memory to the current payload type. Saving always writes the current version. Migration transforms work on JSON objects rather than old domain objects, so the application only needs to maintain its current model.

`VersionRelation` exposes `BEFORE`, `EQUAL`, `AFTER`, and `INCOMPARABLE` for code which needs to reason about the schema order explicitly.

## Typed models

The core has no runtime dependency. A Pydantic v2 adapter is supplied as an optional integration because it gives strict structural validation and precise field paths:

```python
payload_codec = PydanticCodec.for_type(ScenarioDto)
codec = VersionedObjectCodec(
    payload=payload_codec,
    current_version="cosmo-A-1.0",
)
store = JsonStore(codec)
```

If the static model should stay independent from its persistence DTO, place `MappedCodec` around the DTO codec. The mapping functions return `Result` too, so cross-field/domain conversion failures remain normal values.

## File safety

`JsonStore.save()` serializes and validates first, writes a temporary file in the destination directory, flushes + `fsync`s it, then replaces the destination with `os.replace`. A failed encode cannot truncate the old file.

The method intentionally does **not** create parent directories: whether a missing project directory should be created is a higher-level application decision.

## Running tests

```bash
python -m pip install -e '.[test]'
pytest
```

Tests include syntax failures, duplicate fields, non-finite values, invalid object graphs, type validation, migration behavior, atomic persistence and structural round-trip of all four JSON scenarios from the case archive.
