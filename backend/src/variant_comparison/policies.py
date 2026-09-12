from __future__ import annotations

from dataclasses import dataclass

from static_model import Route


@dataclass(frozen=True, slots=True)
class NodePathRouteComparison:
    def same_route(self, left: Route, right: Route) -> bool:
        return left.node_ids == right.node_ids
