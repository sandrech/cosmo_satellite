from dataclasses import replace

from spatial3d import (
    CircularOrbitAssignment,
    Err,
    Satellite,
    SpatialModel,
    SpatialProblemCode,
)
from .helpers import minimal_spec, minimal_trajectory


def test_missing_trajectory_assignment_is_model_error_value() -> None:
    spec = minimal_spec()
    trajectory = minimal_trajectory(spec)
    trajectory = replace(
        trajectory,
        configuration=replace(trajectory.configuration, assignments=()),
    )
    result = SpatialModel.create(spec, trajectory)
    assert isinstance(result, Err)
    assert any(problem.code == SpatialProblemCode.TRAJECTORY_BINDING for problem in result.error)


def test_unknown_trajectory_plane_is_model_error_value() -> None:
    spec = minimal_spec()
    trajectory = minimal_trajectory(spec)
    trajectory = replace(
        trajectory,
        configuration=replace(
            trajectory.configuration,
            assignments=(CircularOrbitAssignment("S1", "missing", 0.0),),
        ),
    )
    result = SpatialModel.create(spec, trajectory)
    assert isinstance(result, Err)
    assert any(problem.code == SpatialProblemCode.INVALID_REFERENCE for problem in result.error)


def test_duplicate_node_ids_rejected() -> None:
    spec = minimal_spec()
    spec = replace(spec, satellites=(Satellite("C1", 1),))
    result = SpatialModel.create(spec, minimal_trajectory(spec))
    assert isinstance(result, Err)
    assert any(problem.code == SpatialProblemCode.DUPLICATE_ID for problem in result.error)


def test_trajectory_and_spatial_body_must_match() -> None:
    from spatial3d import BodyConstants

    spec = minimal_spec()
    trajectory = minimal_trajectory(spec)
    trajectory = replace(trajectory, body=BodyConstants(7000.0))
    result = SpatialModel.create(spec, trajectory)
    assert isinstance(result, Err)
    assert any(problem.code == SpatialProblemCode.TRAJECTORY_BINDING for problem in result.error)
