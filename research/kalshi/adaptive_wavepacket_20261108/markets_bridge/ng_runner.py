"""Henry Hub NG historical workflow: tape -> RawFrames -> two estimators -> archive-first probes.

Independent piece (no Frankie, AWS calls only through the repo's own read-time S3
loader when --source s3 is given, no Search, no collectors, no paper ledger).
It computes NO trade signal. What it produces is research-hold registries and a
one-screen summary that says, per direction and per estimator, whether an
entropy-change association survived the matched past-lag null, the circular-shift
null, the reparameterization null and the lag profile, with every abstention and
its reason retained.

Inputs (all existing Markets contracts):
  * NG continuous trade tape, one day per call: research/kalshi/event_move_baseline.load_cont_day
    (root "NG"; local cache data/nymex_cont/ or S3 nymex/nymex_cont/NG_YYYYMMDD.jsonl.gz).
    Trade aggressor side is not stored; it is classified exactly as month_characterize.dipole_pieces
    does (Lee-Ready: price above the concurrent mid = buy, below = sell), then summed per second into
    ng_buy / ng_sell volume channels (the H_a / H_b channels of the Markets operator basis). Optional
    depth channels ng_bid_dep / ng_ask_dep (sum of the 10 MBP levels on each side).
  * Optional Kalshi KXNATGASD bins (research/kalshi/data/<SERIES>_bins.jsonl via
    kalshi_coupling_adapter.load_kalshi_market), aligned to the NG second grid: kalshi_buy / kalshi_sell.
  * Settle exclusion: SETTLE_UTC["KXNATGASD"] = 21:00 UTC with a 30-minute guard by default
    (release_signal_history.SETTLE_UTC, lag_exploit_backtest --settle-guard-s), overridable.
  * Marks (--mark-utc HH:MM, e.g. the EIA storage release 14:30 UTC on Thursdays) are recorded in the
    summary as regime boundaries and in the frames' provenance; they do not change any fit.

Discipline carried over unchanged: zero synthetic trading data (the test uses a real cached day or
skips); the leakage gate already passes on these fitters (markets_bridge/leakage_gate.py); per-day
runs, never pooled across days; net-of-fee is NOT computed here (that is lag_join.py's job before any
paper trade).

Run from the Markets root:

    PYTHONPATH=.:research/kalshi:research/kalshi/adaptive_wavepacket_20261108/working_tree \\
      python3 -m research.kalshi.adaptive_wavepacket_20261108.markets_bridge.ng_runner \\
      --day 20260617 --source local --out /tmp/ng-probe-20260617 [--kalshi-bins research/kalshi/data/KXNATGASD_bins.jsonl]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import time
from dataclasses import asdict, is_dataclass
from itertools import permutations
from pathlib import Path
from typing import Sequence

import numpy as np

from adaptive_locality.core import LocalityError, _digest
from adaptive_locality.information import RawMember, RawFrame, FixedBins, derive_information
from adaptive_locality.coupling import circular_shift_null
from adaptive_locality.research_holds import ResearchHoldRegistry
from adaptive_locality.standalone_review import (archive_first_five_step_review,
                                                 archive_first_level2_review,
                                                 archive_first_geometric_review)
from .estimators import derive_information_continuous, estimator_identity, ESTIMATORS

TRUST = "RESEARCH_ONLY_NO_TRADE_SIGNAL_NO_SCIENTIFIC_ACCEPTANCE"
NG_SETTLE_UTC = (21, 0)          # release_signal_history.SETTLE_UTC["KXNATGASD"]
NG_SETTLE_GUARD_S = 1800         # lag_exploit_backtest default --settle-guard-s
EIA_STORAGE_UTC = (14, 30)       # 10:30 ET weekly storage report, recorded as a mark only


# --------------------------------------------------------------------------- tape -> channels
def second_channels_from_tape(tape: dict, *, depth: bool = False) -> tuple[np.ndarray, dict]:
    """Per-second Lee-Ready buy/sell volume (and optional depth) from a load_cont_day() dict."""
    ts = np.asarray(tape["ts"], dtype=float)
    if ts.size < 64:
        raise LocalityError("tape has fewer than 64 trades")
    price = np.asarray(tape["price"], dtype=float)
    size = np.asarray(tape["size"], dtype=float)
    mid = (np.asarray(tape["bid_px"], dtype=float) + np.asarray(tape["ask_px"], dtype=float)) / 2.0
    usable = mid > 0
    buy = np.where(usable & (price > mid), size, 0.0)
    sell = np.where(usable & (price < mid), size, 0.0)
    sec = np.floor(ts).astype(np.int64)
    t0, t1 = int(sec.min()), int(sec.max())
    grid = np.arange(t0, t1 + 1, dtype=np.int64)
    idx = sec - t0
    channels = {}
    for name, values in (("ng_buy", buy), ("ng_sell", sell)):
        acc = np.zeros(grid.size)
        np.add.at(acc, idx, values)
        channels[name] = acc
    if depth:
        for name, key in (("ng_bid_dep", "bid_dep"), ("ng_ask_dep", "ask_dep")):
            acc = np.zeros(grid.size)
            last = np.zeros(grid.size)
            # last observed depth within the second; seconds with no trade keep 0 (no imputation)
            vals = np.asarray(tape[key], dtype=float)
            for i, v in zip(idx, vals):
                last[i] = v
            channels[name] = last
    return grid, channels


def kalshi_channels(path: str, grid: np.ndarray) -> dict:
    """Optional KXNATGASD bins aligned to the NG grid; seconds without a bin stay 0 (no imputation)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # research/kalshi
    from kalshi_coupling_adapter import load_kalshi_market  # type: ignore
    markets = load_kalshi_market(Path(path).parent, Path(path).name.replace("_bins.jsonl", ""))
    t0 = int(grid[0])
    buy = np.zeros(grid.size)
    sell = np.zeros(grid.size)
    for bars in markets.values():
        for bar in bars:
            t = int(getattr(bar, "ts", 0))
            i = t - t0
            if 0 <= i < grid.size:
                buy[i] += float(getattr(bar, "buy_vol", 0.0) or 0.0)
                sell[i] += float(getattr(bar, "sell_vol", 0.0) or 0.0)
    return {"kalshi_buy": buy, "kalshi_sell": sell}


