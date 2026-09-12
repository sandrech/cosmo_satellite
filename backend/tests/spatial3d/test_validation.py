from dataclasses import replace

from spatial3d import Err, OrbitalPlane, Satellite, SpatialModel, SpatialProblemCode
from .helpers import minimal_spec


def test_unknown_plane_is_model_error_value() -> None:
    spec = minimal_spec()
    spec = replace(spec, satellites=(replace(spec.satellites[0], plane_id="missing"),))
    result = SpatialModel.create(spec)
    assert isinstance(result, Err)
    assert any(problem.code == SpatialProblemCode.UNKNOWN_PLANE for problem in result.error)


def test_duplicate_node_ids_rejected() -> None:
    spec = minimal_spec()
    spec = replace(spec, satellites=(Satellite("C1", "P1", 0.0, 1),))
    result = SpatialModel.create(spec)
    assert isinstance(result, Err)
    assert any(problem.code == SpatialProblemCode.DUPLICATE_ID for problem in result.error)
