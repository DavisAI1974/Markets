from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from adapters.od_refrag_adapter import SpectralChunk


@dataclass(frozen=True)
class EncodedChunk:
    chunk: SpectralChunk
    embedding: list[float]
    uncertainty: float


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: SpectralChunk
    embedding: list[float]
    score: float
    rank: int
    information_gain: float = 0.0


@dataclass(frozen=True)
class StageTrace:
    stage: str
    wall_time_ms: float
    input_size: int
    output_size: int
    status: str
    error: str | None = None


@dataclass
class PipelineArtifacts:
    run_id: str
    traces: list[StageTrace] = field(default_factory=list)
    outputs: dict[str, Any] = field(default_factory=dict)