# --------------------------------------------------------------------------- frames
def in_window(ts: int, start: tuple[int, int], seconds: int) -> bool:
    moment = _dt.datetime.fromtimestamp(int(ts), tz=_dt.timezone.utc)
    sod = moment.hour * 3600 + moment.minute * 60 + moment.second
    s0 = start[0] * 3600 + start[1] * 60
    return s0 - seconds <= sod < s0 + seconds


def frames_from_channels(ts: np.ndarray, channels: dict[str, np.ndarray], *, window: int,
                         stride: int, source_identity: str, provenance: str,
                         settle_utc: tuple[int, int] | None = NG_SETTLE_UTC,
                         settle_guard_s: int = NG_SETTLE_GUARD_S) -> tuple[tuple, tuple]:
    """Sliding windows become RawFrames; members are the window's seconds (no averaging)."""
    if type(window) is not int or window < 8 or type(stride) is not int or stride < 1:
        raise LocalityError("window >= 8 and stride >= 1 required")
    names = tuple(sorted(channels))
    if len(names) < 2:
        raise LocalityError("at least two channels required")
    n = len(ts)
    if any(len(channels[k]) != n for k in names):
        raise LocalityError("channel length mismatch")
    frames, excluded = [], []
    for end in range(window - 1, n, stride):
        clock = int(ts[end])
        members = []
        for node in names:
            values = channels[node][end - window + 1:end + 1]
            for offset, value in enumerate(values):
                members.append(RawMember(f"{source_identity}:{clock}:{node}:{offset}", str(offset),
                                         node, float(value), provenance))
        frame = RawFrame(clock, source_identity, tuple(members))
        if settle_utc is not None and in_window(clock, settle_utc, settle_guard_s):
            excluded.append(frame)
        else:
            frames.append(frame)
    return tuple(frames), tuple(excluded)


