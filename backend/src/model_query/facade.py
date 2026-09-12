from __future__ import annotations

from dataclasses import dataclass
import math

from spatial3d import (
    Err as SpatialErr,
    SpatialModel,
    project_network,
    project_scene,
)
from spatial_static_adapter import from_network_projection
from static_model import (
    Err as StaticErr,
    StaticAnalysisPlan,
    StaticComponents,
    StaticModel,
    validate_plan,
)

from .result import Err, Ok, QueryProblem, QueryProblemCode, QueryProblems, Result
from .types import SampledTrace, SamplingRange, SnapshotBundle


def _message(problems: tuple[object, ...]) -> str:
    return "; ".join(getattr(problem, "message", str(problem)) for problem in problems)


@dataclass(frozen=True, slots=True)
class ModelQuery:
    """Small application facade over spatial3d + static_model.

    It deliberately owns no geometry, routing, persistence, transport, or
    temporal-aggregation semantics. It only composes the existing components
    for two interactive UI query shapes: one exact snapshot and a finite sampled
    trace.
    """

    spatial_model: SpatialModel
    static_components: StaticComponents
    static_plan: StaticAnalysisPlan

    @classmethod
    def create(
        cls,
        spatial_model: SpatialModel,
        *,
        static_components: StaticComponents | None = None,
        static_plan: StaticAnalysisPlan | None = None,
    ) -> Result["ModelQuery", QueryProblems]:
        plan = static_plan or StaticAnalysisPlan.reference_case()
        valid = validate_plan(plan)
        if isinstance(valid, StaticErr):
            return Err(tuple(
                QueryProblem(
                    QueryProblemCode.INVALID_PLAN,
                    problem.message,
                    problem.path,
                )
                for problem in valid.error
            ))
        return Ok(cls(
            spatial_model=spatial_model,
            static_components=static_components or StaticComponents.reference_case(),
            static_plan=plan,
        ))

    def snapshot_at(self, t_s: float) -> Result[SnapshotBundle, QueryProblems]:
        spatial = self.spatial_model.snapshot(t_s)
        if isinstance(spatial, SpatialErr):
            return Err((QueryProblem(
                QueryProblemCode.SPATIAL_SNAPSHOT,
                _message(spatial.error),
                ("t_s",),
            ),))

        snapshot = spatial.value
        scene = project_scene(snapshot)
        network = project_network(snapshot)
        static_network = from_network_projection(network)

        model = StaticModel.create(
            static_network,
            components=self.static_components,
            plan=self.static_plan,
        )
        if isinstance(model, StaticErr):
            return Err((QueryProblem(
                QueryProblemCode.STATIC_MODEL,
                _message(model.error),
                ("analysis",),
            ),))

        analysis = model.value.analyze()
        if isinstance(analysis, StaticErr):
            return Err((QueryProblem(
                QueryProblemCode.STATIC_MODEL,
                _message(analysis.error),
                ("analysis",),
            ),))

        return Ok(SnapshotBundle(snapshot.t_s, scene, network, analysis.value))

    def sample_range(
        self,
        start_s: float,
        end_s: float,
        step_s: float,
    ) -> Result[SampledTrace, QueryProblems]:
        sampling_result = _sampling_range(start_s, end_s, step_s)
        if isinstance(sampling_result, Err):
            return sampling_result
        sampling = sampling_result.value

        frames: list[SnapshotBundle] = []
        for index, t_s in enumerate(sampling.sample_times):
            frame = self.snapshot_at(t_s)
            if isinstance(frame, Err):
                return Err(tuple(
                    QueryProblem(
                        problem.code,
                        problem.message,
                        ("frames", index, *problem.path),
                    )
                    for problem in frame.error
                ))
            frames.append(frame.value)

        return Ok(SampledTrace(sampling, tuple(frames)))


def _sampling_range(
    start_s: object,
    end_s: object,
    step_s: object,
) -> Result[SamplingRange, QueryProblems]:
    values: list[float] = []
    for field, number in (("start_s", start_s), ("end_s", end_s), ("step_s", step_s)):
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
            return Err((QueryProblem(
                QueryProblemCode.INVALID_RANGE,
                f"{field} must be a finite number",
                (field,),
            ),))
        values.append(float(number))

    value = SamplingRange(*values)
    if value.end_s <= value.start_s:
        return Err((QueryProblem(
            QueryProblemCode.INVALID_RANGE,
            "end_s must be greater than start_s",
            ("end_s",),
        ),))
    if value.step_s <= 0:
        return Err((QueryProblem(
            QueryProblemCode.INVALID_RANGE,
            "step_s must be positive",
            ("step_s",),
        ),))
    return Ok(value)
