"""
od_refrag_adapter.py
DavisAI Systems — Operator Discovery adapter for the refrag compress-sense-expand pipeline.

This module provides the interface layer between refrag's retrieval pipeline and OD's
spectral operator discovery engine. It replaces text-oriented chunking and encoding
with spectral-native equivalents while preserving refrag's retrieval, selection,
and mixed-prompt architecture unchanged.

Architecture:
    Raw Data (.npy) → SpectralChunker → SpectralChunkEncoder → [MLPProjector] →
    FaissIndex → SimilaritySelector → build_mixed_prompt → OperatorDecoder

Drop-in replacements:
    chunk_tokens        → SpectralChunker.chunk()
    SimpleChunkEncoder  → SpectralChunkEncoder
    TinyDecoderModel    → OperatorDecoder (candidate operator generation)
    _text_to_token_ids  → (eliminated — raw numerical data, no tokenization)

Usage:
    from od_refrag_adapter import SpectralChunker, SpectralChunkEncoder, OperatorQuery

    chunker = SpectralChunker(window_size=256, stride=128)
    encoder = SpectralChunkEncoder(d_enc=64)
    # Then plug into existing refrag pipeline: projector → index → selector → decode
"""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass, field
from typing import Any, Protocol


SPECTRAL_SUMMARY_FEATURES: tuple[str, ...] = (
    "mean",
    "std",
    "spectral_energy",
    "spectral_entropy",
    "peak_frequency",
    "spectral_centroid",
)


def spectral_feature_registry(d_enc: int) -> tuple[str, ...]:
    """Return the exact named output order for one spectral encoder.

    The registry is generated from the encoder's configured dimension rather
    than restating a vector width in a downstream consumer.  ReFRAG therefore
    remains the single owner of both feature order and feature cardinality.
    """
    if isinstance(d_enc, bool) or not isinstance(d_enc, int):
        raise TypeError("d_enc must be an integer")
    if d_enc < len(SPECTRAL_SUMMARY_FEATURES):
        raise ValueError(
            "d_enc must accommodate every named spectral summary feature"
        )
    return SPECTRAL_SUMMARY_FEATURES + tuple(
        f"spectral_coefficient_{index}"
        for index in range(d_enc - len(SPECTRAL_SUMMARY_FEATURES))
    )


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SpectralChunk:
    """One windowed segment of raw numerical data — analogous to refrag's Chunk."""
    chunk_id: str
    source_id: str          # e.g. "spin-boson-0042.npy"
    window_start: int
    window_end: int
    values: list[float]     # raw data within the window
    sample_rate: float = 1.0

    @staticmethod
    def make_id(source_id: str, window_start: int, window_end: int) -> str:
        """Deterministic chunk ID keyed by source + window parameters.

        Mirrors refrag's deterministic chunk_id scheme but includes window
        params so the embedding cache survives across operator sweeps.
        """
        raw = f"{source_id}:{window_start}:{window_end}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class SpectralFeatures:
    """Feature vector extracted from a SpectralChunk — replaces token statistics."""
    mean: float
    std: float
    spectral_energy: float      # total power in frequency domain
    spectral_entropy: float     # spread of frequency content
    peak_frequency: float       # dominant frequency component
    spectral_centroid: float    # center of mass of spectrum
    coefficients: list[float]   # downsampled spectral coefficients


@dataclass
class OperatorCandidate:
    """A candidate operator used as a 'query' against the spectral index.

    In refrag text mode, the query is a text string embedded for similarity search.
    In OD mode, the query is a candidate operator whose spectral signature we
    match against data regions to find where it's most testable/falsifiable.
    """
    operator_id: str
    spectral_signature: list[float]   # projected into same space as chunk embeds
    coefficients: dict[str, float] = field(default_factory=dict)
    source_domain: str = ""


# ---------------------------------------------------------------------------
# SpectralChunker — replaces chunk_tokens
# ---------------------------------------------------------------------------

