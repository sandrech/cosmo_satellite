from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from dynamic_model import TimeGrid


@dataclass(frozen=True, slots=True)
class FocusWindow:
    index: int
    direction: int
    radius_frames: int


class ContextFrameScheduler:
    """Priority scheduler for an interactive time grid.

    Work closest to the current focus is selected first.  A focus radius forms
    the high-priority context window; outside it the remaining grid is filled in
    progressively.  Direction only breaks equal-distance ties, which gives a
    small predictive prefetch bias without starving the side behind the cursor.
    """

    def __init__(
        self,
        grid: TimeGrid,
        *,
        batch_size: int,
        focus_t_s: float = 0.0,
        focus_radius_s: float | None = None,
        direction: int = 0,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self._grid = grid
        self._batch_size = batch_size
        self._pending = set(range(grid.sample_count))
        self._version = 0
        self._focus = FocusWindow(0, 0, max(1, batch_size))
        self.update_focus(
            focus_t_s,
            radius_s=focus_radius_s,
            direction=direction,
        )

    @property
    def version(self) -> int:
        return self._version

    @property
    def focus(self) -> FocusWindow:
        return self._focus

    @property
    def focus_t_s(self) -> int:
        return self.time_for_index(self._focus.index)

    @property
    def remaining(self) -> int:
        return len(self._pending)

    @property
    def delivered(self) -> int:
        return self._grid.sample_count - len(self._pending)

    def time_for_index(self, index: int) -> int:
        return self._grid.start_s + index * self._grid.step_s

    def index_for_time(self, t_s: float) -> int:
        raw = round((float(t_s) - self._grid.start_s) / self._grid.step_s)
        return min(max(raw, 0), self._grid.sample_count - 1)

    def update_focus(
        self,
        t_s: float,
        *,
        radius_s: float | None = None,
        direction: int = 0,
    ) -> FocusWindow:
        radius_frames = (
            max(1, ceil(float(radius_s) / self._grid.step_s))
            if radius_s is not None and radius_s > 0
            else max(1, self._batch_size * 2)
        )
        normalized_direction = -1 if direction < 0 else 1 if direction > 0 else 0
        next_focus = FocusWindow(
            self.index_for_time(t_s),
            normalized_direction,
            radius_frames,
        )
        if next_focus != self._focus:
            self._focus = next_focus
            self._version += 1
        return self._focus

    def next_indices(self) -> tuple[int, ...]:
        if not self._pending:
            return ()
        focus = self._focus

        def score(index: int) -> tuple[int, int, int, int]:
            delta = index - focus.index
            distance = abs(delta)
            outside_window = int(distance > focus.radius_frames)
            wrong_direction = int(
                focus.direction != 0
                and delta != 0
                and (delta > 0) != (focus.direction > 0)
            )
            return outside_window, distance, wrong_direction, index

        return tuple(sorted(self._pending, key=score)[: self._batch_size])

    def mark_delivered(self, indices: tuple[int, ...] | list[int]) -> None:
        self._pending.difference_update(indices)

    def focus_is_delivered(self) -> bool:
        return self._focus.index not in self._pending
