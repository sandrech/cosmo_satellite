from __future__ import annotations

from dataclasses import dataclass
import math

from .availability import DeploymentAndOutageSatelliteAvailability, GatewayOutageGroundAvailability
from .contacts import (
    AllSatellitePairCandidates,
    MinimumElevationVisibility,
    RangeAndEarthOcclusionInterSatelliteLink,
    VisibleGroundLink,
)
from .contracts import (
    GroundAvailabilityPolicy,
    GroundGeometry,
    GroundLinkPolicy,
    GroundObservationModel,
    GroundVisibilityPolicy,
    InterSatelliteLinkPolicy,
    InterSatelliteObservationModel,
    SatelliteAvailabilityPolicy,
    SatellitePairCandidateSource,
    SatelliteTrajectoryProvider,
)
from .kinematics import SphericalGroundGeometry
from .observations import SphericalGroundObservationModel, SegmentInterSatelliteObservationModel
from .result import Err, Ok, Result, SpatialProblem, SpatialProblemCode, SpatialProblems
from .specification import SpatialSpecification, validate_specification
from .state import (
    Contact,
    ContactKind,
    CoordinateFrame,
    GroundState,
    GroundVisibility,
    ReferenceFrame,
    SatelliteState,
    SpatialSnapshot,
)


@dataclass(frozen=True, slots=True)
class SpatialComponents:
    ground_geometry: GroundGeometry
    satellite_availability: SatelliteAvailabilityPolicy
    ground_availability: GroundAvailabilityPolicy
    ground_observation: GroundObservationModel
    ground_visibility: GroundVisibilityPolicy
    ground_link: GroundLinkPolicy
    inter_satellite_observation: InterSatelliteObservationModel
    inter_satellite_link: InterSatelliteLinkPolicy
    satellite_pair_candidates: SatellitePairCandidateSource

    @classmethod
    def reference_case(cls) -> "SpatialComponents":
        return cls(
            ground_geometry=SphericalGroundGeometry(),
            satellite_availability=DeploymentAndOutageSatelliteAvailability(),
            ground_availability=GatewayOutageGroundAvailability(),
            ground_observation=SphericalGroundObservationModel(),
            ground_visibility=MinimumElevationVisibility(),
            ground_link=VisibleGroundLink(),
            inter_satellite_observation=SegmentInterSatelliteObservationModel(),
            inter_satellite_link=RangeAndEarthOcclusionInterSatelliteLink(),
            satellite_pair_candidates=AllSatellitePairCandidates(),
        )


@dataclass(frozen=True, slots=True)
class SpatialModel:
    spec: SpatialSpecification
    trajectory: SatelliteTrajectoryProvider
    components: SpatialComponents

    @classmethod
    def create(
        cls,
        spec: SpatialSpecification,
        trajectory: SatelliteTrajectoryProvider,
        components: SpatialComponents | None = None,
    ) -> Result["SpatialModel", SpatialProblems]:
        valid = validate_specification(spec)
        if isinstance(valid, Err):
            return valid
        trajectory_valid = trajectory.validate_for(spec)
        if isinstance(trajectory_valid, Err):
            return trajectory_valid
        return Ok(cls(spec, trajectory, components or SpatialComponents.reference_case()))

    def snapshot(self, t_s: float) -> Result[SpatialSnapshot, SpatialProblems]:
        if isinstance(t_s, bool) or not isinstance(t_s, (int, float)) or not math.isfinite(t_s):
            return Err((SpatialProblem(SpatialProblemCode.INVALID_NUMBER, "time must be finite", ("t_s",)),))

        time = float(t_s)
        spec = self.spec
        components = self.components
        body = spec.body
        limits = spec.links
        trajectory = self.trajectory

        satellite_states: list[SatelliteState] = []
        active_states: list[SatelliteState] = []
        satellite_states_append = satellite_states.append
        active_states_append = active_states.append
        state_at = trajectory.state_at
        group_id = trajectory.group_id
        satellite_active = components.satellite_availability.active
        for satellite in spec.satellites:
            kinematic = state_at(satellite.id, time)
            active = satellite_active(spec, satellite, time)
            state = SatelliteState(
                id=satellite.id,
                trajectory_group_id=group_id(satellite.id),
                position=kinematic,
                active=active,
            )
            satellite_states_append(state)
            if active:
                active_states_append(state)

        ground_states: list[GroundState] = []
        ground_states_append = ground_states.append
        ground_position = components.ground_geometry.position
        ground_available = components.ground_availability.available
        for site in spec.ground_sites:
            ground_states_append(
                GroundState(
                    id=site.id,
                    name=site.name,
                    role=site.role,
                    earth_fixed_km=ground_position(body, site),
                    available=ground_available(spec, site, time),
                )
            )
        ground_by_id = {state.id: state for state in ground_states}

        contacts: list[Contact] = []
        isl_observations: list[InterSatelliteObservation] = []
        contacts_append = contacts.append
        isl_observations_append = isl_observations.append
        observe_isl = components.inter_satellite_observation.observe
        allow_isl = components.inter_satellite_link.allows
        pair_candidates = components.satellite_pair_candidates.candidates
        for left, right in pair_candidates(active_states, body=body, limits=limits):
            observation = observe_isl(left, right)
            isl_observations_append(observation)
            if allow_isl(body, limits, observation):
                contacts_append(
                    Contact(
                        observation.a,
                        observation.b,
                        observation.distance_km,
                        ContactKind.INTER_SATELLITE,
                    )
                )

        ground_observations: list[GroundObservation] = []
        visibility: list[GroundVisibility] = []
        ground_observations_append = ground_observations.append
        visibility_append = visibility.append
        observe_ground = components.ground_observation.observe
        visible_ground = components.ground_visibility.visible
        allow_ground = components.ground_link.allows
        for site in spec.ground_sites:
            ground_state = ground_by_id[site.id]
            ground_position_km = ground_state.earth_fixed_km
            ground_state_available = ground_state.available
            site_id = site.id
            for satellite_state in active_states:
                observation = observe_ground(
                    body,
                    ground_position_km,
                    satellite_state.position.earth_fixed_km,
                    ground_id=site_id,
                    satellite_id=satellite_state.id,
                )
                ground_observations_append(observation)
                visible = visible_ground(limits, observation)
                if visible:
                    visibility_append(
                        GroundVisibility(
                            observation.ground_id,
                            observation.satellite_id,
                            observation.elevation_deg,
                            observation.distance_km,
                        )
                    )
                if ground_state_available and allow_ground(
                    limits, observation, geometrically_visible=visible
                ):
                    contacts_append(
                        Contact(
                            site_id,
                            satellite_state.id,
                            observation.distance_km,
                            ContactKind.GROUND_SATELLITE,
                        )
                    )

        return Ok(
            SpatialSnapshot(
                t_s=time,
                reference_frame=ReferenceFrame(CoordinateFrame.EARTH_FIXED, body.radius_km),
                satellites=tuple(satellite_states),
                ground_sites=tuple(ground_states),
                contacts=tuple(contacts),
                ground_observations=tuple(ground_observations),
                ground_visibility=tuple(visibility),
                inter_satellite_observations=tuple(isl_observations),
            )
        )
