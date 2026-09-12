from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from enum import StrEnum

from .problems import Problem, ProblemCode, Problems
from .result import Err, Ok, Result
from .types import JsonObject

SchemaVersion = str
MigrationFunction = Callable[[JsonObject], Result[JsonObject, Problems]]


def is_schema_version(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_version(version: SchemaVersion, *, name: str) -> None:
    if not is_schema_version(version):
        raise ValueError(f"{name} must be a non-empty, non-whitespace string")


@dataclass(frozen=True, slots=True)
class Migration:
    source: SchemaVersion
    target: SchemaVersion
    transform: MigrationFunction

    def __post_init__(self) -> None:
        _validate_version(self.source, name="migration source")
        _validate_version(self.target, name="migration target")
        if self.source == self.target:
            raise ValueError("migration source and target must differ")
        if not callable(self.transform):
            raise TypeError("migration transform must be callable")


class VersionRelation(StrEnum):
    """Relation between two schema versions in the migration partial order."""

    BEFORE = "before"
    EQUAL = "equal"
    AFTER = "after"
    INCOMPARABLE = "incomparable"


class MigrationGraph:
    """A migration DAG whose reachability relation is a partial order.

    For versions ``a`` and ``b``:

    - ``a < b`` iff there is a directed path from ``a`` to ``b``;
    - ``a == b`` iff the identifiers are equal;
    - otherwise the versions may be incomparable.

    Branches and merges are allowed.  Data migration itself must still be
    deterministic: ``upgrade`` rejects a source/target pair when more than one
    distinct migration path exists between them.
    """

    __slots__ = ("_outgoing", "_versions")

    def __init__(self, migrations: Iterable[Migration] = ()) -> None:
        outgoing: dict[SchemaVersion, list[Migration]] = defaultdict(list)
        versions: set[SchemaVersion] = set()
        edges: set[tuple[SchemaVersion, SchemaVersion]] = set()

        for migration in migrations:
            edge = (migration.source, migration.target)
            if edge in edges:
                raise ValueError(
                    f"duplicate migration edge: {migration.source} -> {migration.target}"
                )
            edges.add(edge)
            outgoing[migration.source].append(migration)
            versions.add(migration.source)
            versions.add(migration.target)

        self._outgoing = {
            source: tuple(sorted(items, key=lambda item: item.target))
            for source, items in outgoing.items()
        }
        self._versions = frozenset(versions)
        self._validate_acyclic()

    @property
    def versions(self) -> frozenset[SchemaVersion]:
        return self._versions

    def relation(self, left: SchemaVersion, right: SchemaVersion) -> VersionRelation:
        _validate_version(left, name="left version")
        _validate_version(right, name="right version")

        if left == right:
            return VersionRelation.EQUAL
        if self._reachable(left, right):
            return VersionRelation.BEFORE
        if self._reachable(right, left):
            return VersionRelation.AFTER
        return VersionRelation.INCOMPARABLE

    def precedes(self, left: SchemaVersion, right: SchemaVersion) -> bool:
        return self.relation(left, right) is VersionRelation.BEFORE

    def comparable(self, left: SchemaVersion, right: SchemaVersion) -> bool:
        return self.relation(left, right) is not VersionRelation.INCOMPARABLE

    def upgrade(
        self,
        payload: JsonObject,
        source: SchemaVersion,
        target: SchemaVersion,
    ) -> Result[JsonObject, Problems]:
        relation = self.relation(source, target)
        if relation is VersionRelation.EQUAL:
            return Ok(payload)
        if relation is not VersionRelation.BEFORE:
            return Err((Problem(
                ProblemCode.SCHEMA_UNSUPPORTED_VERSION,
                "source schema version does not precede the target version",
                details=(("source", source), ("target", target), ("relation", relation.value)),
            ),))

        paths = list(self._paths(source, target, limit=2))
        if len(paths) != 1:
            return Err((Problem(
                ProblemCode.MIGRATION_AMBIGUOUS_PATH,
                "more than one migration path exists between schema versions",
                details=(("source", source), ("target", target)),
            ),))

        current_payload = payload
        for migration in paths[0]:
            migrated = migration.transform(dict(current_payload))
            if isinstance(migrated, Err):
                details = (
                    ("source", migration.source),
                    ("target", migration.target),
                )
                return Err(tuple(
                    Problem(
                        problem.code,
                        problem.message,
                        ("<migration>", *problem.path),
                        (*problem.details, *details),
                    )
                    for problem in migrated.error
                ))
            current_payload = migrated.value

        return Ok(current_payload)

    def _reachable(self, source: SchemaVersion, target: SchemaVersion) -> bool:
        if source == target:
            return True

        pending = [source]
        visited: set[SchemaVersion] = set()
        while pending:
            current = pending.pop()
            if current in visited:
                continue
            visited.add(current)
            for migration in self._outgoing.get(current, ()):
                if migration.target == target:
                    return True
                pending.append(migration.target)
        return False

    def _paths(
        self,
        source: SchemaVersion,
        target: SchemaVersion,
        *,
        limit: int,
    ) -> Iterator[tuple[Migration, ...]]:
        """Yield at most ``limit`` distinct paths from source to target."""

        yielded = 0
        stack: list[tuple[SchemaVersion, tuple[Migration, ...]]] = [(source, ())]
        while stack and yielded < limit:
            current, path = stack.pop()
            for migration in reversed(self._outgoing.get(current, ())):
                next_path = (*path, migration)
                if migration.target == target:
                    yielded += 1
                    yield next_path
                    if yielded >= limit:
                        return
                elif self._reachable(migration.target, target):
                    stack.append((migration.target, next_path))

    def _validate_acyclic(self) -> None:
        state: dict[SchemaVersion, int] = {}
        path: list[SchemaVersion] = []

        def visit(version: SchemaVersion) -> None:
            status = state.get(version, 0)
            if status == 2:
                return
            if status == 1:
                try:
                    start = path.index(version)
                    cycle = [*path[start:], version]
                except ValueError:
                    cycle = [version, version]
                raise ValueError(
                    "migration graph must be acyclic: " + " -> ".join(cycle)
                )

            state[version] = 1
            path.append(version)
            for migration in self._outgoing.get(version, ()):
                visit(migration.target)
            path.pop()
            state[version] = 2

        for version in sorted(self._versions):
            visit(version)


# Compatibility name for callers of the first revision.  The implementation is
# now a DAG rather than a chain; new code should use MigrationGraph.
MigrationChain = MigrationGraph
