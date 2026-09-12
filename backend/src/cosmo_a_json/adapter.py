from __future__ import annotations

from dataclasses import dataclass

from json_component import VersionedObjectCodec
from json_component.pydantic_adapter import PydanticCodec
from spatial3d import (
    BodyConstants,
    GatewayOutage,
    GroundRole,
    GroundSite,
    Interval,
    LinkLimits,
    OrbitEnvironment,
    OrbitalPlane,
    Satellite,
    SatelliteOutage,
    SpatialSpecification,
)

from .dto import ScenarioDto

CASE_BODY = BodyConstants(
    radius_km=6371.0,
    gravitational_parameter_km3_s2=398600.435507,
    rotation_period_s=86164.09054,
)


@dataclass(frozen=True, slots=True)
class ScenarioCalculationSettings:
    horizon_s: int
    step_s: int
    target_availability: float


@dataclass(frozen=True, slots=True)
class AdaptedScenario:
    scenario_id: str
    title: str
    spatial: SpatialSpecification
    calculation: ScenarioCalculationSettings


def scenario_codec() -> VersionedObjectCodec[ScenarioDto]:
    return VersionedObjectCodec(
        payload=PydanticCodec.for_type(ScenarioDto),
        current_version="cosmo-A-1.0",
    )


def adapt_scenario(dto: ScenarioDto) -> AdaptedScenario:
    e = dto.environment
    d = dto.design
    spatial = SpatialSpecification(
        body=CASE_BODY,
        orbit=OrbitEnvironment(e.altitude_km, e.inclination_deg, e.earth_angle0_deg),
        links=LinkLimits(e.min_elevation_deg, e.isl_range_km),
        launch_stage=d.launch_stage,
        planes=tuple(OrbitalPlane(item.id, item.raan_deg, item.phase_deg) for item in d.planes),
        satellites=tuple(
            Satellite(item.id, item.plane_id, item.slot_deg, item.launch_batch)
            for item in d.satellites
        ),
        ground_sites=tuple(
            GroundSite(
                item.id,
                item.name,
                GroundRole(item.role),
                item.lat_deg,
                item.lon_deg,
            )
            for item in dto.ground_sites
        ),
        satellite_outages=tuple(
            SatelliteOutage(item.satellite_id, Interval(item.start_s, item.end_s))
            for item in dto.failures
        ),
        gateway_outages=tuple(
            GatewayOutage(item.gateway_id, Interval(item.start_s, item.end_s))
            for item in dto.gateway_outages
        ),
    )
    return AdaptedScenario(
        scenario_id=dto.meta.id,
        title=dto.meta.title,
        spatial=spatial,
        calculation=ScenarioCalculationSettings(e.horizon_s, e.step_s, e.target_availability),
    )