class SpectralChunker:
    """Window-based segmentation of raw numerical data.

    Replaces refrag's text chunking. Instead of splitting on token boundaries,
    this splits time-series or spatial data into overlapping windows.

    Args:
        window_size: Number of samples per chunk.
        stride: Step between consecutive windows. stride < window_size = overlap.
        min_variance: Minimum variance threshold. Windows below this are
            tagged as low-information (thermal equilibrium / noise floor).
    """

    def __init__(
        self,
        window_size: int = 256,
        stride: int = 128,
        min_variance: float = 1e-8,
    ):
        self.window_size = window_size
        self.stride = stride
        self.min_variance = min_variance

    def chunk(self, source_id: str, data: list[float], sample_rate: float = 1.0) -> list[SpectralChunk]:
        """Segment raw data into overlapping SpectralChunks.

        Returns:
            List of SpectralChunks. Low-variance windows are included but
            can be filtered downstream by the selector.
        """
        chunks: list[SpectralChunk] = []
        n = len(data)
        if n == 0:
            return chunks

        pos = 0
        while pos + self.window_size <= n:
            window = data[pos : pos + self.window_size]
            chunk_id = SpectralChunk.make_id(source_id, pos, pos + self.window_size)
            chunks.append(SpectralChunk(
                chunk_id=chunk_id,
                source_id=source_id,
                window_start=pos,
                window_end=pos + self.window_size,
                values=window,
                sample_rate=sample_rate,
            ))
            pos += self.stride

        # Handle trailing data if it has meaningful length
        remainder = n - pos
        if remainder >= self.window_size // 4:
            window = data[pos:]
            chunk_id = SpectralChunk.make_id(source_id, pos, n)
            chunks.append(SpectralChunk(
                chunk_id=chunk_id,
                source_id=source_id,
                window_start=pos,
                window_end=n,
                values=window,
                sample_rate=sample_rate,
            ))

        return chunks


# ---------------------------------------------------------------------------
# SpectralChunkEncoder — replaces SimpleChunkEncoder
# ---------------------------------------------------------------------------

