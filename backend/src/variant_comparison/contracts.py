from __future__ import annotations

from typing import Protocol

from static_model import Route


class RouteComparisonPolicy(Protocol):
    def same_route(self, left: Route, right: Route) -> bool: ...
