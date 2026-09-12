from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .math3d import Vec3
from .specification import GroundRole


class CoordinateFrame(StrEnum):
    EARTH_FIXED = "earth_fixed"


@dataclass(frozen=True, slots=True)
class ReferenceFrame:
    coordinate_frame: CoordinateFrame
    body_radius_km: float


@dataclass(frozen=True, slots=True)
class SatelliteKinematicState:
    inertial_km: Vec3
    earth_fixed_km: Vec3


@dataclass(frozen=True, slots=True)
class SatelliteState:
    id: str
    trajectory_group_id: str | None
    position: SatelliteKinematicState
    active: bool


@dataclass(frozen=True, slots=True)
class GroundState:
    id: str
    name: str
    role: GroundRole
    earth_fixed_km: Vec3
    available: bool


class ContactKind(StrEnum):
    INTER_SATELLITE = "inter_satellite"
    GROUND_SATELLITE = "ground_satellite"


@dataclass(frozen=True, slots=True)
class Contact:
    a: str
    b: str
    distance_km: float
    kind: ContactKind


@dataclass(frozen=True, slots=True)
class GroundObservation:
    """Raw geometry between one ground site and one active satellite."""

    ground_id: str
    satellite_id: str
    elevation_deg: float
    distance_km: float


@dataclass(frozen=True, slots=True)
class GroundVisibility:
    """A ground/satellite pair satisfying the configured visibility criterion."""

    ground_id: str
    satellite_id: str
    elevation_deg: float
    distance_km: float


@dataclass(frozen=True, slots=True)
class InterSatelliteObservation:
    """Raw geometry needed by ISL policies.

    ``closest_center_distance_km`` is the distance from the central-body origin
    to the closest point on the segment joining the two satellite positions.
    """

    a: str
    b: str
    distance_km: float
    closest_center_distance_km: float


@dataclass(frozen=True, slots=True)
class SpatialSnapshot:
    t_s: float
    reference_frame: ReferenceFrame
    satellites: tuple[SatelliteState, ...]
    ground_sites: tuple[GroundState, ...]
    contacts: tuple[Contact, ...]
    ground_observations: tuple[GroundObservation, ...]
    ground_visibility: tuple[GroundVisibility, ...]
    inter_satellite_observations: tuple[InterSatelliteObservation, ...]
