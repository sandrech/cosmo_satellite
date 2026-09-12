from __future__ import annotations

from dataclasses import dataclass
import math

from .availability import DeploymentAndOutageSatelliteAvailability, GatewayOutageGroundAvailability
from .contacts import AllSatellitePairs, ElevationGroundContact, RangeAndEarthOcclusionInterSatelliteContact
from .contracts import (
    GroundAvailabilityPolicy,
    GroundContactPolicy,
    GroundGeometry,
    InterSatelliteContactPolicy,
    SatelliteAvailabilityPolicy,
    SatelliteKinematics,
    SatellitePairSource,
)
from .kinematics import CircularOrbitKinematics, SphericalGroundGeometry
from .result import Err, Ok, Result, SpatialProblem, SpatialProblemCode, SpatialProblems
from .specification import SpatialSpecification, validate_specification
from .state import Contact, ContactKind, GroundState, SatelliteState, SpatialSnapshot


@dataclass(frozen=True, slots=True)
class SpatialComponents:
    kinematics: SatelliteKinematics
    ground_geometry: GroundGeometry
    satellite_availability: SatelliteAvailabilityPolicy
    ground_availability: GroundAvailabilityPolicy
    ground_contact: GroundContactPolicy
    inter_satellite_contact: InterSatelliteContactPolicy
    satellite_pairs: SatellitePairSource

    @classmethod
    def reference_case(cls) -> "SpatialComponents":
        return cls(
            kinematics=CircularOrbitKinematics(),
            ground_geometry=SphericalGroundGeometry(),
            satellite_availability=DeploymentAndOutageSatelliteAvailability(),
            ground_availability=GatewayOutageGroundAvailability(),
            ground_contact=ElevationGroundContact(),
            inter_satellite_contact=RangeAndEarthOcclusionInterSatelliteContact(),
            satellite_pairs=AllSatellitePairs(),
        )


@dataclass(frozen=True, slots=True)
class SpatialModel:
    spec: SpatialSpecification
    components: SpatialComponents

    @classmethod
    def create(
        cls,
        spec: SpatialSpecification,
        components: SpatialComponents | None = None,
    ) -> Result["SpatialModel", SpatialProblems]:
        valid = validate_specification(spec)
        if isinstance(valid, Err):
            return valid
        return Ok(cls(spec, components or SpatialComponents.reference_case()))

    def snapshot(self, t_s: float) -> Result[SpatialSnapshot, SpatialProblems]:
        if isinstance(t_s, bool) or not isinstance(t_s, (int, float)) or not math.isfinite(t_s):
            return Err((SpatialProblem(SpatialProblemCode.INVALID_NUMBER, "time must be finite", ("t_s",)),))

        planes = {plane.id: plane for plane in self.spec.planes}
        satellite_states: list[SatelliteState] = []
        satellite_by_id: dict[str, SatelliteState] = {}
        active_ids: list[str] = []
        for satellite in self.spec.satellites:
            state = self.components.kinematics.state_at(
                self.spec.body,
                self.spec.orbit,
                planes[satellite.plane_id],
                satellite,
                float(t_s),
            )
            active = self.components.satellite_availability.active(self.spec, satellite, float(t_s))
            result = SatelliteState(satellite.id, satellite.plane_id, state, active)
            satellite_states.append(result)
            satellite_by_id[satellite.id] = result
            if active:
                active_ids.append(satellite.id)

        ground_states: list[GroundState] = []
        ground_by_id: dict[str, GroundState] = {}
        for site in self.spec.ground_sites:
            result = GroundState(
                id=site.id,
                name=site.name,
                role=site.role,
                earth_fixed_km=self.components.ground_geometry.position(self.spec.body, site),
                available=self.components.ground_availability.available(self.spec, site, float(t_s)),
            )
            ground_states.append(result)
            ground_by_id[site.id] = result

        contacts: list[Contact] = []
        for left_id, right_id in self.components.satellite_pairs.pairs(active_ids):
            left = satellite_by_id[left_id]
            right = satellite_by_id[right_id]
            distance = self.components.inter_satellite_contact.contact_distance(
                self.spec.body,
                self.spec.links,
                left.position.earth_fixed_km,
                right.position.earth_fixed_km,
            )
            if distance is not None:
                contacts.append(Contact(left_id, right_id, distance, ContactKind.INTER_SATELLITE))

        observations = []
        for site in self.spec.ground_sites:
            ground_state = ground_by_id[site.id]
            for satellite_id in active_ids:
                satellite_state = satellite_by_id[satellite_id]
                observation = self.components.ground_contact.observe(
                    self.spec.body,
                    self.spec.links,
                    ground_state.earth_fixed_km,
                    satellite_state.position.earth_fixed_km,
                    ground_id=site.id,
                    satellite_id=satellite_id,
                )
                observations.append(observation)
                if ground_state.available and observation.geometrically_visible:
                    contacts.append(Contact(
                        site.id,
                        satellite_id,
                        observation.distance_km,
                        ContactKind.GROUND_SATELLITE,
                    ))

        return Ok(SpatialSnapshot(
            t_s=float(t_s),
            satellites=tuple(satellite_states),
            ground_sites=tuple(ground_states),
            contacts=tuple(contacts),
            ground_observations=tuple(observations),
        ))
