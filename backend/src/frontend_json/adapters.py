from __future__ import annotations

from json_component import MappedCodec, Ok, Problems, Result
from json_component.pydantic_adapter import PydanticCodec
from spatial3d import (
    ContactKind,
    CoordinateFrame,
    NetworkEdge,
    NetworkGroundObservation,
    NetworkGroundVisibility,
    NetworkNode,
    NetworkNodeKind,
    NetworkProjection,
    SceneFrame,
    ScenePoint,
    ScenePointKind,
    SceneSegment,
    Vec3,
)
from static_model import (
    ClientFailureImpact,
    ClientSnapshotAnalysis,
    CoverageState,
    LinkKind,
    NetworkSummary,
    NoRouteReason,
    RankedSatelliteImpact,
    ResilienceState,
    Route,
    RouteFailureDelta,
    RouteMetrics,
    RouteSegment,
    RoutingState,
    SatelliteConnectivity,
    SatelliteFailureImpact,
    ServiceState,
    StaticAnalysis,
)

from .dto import (
    ClientFailureImpactDto,
    ClientSnapshotAnalysisDto,
    CoverageStateDto,
    GroundObservationDto,
    NetworkEdgeDto,
    NetworkNodeDto,
    NetworkProjectionDto,
    NetworkSummaryDto,
    RankedSatelliteImpactDto,
    ResilienceStateDto,
    RouteDto,
    RouteFailureDeltaDto,
    RouteMetricsDto,
    RouteSegmentDto,
    RoutingStateDto,
    SatelliteConnectivityDto,
    SatelliteFailureImpactDto,
    SatelliteFailureImpactSummaryDto,
    SceneFrameDto,
    ScenePointDto,
    SceneSegmentDto,
    ServiceStateDto,
    StaticAnalysisDto,
    Vec3Dto,
)


def _ok(value):
    return Ok(value)


def _vec_to_dto(value: Vec3) -> Vec3Dto:
    return Vec3Dto(x_km=value.x, y_km=value.y, z_km=value.z)


def _vec_from_dto(value: Vec3Dto) -> Vec3:
    return Vec3(value.x_km, value.y_km, value.z_km)


def scene_to_dto(frame: SceneFrame) -> SceneFrameDto:
    return SceneFrameDto(
        t_s=frame.t_s,
        coordinate_frame=frame.coordinate_frame.value,
        body_radius_km=frame.body_radius_km,
        points=[
            ScenePointDto(
                id=point.id,
                label=point.label,
                kind=point.kind.value,
                position=_vec_to_dto(point.earth_fixed_km),
                available=point.available,
                trajectory_group_id=point.trajectory_group_id,
            )
            for point in frame.points
        ],
        contacts=[
            SceneSegmentDto(
                a=segment.a,
                b=segment.b,
                distance_km=segment.distance_km,
                kind=segment.kind.value,
            )
            for segment in frame.contacts
        ],
    )


def scene_from_dto(dto: SceneFrameDto) -> SceneFrame:
    return SceneFrame(
        t_s=dto.t_s,
        coordinate_frame=CoordinateFrame(dto.coordinate_frame),
        body_radius_km=dto.body_radius_km,
        points=tuple(
            ScenePoint(
                id=point.id,
                label=point.label,
                kind=ScenePointKind(point.kind),
                earth_fixed_km=_vec_from_dto(point.position),
                available=point.available,
                trajectory_group_id=point.trajectory_group_id,
            )
            for point in dto.points
        ),
        contacts=tuple(
            SceneSegment(
                a=segment.a,
                b=segment.b,
                distance_km=segment.distance_km,
                kind=ContactKind(segment.kind),
            )
            for segment in dto.contacts
        ),
    )


def scene_codec() -> MappedCodec[SceneFrame, SceneFrameDto]:
    return MappedCodec(
        storage=PydanticCodec.for_type(SceneFrameDto),
        from_storage=lambda value: _ok(scene_from_dto(value)),
        to_storage=lambda value: _ok(scene_to_dto(value)),
    )


