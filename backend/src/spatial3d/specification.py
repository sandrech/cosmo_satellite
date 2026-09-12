from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math

from .result import Err, Ok, Result, SpatialProblem, SpatialProblemCode, SpatialProblems


class GroundRole(StrEnum):
    CLIENT = "client"
    GATEWAY = "gateway"


@dataclass(frozen=True, slots=True)
class BodyConstants:
    radius_km: float
    gravitational_parameter_km3_s2: float
    rotation_period_s: float


@dataclass(frozen=True, slots=True)
class OrbitEnvironment:
    altitude_km: float
    inclination_deg: float
    earth_angle0_deg: float


@dataclass(frozen=True, slots=True)
class LinkLimits:
    min_elevation_deg: float
    isl_range_km: float


@dataclass(frozen=True, slots=True)
class OrbitalPlane:
    id: str
    raan_deg: float
    phase_deg: float


@dataclass(frozen=True, slots=True)
class Satellite:
    id: str
    plane_id: str
    slot_deg: float
    launch_batch: int


@dataclass(frozen=True, slots=True)
class GroundSite:
    id: str
    name: str
    role: GroundRole
    lat_deg: float
    lon_deg: float


@dataclass(frozen=True, slots=True)
class Interval:
    start_s: float
    end_s: float

    def contains(self, t_s: float) -> bool:
        return self.start_s <= t_s < self.end_s


@dataclass(frozen=True, slots=True)
class SatelliteOutage:
    satellite_id: str
    interval: Interval


@dataclass(frozen=True, slots=True)
class GatewayOutage:
    gateway_id: str
    interval: Interval


