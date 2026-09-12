from __future__ import annotations

from dataclasses import dataclass

from .specification import GroundRole, GroundSite, Satellite, SpatialSpecification


@dataclass(frozen=True, slots=True)
class DeploymentAndOutageSatelliteAvailability:
    def active(self, spec: SpatialSpecification, satellite: Satellite, t_s: float) -> bool:
        if satellite.launch_batch > spec.launch_stage:
            return False
        return not any(
            outage.satellite_id == satellite.id and outage.interval.contains(t_s)
            for outage in spec.satellite_outages
        )


@dataclass(frozen=True, slots=True)
class GatewayOutageGroundAvailability:
    def available(self, spec: SpatialSpecification, site: GroundSite, t_s: float) -> bool:
        if site.role != GroundRole.GATEWAY:
            return True
        return not any(
            outage.gateway_id == site.id and outage.interval.contains(t_s)
            for outage in spec.gateway_outages
        )
