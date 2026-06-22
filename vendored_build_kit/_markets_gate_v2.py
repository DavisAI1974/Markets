"""gate_v2 -- the v2 combined info+flow admission gate, as a self-contained,
independently-testable module the live mock engine imports.

Decision rule (matches _markets_dipole_export_centroids_v2.py / the validated
_markets_combined_info_flow_kfold.py classifier exactly):

  info_score = <c, c_win>/||c_win|| - <c, c_lose>/||c_lose||
  feats      = {info_score, mean_dipole_signed, volume_zscore, trade_present_score}
  score      = sum_k feature_weights[k] * (feats[k] - mean[k]) / std[k]
  admit      iff score > threshold              (all per-pair, from the gate file)

Two entry points:
  * score_from_coefs(...) -- caller supplies operator coefficients (no pipeline
    run). Used to validate the gate MATH against the offline classifier and by
    any caller that already has coefs.
  * score(...) -- recomputes the info arm LIVE: slices the pre-entry 30m bar
    window, runs the refrag pipeline (window=192, stride=16 -- the cs100_v2
    config, NOT the handoff's stale stride=96), then scores. Coefs are memoized
    per (pair, decision-second) so multiple scenarios on the same chunk reuse
    one pipeline run.

The info arm's live reproducibility was confirmed by _canary_infoarm_repro.py
(determinism 1.0, reproduction cosine 0.995) and _canary_infoarm_sweep.py
(sign-correct winner/loser separation preserved across winners AND losers).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

REFRAG = Path(r"E:\refrag")
ADAPTERS = REFRAG / "adapters"
import sys
for _p in (str(REFRAG), str(ADAPTERS), str(Path(__file__).resolve().parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _markets_combined_info_flow_kfold import dot, norm  # noqa: E402

GATE_FILE = Path(r"E:\Markets\_markets_dipole_centroids_preentry_cs100_v2_schemav2.json")
FEATURE_SET = ["info_score", "mean_dipole_signed", "volume_zscore", "trade_present_score"]
PRE_ENTRY_S = 30 * 60

# cs100_v2 chunker config (proven by 898 log-returns -> 45 chunks in the canary).
CHUNKER = {"window_size": 192, "stride": 16, "min_segment_length": 16}
QUERY = {"query_mode": "from_spectral_target", "target_frequencies": [0.1, 0.25],
         "target_energy": 1.0, "top_k": 8, "expand_budget": 4}


def side_word(side) -> str:
    s = str(side).strip().lower()
    if s in ("buy", "long", "bullish"):
        return "buy"
    if s in ("sell", "short", "bearish"):
        return "sell"
    return s


def side_sign(side) -> float:
    w = side_word(side)
    return 1.0 if w == "buy" else (-1.0 if w == "sell" else 0.0)


def pair_key(asset, venue, side) -> str:
    return f"markets_{str(asset).strip().lower()}_{str(venue).strip().lower()}_{side_word(side)}"


class GateV2:
    """Loads the schema-v2 gate file once; scores candidates against it."""

    def __init__(self, gate_file: Path = GATE_FILE):
        blob = json.loads(Path(gate_file).read_text(encoding="utf-8"))
        if blob.get("schema_version") != 2:
            raise ValueError(f"{gate_file} is not schema_version 2 (got {blob.get('schema_version')})")
        self.gate_file = Path(gate_file)
        self.meta = {k: v for k, v in blob.items() if k != "pairs"}
        self.pairs = blob["pairs"]
        self._coef_cache: dict[tuple[str, int], dict] = {}
        # lazily-imported live-recompute deps (only needed by score(), not score_from_coefs())
        self._live = None

    # ---- gate math (no pipeline run) -------------------------------------
    def info_score(self, coefs, blob) -> float:
        return (dot(coefs, blob["c_win_centroid"]) / blob["c_win_norm"]
                - dot(coefs, blob["c_lose_centroid"]) / blob["c_lose_norm"])

    def score_from_coefs(self, asset, venue, side, coefs,
                         mean_dipole, volume_zscore, trade_present_score) -> dict:
        pk = pair_key(asset, venue, side)
        blob = self.pairs.get(pk)
        if blob is None:
            return {"pair": pk, "status": "unknown_pair", "admit": None}
        feats = {
            "info_score": self.info_score(coefs, blob),
            "mean_dipole_signed": float(mean_dipole) * side_sign(side),
            "volume_zscore": float(volume_zscore),
            "trade_present_score": float(trade_present_score),
        }
        fs, fw, thr = blob["feature_stats"], blob["feature_weights"], blob["threshold"]
        comps, score = {}, 0.0
        for k in FEATURE_SET:
            mu, sd = fs[k]["mean"], (fs[k]["std"] or 1.0)
            z = (feats[k] - mu) / sd
            contrib = fw[k] * z
            score += contrib
            comps[k] = {"raw": feats[k], "z": z, "weight": fw[k], "contrib": contrib}
        return {
            "pair": pk, "status": "scored", "admit": bool(score > thr),
            "score": score, "threshold": thr, "margin": score - thr,
            "info_score": feats["info_score"], "components": comps,
        }

    # ---- live info-arm recompute -----------------------------------------
    def _ensure_live(self):
        if self._live is None:
            from markets_refrag_adapter import run_pipeline_on_winner, winner_domain
            from markets_bar_loader import load_closes, slice_closes, closes_to_log_returns
            from refrag_discovery.runtime.operator_orchestrator import OperatorOrchestrator
            self._live = dict(
                run_pipeline_on_winner=run_pipeline_on_winner, winner_domain=winner_domain,
                load_closes=load_closes, slice_closes=slice_closes,
                closes_to_log_returns=closes_to_log_returns, Orch=OperatorOrchestrator,
            )
        return self._live

    def recompute_coefs(self, asset, venue, side, decision_ts) -> dict:
        """Slice pre-entry 30m window and run the refrag pipeline. Memoized per
        (pair, decision-second). Returns {coefs, status, n_log_returns, latency_s}."""
        pk = pair_key(asset, venue, side)
        cache_key = (pk, int(decision_ts))
        if cache_key in self._coef_cache:
            return self._coef_cache[cache_key]
        L = self._ensure_live()
        t0 = time.time()
        closes = L["load_closes"](asset, venue, t_min=decision_ts - PRE_ENTRY_S - 3600,
                                  t_max=decision_ts + 60)
        sliced = L["slice_closes"](closes, decision_ts - PRE_ENTRY_S, decision_ts)
        lr = L["closes_to_log_returns"](sliced)
        if len(lr) < CHUNKER["window_size"]:
            res = {"coefs": None, "status": "insufficient_bars",
                   "n_log_returns": len(lr), "latency_s": time.time() - t0}
            self._coef_cache[cache_key] = res
            return res
        orch = L["Orch"]()
        domain = L["winner_domain"](asset, venue, side_word(side), "win",
                                    domain_suffix="gate_v2_live")
        src_id = f"live|{str(asset).lower()}|{str(venue).lower()}|{side_word(side)}|{int(decision_ts)}"
        out = L["run_pipeline_on_winner"](orch, src_id, lr, domain,
                                          chunker_config=dict(CHUNKER), query_config=dict(QUERY))
        coefs = [float(c) for c in out["result"]["operator_coefficients"]]
        res = {"coefs": coefs, "status": "ok", "n_log_returns": len(lr),
               "latency_s": time.time() - t0}
        self._coef_cache[cache_key] = res
        return res

    def score(self, asset, venue, side, decision_ts,
              mean_dipole, volume_zscore, trade_present_score) -> dict:
        """Full live gate: recompute info arm + combine with flow arm + threshold."""
        pk = pair_key(asset, venue, side)
        if pk not in self.pairs:
            return {"pair": pk, "status": "unknown_pair", "admit": None}
        rc = self.recompute_coefs(asset, venue, side, decision_ts)
        if rc["status"] != "ok":
            return {"pair": pk, "status": rc["status"], "admit": None,
                    "n_log_returns": rc["n_log_returns"], "recompute_latency_s": rc["latency_s"]}
        out = self.score_from_coefs(asset, venue, side, rc["coefs"],
                                    mean_dipole, volume_zscore, trade_present_score)
        out["recompute_latency_s"] = rc["latency_s"]
        out["n_log_returns"] = rc["n_log_returns"]
        return out


_DEFAULT_GATE: GateV2 | None = None


def get_gate(gate_file: Path = GATE_FILE) -> GateV2:
    """Process-wide singleton so the gate file + coef cache are shared."""
    global _DEFAULT_GATE
    if _DEFAULT_GATE is None or _DEFAULT_GATE.gate_file != Path(gate_file):
        _DEFAULT_GATE = GateV2(gate_file)
    return _DEFAULT_GATE
