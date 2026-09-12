from __future__ import annotations

from dataclasses import dataclass

from .contracts import CriticalityRankingPolicy, RouteCostPolicy
from .policies import DistanceCost, HopCountCost, LexicographicCriticalityRanking


@dataclass(frozen=True, slots=True)
class RouteStrategy:
    id: str
    cost: RouteCostPolicy


@dataclass(frozen=True, slots=True)
class StaticAnalysisPlan:
    route_strategies: tuple[RouteStrategy, ...]
    primary_route_strategy_id: str
    compute_resilience: bool = True
    compute_failure_impacts: bool = True
    criticality_ranking: CriticalityRankingPolicy | None = None

    @classmethod
    def reference_case(cls) -> "StaticAnalysisPlan":
        return cls(
            route_strategies=(
                RouteStrategy("minimum_hops", HopCountCost()),
                RouteStrategy("minimum_distance", DistanceCost()),
            ),
            primary_route_strategy_id="minimum_hops",
            compute_resilience=True,
            compute_failure_impacts=True,
            criticality_ranking=LexicographicCriticalityRanking(),
        )
