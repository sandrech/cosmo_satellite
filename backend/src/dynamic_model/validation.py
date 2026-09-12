from __future__ import annotations

import math

from static_model import StaticAnalysisPlan

from .result import DynamicProblem, DynamicProblemCode, DynamicProblems, Err, Ok, Result
from .types import TimeGrid


def validate_grid(grid: TimeGrid) -> Result[None, DynamicProblems]:
    problems: list[DynamicProblem] = []
    for field, value in (("start_s", grid.start_s), ("end_s", grid.end_s), ("step_s", grid.step_s)):
        if isinstance(value, bool) or not isinstance(value, int):
            problems.append(DynamicProblem(
                DynamicProblemCode.INVALID_GRID,
                f"{field} must be an integer number of seconds",
                (field,),
            ))
    if problems:
        return Err(tuple(problems))
    if grid.start_s < 0:
        problems.append(DynamicProblem(DynamicProblemCode.INVALID_GRID, "start_s must be non-negative", ("start_s",)))
    if grid.end_s <= grid.start_s:
        problems.append(DynamicProblem(DynamicProblemCode.INVALID_GRID, "end_s must be greater than start_s", ("end_s",)))
    if grid.step_s <= 0:
        problems.append(DynamicProblem(DynamicProblemCode.INVALID_GRID, "step_s must be positive", ("step_s",)))
    if grid.step_s > 0 and grid.end_s > grid.start_s and (grid.end_s - grid.start_s) % grid.step_s != 0:
        problems.append(DynamicProblem(
            DynamicProblemCode.INVALID_GRID,
            "grid duration must be divisible by step_s",
            ("step_s",),
        ))
    return Err(tuple(problems)) if problems else Ok(None)


def validate_target(target_availability: float) -> Result[None, DynamicProblems]:
    if (
        isinstance(target_availability, bool)
        or not isinstance(target_availability, (int, float))
        or not math.isfinite(float(target_availability))
        or not 0.0 <= float(target_availability) <= 1.0
    ):
        return Err((DynamicProblem(
            DynamicProblemCode.INVALID_TARGET,
            "target_availability must be a finite value in [0, 1]",
            ("target_availability",),
        ),))
    return Ok(None)


def validate_static_plan(plan: StaticAnalysisPlan) -> Result[None, DynamicProblems]:
    problems: list[DynamicProblem] = []
    if not plan.compute_resilience:
        problems.append(DynamicProblem(
            DynamicProblemCode.INVALID_PLAN,
            "dynamic reference analysis requires static resilience at every sample",
            ("static_plan", "compute_resilience"),
        ))
    if not plan.compute_failure_impacts:
        problems.append(DynamicProblem(
            DynamicProblemCode.INVALID_PLAN,
            "dynamic satellite criticality requires static failure impacts at every sample",
            ("static_plan", "compute_failure_impacts"),
        ))
    return Err(tuple(problems)) if problems else Ok(None)
