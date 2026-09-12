from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .math3d import Vec3
from .specification import GroundRole


@dataclass(frozen=True, slots=True)
class SatelliteKinematicState:
    inertial_km: Vec3
    earth_fixed_km: Vec3


@dataclass(frozen=True, slots=True)
class SatelliteState:
    id: str
    plane_id: str
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
    ground_id: str
    satellite_id: str
    elevation_deg: float
    distance_km: float
    geometrically_visible: bool


@dataclass(frozen=True, slots=True)
class SpatialSnapshot:
    t_s: float
    satellites: tuple[SatelliteState, ...]
    ground_sites: tuple[GroundState, ...]
    contacts: tuple[Contact, ...]
    ground_observations: tuple[GroundObservation, ...]
