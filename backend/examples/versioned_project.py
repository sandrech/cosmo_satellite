from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from json_component import (
    Err,
    JsonObject,
    JsonStore,
    MappedCodec,
    Migration,
    MigrationGraph,
    Ok,
    VersionedObjectCodec,
)
from json_component.pydantic_adapter import PydanticCodec


class ProjectDto(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: str
    enabled: bool


@dataclass(frozen=True, slots=True)
class Project:
    name: str
    enabled: bool


def migrate_0_1_to_0_2(payload: JsonObject):
    migrated = dict(payload)
    migrated["name"] = migrated.pop("title", "unnamed")
    return Ok(migrated)


def from_dto(dto: ProjectDto):
    return Ok(Project(dto.name, dto.enabled))


def to_dto(project: Project):
    return Ok(ProjectDto(name=project.name, enabled=project.enabled))


payload_codec = MappedCodec(
    PydanticCodec.for_type(ProjectDto),
    from_storage=from_dto,
    to_storage=to_dto,
)
codec = VersionedObjectCodec(
    payload=payload_codec,
    current_version="project-0.2",
    migrations=MigrationGraph([
        Migration("project-0.1", "project-0.2", migrate_0_1_to_0_2),
    ]),
)
store = JsonStore(codec)

result = store.loads('{"schema_version":"project-0.1","title":"demo","enabled":true}')
if isinstance(result, Err):
    for problem in result.error:
        print(problem)
else:
    print(result.value)
