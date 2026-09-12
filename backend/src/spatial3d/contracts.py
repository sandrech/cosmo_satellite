from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol

from .math3d import Vec3
from .specification import (
    BodyConstants,
    GroundSite,
    LinkLimits,
    OrbitEnvironment,
    OrbitalPlane,
    Satellite,
    SpatialSpecification,
)
from .state import GroundObservation, SatelliteKinematicState


class SatelliteKinematics(Protocol):
    def state_at(
        self,
        body: BodyConstants,
        orbit: OrbitEnvironment,
        plane: OrbitalPlane,
        satellite: Satellite,
        t_s: float,
    ) -> SatelliteKinematicState: ...


class GroundGeometry(Protocol):
    def position(self, body: BodyConstants, site: GroundSite) -> Vec3: ...


class SatelliteAvailabilityPolicy(Protocol):
    def active(self, spec: SpatialSpecification, satellite: Satellite, t_s: float) -> bool: ...


class GroundAvailabilityPolicy(Protocol):
    def available(self, spec: SpatialSpecification, site: GroundSite, t_s: float) -> bool: ...


class GroundContactPolicy(Protocol):
    def observe(
        self,
        body: BodyConstants,
        limits: LinkLimits,
        ground_position: Vec3,
        satellite_position: Vec3,
        *,
        ground_id: str,
        satellite_id: str,
    ) -> GroundObservation: ...


class InterSatelliteContactPolicy(Protocol):
    def contact_distance(
        self,
        body: BodyConstants,
        limits: LinkLimits,
        a: Vec3,
        b: Vec3,
    ) -> float | None: ...


class SatellitePairSource(Protocol):
    def pairs(self, satellites: Sequence[str]) -> Iterable[tuple[str, str]]: ...