def network_to_dto(projection: NetworkProjection) -> NetworkProjectionDto:
    return NetworkProjectionDto(
        t_s=projection.t_s,
        nodes=[NetworkNodeDto(id=node.id, kind=node.kind.value, available=node.available) for node in projection.nodes],
        edges=[
            NetworkEdgeDto(a=edge.a, b=edge.b, distance_km=edge.distance_km, kind=edge.kind.value)
            for edge in projection.edges
        ],
        ground_observations=[
            GroundObservationDto(
                ground_id=item.ground_id,
                satellite_id=item.satellite_id,
                elevation_deg=item.elevation_deg,
                distance_km=item.distance_km,
            )
            for item in projection.ground_observations
        ],
        ground_visibility=[
            GroundObservationDto(
                ground_id=item.ground_id,
                satellite_id=item.satellite_id,
                elevation_deg=item.elevation_deg,
                distance_km=item.distance_km,
            )
            for item in projection.ground_visibility
        ],
    )


def network_from_dto(dto: NetworkProjectionDto) -> NetworkProjection:
    return NetworkProjection(
        t_s=dto.t_s,
        nodes=tuple(NetworkNode(node.id, NetworkNodeKind(node.kind), node.available) for node in dto.nodes),
        edges=tuple(
            NetworkEdge(edge.a, edge.b, edge.distance_km, ContactKind(edge.kind))
            for edge in dto.edges
        ),
        ground_observations=tuple(
            NetworkGroundObservation(item.ground_id, item.satellite_id, item.elevation_deg, item.distance_km)
            for item in dto.ground_observations
        ),
        ground_visibility=tuple(
            NetworkGroundVisibility(item.ground_id, item.satellite_id, item.elevation_deg, item.distance_km)
            for item in dto.ground_visibility
        ),
    )


def network_codec() -> MappedCodec[NetworkProjection, NetworkProjectionDto]:
    return MappedCodec(
        storage=PydanticCodec.for_type(NetworkProjectionDto),
        from_storage=lambda value: _ok(network_from_dto(value)),
        to_storage=lambda value: _ok(network_to_dto(value)),
    )


def _route_to_dto(route: Route) -> RouteDto:
    return RouteDto(
        strategy_id=route.strategy_id,
        source_id=route.source_id,
        target_id=route.target_id,
        node_ids=list(route.node_ids),
        segments=[
            RouteSegmentDto(
                from_id=segment.from_id,
                to_id=segment.to_id,
                kind=segment.kind.value,
                distance_km=segment.distance_km,
                elevation_deg=segment.elevation_deg,
            )
            for segment in route.segments
        ],
        metrics=RouteMetricsDto(
            hop_count=route.metrics.hop_count,
            total_distance_km=route.metrics.total_distance_km,
            objective_value=route.metrics.objective_value,
        ),
    )


def _route_from_dto(dto: RouteDto) -> Route:
    return Route(
        strategy_id=dto.strategy_id,
        source_id=dto.source_id,
        target_id=dto.target_id,
        node_ids=tuple(dto.node_ids),
        segments=tuple(
            RouteSegment(
                from_id=segment.from_id,
                to_id=segment.to_id,
                kind=LinkKind(segment.kind),
                distance_km=segment.distance_km,
                elevation_deg=segment.elevation_deg,
            )
            for segment in dto.segments
        ),
        metrics=RouteMetrics(
            hop_count=dto.metrics.hop_count,
            total_distance_km=dto.metrics.total_distance_km,
            objective_value=dto.metrics.objective_value,
        ),
    )


def _routing_to_dto(value: RoutingState) -> RoutingStateDto:
    return RoutingStateDto(
        selected_route=None if value.selected_route is None else _route_to_dto(value.selected_route),
        routes=[_route_to_dto(route) for route in value.routes],
    )


def _routing_from_dto(value: RoutingStateDto) -> RoutingState:
    routes = tuple(_route_from_dto(route) for route in value.routes)
    selected = None if value.selected_route is None else _route_from_dto(value.selected_route)
    return RoutingState(selected, routes)


