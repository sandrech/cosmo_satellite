from __future__ import annotations

from json_component.pydantic_adapter import PydanticCodec
from static_model import ClientSnapshotAnalysis, Route

from .dto import ResultDocumentDto, RouteRecordDto


def route_record(t_s: int | float, client_id: str, route: Route | None) -> RouteRecordDto:
    """Project a domain route to the mandatory cosmo-A result representation."""
    return RouteRecordDto(
        t_s=t_s,
        client_id=client_id,
        path=[] if route is None else list(route.node_ids),
    )


def route_record_from_analysis(t_s: int | float, analysis: ClientSnapshotAnalysis) -> RouteRecordDto:
    return route_record(t_s, analysis.client_id, analysis.routing.selected_route)


def result_codec() -> PydanticCodec[ResultDocumentDto]:
    return PydanticCodec.for_type(ResultDocumentDto)