class SpectralChunkEncoder:
    """Extracts spectral features from data chunks — replaces SimpleChunkEncoder.

    The original encoder computed [mean, std, min, max] + cyclic token resampling.
    This computes [mean, std, spectral_energy, spectral_entropy, peak_freq,
    spectral_centroid] + downsampled spectral coefficients.

    Args:
        d_enc: Total embedding dimension. First 6 dims are summary features,
            remaining (d_enc - 6) are downsampled spectral coefficients.
    """

    def __init__(self, d_enc: int = 64):
        self.d_enc = d_enc
        self.feature_registry = spectral_feature_registry(d_enc)
        self.n_summary = len(SPECTRAL_SUMMARY_FEATURES)

    def _fft_magnitudes(self, values: list[float]) -> list[float]:
        """Compute FFT magnitude spectrum (real-valued DFT via pure Python).

        For production, replace with numpy.fft. This is sandbox-compatible.
        """
        n = len(values)
        if n == 0:
            return []
        # Only need positive frequencies
        n_freq = n // 2 + 1
        magnitudes = []
        for k in range(n_freq):
            re = sum(values[j] * math.cos(2.0 * math.pi * k * j / n) for j in range(n))
            im = sum(values[j] * math.sin(2.0 * math.pi * k * j / n) for j in range(n))
            magnitudes.append(math.sqrt(re * re + im * im) / n)
        return magnitudes

    def _extract_features(self, values: list[float], sample_rate: float = 1.0) -> SpectralFeatures:
        """Extract spectral feature set from a single chunk's raw values."""
        n = len(values)
        if n == 0:
            return SpectralFeatures(
                mean=0.0, std=0.0, spectral_energy=0.0,
                spectral_entropy=0.0, peak_frequency=0.0,
                spectral_centroid=0.0, coefficients=[],
            )

        # Time-domain statistics
        mean = sum(values) / n
        var = sum((v - mean) ** 2 for v in values) / n
        std = math.sqrt(var)

        # Frequency-domain features
        mags = self._fft_magnitudes(values)
        if not mags:
            return SpectralFeatures(
                mean=mean, std=std, spectral_energy=0.0,
                spectral_entropy=0.0, peak_frequency=0.0,
                spectral_centroid=0.0, coefficients=[],
            )

        spectral_energy = sum(m * m for m in mags)

        # Spectral entropy (normalized)
        total_mag = sum(mags)
        if total_mag > 0:
            probs = [m / total_mag for m in mags]
            spectral_entropy = -sum(
                p * math.log(p + 1e-12) for p in probs
            ) / math.log(len(mags) + 1)
        else:
            spectral_entropy = 0.0

        # Peak frequency
        peak_idx = max(range(len(mags)), key=lambda i: mags[i])
        freq_resolution = sample_rate / n
        peak_frequency = peak_idx * freq_resolution

        # Spectral centroid
        freq_bins = [i * freq_resolution for i in range(len(mags))]
        if total_mag > 0:
            spectral_centroid = sum(f * m for f, m in zip(freq_bins, mags)) / total_mag
        else:
            spectral_centroid = 0.0

        return SpectralFeatures(
            mean=mean,
            std=std,
            spectral_energy=spectral_energy,
            spectral_entropy=spectral_entropy,
            peak_frequency=peak_frequency,
            spectral_centroid=spectral_centroid,
            coefficients=mags,
        )

    def encode(self, chunks: list[SpectralChunk]) -> list[list[float]]:
        """Encode a batch of SpectralChunks into fixed-dimension vectors.

        Drop-in replacement for SimpleChunkEncoder.encode().
        Returns list of d_enc-dimensional vectors.
        """
        n_coeff = self.d_enc - self.n_summary
        out: list[list[float]] = []

        for chunk in chunks:
            feat = self._extract_features(chunk.values, chunk.sample_rate)

            # Summary features (6 dims)
            summary = [
                feat.mean,
                feat.std,
                feat.spectral_energy,
                feat.spectral_entropy,
                feat.peak_frequency,
                feat.spectral_centroid,
            ]

            # Downsampled spectral coefficients (d_enc - 6 dims)
            coeffs = feat.coefficients
            if n_coeff == 0:
                resampled = []
            elif len(coeffs) == 0:
                resampled = [0.0] * n_coeff
            elif len(coeffs) <= n_coeff:
                # Pad with zeros
                resampled = coeffs + [0.0] * (n_coeff - len(coeffs))
            else:
                # Downsample by strided selection
                step = len(coeffs) / n_coeff
                resampled = [coeffs[int(i * step)] for i in range(n_coeff)]

            # Normalize spectral coefficients to [0, 1] range
            max_coeff = max(abs(c) for c in resampled) if resampled else 1.0
            if max_coeff > 0:
                resampled = [c / max_coeff for c in resampled]

            out.append(summary + resampled)

        return out


OD_FEATURE_REGISTRY: tuple[str, ...] = SpectralChunkEncoder().feature_registry


# ---------------------------------------------------------------------------
# OperatorQuery — replaces text query embedding
# ---------------------------------------------------------------------------