def _client_to_dto(value: ClientSnapshotAnalysis) -> ClientSnapshotAnalysisDto:
    resilience = None
    if value.resilience is not None:
        resilience = ResilienceStateDto(
            satellite_connectivity=SatelliteConnectivityDto(
                node_disjoint_path_count=value.resilience.satellite_connectivity.node_disjoint_path_count,
                minimum_cut=list(value.resilience.satellite_connectivity.minimum_cut),
            ),
            critical_satellites=list(value.resilience.critical_satellites),
            survives_any_single_satellite_failure=value.resilience.survives_any_single_satellite_failure,
        )
    return ClientSnapshotAnalysisDto(
        client_id=value.client_id,
        coverage=CoverageStateDto(
            visible_satellites=list(value.coverage.visible_satellites),
            has_visibility=value.coverage.has_visibility,
        ),
        service=ServiceStateDto(
            reachable=value.service.reachable,
            valid_ingress_satellites=list(value.service.valid_ingress_satellites),
            reachable_gateways=list(value.service.reachable_gateways),
            no_route_reason=None if value.service.no_route_reason is None else value.service.no_route_reason.value,
        ),
        routing=_routing_to_dto(value.routing),
        resilience=resilience,
    )


def _client_from_dto(value: ClientSnapshotAnalysisDto) -> ClientSnapshotAnalysis:
    resilience = None
    if value.resilience is not None:
        resilience = ResilienceState(
            SatelliteConnectivity(
                value.resilience.satellite_connectivity.node_disjoint_path_count,
                tuple(value.resilience.satellite_connectivity.minimum_cut),
            ),
            tuple(value.resilience.critical_satellites),
            value.resilience.survives_any_single_satellite_failure,
        )
    return ClientSnapshotAnalysis(
        client_id=value.client_id,
        coverage=CoverageState(tuple(value.coverage.visible_satellites)),
        service=ServiceState(
            value.service.reachable,
            tuple(value.service.valid_ingress_satellites),
            tuple(value.service.reachable_gateways),
            None if value.service.no_route_reason is None else NoRouteReason(value.service.no_route_reason),
        ),
        routing=_routing_from_dto(value.routing),
        resilience=resilience,
    )


def _delta_to_dto(value: RouteFailureDelta) -> RouteFailureDeltaDto:
    return RouteFailureDeltaDto(
        strategy_id=value.strategy_id,
        before=None if value.before is None else _route_to_dto(value.before),
        after=None if value.after is None else _route_to_dto(value.after),
        route_lost=value.route_lost,
        path_changed=value.path_changed,
        objective_increase=value.objective_increase,
    )


def _delta_from_dto(value: RouteFailureDeltaDto) -> RouteFailureDelta:
    return RouteFailureDelta(
        strategy_id=value.strategy_id,
        before=None if value.before is None else _route_from_dto(value.before),
        after=None if value.after is None else _route_from_dto(value.after),
    )


def _impact_to_dto(value: SatelliteFailureImpact) -> SatelliteFailureImpactDto:
    clients = [
        ClientFailureImpactDto(
            client_id=item.client_id,
            service_lost=item.service_lost,
            geometric_visibility_lost=item.geometric_visibility_lost,
            visible_satellites_lost=item.visible_satellites_lost,
            valid_ingress_lost=item.valid_ingress_lost,
            reachable_gateways_lost=item.reachable_gateways_lost,
            satellite_connectivity_loss=item.satellite_connectivity_loss,
            route_deltas=[_delta_to_dto(delta) for delta in item.route_deltas],
        )
        for item in value.clients
    ]
    return SatelliteFailureImpactDto(
        satellite_id=value.satellite_id,
        clients=clients,
        summary=SatelliteFailureImpactSummaryDto(
            lost_clients=list(value.lost_clients),
            clients_losing_geometric_visibility=list(value.clients_losing_geometric_visibility),
            total_visible_satellites_lost=value.total_visible_satellites_lost,
            total_valid_ingress_lost=value.total_valid_ingress_lost,
            total_reachable_gateways_lost=value.total_reachable_gateways_lost,
            total_connectivity_loss=value.total_connectivity_loss,
            routes_lost=value.routes_lost,
            routes_changed=value.routes_changed,
        ),
    )


