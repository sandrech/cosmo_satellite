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
    """Geometry of the central body required by the spatial core.

    Dynamics constants intentionally do not live here.  A trajectory provider owns
    whatever dynamical parameters it needs (for example ``mu`` and the body rotation
    period for the reference circular-orbit model).
    """

    radius_km: float


@dataclass(frozen=True, slots=True)
class LinkLimits:
    min_elevation_deg: float
    isl_range_km: float


@dataclass(frozen=True, slots=True)
class Satellite:
    """Satellite identity and availability metadata, independent of trajectory model."""

    id: str
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
    """Generic input owned by the spatial component.

    There are deliberately no RAAN/phase/slot/TLE fields here.  Those belong to the
    selected :class:`SatelliteTrajectoryProvider`, which makes the trajectory model
    genuinely replaceable instead of merely swapping an algorithm over circular-orbit
    data structures.
    """

    body: BodyConstants
    links: LinkLimits
    launch_stage: int
    satellites: tuple[Satellite, ...]
    ground_sites: tuple[GroundSite, ...]
    satellite_outages: tuple[SatelliteOutage, ...] = ()
    gateway_outages: tuple[GatewayOutage, ...] = ()


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_specification(spec: SpatialSpecification) -> Result[None, SpatialProblems]:
    """Validate only invariants required by generic spatial algorithms.

    Exact cosmo-A schema ranges (launch stages 1..3, altitude bounds, RAAN ranges,
    outage-inside-horizon, and so on) belong to ``cosmo_a_json``.  Keeping those
    checks at the adapter boundary allows this component to be reused with another
    scenario format or trajectory provider.
    """

    problems: list[SpatialProblem] = []

    numbers = (
        (spec.body.radius_km, ("body", "radius_km")),
        (spec.links.min_elevation_deg, ("links", "min_elevation_deg")),
        (spec.links.isl_range_km, ("links", "isl_range_km")),
    )
    for value, path in numbers:
        if not _finite(value):
            problems.append(SpatialProblem(SpatialProblemCode.INVALID_NUMBER, "value must be finite", path))

    if _finite(spec.body.radius_km) and spec.body.radius_km <= 0:
        problems.append(
            SpatialProblem(
                SpatialProblemCode.INVALID_RANGE,
                "body radius must be positive",
                ("body", "radius_km"),
            )
        )
    if _finite(spec.links.isl_range_km) and spec.links.isl_range_km <= 0:
        problems.append(
            SpatialProblem(
                SpatialProblemCode.INVALID_RANGE,
                "ISL range must be positive",
                ("links", "isl_range_km"),
            )
        )
    if _finite(spec.links.min_elevation_deg) and not (-90 <= spec.links.min_elevation_deg <= 90):
        problems.append(
            SpatialProblem(
                SpatialProblemCode.INVALID_RANGE,
                "minimum elevation must be in [-90, 90]",
                ("links", "min_elevation_deg"),
            )
        )
    if not isinstance(spec.launch_stage, int) or isinstance(spec.launch_stage, bool) or spec.launch_stage < 0:
        problems.append(
            SpatialProblem(
                SpatialProblemCode.INVALID_RANGE,
                "launch stage must be a non-negative integer",
                ("launch_stage",),
            )
        )

    satellite_ids = [satellite.id for satellite in spec.satellites]
    ground_ids = [site.id for site in spec.ground_sites]
    for label, ids, path in (
        ("satellite", satellite_ids, ("satellites",)),
        ("ground", ground_ids, ("ground_sites",)),
    ):
        if any(not node_id for node_id in ids):
            problems.append(SpatialProblem(SpatialProblemCode.INVALID_REFERENCE, f"{label} id must not be empty", path))
        if len(ids) != len(set(ids)):
            problems.append(SpatialProblem(SpatialProblemCode.DUPLICATE_ID, f"duplicate {label} id", path))

    if set(satellite_ids) & set(ground_ids):
        problems.append(
            SpatialProblem(
                SpatialProblemCode.DUPLICATE_ID,
                "satellite and ground node ids must be disjoint",
                ("ground_sites",),
            )
        )

    for index, satellite in enumerate(spec.satellites):
        if (
            not isinstance(satellite.launch_batch, int)
            or isinstance(satellite.launch_batch, bool)
            or satellite.launch_batch < 0
        ):
            problems.append(
                SpatialProblem(
                    SpatialProblemCode.INVALID_RANGE,
                    "launch batch must be a non-negative integer",
                    ("satellites", index, "launch_batch"),
                )
            )

    for index, site in enumerate(spec.ground_sites):
        if not _finite(site.lat_deg) or not -90 <= site.lat_deg <= 90:
            problems.append(
                SpatialProblem(
                    SpatialProblemCode.INVALID_RANGE,
                    "latitude must be finite and in [-90, 90]",
                    ("ground_sites", index, "lat_deg"),
                )
            )
        if not _finite(site.lon_deg) or not -180 <= site.lon_deg <= 180:
            problems.append(
                SpatialProblem(
                    SpatialProblemCode.INVALID_RANGE,
                    "longitude must be finite and in [-180, 180]",
                    ("ground_sites", index, "lon_deg"),
                )
            )

    satellite_set = set(satellite_ids)
    gateway_set = {site.id for site in spec.ground_sites if site.role == GroundRole.GATEWAY}
    for index, outage in enumerate(spec.satellite_outages):
        if outage.satellite_id not in satellite_set:
            problems.append(
                SpatialProblem(
                    SpatialProblemCode.INVALID_REFERENCE,
                    "outage references unknown satellite",
                    ("satellite_outages", index, "satellite_id"),
                )
            )
        if not _valid_interval(outage.interval):
            problems.append(
                SpatialProblem(
                    SpatialProblemCode.INVALID_INTERVAL,
                    "outage interval must be finite, non-negative, and non-empty",
                    ("satellite_outages", index),
                )
            )
    for index, outage in enumerate(spec.gateway_outages):
        if outage.gateway_id not in gateway_set:
            problems.append(
                SpatialProblem(
                    SpatialProblemCode.INVALID_REFERENCE,
                    "outage references unknown gateway",
                    ("gateway_outages", index, "gateway_id"),
                )
            )
        if not _valid_interval(outage.interval):
            problems.append(
                SpatialProblem(
                    SpatialProblemCode.INVALID_INTERVAL,
                    "outage interval must be finite, non-negative, and non-empty",
                    ("gateway_outages", index),
                )
            )

    if problems:
        return Err(tuple(problems))
    return Ok(None)


def _valid_interval(interval: Interval) -> bool:
    return _finite(interval.start_s) and _finite(interval.end_s) and 0 <= interval.start_s < interval.end_s