def frozen_bins_from_history(frames: Sequence[RawFrame], *, calibration_fraction: float = 0.3,
                             nbins: int = 12, version: str = "ng-hist-v1") -> FixedBins:
    """Equal-width bins per node fixed from the EARLIEST fraction of frames only (no lookahead)."""
    frames = tuple(sorted(frames, key=lambda f: f.clock))
    if not frames or not 0 < calibration_fraction <= 1 or nbins < 3:
        raise LocalityError("frames, a calibration fraction in (0,1] and >=3 bins required")
    cutoff = max(1, int(len(frames) * calibration_fraction))
    history = frames[:cutoff]
    by_node: dict[str, list[float]] = {}
    for frame in history:
        for s in frame.samples:
            by_node.setdefault(s.node, []).append(s.value)
    edges = []
    for node, values in sorted(by_node.items()):
        lo, hi = min(values), max(values)
        span = hi - lo
        if span <= 0:
            span = max(abs(lo), 1.0)
        hi = hi + 0.05 * span
        lo = lo - 0.05 * span if lo != 0 else lo
        step = (hi - lo) / nbins
        edges.append((node, tuple(round(lo + k * step, 12) for k in range(nbins + 1))))
    return FixedBins(frames[0].source_identity,
                     f"{version}:cutoff_clock={history[-1].clock}:frames={cutoff}:nbins={nbins}",
                     tuple(edges))


# --------------------------------------------------------------------------- probe
class _ContinuousDeriver:
    def __init__(self, bins: FixedBins, k: int = 4, seed: int = 0):
        self.k, self.seed = k, seed
        self.identity = estimator_identity(bins, "vasicek-ksg", k=k, seed=seed)

    def __call__(self, raw: RawFrame, bins: FixedBins):
        return derive_information_continuous(raw, bins, k=self.k, seed=self.seed)


def _plain(value):
    if is_dataclass(value):
        return _plain(asdict(value))
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, (np.floating, np.integer)):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _direction_summary(result) -> dict:
    return {"target": result.target, "donor": result.donor, "status": result.status,
            "reason": result.reason, "improvement": result.improvement,
            "shifted_null_improvement": result.shifted_null_improvement,
            "dipole_balance": result.dipole_balance,
            "balance_standard_error": result.balance_standard_error,
            "opposing_dipole_signs": result.opposing_dipole_signs,
            "donor_lag1_autocorrelation": result.donor_lag1_autocorrelation,
            "lag_profile": list(result.null_gain_by_lag),
            "training_intervals": result.training_intervals,
            "test_intervals": result.test_intervals}


