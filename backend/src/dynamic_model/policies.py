from __future__ import annotations

from dataclasses import dataclass

from spatial3d import SpatialSnapshot
from spatial_static_adapter import from_spatial_snapshot
from static_model import Route, StaticNetwork

from .types import SatelliteTemporalCriticality


@dataclass(frozen=True, slots=True)
class SpatialStaticNetworkAdapter:
    def from_snapshot(self, snapshot: SpatialSnapshot) -> StaticNetwork:
        return from_spatial_snapshot(snapshot)


@dataclass(frozen=True, slots=True)
class NodePathRouteIdentity:
    """A route changes when its ordered node path changes.

    Link distances may vary continuously while the logical route remains the same.
    """

    def same_route(self, left: Route, right: Route) -> bool:
        return left.node_ids == right.node_ids


@dataclass(frozen=True, slots=True)
class LexicographicDynamicCriticalityRanking:
    """Explainable period-wide satellite criticality ordering.

    The ordering follows the task objective rather than graph centrality:
    causing clients to fall below the target dominates additional outage time,
    then availability loss, maximum-outage growth, loss of redundancy and
    route degradation.  Raw impact vectors remain available independently of
    this policy.
    """

    def rank(
        self,
        criticalities: tuple[SatelliteTemporalCriticality, ...],
    ) -> tuple[SatelliteTemporalCriticality, ...]:
        def key(item: SatelliteTemporalCriticality) -> tuple[object, ...]:
            summary = item.summary
            return (
                -len(summary.clients_falling_below_target),
                -summary.total_additional_outage_s,
                -summary.maximum_client_availability_loss,
                -summary.maximum_outage_increase_s,
                -summary.geometric_visibility_loss_s,
                -summary.valid_ingress_loss_satellite_s,
                -summary.reachable_gateway_loss_gateway_s,
                -summary.connectivity_loss_path_s,
                -summary.route_lost_samples,
                -summary.route_changed_samples,
                -summary.route_switch_increase,
                item.satellite_id,
            )

        return tuple(sorted(criticalities, key=key))
