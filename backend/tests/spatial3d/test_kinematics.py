import math

from spatial3d import SphericalGroundGeometry, Vec3
from .helpers import minimal_spec, minimal_trajectory


def test_reference_orbit_radius_is_preserved() -> None:
    spec = minimal_spec()
    trajectory = minimal_trajectory(spec)
    state = trajectory.state_at("S1", 12345.0)
    expected = spec.body.radius_km + trajectory.configuration.environment.altitude_km
    assert math.isclose(state.inertial_km.norm(), expected, abs_tol=1e-9)
    assert math.isclose(state.earth_fixed_km.norm(), expected, abs_tol=1e-9)


def test_t0_reference_formula_for_zero_raan_slot_phase() -> None:
    spec = minimal_spec()
    trajectory = minimal_trajectory(spec)
    state = trajectory.state_at("S1", 0.0)
    radius = 6921.0
    theta = math.radians(12.0)
    assert state.inertial_km == Vec3(radius, 0.0, 0.0)
    assert math.isclose(state.earth_fixed_km.x, radius * math.cos(theta), abs_tol=1e-10)
    assert math.isclose(state.earth_fixed_km.y, -radius * math.sin(theta), abs_tol=1e-10)
    assert math.isclose(state.earth_fixed_km.z, 0.0, abs_tol=1e-10)


def test_ground_point_lies_on_sphere() -> None:
    spec = minimal_spec()
    point = SphericalGroundGeometry().position(spec.body, spec.ground_sites[0])
    assert math.isclose(point.norm(), 6371.0, abs_tol=1e-9)
