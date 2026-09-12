from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
import math

from .math3d import Vec3
from .specification import BodyConstants, LinkLimits
from .state import GroundObservation


@dataclass(frozen=True, slots=True)
class ElevationGroundContact:
    """Ground contact is inclusive at the minimum elevation, as specified by the case."""

    def observe(
        self,
        body: BodyConstants,
        limits: LinkLimits,
        ground_position: Vec3,
        satellite_position: Vec3,
        *,
        ground_id: str,
        satellite_id: str,
    ) -> GroundObservation:
        delta = satellite_position - ground_position
        distance = delta.norm()
        if distance == 0.0:
            elevation = 90.0
        else:
            sine = delta.dot(ground_position) / (distance * body.radius_km)
            sine = max(-1.0, min(1.0, sine))
            elevation = math.degrees(math.asin(sine))
        return GroundObservation(
            ground_id=ground_id,
            satellite_id=satellite_id,
            elevation_deg=elevation,
            distance_km=distance,
            geometrically_visible=elevation >= limits.min_elevation_deg,
        )


@dataclass(frozen=True, slots=True)
class RangeAndEarthOcclusionInterSatelliteContact:
    """Exact case rule: strict range and strict clearance above the spherical Earth."""

    def contact_distance(
        self,
        body: BodyConstants,
        limits: LinkLimits,
        a: Vec3,
        b: Vec3,
    ) -> float | None:
        delta = b - a
        distance = delta.norm()
        if not distance < limits.isl_range_km:
            return None

        denominator = delta.norm_squared()
        if denominator == 0.0:
            closest = a.norm()
        else:
            q = -a.dot(delta) / denominator
            q = max(0.0, min(1.0, q))
            closest = (a + delta * q).norm()
        if not closest > body.radius_km:
            return None
        return distance


@dataclass(frozen=True, slots=True)
class AllSatellitePairs:
    def pairs(self, satellites: Sequence[str]) -> Iterable[tuple[str, str]]:
        for index, left in enumerate(satellites):
            for right in satellites[index + 1 :]:
                yield left, right
