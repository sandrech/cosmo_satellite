from __future__ import annotations

from typing import Any

from dynamic_model import DynamicAnalysis
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


def result_document_from_dynamic_analysis(
    effective_scenario: dict[str, Any],
    analysis: DynamicAnalysis,
) -> ResultDocumentDto:
    """Build the mandatory full-period result document from a dynamic trace.

    ``ResultDocumentDto`` performs the authoritative contract check: the dynamic
    grid and client set must cover every ``t_s × client`` pair required by the
    effective cosmo-A scenario.  A partial dynamic run therefore cannot be
    accidentally exported as a complete competition result.
    """

    routes = [
        route_record_from_analysis(frame.t_s, client)
        for frame in analysis.frames
        for client in frame.static.clients
    ]
    return ResultDocumentDto(
        effective_scenario=effective_scenario,
        routes=routes,
    )


def result_codec() -> PydanticCodec[ResultDocumentDto]:
    return PydanticCodec.for_type(ResultDocumentDto)
