from __future__ import annotations

from dataclasses import dataclass

from json_component import VersionedObjectCodec
from json_component.pydantic_adapter import PydanticCodec
from spatial3d import (
    BodyConstants,
    CircularOrbitAssignment,
    CircularOrbitConfiguration,
    CircularOrbitEnvironment,
    CircularOrbitTrajectory,
    GatewayOutage,
    GroundRole,
    GroundSite,
    Interval,
    LinkLimits,
    OrbitalPlane,
    Satellite,
    SatelliteOutage,
    SpatialSpecification,
)

from .dto import ScenarioDto

CASE_BODY = BodyConstants(radius_km=6371.0)
CASE_GRAVITATIONAL_PARAMETER_KM3_S2 = 398600.435507
CASE_ROTATION_PERIOD_S = 86164.09054


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
    trajectory: CircularOrbitTrajectory
    calculation: ScenarioCalculationSettings


def scenario_codec() -> VersionedObjectCodec[ScenarioDto]:
    return VersionedObjectCodec(
        payload=PydanticCodec.for_type(ScenarioDto),
        current_version="cosmo-A-1.0",
    )


def adapt_scenario(dto: ScenarioDto) -> AdaptedScenario:
    """Map the exact cosmo-A persistence schema to generic spatial data + trajectory.

    The circular-orbit fields stay in this adapter/trajectory boundary rather than
    becoming mandatory fields of ``SpatialSpecification``.  This is what lets a
    different source format supply a different trajectory provider without changing
    the spatial core.
    """

    e = dto.environment
    d = dto.design
    spatial = SpatialSpecification(
        body=CASE_BODY,
        links=LinkLimits(e.min_elevation_deg, e.isl_range_km),
        launch_stage=d.launch_stage,
        satellites=tuple(Satellite(item.id, item.launch_batch) for item in d.satellites),
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
    trajectory = CircularOrbitTrajectory(
        CASE_BODY,
        CircularOrbitConfiguration(
            environment=CircularOrbitEnvironment(
                altitude_km=e.altitude_km,
                inclination_deg=e.inclination_deg,
                earth_angle0_deg=e.earth_angle0_deg,
                gravitational_parameter_km3_s2=CASE_GRAVITATIONAL_PARAMETER_KM3_S2,
                rotation_period_s=CASE_ROTATION_PERIOD_S,
            ),
            planes=tuple(OrbitalPlane(item.id, item.raan_deg, item.phase_deg) for item in d.planes),
            assignments=tuple(
                CircularOrbitAssignment(item.id, item.plane_id, item.slot_deg)
                for item in d.satellites
            ),
        ),
    )
    return AdaptedScenario(
        scenario_id=dto.meta.id,
        title=dto.meta.title,
        spatial=spatial,
        trajectory=trajectory,
        calculation=ScenarioCalculationSettings(e.horizon_s, e.step_s, e.target_availability),
    )
