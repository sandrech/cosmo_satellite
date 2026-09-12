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
        satellite_states: list[SatelliteState] = []
        active_states: list[SatelliteState] = []
        for satellite in self.spec.satellites:
            kinematic = self.trajectory.state_at(satellite.id, time)
            active = self.components.satellite_availability.active(self.spec, satellite, time)
            state = SatelliteState(
                id=satellite.id,
                trajectory_group_id=self.trajectory.group_id(satellite.id),
                position=kinematic,
                active=active,
            )
            satellite_states.append(state)
            if active:
                active_states.append(state)

        ground_states: list[GroundState] = []
        for site in self.spec.ground_sites:
            ground_states.append(
                GroundState(
                    id=site.id,
                    name=site.name,
                    role=site.role,
                    earth_fixed_km=self.components.ground_geometry.position(self.spec.body, site),
                    available=self.components.ground_availability.available(self.spec, site, time),
                )
            )
        ground_by_id = {state.id: state for state in ground_states}

        contacts: list[Contact] = []
        isl_observations = []
        for left, right in self.components.satellite_pair_candidates.candidates(
            active_states,
            body=self.spec.body,
            limits=self.spec.links,
        ):
            observation = self.components.inter_satellite_observation.observe(left, right)
            isl_observations.append(observation)
            if self.components.inter_satellite_link.allows(self.spec.body, self.spec.links, observation):
                contacts.append(
                    Contact(
                        observation.a,
                        observation.b,
                        observation.distance_km,
                        ContactKind.INTER_SATELLITE,
                    )
                )

        ground_observations = []
        visibility: list[GroundVisibility] = []
        for site in self.spec.ground_sites:
            ground_state = ground_by_id[site.id]
            for satellite_state in active_states:
                observation = self.components.ground_observation.observe(
                    self.spec.body,
                    ground_state.earth_fixed_km,
                    satellite_state.position.earth_fixed_km,
                    ground_id=site.id,
                    satellite_id=satellite_state.id,
                )
                ground_observations.append(observation)
                visible = self.components.ground_visibility.visible(self.spec.links, observation)
                if visible:
                    visibility.append(
                        GroundVisibility(
                            observation.ground_id,
                            observation.satellite_id,
                            observation.elevation_deg,
                            observation.distance_km,
                        )
                    )
                if (
                    ground_state.available
                    and self.components.ground_link.allows(
                        self.spec.links,
                        observation,
                        geometrically_visible=visible,
                    )
                ):
                    contacts.append(
                        Contact(
                            site.id,
                            satellite_state.id,
                            observation.distance_km,
                            ContactKind.GROUND_SATELLITE,
                        )
                    )

        return Ok(
            SpatialSnapshot(
                t_s=time,
                reference_frame=ReferenceFrame(CoordinateFrame.EARTH_FIXED, self.spec.body.radius_km),
                satellites=tuple(satellite_states),
                ground_sites=tuple(ground_states),
                contacts=tuple(contacts),
                ground_observations=tuple(ground_observations),
                ground_visibility=tuple(visibility),
                inter_satellite_observations=tuple(isl_observations),
            )
        )
