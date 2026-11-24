from __future__ import annotations

from adapters.od_refrag_adapter import SpectralChunk, SpectralChunker as AdapterSpectralChunker


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _variance(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = _mean(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def _detect_change_points(
    data: list[float],
    *,
    min_segment_length: int,
    min_variance: float,
) -> list[int]:
    if len(data) < min_segment_length * 2:
        return []
    global_scale = (_variance(data) ** 0.5) or min_variance
    threshold = max(min_variance * 10.0, global_scale * 0.35)
    change_points: list[int] = []
    for idx in range(min_segment_length, len(data) - min_segment_length, min_segment_length):
        left = data[idx - min_segment_length : idx]
        right = data[idx : idx + min_segment_length]
        drift = abs(_mean(left) - _mean(right)) + abs((_variance(left) ** 0.5) - (_variance(right) ** 0.5))
        if drift >= threshold:
            change_points.append(idx)
    return change_points


def _segment_bounds(length: int, change_points: list[int]) -> list[tuple[int, int]]:
    points = [0] + sorted({point for point in change_points if 0 < point < length}) + [length]
    return [(start, end) for start, end in zip(points, points[1:]) if end > start]


def _make_chunk(
    source_id: str,
    start: int,
    end: int,
    values: list[float],
    sample_rate: float,
) -> SpectralChunk:
    return SpectralChunk(
        chunk_id=SpectralChunk.make_id(source_id, start, end),
        source_id=source_id,
        window_start=start,
        window_end=end,
        values=values,
        sample_rate=sample_rate,
    )


def execute(
    *,
    source_id: str,
    data: list[float],
    chunking_mode: str = "hybrid",
    window_size: int = 256,
    stride: int = 128,
    min_variance: float = 1e-8,
    sample_rate: float = 1.0,
    pelt_penalty: str = "bic",
    min_segment_length: int = 32,
) -> dict:
    if chunking_mode not in {"fixed", "adaptive", "hybrid"}:
        raise ValueError("chunking_mode must be fixed, adaptive, or hybrid")

    adapter_chunker = AdapterSpectralChunker(
        window_size=window_size,
        stride=stride,
        min_variance=min_variance,
    )
    change_points = _detect_change_points(
        data,
        min_segment_length=min_segment_length,
        min_variance=min_variance,
    )

    if chunking_mode == "fixed":
        chunks = adapter_chunker.chunk(source_id, data, sample_rate=sample_rate)
    else:
        chunks = []
        for start, end in _segment_bounds(len(data), change_points):
            segment_values = data[start:end]
            if chunking_mode == "adaptive" or len(segment_values) <= window_size:
                chunks.append(
                    _make_chunk(source_id, start, end, segment_values, sample_rate)
                )
                continue
            local_chunks = adapter_chunker.chunk(
                source_id,
                segment_values,
                sample_rate=sample_rate,
            )
            for chunk in local_chunks:
                chunk_start = start + chunk.window_start
                chunk_end = start + chunk.window_end
                chunks.append(
                    _make_chunk(
                        source_id,
                        chunk_start,
                        chunk_end,
                        data[chunk_start:chunk_end],
                        sample_rate,
                    )
                )

    global_std = _variance(data) ** 0.5 if data else 0.0
    avg_chunk_variance = (
        sum(_variance(chunk.values) for chunk in chunks) / max(1, len(chunks))
        if chunks
        else 0.0
    )
    segmentation_quality = 1.0
    if global_std > 0:
        segmentation_quality = min(1.0, max(0.0, avg_chunk_variance / (global_std ** 2 + 1e-12)))

    return {
        "chunks": chunks,
        "change_points": change_points,
        "segmentation_quality": round(segmentation_quality, 4),
        "metadata": {
            "chunking_mode": chunking_mode,
            "window_size": window_size,
            "stride": stride,
            "pelt_penalty": pelt_penalty,
            "min_segment_length": min_segment_length,
        },
    }
