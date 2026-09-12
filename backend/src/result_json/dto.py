from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, allow_inf_nan=False)


class RouteRecordDto(StrictModel):
    t_s: int | float
    client_id: str
    path: list[str]

    @model_validator(mode="after")
    def validate_route_record(self) -> "RouteRecordDto":
        if isinstance(self.t_s, bool) or not math.isfinite(float(self.t_s)):
            raise ValueError("t_s must be finite")
        if not self.client_id:
            raise ValueError("client_id must not be empty")
        if self.path and self.path[0] != self.client_id:
            raise ValueError("non-empty path must start with client_id")
        if any(not node_id for node_id in self.path):
            raise ValueError("path node identifiers must not be empty")
        return self


class ResultDocumentDto(StrictModel):
    schema_version: Literal["cosmo-A-result-1.0"] = "cosmo-A-result-1.0"
    effective_scenario: dict[str, Any]
    routes: list[RouteRecordDto]

    @model_validator(mode="after")
    def validate_case_result_contract(self) -> "ResultDocumentDto":
        keys = [(float(record.t_s), record.client_id) for record in self.routes]
        if len(keys) != len(set(keys)):
            raise ValueError("routes must contain exactly one record per (t_s, client_id) pair")

        scenario = self.effective_scenario
        if scenario.get("schema_version") != "cosmo-A-1.0":
            raise ValueError("effective_scenario must use schema_version cosmo-A-1.0")
        environment = scenario.get("environment")
        ground_sites = scenario.get("ground_sites")
        design = scenario.get("design")
        if not isinstance(environment, dict) or not isinstance(ground_sites, list) or not isinstance(design, dict):
            raise ValueError("effective_scenario must contain environment, design and ground_sites")

        horizon_s = environment.get("horizon_s")
        step_s = environment.get("step_s")
        if (
            isinstance(horizon_s, bool)
            or isinstance(step_s, bool)
            or not isinstance(horizon_s, int)
            or not isinstance(step_s, int)
            or horizon_s <= 0
            or step_s <= 0
            or horizon_s % step_s != 0
        ):
            raise ValueError("effective_scenario contains an invalid time grid")

        clients = {
            site.get("id")
            for site in ground_sites
            if isinstance(site, dict) and site.get("role") == "client" and isinstance(site.get("id"), str)
        }
        gateways = {
            site.get("id")
            for site in ground_sites
            if isinstance(site, dict) and site.get("role") == "gateway" and isinstance(site.get("id"), str)
        }
        satellites_raw = design.get("satellites")
        satellites = {
            sat.get("id")
            for sat in satellites_raw
            if isinstance(sat, dict) and isinstance(sat.get("id"), str)
        } if isinstance(satellites_raw, list) else set()
        if not clients or not gateways:
            raise ValueError("effective_scenario must contain at least one client and gateway")

        expected = {
            (float(t_s), client_id)
            for t_s in range(0, horizon_s, step_s)
            for client_id in clients
        }
        if set(keys) != expected:
            raise ValueError("routes must contain exactly one record for every time-grid/client pair")

        for record in self.routes:
            if record.client_id not in clients:
                raise ValueError(f"unknown client in route record: {record.client_id}")
            if not record.path:
                continue
            if len(record.path) < 3:
                raise ValueError("non-empty route must contain client, at least one satellite and gateway")
            if record.path[-1] not in gateways:
                raise ValueError("non-empty route must end at a gateway")
            if any(node_id not in satellites for node_id in record.path[1:-1]):
                raise ValueError("route intermediate nodes must be satellites")
        return self
