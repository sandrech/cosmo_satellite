from typing import Generic, Iterable, Protocol, TypeVar

ScenarioT = TypeVar("ScenarioT")
FrameT = TypeVar("FrameT")


class StaticModel(Protocol, Generic[ScenarioT, FrameT]):
    """Reusable contract: calculate one independent frame at an exact t_s."""

    def calculate(self, scenario: ScenarioT, t_s: int) -> FrameT:
        ...


class DynamicModel(Protocol, Generic[ScenarioT, FrameT]):
    """Reusable contract: calculate a sequence by delegating every step."""

    def run(self, scenario: ScenarioT, time_grid: Iterable[int]) -> Iterable[FrameT]:
        ...
