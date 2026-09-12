from __future__ import annotations

from dataclasses import dataclass
import math

from .math3d import Vec3
from .specification import BodyConstants
from .state import GroundObservation, InterSatelliteObservation, SatelliteState


@dataclass(frozen=True, slots=True)
class SphericalGroundObservationModel:
    """Measure slant range and elevation for a spherical central body."""

    def observe(
        self,
        body: BodyConstants,
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
        return GroundObservation(ground_id, satellite_id, elevation, distance)


@dataclass(frozen=True, slots=True)
class SegmentInterSatelliteObservationModel:
    """Measure pair distance and closest segment approach to the body origin."""

    def observe(self, a: SatelliteState, b: SatelliteState) -> InterSatelliteObservation:
        left = a.position.earth_fixed_km
        right = b.position.earth_fixed_km
        delta = right - left
        distance = delta.norm()
        denominator = delta.norm_squared()
        if denominator == 0.0:
            closest = left.norm()
        else:
            q = -left.dot(delta) / denominator
            q = max(0.0, min(1.0, q))
            closest = (left + delta * q).norm()
        return InterSatelliteObservation(a.id, b.id, distance, closest)
