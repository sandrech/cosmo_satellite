import math

from spatial3d import (
    BodyConstants,
    ElevationGroundContact,
    LinkLimits,
    RangeAndEarthOcclusionInterSatelliteContact,
    Vec3,
)

BODY = BodyConstants(6371.0, 398600.435507, 86164.09054)


def test_ground_threshold_is_inclusive() -> None:
    ground = Vec3(BODY.radius_km, 0.0, 0.0)
    elevation = math.radians(10.0)
    distance = 1000.0
    satellite = ground + Vec3(distance * math.sin(elevation), distance * math.cos(elevation), 0.0)
    observation = ElevationGroundContact().observe(
        BODY,
        LinkLimits(10.0, 3000.0),
        ground,
        satellite,
        ground_id="G",
        satellite_id="S",
    )
    assert math.isclose(observation.elevation_deg, 10.0, abs_tol=1e-12)
    assert observation.geometrically_visible


def test_isl_range_boundary_is_strict() -> None:
    policy = RangeAndEarthOcclusionInterSatelliteContact()
    a = Vec3(7000.0, 0.0, 0.0)
    b = Vec3(7000.0, 3000.0, 0.0)
    assert policy.contact_distance(BODY, LinkLimits(10.0, 3000.0), a, b) is None


def test_isl_rejects_exact_tangency_to_body() -> None:
    policy = RangeAndEarthOcclusionInterSatelliteContact()
    a = Vec3(-1000.0, BODY.radius_km, 0.0)
    b = Vec3(1000.0, BODY.radius_km, 0.0)
    assert policy.contact_distance(BODY, LinkLimits(10.0, 3000.0), a, b) is None


def test_isl_rejects_segment_crossing_earth() -> None:
    policy = RangeAndEarthOcclusionInterSatelliteContact()
    limits = LinkLimits(10.0, 20000.0)
    assert policy.contact_distance(BODY, limits, Vec3(7000.0, 0.0, 0.0), Vec3(-7000.0, 0.0, 0.0)) is None


def test_isl_accepts_clear_segment_inside_range() -> None:
    policy = RangeAndEarthOcclusionInterSatelliteContact()
    a = Vec3(7000.0, 0.0, 0.0)
    b = Vec3(7000.0, 1000.0, 0.0)
    assert math.isclose(policy.contact_distance(BODY, LinkLimits(10.0, 3000.0), a, b), 1000.0)
