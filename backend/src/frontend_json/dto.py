from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, allow_inf_nan=False)


class Vec3Dto(StrictModel):
    x_km: float
    y_km: float
    z_km: float


class ScenePointDto(StrictModel):
    id: str
    label: str
    kind: Literal["satellite", "client", "gateway"]
    position: Vec3Dto
    available: bool
    trajectory_group_id: str | None = None


class SceneSegmentDto(StrictModel):
    a: str
    b: str
    distance_km: float = Field(ge=0.0)
    kind: Literal["inter_satellite", "ground_satellite"]


class SceneFrameDto(StrictModel):
    schema_version: Literal["spatial-scene-1.0"] = "spatial-scene-1.0"
    t_s: float
    coordinate_frame: Literal["earth_fixed"]
    body_radius_km: float = Field(gt=0.0)
    points: list[ScenePointDto]
    contacts: list[SceneSegmentDto]

    @model_validator(mode="after")
    def validate_scene(self) -> "SceneFrameDto":
        ids = [point.id for point in self.points]
        if any(not item for item in ids) or len(ids) != len(set(ids)):
            raise ValueError("scene point identifiers must be non-empty and unique")
        known = set(ids)
        for contact in self.contacts:
            if contact.a == contact.b:
                raise ValueError("scene contacts must connect distinct points")
            if contact.a not in known or contact.b not in known:
                raise ValueError("scene contact endpoint does not exist")
        return self


class NetworkNodeDto(StrictModel):
    id: str
    kind: Literal["satellite", "client", "gateway"]
    available: bool


class NetworkEdgeDto(StrictModel):
    a: str
    b: str
    distance_km: float = Field(ge=0.0)
    kind: Literal["inter_satellite", "ground_satellite"]


class GroundObservationDto(StrictModel):
    ground_id: str
    satellite_id: str
    elevation_deg: float = Field(ge=-90.0, le=90.0)
    distance_km: float = Field(ge=0.0)


class NetworkProjectionDto(StrictModel):
    schema_version: Literal["spatial-network-1.0"] = "spatial-network-1.0"
    t_s: float
    nodes: list[NetworkNodeDto]
    edges: list[NetworkEdgeDto]
    ground_observations: list[GroundObservationDto]
    ground_visibility: list[GroundObservationDto]

    @model_validator(mode="after")
    def validate_projection(self) -> "NetworkProjectionDto":
        node_ids = [node.id for node in self.nodes]
        if any(not item for item in node_ids) or len(node_ids) != len(set(node_ids)):
            raise ValueError("network node identifiers must be non-empty and unique")
        by_id = {node.id: node for node in self.nodes}
        for edge in self.edges:
            if edge.a == edge.b:
                raise ValueError("network edges must connect distinct nodes")
            if edge.a not in by_id or edge.b not in by_id:
                raise ValueError("network edge endpoint does not exist")
        observations = {
            (item.ground_id, item.satellite_id, item.elevation_deg, item.distance_km)
            for item in self.ground_observations
        }
        for item in (*self.ground_observations, *self.ground_visibility):
            ground = by_id.get(item.ground_id)
            satellite = by_id.get(item.satellite_id)
            if ground is None or ground.kind not in ("client", "gateway"):
                raise ValueError("ground observation must reference a ground node")
            if satellite is None or satellite.kind != "satellite":
                raise ValueError("ground observation must reference a satellite")
        for item in self.ground_visibility:
            key = (item.ground_id, item.satellite_id, item.elevation_deg, item.distance_km)
            if key not in observations:
                raise ValueError("visible ground/satellite pair must also be a raw observation")
        return self


class RouteSegmentDto(StrictModel):
    from_id: str
    to_id: str
    kind: Literal["inter_satellite", "ground_satellite"]
    distance_km: float = Field(ge=0.0)
    elevation_deg: float | None = Field(default=None, ge=-90.0, le=90.0)


class RouteMetricsDto(StrictModel):
    hop_count: int = Field(ge=0)
    total_distance_km: float = Field(ge=0.0)
    objective_value: float


