from __future__ import annotations

from json_component import MappedCodec, Ok
from json_component.pydantic_adapter import PydanticCodec
from model_query import SampledTrace, SamplingRange, SnapshotBundle

from .adapters import (
    network_from_dto,
    network_to_dto,
    network_to_jsonable,
    scene_from_dto,
    scene_to_dto,
    scene_to_jsonable,
    static_analysis_from_dto,
    static_analysis_to_dto,
    static_analysis_to_jsonable,
)
from .query_dto import SampledTraceDto, SamplingRangeDto, SnapshotBundleDto


def _ok(value):
    return Ok(value)


def snapshot_bundle_to_dto(value: SnapshotBundle) -> SnapshotBundleDto:
    return SnapshotBundleDto(
        t_s=value.t_s,
        scene=scene_to_dto(value.scene),
        network=network_to_dto(value.network),
        analysis=static_analysis_to_dto(value.analysis),
    )



def snapshot_bundle_to_jsonable(value: SnapshotBundle) -> dict[str, object]:
    """Fast trusted-output serializer for API hot paths."""
    return {
        "schema_version": "model-snapshot-2.0",
        "t_s": value.t_s,
        "scene": scene_to_jsonable(value.scene),
        "network": network_to_jsonable(value.network),
        "analysis": static_analysis_to_jsonable(value.analysis),
    }

def snapshot_bundle_from_dto(value: SnapshotBundleDto) -> SnapshotBundle:
    return SnapshotBundle(
        t_s=value.t_s,
        scene=scene_from_dto(value.scene),
        network=network_from_dto(value.network),
        analysis=static_analysis_from_dto(value.analysis),
    )


def snapshot_bundle_codec() -> MappedCodec[SnapshotBundle, SnapshotBundleDto]:
    return MappedCodec(
        storage=PydanticCodec.for_type(SnapshotBundleDto),
        from_storage=lambda value: _ok(snapshot_bundle_from_dto(value)),
        to_storage=lambda value: _ok(snapshot_bundle_to_dto(value)),
    )


def sampled_trace_to_dto(value: SampledTrace) -> SampledTraceDto:
    return SampledTraceDto(
        sampling=SamplingRangeDto(
            start_s=value.sampling.start_s,
            end_s=value.sampling.end_s,
            step_s=value.sampling.step_s,
        ),
        frames=[snapshot_bundle_to_dto(frame) for frame in value.frames],
    )


def sampled_trace_from_dto(value: SampledTraceDto) -> SampledTrace:
    return SampledTrace(
        sampling=SamplingRange(
            value.sampling.start_s,
            value.sampling.end_s,
            value.sampling.step_s,
        ),
        frames=tuple(snapshot_bundle_from_dto(frame) for frame in value.frames),
    )


def sampled_trace_codec() -> MappedCodec[SampledTrace, SampledTraceDto]:
    return MappedCodec(
        storage=PydanticCodec.for_type(SampledTraceDto),
        from_storage=lambda value: _ok(sampled_trace_from_dto(value)),
        to_storage=lambda value: _ok(sampled_trace_to_dto(value)),
    )


def encode_snapshot_bundle(value: SnapshotBundle):
    return snapshot_bundle_codec().encode(value)


def decode_snapshot_bundle(value):
    return snapshot_bundle_codec().decode(value)


def encode_sampled_trace(value: SampledTrace):
    return sampled_trace_codec().encode(value)


def decode_sampled_trace(value):
    return sampled_trace_codec().decode(value)
