from __future__ import annotations

from dataclasses import dataclass
import math

from .math3d import Vec3
from .specification import BodyConstants, GroundSite


@dataclass(frozen=True, slots=True)
class SphericalGroundGeometry:
    def position(self, body: BodyConstants, site: GroundSite) -> Vec3:
        latitude = math.radians(site.lat_deg)
        longitude = math.radians(site.lon_deg)
        cos_latitude = math.cos(latitude)
        return Vec3(
            body.radius_km * cos_latitude * math.cos(longitude),
            body.radius_km * cos_latitude * math.sin(longitude),
            body.radius_km * math.sin(latitude),
        )