class OperatorQuery:
    """Builds a query embedding from a candidate operator for index search.

    In refrag text mode: query_text → token_ids → encoder → projector → query_embed
    In OD mode: candidate operator → spectral signature → query_embed

    The query asks: 'which data regions are most relevant for validating
    or falsifying this candidate operator?'
    """

    def __init__(self, d_enc: int = 64):
        self.d_enc = d_enc
        self.feature_registry = spectral_feature_registry(d_enc)

    def from_candidate(self, candidate: OperatorCandidate) -> list[float]:
        """Convert a candidate operator into a query vector.

        The spectral_signature should already be in the same embedding space
        as the chunk encodings (post-encoder, pre-projector). If not,
        pad/truncate to d_enc.
        """
        sig = candidate.spectral_signature
        if len(sig) >= self.d_enc:
            return sig[: self.d_enc]
        return sig + [0.0] * (self.d_enc - len(sig))

    def from_spectral_target(
        self,
        target_frequencies: list[float],
        target_energy: float,
        sample_rate: float = 1.0,
    ) -> list[float]:
        """Build a query targeting specific spectral characteristics.

        Useful for exploring: 'find me data regions with energy concentrated
        near these frequencies' — e.g., searching for resonance signatures.
        """
        n_coeff = self.d_enc - len(SPECTRAL_SUMMARY_FEATURES)
        summary = [
            0.0,                # mean (don't care)
            0.0,                # std (don't care)
            target_energy,      # spectral_energy (match this)
            0.5,                # spectral_entropy (moderate spread)
            target_frequencies[0] if target_frequencies else 0.0,
            sum(target_frequencies) / len(target_frequencies) if target_frequencies else 0.0,
        ]

        if n_coeff == 0:
            return summary

        # Build synthetic spectral profile peaked at target frequencies
        freq_resolution = sample_rate / (2.0 * n_coeff)
        coeff_profile = [0.0] * n_coeff
        for tf in target_frequencies:
            idx = min(int(tf / freq_resolution), n_coeff - 1) if freq_resolution > 0 else 0
            coeff_profile[idx] = 1.0

        return summary + coeff_profile


# ---------------------------------------------------------------------------
# OperatorDecoder — replaces TinyDecoderModel for OD
# ---------------------------------------------------------------------------

class OperatorDecoder:
    """Generates candidate operator components from mixed prefill embeddings.

    Replaces TinyDecoderModel. Instead of generating text token IDs,
    this generates candidate operator coefficients or spectral components.

    In production, this wraps the actual OD spectral recovery engine.
    This sandbox version provides a deterministic stub.
    """

    def prefill(self, prefill_embeds: list[list[float]], prefill_mask: list[int]) -> list[float]:
        """Ingest mixed compressed/expanded data and produce initial operator estimate.

        Returns:
            Initial coefficient vector for the candidate operator.
        """
        if not prefill_embeds:
            return [0.0]

        # Sandbox stub: extract dominant features from the prefill
        d = len(prefill_embeds[0]) if prefill_embeds else 1
        # Weighted mean across all prefill vectors (masked)
        accum = [0.0] * d
        weight_total = 0.0
        for emb, mask in zip(prefill_embeds, prefill_mask):
            if mask:
                for j in range(d):
                    accum[j] += emb[j]
                weight_total += 1.0

        if weight_total > 0:
            accum = [a / weight_total for a in accum]

        return accum

    def refine(self, initial: list[float], n_iterations: int = 4) -> list[float]:
        """Iterative refinement of operator coefficients.

        Stub for the actual falsification-refinement loop where OD
        tests and adjusts the candidate operator against the data.
        """
        current = list(initial)
        for step in range(n_iterations):
            # Placeholder: damped adjustment
            norm = math.sqrt(sum(c * c for c in current) + 1e-12)
            current = [c / norm for c in current]
        return current


# ---------------------------------------------------------------------------
# Cache key strategy for OD
# ---------------------------------------------------------------------------

def make_cache_key(source_id: str, window_start: int, window_end: int, encoder_version: str = "v1") -> str:
    """Generate cache key for spectral embeddings.

    Keyed by data source + window parameters + encoder version so:
    - Same window across different operator sweeps → cache hit
    - Encoder upgrade → cache miss (recompute)
    - Different window params on same source → cache miss
    """
    raw = f"{encoder_version}:{source_id}:{window_start}:{window_end}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


# ---------------------------------------------------------------------------
# Integration example: OD-adapted e2e pipeline
# ---------------------------------------------------------------------------

