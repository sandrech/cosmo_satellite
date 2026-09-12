from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import math
from types import MappingProxyType

from .math3d import Vec3
from .result import Err, Ok, Result, SpatialProblem, SpatialProblemCode, SpatialProblems
from .specification import BodyConstants, SpatialSpecification
from .state import SatelliteKinematicState


@dataclass(frozen=True, slots=True)
class CircularOrbitEnvironment:
    altitude_km: float
    inclination_deg: float
    earth_angle0_deg: float
    gravitational_parameter_km3_s2: float
    rotation_period_s: float


@dataclass(frozen=True, slots=True)
class OrbitalPlane:
    id: str
    raan_deg: float
    phase_deg: float


@dataclass(frozen=True, slots=True)
class CircularOrbitAssignment:
    satellite_id: str
    plane_id: str
    slot_deg: float


@dataclass(frozen=True, slots=True)
class CircularOrbitConfiguration:
    environment: CircularOrbitEnvironment
    planes: tuple[OrbitalPlane, ...]
    assignments: tuple[CircularOrbitAssignment, ...]


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_circular_configuration(
    body: BodyConstants,
    configuration: CircularOrbitConfiguration,
    satellite_ids: tuple[str, ...],
) -> Result[None, SpatialProblems]:
    """Validate generic mathematical invariants of the circular trajectory model.

    cosmo-A-specific bounds such as altitude 200..1200 km and angles in [0, 360)
    remain persistence/schema concerns and are intentionally not duplicated here.
    """

    problems: list[SpatialProblem] = []
    env = configuration.environment

    if body.radius_km <= 0:
        problems.append(
            SpatialProblem(
                SpatialProblemCode.INVALID_TRAJECTORY,
                "trajectory body radius must be positive",
                ("trajectory", "body", "radius_km"),
            )
        )
    numeric = (
        (env.altitude_km, ("trajectory", "environment", "altitude_km")),
        (env.inclination_deg, ("trajectory", "environment", "inclination_deg")),
        (env.earth_angle0_deg, ("trajectory", "environment", "earth_angle0_deg")),
        (
            env.gravitational_parameter_km3_s2,
            ("trajectory", "environment", "gravitational_parameter_km3_s2"),
        ),
        (env.rotation_period_s, ("trajectory", "environment", "rotation_period_s")),
    )
    for value, path in numeric:
        if not _finite(value):
            problems.append(SpatialProblem(SpatialProblemCode.INVALID_NUMBER, "value must be finite", path))

    if _finite(env.altitude_km) and body.radius_km + env.altitude_km <= 0:
        problems.append(
            SpatialProblem(
                SpatialProblemCode.INVALID_TRAJECTORY,
                "orbit radius must be positive",
                ("trajectory", "environment", "altitude_km"),
            )
        )
    if _finite(env.gravitational_parameter_km3_s2) and env.gravitational_parameter_km3_s2 <= 0:
        problems.append(
            SpatialProblem(
                SpatialProblemCode.INVALID_TRAJECTORY,
                "gravitational parameter must be positive",
                ("trajectory", "environment", "gravitational_parameter_km3_s2"),
            )
        )
    if _finite(env.rotation_period_s) and env.rotation_period_s <= 0:
        problems.append(
            SpatialProblem(
                SpatialProblemCode.INVALID_TRAJECTORY,
                "rotation period must be positive",
                ("trajectory", "environment", "rotation_period_s"),
            )
        )

    plane_ids = [plane.id for plane in configuration.planes]
    if any(not plane_id for plane_id in plane_ids):
        problems.append(
            SpatialProblem(
                SpatialProblemCode.INVALID_REFERENCE,
                "plane id must not be empty",
                ("trajectory", "planes"),
            )
        )
    if len(plane_ids) != len(set(plane_ids)):
        problems.append(
            SpatialProblem(
                SpatialProblemCode.DUPLICATE_ID,
                "duplicate plane id",
                ("trajectory", "planes"),
            )
        )
    for index, plane in enumerate(configuration.planes):
        for field_name, value in (("raan_deg", plane.raan_deg), ("phase_deg", plane.phase_deg)):
            if not _finite(value):
                problems.append(
                    SpatialProblem(
                        SpatialProblemCode.INVALID_NUMBER,
                        f"{field_name} must be finite",
                        ("trajectory", "planes", index, field_name),
                    )
                )

    assignment_ids = [assignment.satellite_id for assignment in configuration.assignments]
    if len(assignment_ids) != len(set(assignment_ids)):
        problems.append(
            SpatialProblem(
                SpatialProblemCode.DUPLICATE_ID,
                "duplicate circular trajectory assignment",
                ("trajectory", "assignments"),
            )
        )

    expected = set(satellite_ids)
    actual = set(assignment_ids)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        problems.append(
            SpatialProblem(
                SpatialProblemCode.TRAJECTORY_BINDING,
                f"trajectory is missing satellites: {', '.join(missing)}",
                ("trajectory", "assignments"),
            )
        )
    if extra:
        problems.append(
            SpatialProblem(
                SpatialProblemCode.TRAJECTORY_BINDING,
                f"trajectory references unknown satellites: {', '.join(extra)}",
                ("trajectory", "assignments"),
            )
        )

    known_planes = set(plane_ids)
    for index, assignment in enumerate(configuration.assignments):
        if assignment.plane_id not in known_planes:
            problems.append(
                SpatialProblem(
                    SpatialProblemCode.INVALID_REFERENCE,
                    f"unknown plane {assignment.plane_id!r}",
                    ("trajectory", "assignments", index, "plane_id"),
                )
            )
        if not _finite(assignment.slot_deg):
            problems.append(
                SpatialProblem(
                    SpatialProblemCode.INVALID_NUMBER,
                    "slot angle must be finite",
                    ("trajectory", "assignments", index, "slot_deg"),
                )
            )

    if problems:
        return Err(tuple(problems))
    return Ok(None)


