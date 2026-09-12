from __future__ import annotations

from dataclasses import dataclass

from .contracts import DynamicCriticalityRankingPolicy, RouteIdentityPolicy, StaticNetworkAdapter
from .policies import (
    LexicographicDynamicCriticalityRanking,
    NodePathRouteIdentity,
    SpatialStaticNetworkAdapter,
)


@dataclass(frozen=True, slots=True)
class DynamicComponents:
    network_adapter: StaticNetworkAdapter
    route_identity: RouteIdentityPolicy
    criticality_ranking: DynamicCriticalityRankingPolicy

    @classmethod
    def reference_case(cls) -> "DynamicComponents":
        return cls(
            network_adapter=SpatialStaticNetworkAdapter(),
            route_identity=NodePathRouteIdentity(),
            criticality_ranking=LexicographicDynamicCriticalityRanking(),
        )