class RouteDto(StrictModel):
    strategy_id: str
    source_id: str
    target_id: str
    node_ids: list[str]
    segments: list[RouteSegmentDto]
    metrics: RouteMetricsDto

    @model_validator(mode="after")
    def validate_route(self) -> "RouteDto":
        if not self.strategy_id or not self.source_id or not self.target_id:
            raise ValueError("route identifiers must not be empty")
        if len(self.node_ids) < 2:
            raise ValueError("route must contain at least source and target")
        if self.node_ids[0] != self.source_id or self.node_ids[-1] != self.target_id:
            raise ValueError("route endpoints must match node_ids")
        if len(self.segments) != len(self.node_ids) - 1:
            raise ValueError("route segments must correspond one-to-one with node transitions")
        for index, segment in enumerate(self.segments):
            if segment.from_id != self.node_ids[index] or segment.to_id != self.node_ids[index + 1]:
                raise ValueError("route segment chain must match node_ids")
        if self.metrics.hop_count != len(self.segments):
            raise ValueError("route hop_count must equal the number of segments")
        total = sum(segment.distance_km for segment in self.segments)
        if not math.isclose(total, self.metrics.total_distance_km, rel_tol=1e-12, abs_tol=1e-9):
            raise ValueError("route total_distance_km must equal the sum of segment distances")
        return self


class CoverageStateDto(StrictModel):
    visible_satellites: list[str]
    has_visibility: bool

    @model_validator(mode="after")
    def validate_visibility(self) -> "CoverageStateDto":
        if self.has_visibility != bool(self.visible_satellites):
            raise ValueError("has_visibility must agree with visible_satellites")
        return self


class ServiceStateDto(StrictModel):
    reachable: bool
    valid_ingress_satellites: list[str]
    reachable_gateways: list[str]
    no_route_reason: Literal[
        "no_visible_satellite",
        "isl_disconnected",
        "no_gateway_contact",
        "gateway_unavailable",
    ] | None

    @model_validator(mode="after")
    def validate_service(self) -> "ServiceStateDto":
        if self.reachable and self.no_route_reason is not None:
            raise ValueError("reachable service cannot have a no-route reason")
        if not self.reachable and self.no_route_reason is None:
            raise ValueError("unreachable service must have a no-route reason")
        if self.reachable != bool(self.reachable_gateways):
            raise ValueError("reachable must agree with reachable_gateways")
        return self


class RoutingStateDto(StrictModel):
    selected_route: RouteDto | None
    routes: list[RouteDto]

    @model_validator(mode="after")
    def validate_routing(self) -> "RoutingStateDto":
        ids = [route.strategy_id for route in self.routes]
        if len(ids) != len(set(ids)):
            raise ValueError("at most one route per strategy is allowed")
        if self.selected_route is not None and self.selected_route not in self.routes:
            raise ValueError("selected_route must also be present in routes")
        return self


class SatelliteConnectivityDto(StrictModel):
    node_disjoint_path_count: int = Field(ge=0)
    minimum_cut: list[str]


class ResilienceStateDto(StrictModel):
    satellite_connectivity: SatelliteConnectivityDto
    critical_satellites: list[str]
    survives_any_single_satellite_failure: bool


class ClientSnapshotAnalysisDto(StrictModel):
    client_id: str
    coverage: CoverageStateDto
    service: ServiceStateDto
    routing: RoutingStateDto
    resilience: ResilienceStateDto | None


class RouteFailureDeltaDto(StrictModel):
    strategy_id: str
    before: RouteDto | None
    after: RouteDto | None
    route_lost: bool
    path_changed: bool
    objective_increase: float | None

    @model_validator(mode="after")
    def validate_delta(self) -> "RouteFailureDeltaDto":
        expected_lost = self.before is not None and self.after is None
        if self.route_lost != expected_lost:
            raise ValueError("route_lost is inconsistent with before/after")
        if self.before is None or self.after is None:
            expected_changed = self.before != self.after
            expected_increase = None
        else:
            expected_changed = self.before.node_ids != self.after.node_ids
            expected_increase = self.after.metrics.objective_value - self.before.metrics.objective_value
        if self.path_changed != expected_changed:
            raise ValueError("path_changed is inconsistent with before/after")
        if expected_increase is None:
            if self.objective_increase is not None:
                raise ValueError("objective_increase requires both routes")
        elif self.objective_increase is None or not math.isclose(
            self.objective_increase,
            expected_increase,
            rel_tol=1e-12,
            abs_tol=1e-9,
        ):
            raise ValueError("objective_increase is inconsistent with before/after")
        return self


class ClientFailureImpactDto(StrictModel):
    client_id: str
    service_lost: bool
    geometric_visibility_lost: bool
    visible_satellites_lost: int = Field(ge=0)
    valid_ingress_lost: int = Field(ge=0)
    reachable_gateways_lost: int = Field(ge=0)
    satellite_connectivity_loss: int | None = Field(default=None, ge=0)
    route_deltas: list[RouteFailureDeltaDto]


