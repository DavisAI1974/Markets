"""
markets_adapter.py
DavisAI Systems - Markets adapter for the deepnova/refrag operator-discovery
pipeline.

Mirrors od_refrag_adapter.py exactly so deepnova's runtime/control plane
(decoder, evidence graph, falsification prioritizer, manifest synthesizer,
lifecycle tracker, transfer detector, etc.) operates on market data without
any registry/governance changes.

Drop-in mappings (OD -> markets):
    SpectralChunker      -> MarketChunker        (PELT regime-aware windows)
    SpectralChunkEncoder -> MarketChunkEncoder   (spectral + microstructure)
    OperatorQuery        -> MarketQuery          (regime / signature / spectral targets)
    OperatorDecoder      -> SignalDecoder        (Bayesian coefficient stub)

Trading frame (alpha-discovery as operator-discovery):
    "operator"     = parameterized signal function with coefficients
    "recovery"     = fit coefficients on a training window
    "discovery"    = manifest_synthesizer proposes a new signal composition
    "evidence"     = backtest result on an OOS window
    "domain"       = asset / venue / regime
    "ground truth" = realized P&L (a label markets have that physics doesn't)

Run the demo:
    python markets_adapter.py
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class MarketBar:
    """One time-binned market observation. Optional fields default to 0.0."""
    ts: float
    close: float
    open_: float = 0.0
    high: float = 0.0
    low: float = 0.0
    volume: float = 0.0
    buy_vol: float = 0.0
    sell_vol: float = 0.0

    @property
    def mid(self) -> float:
        return self.close

    @property
    def ofi(self) -> float:
        return self.buy_vol - self.sell_vol

    @property
    def dipole(self) -> float:
        s = self.buy_vol + self.sell_vol
        return (self.buy_vol - self.sell_vol) / (s + 1e-9) if s > 0 else 0.0


@dataclass
class MarketChunk:
    """Regime-aware windowed segment of market bars."""
    chunk_id: str
    source_id: str
    window_start: int
    window_end: int
    bars: list[MarketBar]
    realized_vol: float = 0.0
    bic_segment_score: float = 0.0

    @staticmethod
    def make_id(source_id: str, window_start: int, window_end: int) -> str:
        raw = f"{source_id}:{window_start}:{window_end}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class MarketFeatures:
    """Feature vector extracted from a MarketChunk."""
    ret_mean: float
    ret_std: float
    ret_skew: float
    ret_kurt: float
    autocorr_lag1: float
    mean_dipole: float
    mean_ofi: float
    volume_zscore: float
    realized_vol: float
    range_atr: float
    spectral_energy: float
    spectral_entropy: float
    peak_frequency: float
    spectral_centroid: float
    coefficients: list[float]


@dataclass
class SignalCandidate:
    """A candidate alpha signal - analogous to OperatorCandidate."""
    signal_id: str
    spectral_signature: list[float]
    coefficients: dict[str, float] = field(default_factory=dict)
    source_market: str = ""


# ---------------------------------------------------------------------------
# FeatureScaler (per-dim z-score; fit on chunk corpus, apply to chunks + queries)
# ---------------------------------------------------------------------------

class FeatureScaler:
    """Per-dimension z-score normalization across a chunk corpus.

    Fit once on a representative chunk corpus; apply to every embedding
    (chunks AND queries) before similarity search. Without this, cosine
    similarity is dominated by whichever feature has the largest absolute
    magnitude (the FFT coefficient block in the default 64-dim layout).

    Sklearn-style fit/transform; no sklearn dependency.
    """

    def __init__(self, eps: float = 1e-9):
        self.eps = eps
        self.mean: Optional[np.ndarray] = None
        self.std: Optional[np.ndarray] = None

    def fit(self, embeddings: list[list[float]]) -> "FeatureScaler":
        if not embeddings:
            return self
        arr = np.asarray(embeddings, dtype=float)
        self.mean = arr.mean(axis=0)
        self.std = arr.std(axis=0)
        return self

    def transform(self, embedding: list[float]) -> list[float]:
        if self.mean is None or self.std is None:
            return list(embedding)
        v = (np.asarray(embedding, dtype=float) - self.mean) / (self.std + self.eps)
        return v.tolist()

    def transform_batch(self, embeddings: list[list[float]]) -> list[list[float]]:
        if self.mean is None or self.std is None:
            return [list(e) for e in embeddings]
        arr = (np.asarray(embeddings, dtype=float) - self.mean) / (self.std + self.eps)
        return arr.tolist()

    @property
    def is_fitted(self) -> bool:
        return self.mean is not None and self.std is not None


# ---------------------------------------------------------------------------
# PELT change-point detection (normal mean+variance, BIC penalty)
# ---------------------------------------------------------------------------

def _segment_cost(values: np.ndarray, s: int, t: int) -> float:
    """Cost of segment values[s:t] under normal MLE: n * log(var)."""
    n = t - s
    if n < 2:
        return 0.0
    var = float(np.var(values[s:t]))
    if var <= 1e-12:
        return 0.0
    return n * math.log(var)


def pelt_change_points(
    values: np.ndarray,
    min_segment: int = 16,
    penalty: Optional[float] = None,
) -> list[int]:
    """PELT change-point detection. Returns sorted change-point indices (exclusive of 0 and n)."""
    n = len(values)
    if n < 2 * min_segment:
        return []
    if penalty is None:
        penalty = 2.0 * math.log(n)

    F = np.full(n + 1, np.inf)
    F[0] = -penalty
    last_cp = [0] * (n + 1)
    R: list[int] = [0]

    for t in range(min_segment, n + 1):
        best = np.inf
        best_s = 0
        for s in R:
            if t - s < min_segment:
                continue
            c = F[s] + _segment_cost(values, s, t) + penalty
            if c < best:
                best = c
                best_s = s
        if best < F[t]:
            F[t] = best
            last_cp[t] = best_s
        # Prune: keep s if F[s] + cost(s,t) <= F[t]
        R = [s for s in R if F[s] + _segment_cost(values, s, t) <= F[t]]
        R.append(t)

    cps: list[int] = []
    cur = n
    while cur > 0:
        prev = last_cp[cur]
        if 0 < prev < n:
            cps.append(prev)
        if prev == cur:
            break
        cur = prev
    return sorted(cps)


# ---------------------------------------------------------------------------
# MarketChunker (PELT regime-aware)
# ---------------------------------------------------------------------------

class MarketChunker:
    """Window-based segmentation of market bars with PELT regime alignment.

    Modes:
        fixed:    sliding window of max_window_size with stride
        adaptive: PELT change-point segmentation only
        hybrid:   PELT for boundaries; long segments subdivided into fixed windows
    """

    def __init__(
        self,
        max_window_size: int = 256,
        stride: int = 128,
        min_segment: int = 16,
        mode: str = "hybrid",
    ):
        if mode not in ("fixed", "adaptive", "hybrid"):
            raise ValueError(f"unknown chunking mode: {mode}")
        self.max_window_size = max_window_size
        self.stride = stride
        self.min_segment = min_segment
        self.mode = mode

    def chunk(self, source_id: str, bars: list[MarketBar]) -> list[MarketChunk]:
        if not bars:
            return []
        if self.mode == "fixed":
            return self._chunk_fixed(source_id, bars)

        closes = np.array([b.close for b in bars], dtype=float)
        log_ret = np.diff(np.log(np.maximum(closes, 1e-12)))
        cps = pelt_change_points(log_ret, min_segment=self.min_segment)
        bar_cps = [c + 1 for c in cps]
        boundaries = [0] + bar_cps + [len(bars)]

        chunks: list[MarketChunk] = []
        for i in range(len(boundaries) - 1):
            s, e = boundaries[i], boundaries[i + 1]
            if e - s < self.min_segment:
                continue
            if self.mode == "hybrid" and (e - s) > self.max_window_size:
                pos = s
                while pos + self.max_window_size <= e:
                    chunks.append(self._make_chunk(source_id, bars, pos, pos + self.max_window_size))
                    pos += self.stride
                if e - pos >= self.min_segment:
                    chunks.append(self._make_chunk(source_id, bars, pos, e))
            else:
                end = min(s + self.max_window_size, e) if self.mode == "adaptive" else e
                chunks.append(self._make_chunk(source_id, bars, s, end))
        return chunks

    def _chunk_fixed(self, source_id: str, bars: list[MarketBar]) -> list[MarketChunk]:
        chunks: list[MarketChunk] = []
        n = len(bars)
        pos = 0
        while pos + self.max_window_size <= n:
            chunks.append(self._make_chunk(source_id, bars, pos, pos + self.max_window_size))
            pos += self.stride
        if n - pos >= self.max_window_size // 4:
            chunks.append(self._make_chunk(source_id, bars, pos, n))
        return chunks

    def _make_chunk(self, source_id: str, bars: list[MarketBar], s: int, e: int) -> MarketChunk:
        seg = bars[s:e]
        closes = np.array([b.close for b in seg], dtype=float)
        if len(closes) >= 2:
            log_ret = np.diff(np.log(np.maximum(closes, 1e-12)))
            rv = float(np.std(log_ret))
        else:
            rv = 0.0
        return MarketChunk(
            chunk_id=MarketChunk.make_id(source_id, s, e),
            source_id=source_id,
            window_start=s,
            window_end=e,
            bars=seg,
            realized_vol=rv,
        )


# ---------------------------------------------------------------------------
# MarketChunkEncoder (spectral + microstructure features)
# ---------------------------------------------------------------------------

class MarketChunkEncoder:
    """Extracts spectral + microstructure features from MarketChunks.

    Embedding layout (d_enc dims):
        [0:11]   summary stats:        ret_mean, ret_std, ret_skew, ret_kurt,
                                       autocorr_lag1, mean_dipole, mean_ofi,
                                       volume_zscore, realized_vol, range_atr,
                                       spectral_energy
        [11:14]  spectral summary:     spectral_entropy, peak_frequency,
                                       spectral_centroid
        [14:]    downsampled FFT magnitudes (normalized to [0,1])
    """

    def __init__(self, d_enc: int = 64):
        self.d_enc = d_enc
        self.n_summary = 11
        self.n_spectral_block = 3

    def _extract(self, chunk: MarketChunk) -> MarketFeatures:
        bars = chunk.bars
        n = len(bars)
        if n < 2:
            return MarketFeatures(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, [])

        closes = np.array([b.close for b in bars], dtype=float)
        log_ret = np.diff(np.log(np.maximum(closes, 1e-12)))

        ret_mean = float(np.mean(log_ret))
        ret_std = float(np.std(log_ret))
        if ret_std > 1e-12:
            centered = (log_ret - ret_mean) / ret_std
            ret_skew = float(np.mean(centered ** 3))
            ret_kurt = float(np.mean(centered ** 4) - 3.0)
        else:
            ret_skew = 0.0
            ret_kurt = 0.0

        if len(log_ret) >= 3 and ret_std > 1e-12:
            r0 = log_ret[:-1] - ret_mean
            r1 = log_ret[1:] - ret_mean
            denom = float(np.sum((log_ret - ret_mean) ** 2)) + 1e-12
            autocorr = float(np.sum(r0 * r1) / denom)
        else:
            autocorr = 0.0

        dipoles = [b.dipole for b in bars]
        ofis = [b.ofi for b in bars]
        mean_dipole = float(np.mean(dipoles))
        mean_ofi = float(np.mean(ofis))

        volumes = np.array([b.volume for b in bars], dtype=float)
        vstd = float(np.std(volumes))
        vol_z = float((volumes[-1] - np.mean(volumes)) / vstd) if vstd > 1e-12 else 0.0

        highs = np.array([b.high for b in bars], dtype=float)
        lows = np.array([b.low for b in bars], dtype=float)
        if np.any(highs > 0) and np.any(lows > 0):
            ranges = (highs - lows) / np.maximum(closes, 1e-12)
            range_atr = float(np.mean(ranges))
        else:
            range_atr = 0.0

        if len(log_ret) >= 4:
            mags = np.abs(np.fft.rfft(log_ret - ret_mean)) / (len(log_ret) + 1e-12)
            spectral_energy = float(np.sum(mags ** 2))
            total_mag = float(np.sum(mags))
            if total_mag > 1e-12:
                probs = mags / total_mag
                spectral_entropy = float(-np.sum(probs * np.log(probs + 1e-12)) / math.log(len(mags) + 1))
                peak_idx = int(np.argmax(mags))
                peak_frequency = peak_idx / len(log_ret)
                freq_bins = np.arange(len(mags)) / len(log_ret)
                spectral_centroid = float(np.sum(freq_bins * mags) / total_mag)
            else:
                spectral_entropy = 0.0
                peak_frequency = 0.0
                spectral_centroid = 0.0
            coefficients = mags.tolist()
        else:
            spectral_energy = 0.0
            spectral_entropy = 0.0
            peak_frequency = 0.0
            spectral_centroid = 0.0
            coefficients = []

        return MarketFeatures(
            ret_mean=ret_mean, ret_std=ret_std, ret_skew=ret_skew, ret_kurt=ret_kurt,
            autocorr_lag1=autocorr, mean_dipole=mean_dipole, mean_ofi=mean_ofi,
            volume_zscore=vol_z, realized_vol=chunk.realized_vol, range_atr=range_atr,
            spectral_energy=spectral_energy, spectral_entropy=spectral_entropy,
            peak_frequency=peak_frequency, spectral_centroid=spectral_centroid,
            coefficients=coefficients,
        )

    def encode(self, chunks: list[MarketChunk]) -> list[list[float]]:
        n_coeff = self.d_enc - self.n_summary - self.n_spectral_block
        out: list[list[float]] = []
        for chunk in chunks:
            f = self._extract(chunk)
            summary = [
                f.ret_mean, f.ret_std, f.ret_skew, f.ret_kurt, f.autocorr_lag1,
                f.mean_dipole, f.mean_ofi, f.volume_zscore,
                f.realized_vol, f.range_atr, f.spectral_energy,
            ]
            spectral_block = [f.spectral_entropy, f.peak_frequency, f.spectral_centroid]
            coeffs = f.coefficients
            if not coeffs:
                resampled = [0.0] * n_coeff
            elif len(coeffs) <= n_coeff:
                resampled = coeffs + [0.0] * (n_coeff - len(coeffs))
            else:
                step = len(coeffs) / n_coeff
                resampled = [coeffs[int(i * step)] for i in range(n_coeff)]
            max_c = max((abs(c) for c in resampled), default=0.0)
            if max_c > 1e-12:
                resampled = [c / max_c for c in resampled]
            out.append(summary + spectral_block + resampled)
        return out


# ---------------------------------------------------------------------------
# MarketQuery
# ---------------------------------------------------------------------------

class MarketQuery:
    """Builds query embeddings for index search over market regimes."""

    def __init__(self, d_enc: int = 64, n_summary: int = 11, n_spectral_block: int = 3):
        self.d_enc = d_enc
        self.n_summary = n_summary
        self.n_spectral_block = n_spectral_block

    def from_candidate(self, candidate: SignalCandidate) -> list[float]:
        sig = candidate.spectral_signature
        if len(sig) >= self.d_enc:
            return sig[: self.d_enc]
        return sig + [0.0] * (self.d_enc - len(sig))

    def from_regime_target(self, target: MarketFeatures) -> list[float]:
        summary = [
            target.ret_mean, target.ret_std, target.ret_skew, target.ret_kurt,
            target.autocorr_lag1, target.mean_dipole, target.mean_ofi,
            target.volume_zscore, target.realized_vol, target.range_atr,
            target.spectral_energy,
        ]
        spectral_block = [target.spectral_entropy, target.peak_frequency, target.spectral_centroid]
        n_coeff = self.d_enc - self.n_summary - self.n_spectral_block
        coeffs = target.coefficients
        if n_coeff <= 0:
            return summary + spectral_block
        if len(coeffs) >= n_coeff:
            step = len(coeffs) / n_coeff
            resampled = [coeffs[int(i * step)] for i in range(n_coeff)]
        else:
            resampled = coeffs + [0.0] * (n_coeff - len(coeffs))
        return summary + spectral_block + resampled

    def from_spectral_target(self, target_frequencies: list[float], target_energy: float = 1.0) -> list[float]:
        n_coeff = self.d_enc - self.n_summary - self.n_spectral_block
        summary = [0.0] * self.n_summary
        summary[10] = target_energy
        spectral_block = [
            0.5,
            target_frequencies[0] if target_frequencies else 0.0,
            (sum(target_frequencies) / len(target_frequencies)) if target_frequencies else 0.0,
        ]
        coeff_profile = [0.0] * max(n_coeff, 0)
        for tf in target_frequencies:
            if n_coeff <= 0:
                break
            idx = min(int(tf * n_coeff), n_coeff - 1)
            coeff_profile[idx] = 1.0
        return summary + spectral_block + coeff_profile


# ---------------------------------------------------------------------------
# SignalDecoder (Bayesian stub mirroring OperatorDecoder.v2 interface)
# ---------------------------------------------------------------------------

class SignalDecoder:
    """Recovers signal coefficients with a stub Bayesian posterior.

    Mirrors OperatorDecoder.v2: production wraps FNO + Bayesian deep ensemble
    per the manifest's training_contract. The deterministic stub is enough to
    wire end-to-end and feed falsification_prioritizer / evidence_graph_builder.
    """

    def __init__(self, uncertainty_threshold: float = 0.15):
        self.uncertainty_threshold = uncertainty_threshold

    def prefill(self, prefill_embeds: list[list[float]], prefill_mask: list[int]) -> tuple[list[float], dict]:
        """Returns (coefficients, posterior_dict)."""
        if not prefill_embeds:
            return [0.0], {"mean": [0.0], "std": [1.0], "underdetermined": True}
        arr = np.array(prefill_embeds, dtype=float)
        mask = np.array(prefill_mask, dtype=float)
        if mask.sum() == 0:
            mean = arr.mean(axis=0)
            std = arr.std(axis=0)
        else:
            w = mask[:, None]
            total = float(w.sum())
            mean = (arr * w).sum(axis=0) / max(total, 1.0)
            var = ((arr - mean) ** 2 * w).sum(axis=0) / max(total, 1.0)
            std = np.sqrt(var)
        underdetermined = bool(np.mean(std) > self.uncertainty_threshold)
        return mean.tolist(), {
            "mean": mean.tolist(),
            "std": std.tolist(),
            "underdetermined": underdetermined,
        }

    def refine(self, initial: list[float], n_iterations: int = 4) -> list[float]:
        cur = np.array(initial, dtype=float)
        for _ in range(n_iterations):
            n = float(np.linalg.norm(cur)) + 1e-12
            cur = cur / n
        return cur.tolist()


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def _demo():
    import random
    random.seed(42)
    np.random.seed(42)

    # Two-regime synthetic series: quiet (0-300) -> volatile (300-600)
    bars: list[MarketBar] = []
    price = 100.0
    for t in range(600):
        sigma = 0.001 if t < 300 else 0.005
        ret = random.gauss(0.0, sigma)
        price *= math.exp(ret)
        buy = max(0.0, random.gauss(1.0, 0.3))
        sell = max(0.0, random.gauss(1.0, 0.3))
        bars.append(MarketBar(
            ts=float(t), close=price, open_=price,
            high=price * 1.001, low=price * 0.999,
            volume=buy + sell, buy_vol=buy, sell_vol=sell,
        ))

    chunker = MarketChunker(max_window_size=128, stride=64, min_segment=24, mode="hybrid")
    encoder = MarketChunkEncoder(d_enc=64)
    chunks = chunker.chunk("DEMO", bars)
    embeds_raw = encoder.encode(chunks)

    # Fit scaler on the chunk corpus, then apply to chunks + queries
    scaler = FeatureScaler().fit(embeds_raw)
    embeds = scaler.transform_batch(embeds_raw)

    print(f"[markets_adapter] bars={len(bars)} chunks={len(chunks)} embed_dim={len(embeds[0]) if embeds else 0}")
    for i, c in enumerate(chunks):
        print(f"  chunk[{i}] [{c.window_start}:{c.window_end}] rv={c.realized_vol:.5f}")

    target = MarketFeatures(
        ret_mean=0.0, ret_std=0.005, ret_skew=0.0, ret_kurt=0.0,
        autocorr_lag1=0.0, mean_dipole=0.0, mean_ofi=0.0, volume_zscore=0.0,
        realized_vol=0.005, range_atr=0.002, spectral_energy=1.0,
        spectral_entropy=0.5, peak_frequency=0.1, spectral_centroid=0.1,
        coefficients=[],
    )
    q_raw = MarketQuery(d_enc=64).from_regime_target(target)
    q = scaler.transform(q_raw)

    def cosine(a, b):
        a = np.array(a); b = np.array(b)
        denom = float(np.linalg.norm(a) * np.linalg.norm(b)) + 1e-12
        return float(a @ b / denom)

    scores = sorted(((i, cosine(q, e)) for i, e in enumerate(embeds)), key=lambda x: -x[1])
    print(f"[markets_adapter] top-3 regime-similar chunks: {scores[:3]}")
    if scores:
        top_chunk = chunks[scores[0][0]]
        print(f"[markets_adapter] top match: [{top_chunk.window_start}:{top_chunk.window_end}] rv={top_chunk.realized_vol:.5f}")

    decoder = SignalDecoder()
    top_embeds = [embeds[i] for i, _ in scores[:3]]
    coeffs, post = decoder.prefill(top_embeds, [1] * len(top_embeds))
    coeffs = decoder.refine(coeffs, n_iterations=4)
    print(f"[markets_adapter] recovered coeffs[:8]={[f'{c:.3f}' for c in coeffs[:8]]}")
    print(f"[markets_adapter] posterior underdetermined={post['underdetermined']}")


if __name__ == "__main__":
    _demo()
