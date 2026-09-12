from __future__ import annotations

import math
from typing import Literal

from pydantic import Field, model_validator

from .dto import NetworkProjectionDto, SceneFrameDto, StaticAnalysisDto, StrictModel


class SnapshotBundleDto(StrictModel):
    schema_version: Literal["model-snapshot-2.0"] = "model-snapshot-2.0"
    t_s: float
    scene: SceneFrameDto
    network: NetworkProjectionDto
    analysis: StaticAnalysisDto

    @model_validator(mode="after")
    def validate_times(self) -> "SnapshotBundleDto":
        if not math.isclose(self.scene.t_s, self.t_s, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("scene.t_s must match snapshot t_s")
        if not math.isclose(self.network.t_s, self.t_s, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("network.t_s must match snapshot t_s")
        return self


class SamplingRangeDto(StrictModel):
    start_s: float
    end_s: float
    step_s: float = Field(gt=0.0)

    @model_validator(mode="after")
    def validate_range(self) -> "SamplingRangeDto":
        if self.end_s <= self.start_s:
            raise ValueError("end_s must be greater than start_s")
        return self


class SampledTraceDto(StrictModel):
    schema_version: Literal["model-trace-2.0"] = "model-trace-2.0"
    sampling: SamplingRangeDto
    frames: list[SnapshotBundleDto]

    @model_validator(mode="after")
    def validate_frames(self) -> "SampledTraceDto":
        expected = []
        value = self.sampling.start_s
        while value < self.sampling.end_s:
            expected.append(value)
            value = self.sampling.start_s + len(expected) * self.sampling.step_s
        if len(expected) != len(self.frames):
            raise ValueError("trace must contain exactly one frame per requested sample")
        for index, (expected_t, frame) in enumerate(zip(expected, self.frames)):
            if not math.isclose(frame.t_s, expected_t, rel_tol=0.0, abs_tol=1e-10):
                raise ValueError(f"frame {index} does not match the sampling grid")
        return self
