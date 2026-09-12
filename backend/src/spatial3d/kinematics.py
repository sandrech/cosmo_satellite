from __future__ import annotations

from dataclasses import dataclass
import math

from .math3d import Vec3
from .specification import BodyConstants, GroundSite, OrbitEnvironment, OrbitalPlane, Satellite
from .state import SatelliteKinematicState


@dataclass(frozen=True, slots=True)
class CircularOrbitKinematics:
    """Reference circular-orbit equations from the case data specification."""

    def state_at(
        self,
        body: BodyConstants,
        orbit: OrbitEnvironment,
        plane: OrbitalPlane,
        satellite: Satellite,
        t_s: float,
    ) -> SatelliteKinematicState:
        radius = body.radius_km + orbit.altitude_km
        mean_motion = math.sqrt(body.gravitational_parameter_km3_s2 / radius**3)
        inclination = math.radians(orbit.inclination_deg)
        ascending_node = math.radians(plane.raan_deg)
        argument = math.radians(satellite.slot_deg + plane.phase_deg) + mean_motion * t_s

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

        theta = math.radians(orbit.earth_angle0_deg) + 2.0 * math.pi * t_s / body.rotation_period_s
        cos_theta = math.cos(theta)
        sin_theta = math.sin(theta)
        earth_fixed = Vec3(
            cos_theta * inertial.x + sin_theta * inertial.y,
            -sin_theta * inertial.x + cos_theta * inertial.y,
            inertial.z,
        )
        return SatelliteKinematicState(inertial, earth_fixed)


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