@dataclass(frozen=True, slots=True)
class CircularOrbitTrajectory:
    """Reference trajectory provider implementing the equations from the case PDF."""

    body: BodyConstants
    configuration: CircularOrbitConfiguration
    _planes: Mapping[str, OrbitalPlane] = field(init=False, repr=False, compare=False)
    _assignments: Mapping[str, CircularOrbitAssignment] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_planes",
            MappingProxyType({plane.id: plane for plane in self.configuration.planes}),
        )
        object.__setattr__(
            self,
            "_assignments",
            MappingProxyType({item.satellite_id: item for item in self.configuration.assignments}),
        )

    def validate_for(self, spec: SpatialSpecification) -> Result[None, SpatialProblems]:
        if self.body != spec.body:
            return Err((
                SpatialProblem(
                    SpatialProblemCode.TRAJECTORY_BINDING,
                    "trajectory and spatial specification must use the same body geometry",
                    ("trajectory", "body"),
                ),
            ))
        return validate_circular_configuration(
            self.body,
            self.configuration,
            tuple(satellite.id for satellite in spec.satellites),
        )

    def state_at(self, satellite_id: str, t_s: float) -> SatelliteKinematicState:
        assignment = self._assignments[satellite_id]
        plane = self._planes[assignment.plane_id]
        env = self.configuration.environment

        radius = self.body.radius_km + env.altitude_km
        mean_motion = math.sqrt(env.gravitational_parameter_km3_s2 / radius**3)
        inclination = math.radians(env.inclination_deg)
        ascending_node = math.radians(plane.raan_deg)
        argument = math.radians(assignment.slot_deg + plane.phase_deg) + mean_motion * t_s

        cos_u = math.cos(argument)
        sin_u = math.sin(argument)
        cos_omega = math.cos(ascending_node)
        sin_omega = math.sin(ascending_node)
        cos_i = math.cos(inclination)
        sin_i = math.sin(inclination)

        inertial = Vec3(
            radius * (cos_omega * cos_u - sin_omega * sin_u * cos_i),
            radius * (sin_omega * cos_u + cos_omega * sin_u * cos_i),
            radius * sin_u * sin_i,
        )

        theta = math.radians(env.earth_angle0_deg) + 2.0 * math.pi * t_s / env.rotation_period_s
        cos_theta = math.cos(theta)
        sin_theta = math.sin(theta)
        earth_fixed = Vec3(
            cos_theta * inertial.x + sin_theta * inertial.y,
            -sin_theta * inertial.x + cos_theta * inertial.y,
            inertial.z,
        )
        return SatelliteKinematicState(inertial, earth_fixed)

    def group_id(self, satellite_id: str) -> str | None:
        return self._assignments[satellite_id].plane_id
