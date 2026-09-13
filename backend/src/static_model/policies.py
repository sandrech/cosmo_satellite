from __future__ import annotations

from dataclasses import dataclass

from .analysis import NoRouteReason, SatelliteFailureImpact
from .contracts import CoveragePolicy, ReachabilityPolicy, TraversalRole
from .types import Link, LinkKind, Node, NodeKind, StaticNetwork


@dataclass(frozen=True, slots=True)
class ObservedActiveSatelliteCoverage:
    """Geometric visibility of active satellites recorded in the snapshot."""

    def visible_satellites(
        self,
        network: StaticNetwork,
        ground_id: str,
        excluded_nodes: frozenset[str] = frozenset(),
    ) -> tuple[str, ...]:
        nodes = network._nodes_by_id
        visible = {
            observation.satellite_id
            for observation in network._ground_visibility_by_ground.get(ground_id, ())
            if observation.satellite_id not in excluded_nodes
            and observation.satellite_id in nodes
            and nodes[observation.satellite_id].kind == NodeKind.SATELLITE
            and nodes[observation.satellite_id].available
        }
        return tuple(sorted(visible))


@dataclass(frozen=True, slots=True)
class ClientToGatewayReachability:
    """Case semantics: clients/gateways are endpoints, satellites are the only relays."""

    def is_source(self, node: Node) -> bool:
        return node.kind == NodeKind.CLIENT

    def role(self, node: Node, source_id: str) -> TraversalRole:
        if not node.available:
            return TraversalRole.BLOCKED
        if node.id == source_id:
            return TraversalRole.SOURCE if node.kind == NodeKind.CLIENT else TraversalRole.BLOCKED
        if node.kind == NodeKind.SATELLITE:
            return TraversalRole.TRANSIT
        if node.kind == NodeKind.GATEWAY:
            return TraversalRole.TARGET
        return TraversalRole.BLOCKED

    def allows_link(self, link: Link) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class CaseNoRouteReason:
    """Classify the four failure reasons required by the task statement."""

    def classify(
        self,
        network: StaticNetwork,
        source_id: str,
        coverage: CoveragePolicy,
        reachability: ReachabilityPolicy,
        excluded_nodes: frozenset[str] = frozenset(),
    ) -> NoRouteReason:
        if not coverage.visible_satellites(network, source_id, excluded_nodes):
            return NoRouteReason.NO_VISIBLE_SATELLITE

        gateways = [
            node
            for node in network.nodes
            if node.kind == NodeKind.GATEWAY and node.id not in excluded_nodes
        ]
        available_gateways = [node for node in gateways if node.available]
        if not available_gateways:
            return NoRouteReason.GATEWAY_UNAVAILABLE

        available_gateway_ids = {node.id for node in available_gateways}
        has_available_gateway_contact = any(
            link.kind == LinkKind.GROUND_SATELLITE
            and link.a not in excluded_nodes
            and link.b not in excluded_nodes
            and (link.a in available_gateway_ids or link.b in available_gateway_ids)
            and reachability.allows_link(link)
            for link in network.links
        )
        if not has_available_gateway_contact:
            return NoRouteReason.NO_GATEWAY_CONTACT

        return NoRouteReason.ISL_DISCONNECTED


@dataclass(frozen=True, slots=True)
class HopCountCost:
    def cost(self, link: Link) -> float:
        return 1.0


@dataclass(frozen=True, slots=True)
class DistanceCost:
    def cost(self, link: Link) -> float:
        return link.distance_km


@dataclass(frozen=True, slots=True)
class AvailableSatelliteFailureDomain:
    def candidates(self, network: StaticNetwork) -> tuple[str, ...]:
        return network._available_satellite_ids


@dataclass(frozen=True, slots=True)
class LexicographicCriticalityRanking:
    """Explainable ordering; no opaque weighted scalar is invented.

    Service loss dominates geometric coverage loss; then usable ingress,
    gateway diversity, satellite connectivity and route degradation.
    """

    def rank(self, impacts: tuple[SatelliteFailureImpact, ...]) -> tuple[SatelliteFailureImpact, ...]:
        def key(impact: SatelliteFailureImpact) -> tuple[object, ...]:
            # Ranking is a hot path during N-1 analysis.  Compute the complete
            # lexicographic vector in one traversal instead of materializing
            # property tuples and rescanning clients/routes for every coordinate.
            lost_clients = 0
            geometric_visibility_losses = 0
            valid_ingress_lost = 0
            reachable_gateways_lost = 0
            connectivity_loss = 0
            routes_lost = 0
            routes_changed = 0
            for client in impact.clients:
                lost_clients += int(client.service_lost)
                geometric_visibility_losses += int(client.geometric_visibility_lost)
                valid_ingress_lost += client.valid_ingress_lost
                reachable_gateways_lost += client.reachable_gateways_lost
                connectivity_loss += client.satellite_connectivity_loss or 0
                for delta in client.route_deltas:
                    routes_lost += int(delta.route_lost)
                    routes_changed += int(delta.path_changed)
            return (
                -lost_clients,
                -geometric_visibility_losses,
                -valid_ingress_lost,
                -reachable_gateways_lost,
                -connectivity_loss,
                -routes_lost,
                -routes_changed,
                impact.satellite_id,
            )

        return tuple(sorted(impacts, key=key))
