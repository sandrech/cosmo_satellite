from __future__ import annotations

from dataclasses import dataclass
import math

from spatial3d import NetworkProjection, SceneFrame
from static_model import StaticAnalysis


@dataclass(frozen=True, slots=True)
class SnapshotBundle:
    """All frontend-facing model views for one exact model time."""

    t_s: float
    scene: SceneFrame
    network: NetworkProjection
    analysis: StaticAnalysis


@dataclass(frozen=True, slots=True)
class SamplingRange:
    """Half-open sampling range ``[start_s, end_s)`` for playback frames.

    This is intentionally independent from the scenario's official calculation
    grid. It is a query/presentation sampling contract: callers may request a
    denser or sparser range without changing the mathematical model itself.
    """

    start_s: float
    end_s: float
    step_s: float

    @property
    def sample_times(self) -> tuple[float, ...]:
        duration = self.end_s - self.start_s
        count = max(0, math.ceil(duration / self.step_s))
        result = tuple(self.start_s + index * self.step_s for index in range(count))
        return tuple(value for value in result if value < self.end_s)

    @property
    def sample_count(self) -> int:
        return len(self.sample_times)


@dataclass(frozen=True, slots=True)
class SampledTrace:
    """A finite sequence of complete snapshot bundles for UI playback."""

    sampling: SamplingRange
    frames: tuple[SnapshotBundle, ...]