def _impact_from_dto(value: SatelliteFailureImpactDto) -> SatelliteFailureImpact:
    return SatelliteFailureImpact(
        satellite_id=value.satellite_id,
        clients=tuple(
            ClientFailureImpact(
                client_id=item.client_id,
                service_lost=item.service_lost,
                geometric_visibility_lost=item.geometric_visibility_lost,
                visible_satellites_lost=item.visible_satellites_lost,
                valid_ingress_lost=item.valid_ingress_lost,
                reachable_gateways_lost=item.reachable_gateways_lost,
                satellite_connectivity_loss=item.satellite_connectivity_loss,
                route_deltas=tuple(_delta_from_dto(delta) for delta in item.route_deltas),
            )
            for item in value.clients
        ),
    )


def static_analysis_to_dto(value: StaticAnalysis) -> StaticAnalysisDto:
    return StaticAnalysisDto(
        summary=NetworkSummaryDto(
            node_count=value.summary.node_count,
            link_count=value.summary.link_count,
            available_satellites=value.summary.available_satellites,
            available_gateways=value.summary.available_gateways,
            client_count=value.summary.client_count,
            visible_client_count=value.summary.visible_client_count,
            reachable_client_count=value.summary.reachable_client_count,
            all_clients_reachable=value.summary.all_clients_reachable,
        ),
        clients=[_client_to_dto(client) for client in value.clients],
        satellite_failure_impacts=[_impact_to_dto(impact) for impact in value.satellite_failure_impacts],
        satellite_criticality_ranking=[
            RankedSatelliteImpactDto(rank=item.rank, satellite_id=item.impact.satellite_id)
            for item in value.satellite_criticality_ranking
        ],
    )


def static_analysis_from_dto(value: StaticAnalysisDto) -> StaticAnalysis:
    impacts = tuple(_impact_from_dto(impact) for impact in value.satellite_failure_impacts)
    by_satellite = {impact.satellite_id: impact for impact in impacts}
    ranking = tuple(
        RankedSatelliteImpact(item.rank, by_satellite[item.satellite_id])
        for item in value.satellite_criticality_ranking
    )
    return StaticAnalysis(
        summary=NetworkSummary(
            node_count=value.summary.node_count,
            link_count=value.summary.link_count,
            available_satellites=value.summary.available_satellites,
            available_gateways=value.summary.available_gateways,
            client_count=value.summary.client_count,
            visible_client_count=value.summary.visible_client_count,
            reachable_client_count=value.summary.reachable_client_count,
        ),
        clients=tuple(_client_from_dto(client) for client in value.clients),
        satellite_failure_impacts=impacts,
        satellite_criticality_ranking=ranking,
    )


def static_analysis_codec() -> MappedCodec[StaticAnalysis, StaticAnalysisDto]:
    return MappedCodec(
        storage=PydanticCodec.for_type(StaticAnalysisDto),
        from_storage=lambda value: _ok(static_analysis_from_dto(value)),
        to_storage=lambda value: _ok(static_analysis_to_dto(value)),
    )


def encode_scene(frame: SceneFrame):
    """Encode a scene frame to validated JSON-compatible values."""
    return scene_codec().encode(frame)


def decode_scene(value):
    """Decode the versioned scene JSON contract back to a domain frame."""
    return scene_codec().decode(value)


def encode_network(projection: NetworkProjection):
    """Encode a neutral network projection to validated JSON-compatible values."""
    return network_codec().encode(projection)


def decode_network(value):
    """Decode the versioned network projection JSON contract."""
    return network_codec().decode(value)


def encode_static_analysis(analysis: StaticAnalysis):
    """Encode static snapshot analytics without introducing transport concerns."""
    return static_analysis_codec().encode(analysis)


def decode_static_analysis(value):
    """Decode the versioned static-analysis JSON contract."""
    return static_analysis_codec().decode(value)
