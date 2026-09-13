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
        gx = ground_position.x
        gy = ground_position.y
        gz = ground_position.z
        dx = satellite_position.x - gx
        dy = satellite_position.y - gy
        dz = satellite_position.z - gz
        distance_squared = dx * dx + dy * dy + dz * dz
        distance = math.sqrt(distance_squared)
        if distance == 0.0:
            elevation = 90.0
        else:
            dot = dx * gx + dy * gy + dz * gz
            sine = dot / (distance * body.radius_km)
            sine = max(-1.0, min(1.0, sine))
            elevation = math.degrees(math.asin(sine))
        return GroundObservation(ground_id, satellite_id, elevation, distance)


@dataclass(frozen=True, slots=True)
class SegmentInterSatelliteObservationModel:
    """Measure pair distance and closest segment approach to the body origin."""

    def observe(self, a: SatelliteState, b: SatelliteState) -> InterSatelliteObservation:
        left = a.position.earth_fixed_km
        right = b.position.earth_fixed_km
        lx = left.x
        ly = left.y
        lz = left.z
        dx = right.x - lx
        dy = right.y - ly
        dz = right.z - lz
        denominator = dx * dx + dy * dy + dz * dz
        distance = math.sqrt(denominator)
        if denominator == 0.0:
            closest = math.sqrt(lx * lx + ly * ly + lz * lz)
        else:
            q = -(lx * dx + ly * dy + lz * dz) / denominator
            q = max(0.0, min(1.0, q))
            closest_x = lx + dx * q
            closest_y = ly + dy * q
            closest_z = lz + dz * q
            closest = math.sqrt(
                closest_x * closest_x + closest_y * closest_y + closest_z * closest_z
            )
        return InterSatelliteObservation(a.id, b.id, distance, closest)
