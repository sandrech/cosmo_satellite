from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol

from .math3d import Vec3
from .result import Result, SpatialProblems
from .specification import BodyConstants, GroundSite, LinkLimits, Satellite, SpatialSpecification
from .state import (
    GroundObservation,
    InterSatelliteObservation,
    SatelliteKinematicState,
    SatelliteState,
)


class SatelliteTrajectoryProvider(Protocol):
    """Owns trajectory-specific data and produces positions by satellite identity."""

    def validate_for(self, spec: SpatialSpecification) -> Result[None, SpatialProblems]: ...

    def state_at(self, satellite_id: str, t_s: float) -> SatelliteKinematicState: ...

    def group_id(self, satellite_id: str) -> str | None: ...


class GroundGeometry(Protocol):
    def position(self, body: BodyConstants, site: GroundSite) -> Vec3: ...


class SatelliteAvailabilityPolicy(Protocol):
    def active(self, spec: SpatialSpecification, satellite: Satellite, t_s: float) -> bool: ...


class GroundAvailabilityPolicy(Protocol):
    def available(self, spec: SpatialSpecification, site: GroundSite, t_s: float) -> bool: ...


class GroundObservationModel(Protocol):
    def observe(
        self,
        body: BodyConstants,
        ground_position: Vec3,
        satellite_position: Vec3,
        *,
        ground_id: str,
        satellite_id: str,
    ) -> GroundObservation: ...


class GroundVisibilityPolicy(Protocol):
    def visible(self, limits: LinkLimits, observation: GroundObservation) -> bool: ...


class GroundLinkPolicy(Protocol):
    def allows(
        self,
        limits: LinkLimits,
        observation: GroundObservation,
        *,
        geometrically_visible: bool,
    ) -> bool: ...


class InterSatelliteObservationModel(Protocol):
    def observe(
        self,
        a: SatelliteState,
        b: SatelliteState,
    ) -> InterSatelliteObservation: ...


class InterSatelliteLinkPolicy(Protocol):
    def allows(
        self,
        body: BodyConstants,
        limits: LinkLimits,
        observation: InterSatelliteObservation,
    ) -> bool: ...


class SatellitePairCandidateSource(Protocol):
    """Broad phase only; final contact validity remains the link policy's job."""

    def candidates(
        self,
        satellites: Sequence[SatelliteState],
        *,
        body: BodyConstants,
        limits: LinkLimits,
    ) -> Iterable[tuple[SatelliteState, SatelliteState]]: ...
