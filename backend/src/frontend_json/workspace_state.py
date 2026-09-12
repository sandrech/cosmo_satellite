from __future__ import annotations

from typing import Any, Literal

from json_component.pydantic_adapter import PydanticCodec
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, allow_inf_nan=False)


class WorkspaceScenarioDto(StrictModel):
    id: str
    title: str
    altitudeKm: float
    inclinationDeg: float
    earthAngle0Deg: float = 12.0
    launchStage: Literal[1, 2, 3]
    islRangeKm: float
    minElevationDeg: float = 10.0
    stepS: float = Field(gt=0)
    horizonS: float = Field(gt=0)
    targetAvailability: float
    canonical: dict[str, Any] | None = None


class WorkspaceRuntimeDto(StrictModel):
    t_s: float = Field(ge=0)
    client_id: str
    selected_id: str | None = None


class WorkspaceViewportDto(StrictModel):
    page: Literal["project", "analysis", "resilience", "comparison"]
    view_mode: Literal["2d", "3d"]
    earth_style: Literal["black", "imagery"]


class WorkspaceLayersDto(StrictModel):
    satellites: bool
    groundSites: bool
    orbits: bool
    network: bool
    route: bool
    labels: bool


class FrontendWorkspaceStateDto(StrictModel):
    """Versioned state payload produced by the React workbench Save button."""

    schema_version: Literal["frontend-workspace-state-1.0"] = "frontend-workspace-state-1.0"
    saved_at: str
    scenario: WorkspaceScenarioDto
    runtime: WorkspaceRuntimeDto
    viewport: WorkspaceViewportDto
    layers: WorkspaceLayersDto
    hidden_node_ids: list[str]
    frame_snapshot: dict[str, Any] | None = None


def workspace_state_codec() -> PydanticCodec[FrontendWorkspaceStateDto]:
    return PydanticCodec.for_type(FrontendWorkspaceStateDto)


def decode_workspace_state(value):
    """Validate JSON from POST /api/runs/current/state."""
    return workspace_state_codec().decode(value)


def encode_workspace_state(value: FrontendWorkspaceStateDto):
    """Encode a validated workspace state back to JSON-compatible values."""
    return workspace_state_codec().encode(value)