@dataclass(frozen=True, slots=True)
class SpatialSpecification:
    body: BodyConstants
    orbit: OrbitEnvironment
    links: LinkLimits
    launch_stage: int
    planes: tuple[OrbitalPlane, ...]
    satellites: tuple[Satellite, ...]
    ground_sites: tuple[GroundSite, ...]
    satellite_outages: tuple[SatelliteOutage, ...] = ()
    gateway_outages: tuple[GatewayOutage, ...] = ()


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_specification(spec: SpatialSpecification) -> Result[None, SpatialProblems]:
    problems: list[SpatialProblem] = []

    numbers = (
        (spec.body.radius_km, ("body", "radius_km")),
        (spec.body.gravitational_parameter_km3_s2, ("body", "gravitational_parameter_km3_s2")),
        (spec.body.rotation_period_s, ("body", "rotation_period_s")),
        (spec.orbit.altitude_km, ("orbit", "altitude_km")),
        (spec.orbit.inclination_deg, ("orbit", "inclination_deg")),
        (spec.orbit.earth_angle0_deg, ("orbit", "earth_angle0_deg")),
        (spec.links.min_elevation_deg, ("links", "min_elevation_deg")),
        (spec.links.isl_range_km, ("links", "isl_range_km")),
    )
    for value, path in numbers:
        if not _finite(value):
            problems.append(SpatialProblem(SpatialProblemCode.INVALID_NUMBER, "value must be finite", path))

    if _finite(spec.body.radius_km) and spec.body.radius_km <= 0:
        problems.append(SpatialProblem(SpatialProblemCode.INVALID_RANGE, "body radius must be positive", ("body", "radius_km")))
    if _finite(spec.body.gravitational_parameter_km3_s2) and spec.body.gravitational_parameter_km3_s2 <= 0:
        problems.append(SpatialProblem(SpatialProblemCode.INVALID_RANGE, "gravitational parameter must be positive", ("body", "gravitational_parameter_km3_s2")))
    if _finite(spec.body.rotation_period_s) and spec.body.rotation_period_s <= 0:
        problems.append(SpatialProblem(SpatialProblemCode.INVALID_RANGE, "rotation period must be positive", ("body", "rotation_period_s")))
    if _finite(spec.orbit.altitude_km) and spec.orbit.altitude_km <= 0:
        problems.append(SpatialProblem(SpatialProblemCode.INVALID_RANGE, "altitude must be positive", ("orbit", "altitude_km")))
    if _finite(spec.links.isl_range_km) and spec.links.isl_range_km <= 0:
        problems.append(SpatialProblem(SpatialProblemCode.INVALID_RANGE, "ISL range must be positive", ("links", "isl_range_km")))
    if _finite(spec.links.min_elevation_deg) and not (-90 <= spec.links.min_elevation_deg <= 90):
        problems.append(SpatialProblem(SpatialProblemCode.INVALID_RANGE, "minimum elevation must be in [-90, 90]", ("links", "min_elevation_deg")))
    if not isinstance(spec.launch_stage, int) or isinstance(spec.launch_stage, bool) or spec.launch_stage < 0:
        problems.append(SpatialProblem(SpatialProblemCode.INVALID_RANGE, "launch stage must be a non-negative integer", ("launch_stage",)))

    plane_ids = [plane.id for plane in spec.planes]
    satellite_ids = [sat.id for sat in spec.satellites]
    ground_ids = [site.id for site in spec.ground_sites]
    for label, ids, path in (
        ("plane", plane_ids, ("planes",)),
        ("satellite", satellite_ids, ("satellites",)),
        ("ground", ground_ids, ("ground_sites",)),
    ):
        if len(ids) != len(set(ids)):
            problems.append(SpatialProblem(SpatialProblemCode.DUPLICATE_ID, f"duplicate {label} id", path))
    overlap = set(satellite_ids) & set(ground_ids)
    if overlap:
        problems.append(SpatialProblem(SpatialProblemCode.DUPLICATE_ID, "satellite and ground node ids must be disjoint", ("ground_sites",)))

    known_planes = set(plane_ids)
    for index, satellite in enumerate(spec.satellites):
        if satellite.plane_id not in known_planes:
            problems.append(SpatialProblem(SpatialProblemCode.UNKNOWN_PLANE, f"unknown plane {satellite.plane_id!r}", ("satellites", index, "plane_id")))
        if not _finite(satellite.slot_deg):
            problems.append(SpatialProblem(SpatialProblemCode.INVALID_NUMBER, "slot angle must be finite", ("satellites", index, "slot_deg")))
        if not isinstance(satellite.launch_batch, int) or isinstance(satellite.launch_batch, bool) or satellite.launch_batch < 0:
            problems.append(SpatialProblem(SpatialProblemCode.INVALID_RANGE, "launch batch must be a non-negative integer", ("satellites", index, "launch_batch")))

    for index, plane in enumerate(spec.planes):
        for field_name, value in (("raan_deg", plane.raan_deg), ("phase_deg", plane.phase_deg)):
            if not _finite(value):
                problems.append(SpatialProblem(SpatialProblemCode.INVALID_NUMBER, f"{field_name} must be finite", ("planes", index, field_name)))

    for index, site in enumerate(spec.ground_sites):
        if not _finite(site.lat_deg) or not -90 <= site.lat_deg <= 90:
            problems.append(SpatialProblem(SpatialProblemCode.INVALID_RANGE, "latitude must be finite and in [-90, 90]", ("ground_sites", index, "lat_deg")))
        if not _finite(site.lon_deg) or not -180 <= site.lon_deg <= 180:
            problems.append(SpatialProblem(SpatialProblemCode.INVALID_RANGE, "longitude must be finite and in [-180, 180]", ("ground_sites", index, "lon_deg")))

    satellite_set = set(satellite_ids)
    gateway_set = {site.id for site in spec.ground_sites if site.role == GroundRole.GATEWAY}
    for index, outage in enumerate(spec.satellite_outages):
        if outage.satellite_id not in satellite_set:
            problems.append(SpatialProblem(SpatialProblemCode.INVALID_REFERENCE, "outage references unknown satellite", ("satellite_outages", index, "satellite_id")))
        if not _valid_interval(outage.interval):
            problems.append(SpatialProblem(SpatialProblemCode.INVALID_INTERVAL, "outage interval must be finite, non-negative, and non-empty", ("satellite_outages", index)))
    for index, outage in enumerate(spec.gateway_outages):
        if outage.gateway_id not in gateway_set:
            problems.append(SpatialProblem(SpatialProblemCode.INVALID_REFERENCE, "outage references unknown gateway", ("gateway_outages", index, "gateway_id")))
        if not _valid_interval(outage.interval):
            problems.append(SpatialProblem(SpatialProblemCode.INVALID_INTERVAL, "outage interval must be finite, non-negative, and non-empty", ("gateway_outages", index)))

    if problems:
        return Err(tuple(problems))
    return Ok(None)


def _valid_interval(interval: Interval) -> bool:
    return _finite(interval.start_s) and _finite(interval.end_s) and 0 <= interval.start_s < interval.end_s