def run_probe(ts: np.ndarray, channels: dict[str, np.ndarray], *, source_identity: str,
              provenance: str, out_dir: str | Path, archive_prefix: str = "ng",
              window: int = 60, stride: int = 20, nbins: int = 12, calibration_fraction: float = 0.3,
              settle_utc: tuple[int, int] | None = NG_SETTLE_UTC, settle_guard_s: int = NG_SETTLE_GUARD_S,
              marks_utc: Sequence[tuple[int, int]] = (EIA_STORAGE_UTC,),
              level2_window: int = 40, level2_stride: int = 4,
              estimators: Sequence[str] = ESTIMATORS, max_frames: int = 12000,
              shift_null: int = 20, max_archive_bytes: int = 256 * 1024 * 1024,
              bins: FixedBins | None = None) -> dict:
    """bins: pass FixedBins frozen from a PRIOR day (see bins_from_prior_day) to avoid calibrating on
    the same day; otherwise bins are frozen from this day's earliest calibration_fraction of frames."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    started = time.time()
    frames, excluded = frames_from_channels(ts, channels, window=window, stride=stride,
                                            source_identity=source_identity, provenance=provenance,
                                            settle_utc=settle_utc, settle_guard_s=settle_guard_s)
    if len(frames) < 64:
        raise LocalityError(f"only {len(frames)} frames after the settle exclusion; need >= 64")
    if bins is None:
        bins = frozen_bins_from_history(frames, calibration_fraction=calibration_fraction, nbins=nbins)
    else:
        if bins.source_identity != source_identity:
            # Bins frozen on another day carry that day's identity; rebind the identity only, never the edges.
            bins = FixedBins(source_identity, bins.version, bins.edges)
    nodes = tuple(sorted(dict(bins.edges)))
    summary = {"schema": 1, "kind": "MARKETS_NG_HISTORICAL_PROBE", "trust": TRUST,
               "source_identity": source_identity, "provenance": provenance,
               "window_seconds": window, "stride_seconds": stride, "frames": len(frames),
               "settle_excluded_frames": len(excluded),
               "settle_utc": None if settle_utc is None else list(settle_utc),
               "settle_guard_s": settle_guard_s,
               "marks_utc": [list(m) for m in marks_utc],
               "first_clock": frames[0].clock, "last_clock": frames[-1].clock,
               "nodes": list(nodes), "frozen_bins_version": bins.version,
               "estimators": {}, "scientific_jobs_eliminated": 0, "frames_dropped": 0,
               "no_trade_signal_computed": True, "net_of_fee_computed": False}
    for estimator in estimators:
        derive = derive_information if estimator == "frozen-bin" else _ContinuousDeriver(bins)
        contract = estimator_identity(bins, estimator)
        registry = ResearchHoldRegistry(out / f"{estimator}.sqlite", source_identity=source_identity,
                                        contract_identity=contract, max_archive_bytes=max_archive_bytes)
        block = {"calibration_identity": contract, "registry": str(out / f"{estimator}.sqlite")}
        prefix = f"{archive_prefix}-{estimator}"
        with registry:
            if excluded:
                block["settle_excluded_archive_digest"] = registry.archive(
                    f"{prefix}-settle-window-excluded", excluded)
            five = archive_first_five_step_review(frames, bins, registry, archive_prefix=prefix,
                                                  max_frames=max_frames, derive=derive)
            info = tuple(derive(f, bins) for f in frames)
            block["review_required_frames"] = sum(f.status != "READY" for f in info)
            block["review_reasons"] = sorted({r.split(":")[0] for f in info for r in f.review_reasons})
            block["five_step"] = {"report_present": five["report"] is not None,
                                  "research_case_ids": len(five["research_case_ids"]),
                                  "directions": [_direction_summary(r) for r in five["report"]["results"]]
                                  if five["report"] else []}
            ready = tuple(f for f in info if f.status == "READY")
            block["circular_shift_null"] = []
            if five["report"] and len(ready) >= 100 and shift_null:
                for a, b in permutations(nodes, 2):
                    try:
                        null = circular_shift_null(ready, a, b, shifts=shift_null)
                        block["circular_shift_null"].append({
                            "target": a, "donor": b, "shift_count": null["shift_count"],
                            "actual_improvement": null["actual"].improvement,
                            "fraction_of_shifts_at_or_above_actual":
                                null["fraction_of_shifts_at_or_above_actual"]})
                        registry.archive(f"{prefix}-shift-null-{a}-from-{b}", (null,))
                    except LocalityError as exc:
                        block["circular_shift_null"].append({"target": a, "donor": b, "reason": str(exc)})
            level2 = archive_first_level2_review(frames, bins, registry, archive_prefix=prefix,
                                                 max_frames=max_frames, window=level2_window,
                                                 stride=level2_stride, derive=derive)
            block["level2"] = {"level1_windows": None if level2["level1_windows"] is None
                               else len(level2["level1_windows"]),
                               "report_present": level2["report"] is not None,
                               "research_case_ids": len(level2["research_case_ids"])}
            if level2["report"]:
                rep = level2["report"]
                block["level2"].update({
                    "channels": [list(c) for c in rep["channels"]], "clocks": len(rep["clocks"]),
                    "candidate_count": rep["candidate_count"], "held_link_count": rep["held_link_count"],
                    "unresolved_count": rep["unresolved_count"], "segment_clocks": rep["segment_clocks"],
                    "links": [{"target": list(l.target_balance), "donor": list(l.donor_balance),
                               "status": l.status, "gain": l.predictive_gain, "null_gain": l.null_gain}
                              for l in rep["links"]]})
            block["geometry"] = []
            for a, b in permutations(nodes, 2):
                geo = archive_first_geometric_review(frames, bins, registry, a, b,
                                                     archive_prefix=f"{prefix}-geometry-{a}-from-{b}",
                                                     max_frames=max_frames, derive=derive)
                entry = {"target": a, "donor": b, "research_case_ids": len(geo["research_case_ids"])}
                if geo["static_report"]:
                    st = geo["static_report"]
                    entry["static"] = {"status": st["status"], "reason": st["reason"],
                                       "quadratic_gain": st["quadratic_gain"],
                                       "gain_over_algebraic_curve": st["gain_over_algebraic_curve"],
                                       "flags": list(st["algebraic_degeneracy_flags"]),
                                       "frozen_support_novelty_points":
                                           st["frozen_support_novelty_point_count"]}
                if geo["predictive_report"]:
                    pr = geo["predictive_report"]
                    entry["predictive"] = {"status": pr["status"], "past_lag": pr["past_lag"],
                                           "splits": [{"status": s.status, "geometry_gain": s.geometry_gain,
                                                       "past_donor_gain": s.past_donor_gain,
                                                       "quadratic_vs_linear_gain":
                                                           s.quadratic_vs_linear_gain}
                                                      for s in pr["splits"]]}
                block["geometry"].append(entry)
            block["registry_cases"] = registry.counts()
            block["registry_verified"] = registry.verify()
        summary["estimators"][estimator] = block
    summary["elapsed_seconds"] = round(time.time() - started, 3)
    summary["summary_identity"] = _digest(_plain({k: v for k, v in summary.items()
                                                  if k != "elapsed_seconds"}))
    (out / "summary.json").write_text(json.dumps(_plain(summary), indent=2, sort_keys=True) + "\n")
    return summary


def one_screen(summary: dict) -> str:
    lines = [f"MARKETS NG HISTORICAL PROBE  trust={summary['trust']}",
             f"source={summary['source_identity']} frames={summary['frames']} "
             f"settle_excluded={summary['settle_excluded_frames']} window={summary['window_seconds']}s "
             f"stride={summary['stride_seconds']}s nodes={','.join(summary['nodes'])}"]
    for name, block in summary["estimators"].items():
        lines.append(f"[{name}] review_required={block['review_required_frames']} "
                     f"cases={block['registry_cases']['cases']} verified={block['registry_verified']}")
        for d in block["five_step"]["directions"]:
            imp = "n/a" if d["improvement"] is None else f"{d['improvement']:+.3f}"
            bal = "n/a" if d["dipole_balance"] is None else f"{d['dipole_balance']:.3g}"
            se = "" if d["balance_standard_error"] is None else f"+/-{d['balance_standard_error']:.2g}"
            lines.append(f"  five-step {d['target']}<-{d['donor']}: {d['status']} improvement={imp} B={bal}{se}")
        for n in block.get("circular_shift_null", []):
            frac = n.get("fraction_of_shifts_at_or_above_actual")
            lines.append(f"  shift-null {n['target']}<-{n['donor']}: "
                         f"{'n/a' if frac is None else f'{frac:.2f}'} of shifts at/above actual")
        l2 = block["level2"]
        if l2.get("report_present"):
            lines.append(f"  level2: candidates={l2['candidate_count']} held={l2['held_link_count']} "
                         f"unresolved={l2['unresolved_count']} segment={l2['segment_clocks']}")
        for g in block["geometry"]:
            lines.append(f"  geometry {g['target']}<-{g['donor']}: "
                         f"static={g.get('static', {}).get('status', 'n/a')} "
                         f"predictive={g.get('predictive', {}).get('status', 'n/a')}")
    lines.append("No trade signal computed; no fee applied. A candidate is a research hold for review, "
                 "not an entry rule. Next step for any candidate: lag_join.py net-of-fee, per event.")
    return "\n".join(lines)


def bins_from_prior_day(day: str, source: str, *, window: int, stride: int, nbins: int,
                        depth: bool = False, kalshi_bins: str | None = None,
                        settle_utc: tuple[int, int] | None = NG_SETTLE_UTC,
                        settle_guard_s: int = NG_SETTLE_GUARD_S) -> FixedBins:
    """Freeze bins from ALL frames of a PRIOR day (calibration_fraction=1.0), so the probed day is never
    its own calibration. The version string records the calibration day."""
    grid, channels, _ = load_ng_day(day, source, depth=depth)
    if kalshi_bins:
        channels.update(kalshi_channels(kalshi_bins, grid))
    frames, _ = frames_from_channels(grid, channels, window=window, stride=stride,
                                     source_identity=f"NG_{day}", provenance=f"calibration:NG_{day}",
                                     settle_utc=settle_utc, settle_guard_s=settle_guard_s)
    return frozen_bins_from_history(frames, calibration_fraction=1.0, nbins=nbins,
                                    version=f"ng-prior-day-{day}")


CARRY_FORWARD_SHIFT_FRACTION = 0.05
CARRY_FORWARD_B_OVER_SE = 2.0


def replication_table(summaries: Sequence[dict]) -> dict:
    """Side-by-side per-day readings per direction; NOTHING is pooled or averaged.

    For each (target, donor) and each day: status under each estimator, the shift-null fraction, |B|/se,
    the predictive-geometry status, and whether the handoff's carry-forward criteria 1-4 all hold on that
    day. `days_meeting_criteria` is a COUNT of days, which is the replication reading (criterion 5 asks
    for at least three), never a pooled statistic.
    """
    table: dict[str, dict] = {}
    for summary in summaries:
        day = summary.get("source_identity")
        for estimator, block in summary.get("estimators", {}).items():
            shift = {(n["target"], n["donor"]): n.get("fraction_of_shifts_at_or_above_actual")
                     for n in block.get("circular_shift_null", [])}
            predictive = {(g["target"], g["donor"]): g.get("predictive", {}).get("status")
                          for g in block.get("geometry", [])}
            for d in block.get("five_step", {}).get("directions", []):
                key = f"{d['target']}<-{d['donor']}"
                row = table.setdefault(key, {"days": {}})
                entry = row["days"].setdefault(day, {})
                b, se = d.get("dipole_balance"), d.get("balance_standard_error")
                entry[estimator] = {
                    "status": d["status"], "improvement": d.get("improvement"),
                    "shift_fraction": shift.get((d["target"], d["donor"])),
                    "b_over_se": (abs(b) / se) if (b is not None and se) else None,
                    "predictive_status": predictive.get((d["target"], d["donor"])),
                    "reason": d.get("reason")}
    for key, row in table.items():
        meets = {}
        for day, per_est in row["days"].items():
            ok = len(per_est) >= 2 and all(
                e["status"] == "CANDIDATE_ASSOCIATION_REVIEW_ONLY"
                and e["shift_fraction"] is not None and e["shift_fraction"] <= CARRY_FORWARD_SHIFT_FRACTION
                and e["b_over_se"] is not None and e["b_over_se"] > CARRY_FORWARD_B_OVER_SE
                and e["predictive_status"] == "CONSISTENT_MULTISPLIT_ASSOCIATION_REVIEW_ONLY"
                for e in per_est.values())
            meets[day] = ok
        row["meets_criteria_by_day"] = meets
        row["days_meeting_criteria"] = sum(meets.values())
        row["days_run"] = len(meets)
    return {"schema": 1, "kind": "NG_PROBE_REPLICATION_TABLE", "trust": TRUST,
            "criteria": {"both_estimators_candidate": True,
                         "shift_fraction_at_most": CARRY_FORWARD_SHIFT_FRACTION,
                         "b_over_se_above": CARRY_FORWARD_B_OVER_SE,
                         "predictive": "CONSISTENT_MULTISPLIT_ASSOCIATION_REVIEW_ONLY",
                         "days_required_before_lag_join": 3},
            "directions": table, "pooled": False, "averaged": False,
            "net_of_fee_computed": False, "no_trade_signal_computed": True}


def load_ng_day(day: str, source: str = "local", *, depth: bool = False):
    """Load one NG day through the repo's own loader (local cache or S3 read-time fetch)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # research/kalshi
    import event_move_baseline as emb  # type: ignore
    tape = emb.load_cont_day("NG", day, source=source, trades_only=True)
    grid, channels = second_channels_from_tape(tape, depth=depth)
    local = emb._cont_local_path("NG", day)
    size = os.path.getsize(local) if os.path.exists(local) else os.path.getsize(local + ".gz") \
        if os.path.exists(local + ".gz") else None
    provenance = f"nymex_cont:NG_{day}:source={source}:trades={int(np.asarray(tape['ts']).size)}:bytes={size}"
    return grid, channels, provenance


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Henry Hub NG historical probe (no trade signal).")
    parser.add_argument("--day", action="append", required=True,
                        help="YYYYMMDD; repeatable. Each day runs INDEPENDENTLY into <out>/<day>/; "
                             "a replication table (no pooling) is written to <out>/replication.json")
    parser.add_argument("--calibrate-from-day", help="freeze bins from this PRIOR day instead of the probed day")
    parser.add_argument("--source", choices=("local", "s3"), default="local")
    parser.add_argument("--out", required=True, help="output directory (outside git)")
    parser.add_argument("--kalshi-bins", help="optional KXNATGASD_bins.jsonl to add kalshi_buy/kalshi_sell")
    parser.add_argument("--depth", action="store_true", help="add ng_bid_dep/ng_ask_dep channels")
    parser.add_argument("--start-ts", type=int)
    parser.add_argument("--end-ts", type=int)
    parser.add_argument("--max-seconds", type=int)
    parser.add_argument("--window", type=int, default=60)
    parser.add_argument("--stride", type=int, default=20)
    parser.add_argument("--nbins", type=int, default=12)
    parser.add_argument("--calibration-fraction", type=float, default=0.3)
    parser.add_argument("--no-settle-exclusion", action="store_true")
    parser.add_argument("--settle-guard-s", type=int, default=NG_SETTLE_GUARD_S)
    parser.add_argument("--mark-utc", action="append", default=[], help="HH:MM regime mark, repeatable")
    parser.add_argument("--level2-window", type=int, default=40)
    parser.add_argument("--level2-stride", type=int, default=4)
    parser.add_argument("--shift-null", type=int, default=20, help="0 disables")
    parser.add_argument("--estimator", action="append", choices=ESTIMATORS)
    parser.add_argument("--prefix", default="ng")
    args = parser.parse_args(argv)
    settle = None if args.no_settle_exclusion else NG_SETTLE_UTC
    prior_bins = None
    if args.calibrate_from_day:
        if args.calibrate_from_day in args.day:
            raise LocalityError("the calibration day must not be one of the probed days")
        prior_bins = bins_from_prior_day(args.calibrate_from_day, args.source, window=args.window,
                                         stride=args.stride, nbins=args.nbins, depth=args.depth,
                                         kalshi_bins=args.kalshi_bins, settle_utc=settle,
                                         settle_guard_s=args.settle_guard_s)
    marks = [EIA_STORAGE_UTC] + [tuple(int(x) for x in m.split(":")) for m in args.mark_utc]
    summaries = []
    for day in args.day:
        grid, channels, provenance = load_ng_day(day, args.source, depth=args.depth)
        if args.kalshi_bins:
            channels.update(kalshi_channels(args.kalshi_bins, grid))
            provenance += f";kalshi={Path(args.kalshi_bins).name}"
        lo = 0 if args.start_ts is None else int(np.searchsorted(grid, args.start_ts))
        hi = grid.size if args.end_ts is None else int(np.searchsorted(grid, args.end_ts, side="right"))
        if args.max_seconds is not None:
            hi = min(hi, lo + args.max_seconds)
        grid = grid[lo:hi]
        channels = {k: v[lo:hi] for k, v in channels.items()}
        out_dir = Path(args.out) / day if len(args.day) > 1 else Path(args.out)
        summary = run_probe(grid, channels, source_identity=f"NG_{day}", provenance=provenance,
                            out_dir=out_dir, archive_prefix=args.prefix, window=args.window,
                            stride=args.stride, nbins=args.nbins,
                            calibration_fraction=args.calibration_fraction,
                            settle_utc=settle, settle_guard_s=args.settle_guard_s, marks_utc=marks,
                            level2_window=args.level2_window, level2_stride=args.level2_stride,
                            estimators=tuple(args.estimator) if args.estimator else ESTIMATORS,
                            shift_null=args.shift_null, bins=prior_bins)
        print(one_screen(summary))
        print(f"summary: {out_dir / 'summary.json'}")
        summaries.append(summary)
    table = replication_table(summaries)
    (Path(args.out) / "replication.json").write_text(json.dumps(_plain(table), indent=2, sort_keys=True) + "\n")
    for key, row in table["directions"].items():
        print(f"replication {key}: {row['days_meeting_criteria']} of {row['days_run']} day(s) meet criteria 1-4 "
              f"(3 required before lag_join; never pooled)")
    print(f"replication table: {Path(args.out) / 'replication.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
