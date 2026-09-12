from __future__ import annotations

from spatial3d import SpatialSnapshot, project_network, project_scene
from static_model import StaticAnalysis

from .adapters import network_to_dto, scene_to_dto, static_analysis_to_dto


def build_frontend_frame(snapshot: SpatialSnapshot, analysis: StaticAnalysis) -> dict[str, object]:
    """Build the transport-neutral JSON payload consumed by the React frontend.

    The bundle intentionally reuses the three strict frontend_json contracts so an
    HTTP layer only needs to serialize this dictionary.  No domain objects leak
    into the browser contract.
    """

    return {
        "schema_version": "frontend-frame-1.0",
        "scene": scene_to_dto(project_scene(snapshot)).model_dump(mode="json"),
        "network": network_to_dto(project_network(snapshot)).model_dump(mode="json"),
        "analysis": static_analysis_to_dto(analysis).model_dump(mode="json"),
    }