class SatelliteFailureImpactSummaryDto(StrictModel):
    lost_clients: list[str]
    clients_losing_geometric_visibility: list[str]
    total_visible_satellites_lost: int = Field(ge=0)
    total_valid_ingress_lost: int = Field(ge=0)
    total_reachable_gateways_lost: int = Field(ge=0)
    total_connectivity_loss: int = Field(ge=0)
    routes_lost: int = Field(ge=0)
    routes_changed: int = Field(ge=0)


class SatelliteFailureImpactDto(StrictModel):
    satellite_id: str
    clients: list[ClientFailureImpactDto]
    summary: SatelliteFailureImpactSummaryDto

    @model_validator(mode="after")
    def validate_summary(self) -> "SatelliteFailureImpactDto":
        expected = SatelliteFailureImpactSummaryDto(
            lost_clients=[item.client_id for item in self.clients if item.service_lost],
            clients_losing_geometric_visibility=[
                item.client_id for item in self.clients if item.geometric_visibility_lost
            ],
            total_visible_satellites_lost=sum(item.visible_satellites_lost for item in self.clients),
            total_valid_ingress_lost=sum(item.valid_ingress_lost for item in self.clients),
            total_reachable_gateways_lost=sum(item.reachable_gateways_lost for item in self.clients),
            total_connectivity_loss=sum(item.satellite_connectivity_loss or 0 for item in self.clients),
            routes_lost=sum(
                int(delta.route_lost)
                for item in self.clients
                for delta in item.route_deltas
            ),
            routes_changed=sum(
                int(delta.path_changed)
                for item in self.clients
                for delta in item.route_deltas
            ),
        )
        if self.summary != expected:
            raise ValueError("satellite failure impact summary is inconsistent with client impacts")
        return self


class RankedSatelliteImpactDto(StrictModel):
    rank: int = Field(ge=1)
    satellite_id: str


class NetworkSummaryDto(StrictModel):
    node_count: int = Field(ge=0)
    link_count: int = Field(ge=0)
    available_satellites: int = Field(ge=0)
    available_gateways: int = Field(ge=0)
    client_count: int = Field(ge=0)
    visible_client_count: int = Field(ge=0)
    reachable_client_count: int = Field(ge=0)
    all_clients_reachable: bool

    @model_validator(mode="after")
    def validate_summary(self) -> "NetworkSummaryDto":
        if self.visible_client_count > self.client_count or self.reachable_client_count > self.client_count:
            raise ValueError("client counters cannot exceed client_count")
        expected = self.client_count > 0 and self.reachable_client_count == self.client_count
        if self.all_clients_reachable != expected:
            raise ValueError("all_clients_reachable is inconsistent with client counters")
        return self


class StaticAnalysisDto(StrictModel):
    schema_version: Literal["static-analysis-1.0"] = "static-analysis-1.0"
    summary: NetworkSummaryDto
    clients: list[ClientSnapshotAnalysisDto]
    satellite_failure_impacts: list[SatelliteFailureImpactDto]
    satellite_criticality_ranking: list[RankedSatelliteImpactDto]

    @model_validator(mode="after")
    def validate_analysis(self) -> "StaticAnalysisDto":
        client_ids = [client.client_id for client in self.clients]
        if len(client_ids) != len(set(client_ids)):
            raise ValueError("client analyses must have unique client_id values")
        if self.summary.client_count != len(self.clients):
            raise ValueError("summary.client_count must equal number of client analyses")
        impacts = {impact.satellite_id: impact for impact in self.satellite_failure_impacts}
        if len(impacts) != len(self.satellite_failure_impacts):
            raise ValueError("satellite failure impacts must have unique satellite_id values")
        ranks = [item.rank for item in self.satellite_criticality_ranking]
        if ranks and ranks != list(range(1, len(ranks) + 1)):
            raise ValueError("criticality ranks must be consecutive starting from one")
        ranked_ids = [item.satellite_id for item in self.satellite_criticality_ranking]
        if len(ranked_ids) != len(set(ranked_ids)):
            raise ValueError("criticality ranking must not repeat satellites")
        if any(satellite_id not in impacts for satellite_id in ranked_ids):
            raise ValueError("criticality ranking must reference exported failure impacts")
        return self
