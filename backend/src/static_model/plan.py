from __future__ import annotations

from dataclasses import dataclass

from .contracts import CriticalityRankingPolicy, RoutingStrategy
from .policies import LexicographicCriticalityRanking
from .routing import ResilientThenDistanceRouting, minimum_distance_routing, minimum_hops_routing


@dataclass(frozen=True, slots=True)
class StaticAnalysisPlan:
    route_strategies: tuple[RoutingStrategy, ...]
    primary_route_strategy_id: str
    compute_resilience: bool = True
    compute_failure_impacts: bool = True
    criticality_ranking: CriticalityRankingPolicy | None = None

    @classmethod
    def reference_case(cls) -> "StaticAnalysisPlan":
        return cls(
            route_strategies=(
                minimum_hops_routing(),
                minimum_distance_routing(),
            ),
            primary_route_strategy_id="minimum_hops",
            compute_resilience=True,
            compute_failure_impacts=True,
            criticality_ranking=LexicographicCriticalityRanking(),
        )

    @classmethod
    def reference_case_with_resilient_routing(cls) -> "StaticAnalysisPlan":
        return cls(
            route_strategies=(
                minimum_hops_routing(),
                minimum_distance_routing(),
                ResilientThenDistanceRouting(),
            ),
            primary_route_strategy_id="resilient_distance",
            compute_resilience=True,
            compute_failure_impacts=True,
            criticality_ranking=LexicographicCriticalityRanking(),
        )

