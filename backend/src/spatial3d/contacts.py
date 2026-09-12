from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .specification import BodyConstants, LinkLimits
from .state import GroundObservation, InterSatelliteObservation, SatelliteState


@dataclass(frozen=True, slots=True)
class MinimumElevationVisibility:
    """Case visibility rule: equality at the elevation threshold is visible."""

    def visible(self, limits: LinkLimits, observation: GroundObservation) -> bool:
        return observation.elevation_deg >= limits.min_elevation_deg


@dataclass(frozen=True, slots=True)
class VisibleGroundLink:
    """Reference direct-link rule: every geometrically visible active pair is usable."""

    def allows(
        self,
        limits: LinkLimits,
        observation: GroundObservation,
        *,
        geometrically_visible: bool,
    ) -> bool:
        return geometrically_visible


@dataclass(frozen=True, slots=True)
class RangeAndEarthOcclusionInterSatelliteLink:
    """Exact case rule: strict range and strict clearance above the spherical Earth."""

    def allows(
        self,
        body: BodyConstants,
        limits: LinkLimits,
        observation: InterSatelliteObservation,
    ) -> bool:
        return (
            observation.distance_km < limits.isl_range_km
            and observation.closest_center_distance_km > body.radius_km
        )


@dataclass(frozen=True, slots=True)
class AllSatellitePairCandidates:
    def candidates(
        self,
        satellites: Sequence[SatelliteState],
        *,
        body: BodyConstants,
        limits: LinkLimits,
    ) -> Iterable[tuple[SatelliteState, SatelliteState]]:
        del body, limits
        for index, left in enumerate(satellites):
            for right in satellites[index + 1 :]:
                yield left, right