def run_od_e2e_example():
    """Demonstrates the full OD-adapted refrag pipeline.

    This mirrors run_e2e_pipeline.py but with spectral data and operator queries
    instead of text documents and text queries.

    In production, replace:
      - synthetic_data with actual .npy file loading
      - OperatorDecoder stub with OD spectral recovery engine
      - Print statements with MASTER_DISCOVERIES.json logging
    """

    # --- Configuration ---
    d_enc = 64
    window_size = 64       # smaller for demo
    stride = 32
    top_k = 4
    expand_budget = 2

    # --- Simulate raw data (replace with np.load in production) ---
    import random
    random.seed(42)
    sources = {
        "spin-boson-0001": [math.sin(0.1 * t) + 0.3 * math.sin(0.47 * t) + random.gauss(0, 0.05) for t in range(512)],
        "spin-boson-0002": [math.cos(0.2 * t) * math.exp(-0.005 * t) + random.gauss(0, 0.02) for t in range(512)],
        "spin-boson-0003": [random.gauss(0, 0.1) for _ in range(512)],  # noise / thermal equilibrium
    }

    # --- Chunk ---
    chunker = SpectralChunker(window_size=window_size, stride=stride)
    all_chunks: list[SpectralChunk] = []
    for source_id, data in sources.items():
        all_chunks.extend(chunker.chunk(source_id, data))

    # --- Encode ---
    encoder = SpectralChunkEncoder(d_enc=d_enc)
    chunk_embeds = encoder.encode(all_chunks)

    # --- Build index (reuse refrag's FaissIndex interface) ---
    # In production: index = FaissIndex(dim=d_enc, backend="python")
    # index.add(chunk_embeds)
    # For this standalone demo, we do brute-force search:
    def cosine_sim(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a) + 1e-12)
        nb = math.sqrt(sum(x * x for x in b) + 1e-12)
        return dot / (na * nb)

    # --- Query: build from candidate operator targeting ~0.1 Hz and ~0.47 Hz ---
    query_builder = OperatorQuery(d_enc=d_enc)
    query_embed = query_builder.from_spectral_target(
        target_frequencies=[0.1, 0.47],
        target_energy=1.0,
    )

    # --- Retrieve top-k ---
    scores = [(i, cosine_sim(query_embed, emb)) for i, emb in enumerate(chunk_embeds)]
    scores.sort(key=lambda x: x[1], reverse=True)
    hits = scores[:top_k]

    # --- Select which to expand ---
    # Top expand_budget by score get full expansion
    expand_indices = set(range(expand_budget))

    # --- Report ---
    print(f"Total chunks: {len(all_chunks)}")
    print(f"Top-{top_k} retrieved:")
    for rank, (idx, score) in enumerate(hits):
        chunk = all_chunks[idx]
        mode = "EXPAND" if rank in expand_indices else "COMPRESS"
        print(f"  [{mode}] {chunk.source_id} [{chunk.window_start}:{chunk.window_end}] score={score:.4f}")

    # --- Decode (operator recovery from mixed prefill) ---
    decoder = OperatorDecoder()
    retrieved_embeds = [chunk_embeds[idx] for idx, _ in hits]
    # Mixed prefill: expanded chunks get full embedding, compressed stay as-is
    prefill = []
    mask = []
    for rank, (idx, _) in enumerate(hits):
        if rank in expand_indices:
            # Expanded: use raw values as additional "token-level" embeddings
            for v in all_chunks[idx].values[:16]:  # truncate for demo
                prefill.append([v] + [0.0] * (d_enc - 1))
                mask.append(1)
        else:
            prefill.append(chunk_embeds[idx])
            mask.append(1)

    initial_operator = decoder.prefill(prefill, mask)
    refined_operator = decoder.refine(initial_operator, n_iterations=8)
    print(f"Operator coefficients (first 8): {[f'{c:.4f}' for c in refined_operator[:8]]}")
    print("--- Pipeline complete ---")


if __name__ == "__main__":
    run_od_e2e_example()
