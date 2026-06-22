"""odcore/fingerprint.py — live per-cell FINGERPRINT encoder (S35).

Recovers the trade-flow micro features that were computed in the (rebuild-stripped)
mock_trade_replay.current_status_from_visible, and computes them in the CURRENT platform
from a window of minute bars. The goal (Greg, S35) is to fingerprint a trade by its
distinctive traits, as early + accurate as possible, per cell (asset x venue x side).

This module ports the EXACT recipe verbatim from git c486d3b:
  - chunker = MarketChunker(max_window_size=CHUNK_MAX_SIZE, stride=CHUNK_MAX_SIZE//2,
              min_segment=CHUNK_MIN_SEGMENT, mode="hybrid")  (mock_trade_replay.py:905-911)
  - feats   = [MarketChunkEncoder(d_enc=64)._extract(c) for c in chunks]
  - last chunk/feat; head/tail bps via _signed_bps over chunk-bar closes
    (mock_trade_replay.py:873-890, 973-975; _signed_bps backend/api_server.py:944).

Faithful for the 5 chunk-derived micros (the head/tail bps + mean_dipole / volume_zscore /
dipole_acl1). `trade_present_score` is a COMPOSITE that also folds in regime / pressure /
adjusted_confidence (api_server.py:953 @ c486d3b); it is computed best-effort here and flagged
(`present_score_faithful=False` when the pressure pipeline is unavailable) — verify separately.

NOTE: MarketBar in the current platform has no bid/ask/n_trades (git had them); none of the 5
chunk-derived micros need them. MarketChunkEncoder takes only d_enc here (git passed
compute_hawkes/compute_hurst=False, now the default).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from markets_adapter import MarketBar, MarketChunker, MarketChunkEncoder
from regime_classifier import classify_regime, baselines_from_corpus

from .info_dipole import signed_flow_features, cell_signal

# chunker config — verbatim from current_status_from_visible @ c486d3b (constants from api_server)
CHUNK_MAX_SIZE = 30
CHUNK_MIN_SEGMENT = 10
# signed info-dipole flow uses the recent pre-entry order-flow window (≈30 1-min bars, the
# window the operator was validated on in _info_dipole_flow_probe.py)
FLOW_WINDOW_BARS = 30

MICRO_KEYS = ["mean_dipole", "dipole_acl1", "volume_zscore", "trade_present_score",
              "trade_recent_2chunk_bps", "trade_from_onset_bps"]


# --- verbatim ports (backend/api_server.py @ c486d3b) ----------------------------------
def signed_bps(entry: float, exit_price: float, side: str) -> float:
    """_signed_bps: signed log-return in bps. (api_server.py:944 @ c486d3b)"""
    if entry <= 0 or exit_price <= 0:
        return 0.0
    sign = 1 if side == "buy" else -1 if side == "sell" else 0
    if sign == 0:
        return 0.0
    return sign * math.log(max(exit_price, 1e-12) / max(entry, 1e-12)) * 10000.0


def trade_score_band(score: int) -> str:
    """_trade_score_band (api_server.py:932 @ c486d3b)."""
    if score >= 85:
        return "85_100"
    if score >= 70:
        return "70_84"
    if score >= 55:
        return "55_69"
    if score >= 40:
        return "40_54"
    return "0_39"


def present_trade_score(feats_inputs: dict, regime: str, adjusted_confidence: float,
                        pressure_watch_state: str, strong_pressure_regimes: set | None = None) -> int:
    """_present_trade_score, ported verbatim (api_server.py:953 @ c486d3b).

    Composite that folds regime/pressure + dipole + volume + head/tail bps into 0-100.
    `feats_inputs` carries mean_dipole, volume_zscore, trade_from_onset_bps,
    trade_current_chunk_bps, trade_recent_2chunk_bps, trade_age_chunks.
    """
    strong = strong_pressure_regimes or set()
    score = min(35.0, float(adjusted_confidence or 0.0) * 35.0)
    if regime in strong:
        score += 25.0
    elif str(regime).startswith("WHALE_NASCENT"):
        score += 18.0
    elif pressure_watch_state in ("forming", "high_priority"):
        score += 12.0
    elif pressure_watch_state == "internal":
        score += 6.0
    abs_d = abs(float(feats_inputs.get("mean_dipole") or 0.0))
    if abs_d >= 0.50:
        score += 15.0
    elif abs_d >= 0.30:
        score += 10.0
    elif abs_d >= 0.15:
        score += 5.0
    vz = float(feats_inputs.get("volume_zscore") or 0.0)
    if vz >= 1.0:
        score += 10.0
    elif vz >= 0.0:
        score += 6.0
    score += min(10.0, max(-12.0, float(feats_inputs.get("trade_from_onset_bps") or 0.0) / 2.5))
    score += min(8.0, max(-12.0, float(feats_inputs.get("trade_current_chunk_bps") or 0.0) / 2.0))
    age = int(feats_inputs.get("trade_age_chunks") or 0)
    if age >= 9:
        score -= 14.0
    elif age >= 4:
        score -= 6.0
    if (float(feats_inputs.get("trade_from_onset_bps") or 0.0) > 12.0
            and float(feats_inputs.get("trade_recent_2chunk_bps") or 0.0) <= 0.0):
        score -= 8.0
    if float(feats_inputs.get("trade_from_onset_bps") or 0.0) < -8.0:
        score -= 12.0
    return int(max(0, min(100, round(score))))


# --- the live fingerprint --------------------------------------------------------------
@dataclass
class Fingerprint:
    asset: str
    venue: str
    side: str
    chunk_id: str
    window_start: int
    window_end: int
    n_chunks: int
    # the 5 chunk-derived (faithful) micros + the composite
    mean_dipole: float
    dipole_acl1: float
    volume_zscore: float
    trade_current_chunk_bps: float
    trade_recent_2chunk_bps: float
    trade_from_onset_bps: float
    trade_present_score: int
    trade_score_band: str
    present_score_faithful: bool
    # signed information-dipole flow (odcore.info_dipole) — the directional tool the
    # side-agnostic coeff + price-bps micros lack. flow_signal is the PER-CELL selected
    # signed feature (None where this cell hasn't earned the operator); flow_features holds
    # all signed variants for stacking. Never averaged into the other tools.
    flow_features: dict | None = None
    flow_signal: float | None = None
    flow_feature: str | None = None

    def micros(self) -> dict:
        return {
            "mean_dipole": self.mean_dipole, "dipole_acl1": self.dipole_acl1,
            "volume_zscore": self.volume_zscore,
            "trade_current_chunk_bps": self.trade_current_chunk_bps,
            "trade_recent_2chunk_bps": self.trade_recent_2chunk_bps,
            "trade_from_onset_bps": self.trade_from_onset_bps,
            "trade_present_score": self.trade_present_score,
        }

    def stack(self) -> dict:
        """The full stacked fingerprint: micros + the per-cell signed flow signal.

        flow_signal is included only where the cell earned the operator (else None) —
        a complementary directional input STACKED alongside the micros, not blended in.
        """
        out = self.micros()
        out["flow_signal"] = self.flow_signal
        out["flow_feature"] = self.flow_feature
        return out


def compute_fingerprint(asset: str, venue: str, side: str, visible_bars: list[MarketBar],
                        onset_price: float | None = None) -> Fingerprint | None:
    """Compute a trade's distinctive fingerprint micros from a window of minute bars.

    Mirrors current_status_from_visible's chunk/feature recipe exactly. `onset_price` defaults
    to the current chunk start (fresh trade), matching the audit's onset for stage=onset trades.
    """
    if not visible_bars:
        return None
    chunker = MarketChunker(max_window_size=CHUNK_MAX_SIZE, stride=CHUNK_MAX_SIZE // 2,
                            min_segment=CHUNK_MIN_SEGMENT, mode="hybrid")
    chunks = chunker.chunk(f"{venue}-{asset}", visible_bars, multi_signal=True)
    if not chunks:
        return None
    encoder = MarketChunkEncoder(d_enc=64)
    feats = [encoder._extract(c) for c in chunks]
    chunk = chunks[-1]
    feat = feats[-1]
    start_price = float(chunk.bars[0].close)
    close_price = float(chunk.bars[-1].close)
    recent_start = (float(chunks[-2].bars[0].close)
                    if len(chunks) >= 2 and chunks[-2].bars else start_price)
    onset = float(onset_price) if onset_price else start_price
    cur_bps = signed_bps(start_price, close_price, side)
    rec_bps = signed_bps(recent_start, close_price, side)
    onset_bps = signed_bps(onset, close_price, side)

    # composite present_trade_score — best-effort (regime via classify_regime; pressure
    # pipeline may be stripped, in which case the pressure term is omitted -> not faithful)
    present_faithful = True
    regime = ""
    adj_conf = 0.0
    pressure_state = ""
    strong = None
    try:
        base = baselines_from_corpus(feats)
        result = classify_regime(feat, base)
        regime = result.regime.value if hasattr(result.regime, "value") else str(result.regime)
        adj_conf = float(getattr(result, "adjusted_confidence", 0.0) or 0.0)
        try:
            from backend.api_server import STRONG_PRESSURE_REGIMES as _SPR
            strong = set(_SPR)
        except Exception:
            present_faithful = False
        # pressure_watch_state pipeline was stripped in the rebuild; flag if unavailable
        try:
            from backend.api_server import _pressure_watch_from_features as _pwf  # noqa: F401
            present_faithful = present_faithful  # present but not wired here -> still flag below
            present_faithful = False
        except Exception:
            present_faithful = False
    except Exception:
        present_faithful = False
    pscore = present_trade_score(
        {"mean_dipole": feat.mean_dipole, "volume_zscore": feat.volume_zscore,
         "trade_from_onset_bps": onset_bps, "trade_current_chunk_bps": cur_bps,
         "trade_recent_2chunk_bps": rec_bps, "trade_age_chunks": 0},
        regime, adj_conf, pressure_state, strong)

    # signed information-dipole flow over the recent pre-entry order-flow window (no look-ahead:
    # visible_bars are the bars visible at decision time). Per-cell gated via cell_signal.
    fw = visible_bars[-FLOW_WINDOW_BARS:]
    flow_feats = signed_flow_features([b.buy_vol for b in fw], [b.sell_vol for b in fw])
    cell = f"{asset}_{venue}_{side}".lower()
    sel = cell_signal(cell, [b.buy_vol for b in fw], [b.sell_vol for b in fw])
    flow_signal = sel[0] if sel else None
    flow_feature = sel[1] if sel else None

    return Fingerprint(
        asset=asset, venue=venue, side=side,
        chunk_id=chunk.chunk_id, window_start=chunk.window_start, window_end=chunk.window_end,
        n_chunks=len(chunks),
        mean_dipole=float(feat.mean_dipole), dipole_acl1=float(feat.dipole_autocorr_lag1),
        volume_zscore=float(feat.volume_zscore),
        trade_current_chunk_bps=cur_bps, trade_recent_2chunk_bps=rec_bps,
        trade_from_onset_bps=onset_bps,
        trade_present_score=pscore, trade_score_band=trade_score_band(pscore),
        present_score_faithful=present_faithful,
        flow_features=flow_feats, flow_signal=flow_signal, flow_feature=flow_feature,
    )
