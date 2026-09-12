import math

from spatial3d import (
    BodyConstants,
    GroundObservation,
    InterSatelliteObservation,
    LinkLimits,
    MinimumElevationVisibility,
    RangeAndEarthOcclusionInterSatelliteLink,
    SatelliteKinematicState,
    SatelliteState,
    SegmentInterSatelliteObservationModel,
    SphericalGroundObservationModel,
    Vec3,
    VisibleGroundLink,
)

BODY = BodyConstants(6371.0)


def test_ground_threshold_is_inclusive_and_separate_from_measurement() -> None:
    ground = Vec3(BODY.radius_km, 0.0, 0.0)
    elevation = math.radians(10.0)
    distance = 1000.0
    satellite = ground + Vec3(distance * math.sin(elevation), distance * math.cos(elevation), 0.0)
    observation = SphericalGroundObservationModel().observe(
        BODY,
        ground,
        satellite,
        ground_id="G",
        satellite_id="S",
    )
    assert math.isclose(observation.elevation_deg, 10.0, abs_tol=1e-12)
    assert MinimumElevationVisibility().visible(LinkLimits(10.0, 3000.0), observation)
    assert VisibleGroundLink().allows(
        LinkLimits(10.0, 3000.0),
        observation,
        geometrically_visible=True,
    )


def test_ground_observation_does_not_embed_link_policy() -> None:
    observation = GroundObservation("G", "S", 5.0, 1000.0)
    assert not MinimumElevationVisibility().visible(LinkLimits(10.0, 3000.0), observation)
    assert VisibleGroundLink().allows(
        LinkLimits(10.0, 3000.0),
        observation,
        geometrically_visible=False,
    ) is False


def _state(satellite_id: str, point: Vec3) -> SatelliteState:
    return SatelliteState(
        satellite_id,
        None,
        SatelliteKinematicState(point, point),
        True,
    )


def test_isl_observation_is_raw_geometry_then_policy_applies_strict_range() -> None:
    a = _state("A", Vec3(7000.0, 0.0, 0.0))
    b = _state("B", Vec3(7000.0, 3000.0, 0.0))
    observation = SegmentInterSatelliteObservationModel().observe(a, b)
    assert math.isclose(observation.distance_km, 3000.0)
    assert not RangeAndEarthOcclusionInterSatelliteLink().allows(
        BODY,
        LinkLimits(10.0, 3000.0),
        observation,
    )


def test_isl_rejects_exact_tangency_to_body() -> None:
    observation = InterSatelliteObservation(
        "A",
        "B",
        2000.0,
        BODY.radius_km,
    )
    assert not RangeAndEarthOcclusionInterSatelliteLink().allows(
        BODY,
        LinkLimits(10.0, 3000.0),
        observation,
    )


def test_isl_rejects_segment_crossing_earth() -> None:
    a = _state("A", Vec3(7000.0, 0.0, 0.0))
    b = _state("B", Vec3(-7000.0, 0.0, 0.0))
    observation = SegmentInterSatelliteObservationModel().observe(a, b)
    assert not RangeAndEarthOcclusionInterSatelliteLink().allows(
        BODY,
        LinkLimits(10.0, 20000.0),
        observation,
    )


def test_isl_accepts_clear_segment_inside_range() -> None:
    a = _state("A", Vec3(7000.0, 0.0, 0.0))
    b = _state("B", Vec3(7000.0, 1000.0, 0.0))
    observation = SegmentInterSatelliteObservationModel().observe(a, b)
    assert RangeAndEarthOcclusionInterSatelliteLink().allows(
        BODY,
        LinkLimits(10.0, 3000.0),
        observation,
    )
