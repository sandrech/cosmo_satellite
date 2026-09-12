from dynamic_model import DynamicModel, Err, TimeGrid


class NeverUsedSpatialModel:
    pass


def test_invalid_grid_is_a_value_error() -> None:
    result = DynamicModel.create(
        NeverUsedSpatialModel(),  # type: ignore[arg-type]
        TimeGrid(0, 25, 10),
        0.9,
    )
    assert isinstance(result, Err)
    assert result.error[0].code.value == "dynamic.invalid_grid"


def test_invalid_target_is_a_value_error() -> None:
    result = DynamicModel.create(
        NeverUsedSpatialModel(),  # type: ignore[arg-type]
        TimeGrid(0, 20, 10),
        1.1,
    )
    assert isinstance(result, Err)
    assert result.error[0].code.value == "dynamic.invalid_target"
