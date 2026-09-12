from __future__ import annotations

from typing import Protocol

from spatial3d import SpatialSnapshot
from static_model import Route, StaticNetwork

from .types import SatelliteTemporalCriticality


class StaticNetworkAdapter(Protocol):
    def from_snapshot(self, snapshot: SpatialSnapshot) -> StaticNetwork: ...


class RouteIdentityPolicy(Protocol):
    def same_route(self, left: Route, right: Route) -> bool: ...


class DynamicCriticalityRankingPolicy(Protocol):
    def rank(
        self,
        criticalities: tuple[SatelliteTemporalCriticality, ...],
    ) -> tuple[SatelliteTemporalCriticality, ...]: ...
