"""
event_move_baseline.py — the NYMEX-canary EVENT-MOVE baseline (S85).

Expectation-setting, NOT a trade-fire signal. NYMEX is the canary (NYMEX_CANARY_NOTES_S84.md): the
release move happens on the futures tape first, then reprices onto Kalshi seconds-to-a-minute later.
Before we can size the lagged Kalshi scalp we have to know, per surprise-cell, what the CANARY move
itself looks like: how BIG (magnitude) and how LONG it lasts (a blip that reverts vs a run that holds).
This measures exactly that on the TRUE-TICK futures tape (Databento `trades`, every print).

For each scheduled release event with a tape around it we anchor a strictly-pre-release baseline and
measure the forward move:
  MAGNITUDE  peak absolute displacement from the baseline within [R, R+post], reported three ways —
             TICKS (peak_abs / tick_size), DOLLARS (ticks x tick_value), and BPS (peak_abs/baseline*1e4).
             Plus the signed net displacement at R+post.
  DURATION   time_to_peak (s); sustain_s = how long the move holds >= half the peak before it first
             decays back (the "run length" in seconds; right-censored if it never decays in-window);
             retention = |net_end| / peak_abs (1.0 = a run that fully held, ~0 = a blip that round-tripped)
             -> shape in {run, fade, blip}. `blip-vs-run-is-the-duration`.

Everything is reported as DISTRIBUTIONS per cell (quantiles + the run/blip/fade mix), never a lone mean.
Cell = series x surprise-sign x surprise-magnitude (surprise = actual - forecast from the consensus feed;
falls back to 'unknown' when consensus/actual are missing — the unconditional per-series move IS the
coarsest expectation, partial coverage is not failure). `each-trade-individually-never-average`,
`per-cell-never-pool`.

TICK SIZE + VALUE are POINT-IN-TIME from Databento's `definition` schema (min_price_increment x
unit_of_measure_qty), read from data/pyth_ticks/{ROOT}_definitions.jsonl (populate it with
`databento_backfill.py --schema definition`). If that store is absent we fall back to a REFERENCE spec
but tag every move `tick_source=reference_unverified` so it is never silently trusted — the canary notes
are explicit that the reference is to VERIFY against, not to hardcode.

Discipline: the leakage gate (odcore.leakage.assert_no_leakage) runs on the strictly-pre-release anchor
closure BEFORE any distribution — the baseline + pre-vol computed 'as of R' must be invariant to every
tick after R. The forward move metrics are descriptive OUTCOMES (post-event), not predictive features.
Settle window: releases (14:30 UTC) sit well before the 21:00/22:00 UTC daily settle, and the forward
window is capped at post seconds, so it never runs into settle. Zero synthetic. Provisional-until-live.

DEPTH (S86, --depth): with the MBP-10 depth tape (databento_backfill.py --schema mbp-10) each event also
carries the resting-book read — imbalance AT the release R (pre-event, leakage-gated: the direction tilt),
and the book state at the INITIAL PUSH (fast-window peak): aligned_imb_push (book still supporting the move
vs the leader exhausting/flipping = the dipole collapse-toward-balance), far_thinning (consumed-side
liquidity eaten), spread_ratio. The run-length test contrasts these against sustain_s / retention: does a
thinning / one-sidedly-exhausting book predict a LONGER or SHORTER run? Provisional (release-window n).

Usage:
    python research/kalshi/event_move_baseline.py --symbol NG --series KXNATGASD --out data/event_move_NG.json
    python research/kalshi/event_move_baseline.py --symbol CL --series KXWTI --pre 120 --post 1800
    python research/kalshi/event_move_baseline.py --symbol NG --depth --out data/event_move_NG_depth.json
    python research/kalshi/event_move_baseline.py --selftest      # math + leakage-closure unit check
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
sys.path.insert(0, _ROOT)
from odcore.leakage import assert_no_leakage            # noqa: E402

TAPE_DIR = "data/pyth_ticks"
MBP10_DIR = "data/nymex_mbp10"                 # depth tape (databento_backfill.py --schema mbp-10)
CONSENSUS = "data/kalshi/consensus.jsonl"

# symbol -> underlying ROOT (for the definition store, reference spec, and release calendar).
def sym_root(symbol: str) -> str:
    s = symbol.upper()
    if s.startswith("NG"):
        return "NG"
    if s.startswith(("CL", "WTI")):
        return "CL"
    if s.startswith("BRENT") or s.startswith("BZ"):
        return "BRENT"
    return s

# Scheduled release (UTC hh, mm, weekday 0=Mon..6=Sun) per ROOT — the catalyst.
# EIA weekly natgas storage Thu 10:30 ET = 14:30 UTC; EIA weekly crude Wed 10:30 ET = 14:30 UTC.
RELEASE_BY_ROOT = {"NG": (14, 30, 3), "CL": (14, 30, 2), "BRENT": (14, 30, 2)}

# REFERENCE tick specs — TO VERIFY against the definition schema, NEVER the source of truth. Only used
# (and loudly tagged) when the definition store is missing. CL: $0.01/bbl x 1000 bbl = $10/tick.
# NG: $0.001/MMBtu x 10000 MMBtu = $10/tick.
REFERENCE_TICKS = {
    "CL": {"tick_size": 0.01, "unit_qty": 1000.0},
    "NG": {"tick_size": 0.001, "unit_qty": 10000.0},
    "BRENT": {"tick_size": 0.01, "unit_qty": 1000.0},
}

# consensus-forecast series -> the numeric surprise unit is native to the release (B for gas storage,
# M for crude inventories). We parse the number and its sign; magnitude bucketing is relative.
_NUM_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)")


# ---- tape + definitions --------------------------------------------------------------------------
def _parse_ts(v) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()


def load_tape(symbol: str):
    """All ticks for a symbol across day-files -> time-sorted (ts, price, size) arrays, dedup on ts.

    Consumes the {ts,price,size,symbol,src} shape written by databento_backfill / pyth_backfill / the
    live collector identically."""
    paths = sorted(glob.glob(os.path.join(TAPE_DIR, f"{symbol}_*.jsonl")))
    paths = [p for p in paths if "_definitions" not in os.path.basename(p)]
    rows = []
    for path in paths:
        for line in open(path):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("price") is None or r.get("ts") is None:
                continue
            rows.append((_parse_ts(r["ts"]), float(r["price"]), float(r.get("size") or 0.0)))
    if not rows:
        return np.array([]), np.array([]), np.array([])
    rows.sort(key=lambda x: x[0])
    ts = np.array([r[0] for r in rows], float)
    p = np.array([r[1] for r in rows], float)
    sz = np.array([r[2] for r in rows], float)
    # dedup exact-duplicate timestamps (keep last), keeps the leakage permutation well-defined
    keep = np.concatenate([np.diff(ts) > 0, [True]])
    return ts[keep], p[keep], sz[keep]


def load_tape_depth(symbol: str, tape_dir: str = MBP10_DIR):
    """MBP-10 depth tape -> time-sorted arrays (ts, price, size, bid_dep, ask_dep, bid_sz, ask_sz,
    bid_px, ask_px). Records {ts,price,size,bid_px,ask_px,bid_sz,ask_sz,bid_dep,ask_dep,src=databento_mbp10}
    from databento_backfill._write_mbp10_df (trade events + concurrent 10-level book). The price path is
    the SAME trade prints as the trades tape (so move_metrics reproduces S85); the depth rides along."""
    paths = sorted(glob.glob(os.path.join(tape_dir, f"{symbol}_*.jsonl")))
    paths = [p for p in paths if "_definitions" not in os.path.basename(p)]
    rows = []
    for path in paths:
        for line in open(path):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("price") is None or r.get("ts") is None:
                continue
            rows.append((_parse_ts(r["ts"]), float(r["price"]), float(r.get("size") or 0.0),
                         float(r.get("bid_dep") or 0.0), float(r.get("ask_dep") or 0.0),
                         float(r.get("bid_sz") or 0.0), float(r.get("ask_sz") or 0.0),
                         float(r.get("bid_px") or 0.0), float(r.get("ask_px") or 0.0)))
    if not rows:
        return None
    rows.sort(key=lambda x: x[0])
    arr = np.array(rows, float)
    keep = np.concatenate([np.diff(arr[:, 0]) > 0, [True]])   # dedup exact-dup ts (keep last)
    arr = arr[keep]
    return {"ts": arr[:, 0], "price": arr[:, 1], "size": arr[:, 2],
            "bid_dep": arr[:, 3], "ask_dep": arr[:, 4], "bid_sz": arr[:, 5], "ask_sz": arr[:, 6],
            "bid_px": arr[:, 7], "ask_px": arr[:, 8]}


def _imbalance(bid, ask):
    """(bid-ask)/(bid+ask) book imbalance in [-1,1]; +1 = all bid (buy pressure), 0 = balanced."""
    tot = bid + ask
    return float((bid - ask) / tot) if tot > 0 else 0.0


def load_defs(root: str):
    """Point-in-time tick definitions for a ROOT -> list of (ts_effective, tick_size, tick_value),
    time-sorted. Empty if the store is absent (caller falls back to the reference spec)."""
    path = os.path.join(TAPE_DIR, f"{root}_definitions.jsonl")
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = r.get("ts")
        tsz = r.get("tick_size")
        if ts is None or tsz is None:
            continue
        tval = r.get("tick_value")
        if tval is None and r.get("unit_qty") is not None:
            tval = float(tsz) * float(r["unit_qty"])
        out.append((_parse_ts(ts), float(tsz), float(tval) if tval is not None else None))
    out.sort(key=lambda x: x[0])
    return out


def tick_spec_at(root: str, event_ts: float, defs):
    """The tick (size, value, source) in effect AT event_ts — the latest definition row <= event_ts.
    Falls back to the reference spec (loudly tagged) when no definition covers the event."""
    chosen = None
    for ts_eff, tsz, tval in defs:
        if ts_eff <= event_ts:
            chosen = (tsz, tval)
        else:
            break
    if chosen is not None and chosen[1] is not None:
        return chosen[0], chosen[1], "definition"
    ref = REFERENCE_TICKS.get(root)
    if ref is None:
        return None, None, "unknown"
    return ref["tick_size"], ref["tick_size"] * ref["unit_qty"], "reference_unverified"


# ---- consensus / surprise --------------------------------------------------------------------------
def parse_number(s):
    """'-0.1%' -> -0.1 ; '3.0M' -> 3.0 ; '61B' -> 61.0 ; None/'' -> None. Unit-agnostic (compared
    within the same release only), sign preserved."""
    if s is None:
        return None
    m = _NUM_RE.match(str(s))
    return float(m.group(1)) if m else None


def load_consensus():
    """series -> list of {day (UTC date), forecast, actual} from the consensus feed. A release's
    surprise = actual - forecast, keyed to the release day."""
    by_series = defaultdict(list)
    if not os.path.exists(CONSENSUS):
        return by_series
    for line in open(CONSENSUS):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        dt = r.get("date")
        if not dt:
            continue
        try:
            day = datetime.fromisoformat(dt).astimezone(timezone.utc).date().isoformat()
        except ValueError:
            continue
        f = parse_number(r.get("forecast"))
        a = parse_number(r.get("actual"))
        for series in (r.get("series") or []):
            by_series[series].append({"day": day, "forecast": f, "actual": a,
                                      "title": r.get("title")})
    return by_series


def surprise_for(series, day, consensus):
    """(forecast, actual, surprise) for a release on `day` (UTC ISO date), or (None,None,None)."""
    for row in consensus.get(series, []):
        if row["day"] == day and row["forecast"] is not None and row["actual"] is not None:
            return row["forecast"], row["actual"], row["actual"] - row["forecast"]
    return None, None, None


def load_surprise_file(path):
    """{series: {release_iso: surprise_row}} — the historical seasonal-PROXY surprise from eia_surprise.py.
    Used as a fallback when the real (forward) consensus is absent, so historical windows still split into
    beat/miss x big/small cells. Tagged surprise_source='seasonal_proxy' so it is never confused with the
    real desk number."""
    if not path or not os.path.exists(path):
        return {}
    try:
        return json.load(open(path))
    except (json.JSONDecodeError, OSError):
        return {}


def surprise_cell(series, surprise, big_abs):
    """Cell suffix from the surprise. 'unknown' when we lack consensus+actual (still a valid, coarser
    per-series cell — partial coverage is not failure)."""
    if surprise is None:
        return f"{series}|surprise=unknown"
    sign = "beat" if surprise > 0 else ("miss" if surprise < 0 else "inline")
    mag = "big" if abs(surprise) >= big_abs else "small"
    return f"{series}|{sign}|{mag}"


# ---- pre-release anchor (the ONLY pre-event quantity; leakage-gated) -------------------------------
def anchor_at(rel_idx, ts, p, pre_s):
    """Baseline price + pre-release volatility 'as of the release index' — reads only ticks <= rel_idx.

    baseline = last trade price at/just before R (point-in-time anchor). pre_vol = std of tick log-returns
    over [R-pre_s, R] (context/normalizer). MUST be invariant to any tick after rel_idx — that is what the
    leakage gate asserts."""
    if rel_idx < 1:
        return None
    baseline = float(p[rel_idx])
    lo = rel_idx
    t0 = ts[rel_idx] - pre_s
    while lo > 0 and ts[lo - 1] >= t0:
        lo -= 1
    seg = p[lo:rel_idx + 1]
    if seg.size >= 3:
        rets = np.diff(np.log(seg))
        pre_vol = float(np.std(rets)) if rets.size else 0.0
    else:
        pre_vol = 0.0
    return {"baseline": baseline, "pre_vol": pre_vol, "n_pre": int(rel_idx - lo + 1)}


def _anchor_scalar(i, ts, p, bv, sv, pre_s):
    """Collapse the pre-release anchor to one scalar for the leakage gate (baseline + pre_vol)."""
    a = anchor_at(i, ts, p, pre_s)
    if a is None:
        return None
    return round(a["baseline"] * 1e4 + a["pre_vol"] * 1e6, 4)


# ---- forward move metrics (descriptive outcome; post-event) ---------------------------------------
def move_metrics(rel_idx, ts, p, baseline, tick_size, tick_value, post_s, run_thr, blip_thr, fast_s=60.0):
    """Magnitude + duration of the forward move in [R, R+post]. All displacements vs the pre-release
    baseline. Returns None if the window has too few forward ticks.

    Also measures the FAST window [R, R+fast_s] — the sub-minute lag-scalp opportunity (Greg, S85):
    the peak inside the first fast_s seconds, and what fraction of the full-window peak it already
    captures. Natgas is front-loaded (most of the move lands in the first minute); crude is slow."""
    R = ts[rel_idx]
    hi = rel_idx
    horizon = R + post_s
    while hi + 1 < len(ts) and ts[hi + 1] <= horizon:
        hi += 1
    if hi - rel_idx < 3:                           # need a real forward window
        return None
    fts = ts[rel_idx:hi + 1]
    disp = p[rel_idx:hi + 1] - baseline            # signed displacement path
    k_peak = int(np.argmax(np.abs(disp)))
    peak = float(disp[k_peak])                      # signed peak displacement
    peak_abs = abs(peak)
    sgn = 1.0 if peak >= 0 else -1.0
    net_end = float(disp[-1])                        # signed displacement at R+post
    time_to_peak = float(fts[k_peak] - R)
    # FAST window: peak within the first fast_s seconds (the 60s lag-scalp ceiling)
    fast_hi = int(np.searchsorted(fts, R + fast_s, side="right"))
    fdisp = disp[:max(fast_hi, 1)]
    kf = int(np.argmax(np.abs(fdisp)))
    fast_peak = float(fdisp[kf])
    fast_abs = abs(fast_peak)
    fast_ticks = fast_abs / tick_size if tick_size else float("nan")
    fast_capture = (fast_abs / peak_abs) if peak_abs > 0 else 0.0    # frac of full peak already in fast_s
    # sustain: from the peak, time until |disp| first falls below half the peak (the run length in s).
    half = 0.5 * peak_abs
    sustain_s = float(fts[-1] - fts[k_peak])
    censored = True
    for k in range(k_peak, len(disp)):
        if abs(disp[k]) < half:
            sustain_s = float(fts[k] - fts[k_peak]); censored = False
            break
    retention = (net_end * sgn) / peak_abs if peak_abs > 0 else 0.0   # signed toward the peak dir
    shape = "run" if retention >= run_thr else ("blip" if retention < blip_thr else "fade")
    ticks = peak_abs / tick_size if tick_size else float("nan")
    return {
        "peak_bps": round(peak_abs / baseline * 1e4, 2) if baseline else None,
        "peak_signed_bps": round(peak / baseline * 1e4, 2) if baseline else None,
        "peak_ticks": round(ticks, 2),
        "peak_usd": round(ticks * tick_value, 2) if tick_value else None,
        "net_end_bps": round(net_end / baseline * 1e4, 2) if baseline else None,
        "time_to_peak_s": round(time_to_peak, 1),
        "sustain_s": round(sustain_s, 1),
        "sustain_censored": bool(censored),
        "retention": round(float(retention), 3),
        "shape": shape,
        "n_fwd": int(hi - rel_idx + 1),
        # fast (sub-minute) window — the lag-scalp ceiling
        "fast_s": fast_s,
        "fast_bps": round(fast_abs / baseline * 1e4, 2) if baseline else None,
        "fast_ticks": round(fast_ticks, 2),
        "fast_usd": round(fast_ticks * tick_value, 2) if tick_value else None,
        "fast_capture": round(float(fast_capture), 3),
        "peaked_fast": bool(time_to_peak <= fast_s),
        "_k_peak": int(k_peak),                          # global-peak offset from rel_idx
        "_k_fast": int(kf),                              # fast-window (initial-push) peak offset
    }


# ---- depth (MBP-10) features: the book imbalance / thinning / exhaustion read ---------------------
def depth_at_R_scalar(i, ts, p, bd, ad, *_):
    """Leakage-safe pre-event book imbalance AT index i (reads only i's resting depth). Passed to the
    leakage gate with bv=bid_dep, sv=ask_dep — invariant to every row after i by construction."""
    if i < 0 or i >= len(bd):
        return None
    return round(_imbalance(float(bd[i]), float(ad[i])), 6)


def depth_features(rel_idx, push_idx, move_sign, D):
    """Book-depth read for one event on the MBP-10 tape, measured from the release R to the INITIAL PUSH
    (fast-window peak — the immediate move, not a 30-min global peak that book recovery would dominate).
    Distinguishes the two flow mechanisms in the dipole exhaustion frame:
      - imb_R            resting-book imbalance AT the release (pre-event; the leakage-safe direction tilt).
      - aligned_imb_R    imb_R * move_sign — did the pre-event book already lean the way price then moved?
      - aligned_imb_push imbalance * move_sign AT the initial push — does the book still SUPPORT the move
                         (>0 continuation fuel) or has the leader EXHAUSTED / flipped (<=0 = the dipole
                         collapse-toward-balance that precedes reversal)?
      - far_thinning     1 - far_dep_push/far_dep_R, far side = the one being CONSUMED (ask if up, bid if
                         down): +ve = resting liquidity eaten as price ran (fuel spent into the move).
      - spread_ratio     spread_push / spread_R — widening = liquidity stress.
    All are DESCRIPTIVE outcomes except imb_R (pre-event). Distributions per cell, never a lone mean."""
    bd, ad, bpx, apx = D["bid_dep"], D["ask_dep"], D["bid_px"], D["ask_px"]
    imb_R = _imbalance(float(bd[rel_idx]), float(ad[rel_idx]))
    imb_push = _imbalance(float(bd[push_idx]), float(ad[push_idx]))
    aligned_R = imb_R * move_sign
    aligned_push = imb_push * move_sign
    # far side = the side being consumed by the move (ask lifted on up-moves, bid hit on down-moves)
    far_R = float(ad[rel_idx]) if move_sign >= 0 else float(bd[rel_idx])
    far_push = float(ad[push_idx]) if move_sign >= 0 else float(bd[push_idx])
    far_thinning = (1.0 - far_push / far_R) if far_R > 0 else 0.0
    spr_R = max(float(apx[rel_idx]) - float(bpx[rel_idx]), 0.0)
    spr_push = max(float(apx[push_idx]) - float(bpx[push_idx]), 0.0)
    spread_ratio = (spr_push / spr_R) if spr_R > 0 else 1.0
    return {
        "imb_R": round(imb_R, 4),
        "aligned_imb_R": round(aligned_R, 4),
        "aligned_imb_push": round(aligned_push, 4),
        "exhaustion": round(aligned_R - aligned_push, 4),  # +ve = book support collapsed from R to push
        "far_thinning": round(far_thinning, 4),
        "spread_ratio": round(spread_ratio, 3),
    }


# ---- pre/post-release VOLUME (the primed / coiled read; Greg S86) ---------------------------------
def pre_release_volume(rel_idx, ts, sz, pre_s):
    """Traded volume in [R-pre_s, R] + the 'coiled' read, STRICTLY pre-event (leakage-safe: reads only
    ticks at/<= R). A primed/on-edge market goes DEAD before the print (nobody wants to get run over), so
    a LOW pre-release volume / a drying-up rate is the coiled-spring detector.
      pre_vol   = sum trade size in the pre-window
      pre_rate  = pre_vol / window seconds (per-second, for the surge ratio)
      coiled_ratio = late-half rate / early-half rate of the pre-window (<1 = drying up into the release)"""
    R = ts[rel_idx]
    t0 = R - pre_s
    lo = rel_idx
    while lo > 0 and ts[lo - 1] >= t0:
        lo -= 1
    seg_ts = ts[lo:rel_idx + 1]
    seg_sz = sz[lo:rel_idx + 1]
    pre_vol = float(seg_sz.sum())
    span = max(R - ts[lo], 1e-6)
    pre_rate = pre_vol / span
    mid = R - pre_s / 2.0
    early_m = seg_ts < mid
    early = float(seg_sz[early_m].sum())
    late = float(seg_sz[~early_m].sum())
    half = pre_s / 2.0
    early_rate = early / half
    late_rate = late / half
    coiled_ratio = (late_rate / early_rate) if early_rate > 0 else (1.0 if late_rate == 0 else 3.0)
    return {"pre_vol": round(pre_vol, 1), "pre_rate": round(pre_rate, 4), "coiled_ratio": round(coiled_ratio, 3)}


def post_release_volume(rel_idx, ts, sz, fast_s, pre_rate):
    """Post-release surge: traded size in (R, R+fast_s] and the surge ratio vs the pre-release RATE
    (explosion vs relief). DESCRIPTIVE (post-event) — the coiled spring releasing one way or the other."""
    R = ts[rel_idx]
    horizon = R + fast_s
    hi = rel_idx
    while hi + 1 < len(ts) and ts[hi + 1] <= horizon:
        hi += 1
    post_sz = sz[rel_idx + 1:hi + 1]
    post_vol = float(post_sz.sum())
    post_rate = post_vol / max(fast_s, 1e-6)
    surge_ratio = (post_rate / pre_rate) if pre_rate > 0 else float("nan")
    return {"post_vol": round(post_vol, 1), "post_rate": round(post_rate, 4),
            "surge_ratio": round(surge_ratio, 2) if surge_ratio == surge_ratio else None}


def _prevol_scalar(i, ts, p, bv, sv, pre_s):
    """Leakage-safe scalar: pre-release volume 'as of i' (sums sizes bv[lo:i+1], all <= R) — invariant to
    every tick after i by construction. bv carries the trade sizes."""
    if i < 1:
        return None
    return round(pre_release_volume(i, ts, bv, pre_s)["pre_vol"], 3)


# ---- event enumeration --------------------------------------------------------------------------
def tape_days(ts):
    return sorted({datetime.fromtimestamp(t, timezone.utc).date() for t in ts})


def build(symbol, series, cfg):
    D = None
    if cfg.get("depth"):
        D = load_tape_depth(symbol, cfg["depth_dir"])
        if D is None:
            return {"symbol": symbol, "status": "NO_DATA",
                    "msg": f"no depth tape in {os.path.join(cfg['depth_dir'], symbol + '_*.jsonl')} — "
                           f"run databento_backfill.py --schema mbp-10 first"}
        ts, p, sz = D["ts"], D["price"], D["size"]
    else:
        ts, p, sz = load_tape(symbol)
    if ts.size == 0:
        return {"symbol": symbol, "status": "NO_DATA",
                "msg": f"no tape in {os.path.join(TAPE_DIR, symbol + '_*.jsonl')} — "
                       f"run databento_backfill.py (needs DATABENTO_API_KEY) first"}
    root = sym_root(symbol)
    rel = RELEASE_BY_ROOT.get(root)
    if rel is None:
        return {"symbol": symbol, "status": "NO_RELEASE_CAL", "msg": f"no release calendar for root {root}"}
    rhh, rmm, rwd = rel
    defs = load_defs(root)
    consensus = load_consensus()
    proxy_surprise = load_surprise_file(cfg.get("surprise_file")).get(series, {})

    # one event per release-weekday present in the tape
    events = []
    for d in tape_days(ts):
        if d.weekday() != rwd:
            continue
        R = datetime(d.year, d.month, d.day, rhh, rmm, tzinfo=timezone.utc).timestamp()
        # release index = last tick at/before R (the anchor point); require ticks on both sides.
        idx = int(np.searchsorted(ts, R, side="right") - 1)
        if idx < 1 or idx >= len(ts) - 1:
            continue
        if abs(ts[idx] - R) > cfg["max_anchor_gap_s"]:     # tape doesn't actually cover the release
            continue
        anc = anchor_at(idx, ts, p, cfg["pre_s"])
        if anc is None or anc["n_pre"] < cfg["min_pre_ticks"]:
            continue
        tsz, tval, tsrc = tick_spec_at(root, R, defs)
        if tsz is None:
            continue
        mv = move_metrics(idx, ts, p, anc["baseline"], tsz, tval,
                          cfg["post_s"], cfg["run_thr"], cfg["blip_thr"], cfg["fast_s"])
        if mv is None:
            continue
        f, a, surp = surprise_for(series, d.isoformat(), consensus)
        surp_src = "consensus" if surp is not None else "none"
        if surp is None:                               # fall back to the historical seasonal-proxy surprise
            pr = proxy_surprise.get(d.isoformat())
            if pr is not None:
                a, surp, surp_src = pr.get("actual"), pr.get("surprise"), "seasonal_proxy"
        depth = {}
        if D is not None:
            # measure the book over the INITIAL push (fast-window peak), not the 30-min global peak —
            # exhaustion/consumption reads on the immediate move; a global peak 18 min out is dominated
            # by book recovery over the horizon, not by liquidity consumed during the move.
            push_idx = idx + int(mv["_k_fast"])
            move_sign = 1.0 if (mv["peak_signed_bps"] or 0) >= 0 else -1.0
            depth = depth_features(idx, push_idx, move_sign, D)
        # pre/post-release VOLUME (the primed/coiled read) — always, leakage-safe pre-window
        pv = pre_release_volume(idx, ts, sz, cfg["pre_s"])
        postv = post_release_volume(idx, ts, sz, cfg["fast_s"], pv["pre_rate"])
        mv = {k: v for k, v in mv.items() if k not in ("_k_peak", "_k_fast")}
        events.append({"day": d.isoformat(), "release_idx": idx,
                       "baseline": round(anc["baseline"], 5), "pre_vol": round(anc["pre_vol"], 6),
                       "n_pre": anc["n_pre"], "tick_size": tsz, "tick_value": tval,
                       "tick_source": tsrc, "forecast": f, "actual": a, "surprise": surp,
                       "surprise_source": surp_src,
                       "cell": surprise_cell(series, surp, cfg["big_surprise"]), **mv, **depth, **pv, **postv})

    if not events:
        return {"symbol": symbol, "status": "NO_EVENTS",
                "msg": f"tape present but no release-weekday ({rwd}) windows covered "
                       f"(days={len(tape_days(ts))}, ticks={ts.size})"}

    # leakage gate on the pre-release anchor closure at the real release indices
    idxs = [e["release_idx"] for e in events][:12]
    idxs = [i for i in idxs if cfg["pre_s"] and i >= 2 and i < len(p) - 1]
    if len(idxs) >= 2:
        bv = sz; sv = np.zeros_like(sz)
        leak_pass, fails = assert_no_leakage(
            lambda i, ts_, p_, bv_, sv_: _anchor_scalar(i, ts_, p_, bv_, sv_, cfg["pre_s"]),
            ts, p, bv, sv, idxs, reps=3, seed=0)
        leak_pass, leak_fails = bool(leak_pass), len(fails)
        if D is not None:                          # gate the pre-event book-imbalance feature too
            dpass, dfails = assert_no_leakage(depth_at_R_scalar, ts, p, D["bid_dep"], D["ask_dep"],
                                              idxs, reps=3, seed=0)
            leak_pass = leak_pass and bool(dpass)
            leak_fails += len(dfails)
        # gate the pre-release VOLUME feature (bv=sz carries trade sizes; pre_vol sums sizes <= i)
        vpass, vfails = assert_no_leakage(
            lambda i, ts_, p_, bv_, sv_: _prevol_scalar(i, ts_, p_, bv_, sv_, cfg["pre_s"]),
            ts, p, sz, np.zeros_like(sz), idxs, reps=3, seed=0)
        leak_pass = leak_pass and bool(vpass)
        leak_fails += len(vfails)
    else:
        leak_pass, leak_fails = True, 0

    # per-cell distributions (never pooled; the pooled line appears only as a footnote)
    by_cell = defaultdict(list)
    for e in events:
        by_cell[e["cell"]].append(e)
    cells = {}
    for k, evs in sorted(by_cell.items(), key=lambda kv: -len(kv[1])):
        if len(evs) < cfg["min_cell"]:
            continue
        cells[k] = _move_dist(evs)
    src_counts = defaultdict(int)               # tick-source is PER EVENT (roll/definition-window), aggregate it
    surp_src_counts = defaultdict(int)
    for e in events:
        src_counts[e["tick_source"]] += 1
        surp_src_counts[e.get("surprise_source", "none")] += 1
    return {
        "symbol": symbol, "series": series, "status": "OK",
        "n_events": len(events), "tape_days": len(tape_days(ts)), "ticks": int(ts.size),
        "tick_source": dict(src_counts),
        "surprise_source": dict(surp_src_counts),
        "leakage_pass": leak_pass, "leakage_fails": leak_fails,
        "n_cells_reported": len(cells),
        "cells": cells,
        "depth": ({k: _depth_summary(evs) for k, evs in by_cell.items() if len(evs) >= cfg["min_cell"]}
                  if D is not None else None),
        "volume": {k: _volume_summary(evs) for k, evs in by_cell.items() if len(evs) >= cfg["min_cell"]},
        "pooled_footnote": _move_dist(events),          # footnote only, never the headline
        "events": events if cfg["emit_events"] else None,
        "cfg": {k: v for k, v in cfg.items()},
    }


def _q(a, ps):
    return {f"p{p}": round(float(np.percentile(a, p)), 3) for p in ps}


def _move_dist(evs):
    """Distribution summary of a cell's event moves — quantiles + the run/blip/fade mix, NOT a lone mean."""
    n = len(evs)
    peak_bps = np.array([e["peak_bps"] for e in evs], float)
    peak_ticks = np.array([e["peak_ticks"] for e in evs], float)
    peak_usd = np.array([e["peak_usd"] for e in evs if e["peak_usd"] is not None], float)
    ttp = np.array([e["time_to_peak_s"] for e in evs], float)
    sustain = np.array([e["sustain_s"] for e in evs], float)
    retention = np.array([e["retention"] for e in evs], float)
    fast_bps = np.array([e["fast_bps"] for e in evs], float)
    fast_usd = np.array([e["fast_usd"] for e in evs if e["fast_usd"] is not None], float)
    fast_cap = np.array([e["fast_capture"] for e in evs], float)
    peaked_fast = np.array([e["peaked_fast"] for e in evs], bool)
    shapes = defaultdict(int)
    for e in evs:
        shapes[e["shape"]] += 1
    dirs = defaultdict(int)
    for e in evs:
        dirs["up" if (e["peak_signed_bps"] or 0) >= 0 else "down"] += 1
    return {
        "n": n,
        "peak_bps": {**_q(peak_bps, [10, 50, 90]), "max": round(float(peak_bps.max()), 2)},
        "peak_ticks": {**_q(peak_ticks, [10, 50, 90]), "max": round(float(peak_ticks.max()), 2)},
        "peak_usd": ({**_q(peak_usd, [10, 50, 90]), "max": round(float(peak_usd.max()), 2)}
                     if peak_usd.size else None),
        "time_to_peak_s": _q(ttp, [10, 50, 90]),
        "sustain_s": _q(sustain, [10, 50, 90]),
        "retention": _q(retention, [10, 50, 90]),
        "shape_mix": {k: round(v / n, 3) for k, v in shapes.items()},
        "dir_mix": {k: round(v / n, 3) for k, v in dirs.items()},
        # sub-minute lag-scalp ceiling (Greg, S85): move IN the fast window + how front-loaded it is
        "fast_bps": {**_q(fast_bps, [10, 50, 90]), "max": round(float(fast_bps.max()), 2)},
        "fast_usd": ({**_q(fast_usd, [10, 50, 90]), "max": round(float(fast_usd.max()), 2)}
                     if fast_usd.size else None),
        "fast_capture_of_peak": _q(fast_cap, [10, 50, 90]),
        "peaked_fast_frac": round(float(peaked_fast.mean()), 3),
    }


def _volume_summary(evs):
    """The pre/post-release VOLUME read (the primed/coiled detector; Greg S86). Per cell, distributions +
    the coiled->move test. n small -> provisional. Normalization is PER CELL (same scaffold, per-market
    values — never pool NG's normal onto CL). Questions:
      COILED (pre-event, leakage-safe): is the pre-release unusually QUIET (low pre_vol vs the cell median,
        or coiled_ratio<1 = drying up into the print)? A dead pre-release = a primed/on-edge market.
      RELEASE (descriptive): does a coiled pre-release precede a BIGGER move (explosion) — i.e. is pre_vol
        NEGATIVELY related to peak_bps, and the post-release surge_ratio larger? Split at the cell-median
        pre_vol (quiet vs active) and contrast; Spearman signs of pre_vol / coiled_ratio vs peak_bps."""
    n = len(evs)
    pre_vol = np.array([e["pre_vol"] for e in evs], float)
    coiled = np.array([e["coiled_ratio"] for e in evs], float)
    surge = np.array([e["surge_ratio"] for e in evs if e.get("surge_ratio") is not None], float)
    peak_bps = np.array([e["peak_bps"] for e in evs], float)
    med = float(np.median(pre_vol))
    quiet_m = pre_vol <= med                       # per-cell median split (per-market normal)
    def _mq(a, m):
        return round(float(np.median(a[m])), 2) if m.any() else None
    return {
        "n": n,
        "pre_vol": {**_q(pre_vol, [10, 50, 90]), "max": round(float(pre_vol.max()), 1)},
        "coiled_ratio": _q(coiled, [10, 50, 90]),
        "surge_ratio": (_q(surge, [10, 50, 90]) if surge.size else None),
        "coiled_split": {                          # quiet (coiled) vs active pre-release, per-cell median
            "median_pre_vol": round(med, 1),
            "quiet": {"n": int(quiet_m.sum()), "peak_bps": _mq(peak_bps, quiet_m)},
            "active": {"n": int((~quiet_m).sum()), "peak_bps": _mq(peak_bps, ~quiet_m)},
        },
        "spearman_vs_peak_bps": {                   # coiled hypothesis: quieter pre -> bigger move = NEGATIVE
            "pre_vol": _spear_sign(pre_vol, peak_bps),
            "coiled_ratio": _spear_sign(coiled, peak_bps),
        },
    }


def _spear_sign(x, y):
    """Spearman rank correlation (sign + value) — small-n robust, no scipy. None if degenerate."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    if x.size < 3 or np.ptp(x) == 0 or np.ptp(y) == 0:
        return None
    rx = np.argsort(np.argsort(x)).astype(float)
    ry = np.argsort(np.argsort(y)).astype(float)
    rx -= rx.mean(); ry -= ry.mean()
    d = np.sqrt((rx * rx).sum() * (ry * ry).sum())
    return round(float((rx * ry).sum() / d), 3) if d > 0 else None


def _depth_summary(evs):
    """The MBP-10 depth read for a set of events (the exhaustion / run-length test). DESCRIPTIVE +
    one pre-event predictor (imb_R). n is small (release windows) -> provisional; report the split and
    the rank-correlation SIGN, never a lone mean. Two questions:

      DIRECTION (pre-event, leakage-safe): does the resting-book imbalance AT the release lean the way
        price then moved? hit = sign(imb_R)==move_dir; aligned_imb_R>0 = it led correctly.
      RUN-LENGTH (the dipole exhaustion read): do LONGER runs show the book still SUPPORTING the move at
        its peak (high aligned_imb_push, low exhaustion) vs blips where the leader collapses toward
        balance (exhaustion>0)? Split events at the median sustain_s and contrast; also the Spearman sign
        of exhaustion / aligned_imb_push / far_thinning against sustain_s and against retention."""
    n = len(evs)
    imb_R = np.array([e["imb_R"] for e in evs], float)
    aligned_R = np.array([e["aligned_imb_R"] for e in evs], float)
    aligned_pk = np.array([e["aligned_imb_push"] for e in evs], float)
    exhaust = np.array([e["exhaustion"] for e in evs], float)
    thin = np.array([e["far_thinning"] for e in evs], float)
    sustain = np.array([e["sustain_s"] for e in evs], float)
    retention = np.array([e["retention"] for e in evs], float)
    hit = float(np.mean(np.sign(imb_R) == np.sign([e["peak_signed_bps"] or 0 for e in evs])))
    # median-split on sustain_s: long vs short run
    med = float(np.median(sustain))
    long_m = sustain >= med
    def _med(a, m):
        return round(float(np.median(a[m])), 4) if m.any() else None
    return {
        "n": n,
        "direction_pre_event": {
            "imb_R_leans_move_frac": round(hit, 3),
            "aligned_imb_R": _q(aligned_R, [10, 50, 90]),
        },
        "imb_R": _q(imb_R, [10, 50, 90]),
        "aligned_imb_push": _q(aligned_pk, [10, 50, 90]),
        "exhaustion": _q(exhaust, [10, 50, 90]),
        "far_thinning": _q(thin, [10, 50, 90]),
        "run_length_contrast": {
            "sustain_median_s": round(med, 1),
            "long_run": {"n": int(long_m.sum()), "exhaustion": _med(exhaust, long_m),
                         "aligned_imb_push": _med(aligned_pk, long_m), "far_thinning": _med(thin, long_m)},
            "short_run": {"n": int((~long_m).sum()), "exhaustion": _med(exhaust, ~long_m),
                          "aligned_imb_push": _med(aligned_pk, ~long_m), "far_thinning": _med(thin, ~long_m)},
        },
        "spearman_vs_sustain": {
            "exhaustion": _spear_sign(exhaust, sustain),
            "aligned_imb_push": _spear_sign(aligned_pk, sustain),
            "far_thinning": _spear_sign(thin, sustain),
        },
        "spearman_vs_retention": {
            "exhaustion": _spear_sign(exhaust, retention),
            "aligned_imb_push": _spear_sign(aligned_pk, retention),
        },
    }


# ---- selftest (math + leakage-closure unit check; NOT trading data) -------------------------------
def selftest():
    """Deterministic unit check of the conversion math and the leakage closure. Uses a constructed ramp
    array — a CODE test of the tool, not synthetic trading data (no cell/distribution is emitted)."""
    ok = True
    # 1. tick/$/bps conversion on a known NG-style move: baseline 3.000, peak +0.030 = 30 ticks @ $10.
    ts = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], float)
    p = np.array([3.000, 3.000, 3.000, 3.010, 3.020, 3.030, 3.028, 3.026, 3.024, 3.022, 3.020], float)
    mv = move_metrics(2, ts, p, baseline=3.000, tick_size=0.001, tick_value=10.0,
                      post_s=20, run_thr=0.5, blip_thr=0.2)
    exp_ticks = 30.0
    if mv is None or abs(mv["peak_ticks"] - exp_ticks) > 1e-6:
        print(f"  FAIL peak_ticks: {mv and mv['peak_ticks']} != {exp_ticks}"); ok = False
    else:
        print(f"  ok  peak_ticks={mv['peak_ticks']} peak_usd={mv['peak_usd']} "
              f"peak_bps={mv['peak_bps']} shape={mv['shape']} retention={mv['retention']} "
              f"sustain_s={mv['sustain_s']}")
    if mv and abs(mv["peak_usd"] - 300.0) > 1e-6:
        print(f"  FAIL peak_usd: {mv['peak_usd']} != 300.0"); ok = False
    if mv and abs(mv["peak_bps"] - 100.0) > 1e-6:                   # 0.030/3.000*1e4 = 100 bps
        print(f"  FAIL peak_bps: {mv['peak_bps']} != 100.0"); ok = False
    # 2. leakage closure: the anchor at the release index must be invariant to ticks AFTER it.
    bv = np.ones_like(p); sv = np.zeros_like(p)
    leak_pass, fails = assert_no_leakage(
        lambda i, ts_, p_, bv_, sv_: _anchor_scalar(i, ts_, p_, bv_, sv_, pre_s=5),
        ts, p, bv, sv, idxs=[3, 5, 7], reps=3, seed=0)
    if leak_pass:
        print("  ok  leakage closure invariant to post-index ticks (3/3)")
    else:
        print(f"  FAIL leakage: {fails}"); ok = False
    # 3. depth features: up-move, ask (far) side thinning, imbalance building toward the move.
    D = {"bid_dep": np.array([100.0, 100.0, 100.0]), "ask_dep": np.array([100.0, 50.0, 50.0]),
         "bid_px": np.array([2.999, 2.999, 2.999]), "ask_px": np.array([3.000, 3.001, 3.001])}
    df = depth_features(0, 1, move_sign=1.0, D=D)
    exp = {"imb_R": 0.0, "aligned_imb_push": round((100 - 50) / 150, 4),
           "far_thinning": 0.5, "exhaustion": round(0.0 - (100 - 50) / 150, 4)}
    dok = all(abs(df[k] - v) < 1e-6 for k, v in exp.items())
    if dok:
        print(f"  ok  depth: imb_R={df['imb_R']} aligned_imb_push={df['aligned_imb_push']} "
              f"far_thinning={df['far_thinning']} exhaustion={df['exhaustion']}")
    else:
        print(f"  FAIL depth: {df} vs {exp}"); ok = False
    # depth imb_R leakage-safe: invariant to book AFTER the index.
    bd = np.array([80.0, 60.0, 40.0, 90.0]); ad = np.array([20.0, 60.0, 60.0, 10.0])
    dpass, dfails = assert_no_leakage(depth_at_R_scalar, np.arange(4.0), np.zeros(4), bd, ad,
                                      idxs=[1, 2], reps=3, seed=0)
    if dpass:
        print("  ok  depth imb_R invariant to post-index book (leakage-safe)")
    else:
        print(f"  FAIL depth leakage: {dfails}"); ok = False
    # 4. pre/post-release volume: a coiled pre-window (volume drying up) then a post surge.
    vts = np.array([0, 10, 20, 30, 40, 50, 60, 61, 62, 63, 64], float)   # R at idx 6 (t=60)
    vsz = np.array([10, 10, 10, 1, 1, 1, 0, 50, 50, 50, 50], float)      # early pre busy, late pre quiet
    pv = pre_release_volume(6, vts, vsz, pre_s=60.0)
    postv = post_release_volume(6, vts, vsz, fast_s=5.0, pre_rate=pv["pre_rate"])
    if pv["coiled_ratio"] < 1.0 and postv["surge_ratio"] > 1.0:
        print(f"  ok  volume: coiled_ratio={pv['coiled_ratio']} (<1 drying up) surge_ratio={postv['surge_ratio']} (>1 explosion)")
    else:
        print(f"  FAIL volume: {pv} {postv}"); ok = False
    vpass, vfails = assert_no_leakage(
        lambda i, ts_, p_, bv_, sv_: _prevol_scalar(i, ts_, p_, bv_, sv_, 60.0),
        vts, np.zeros_like(vts), vsz, np.zeros_like(vsz), idxs=[5, 6], reps=3, seed=0)
    if vpass:
        print("  ok  pre_vol invariant to post-index sizes (leakage-safe)")
    else:
        print(f"  FAIL volume leakage: {vfails}"); ok = False
    print("SELFTEST", "PASS" if ok else "FAIL")
    return ok


def main():
    ap = argparse.ArgumentParser(description="NYMEX-canary EVENT-MOVE baseline (magnitude + duration)")
    ap.add_argument("--symbol", default="NG", help="tape symbol (NG/CL or a raw contract like NGDQ6)")
    ap.add_argument("--series", default="KXNATGASD", help="Kalshi series (for the surprise/consensus join)")
    ap.add_argument("--pre", type=float, default=120.0, dest="pre_s", help="pre-release anchor/vol window (s)")
    ap.add_argument("--post", type=float, default=1800.0, dest="post_s", help="forward move window (s)")
    ap.add_argument("--min-pre-ticks", type=int, default=3, help="min ticks in the pre-window to anchor")
    ap.add_argument("--max-anchor-gap-s", type=float, default=300.0,
                    help="max gap between the release time and the nearest tick (tape must cover it)")
    ap.add_argument("--fast", type=float, default=60.0, dest="fast_s",
                    help="fast/lag-scalp window (s) — the sub-minute capture ceiling (default 60)")
    ap.add_argument("--run-thr", type=float, default=0.5, help="retention >= this = a 'run'")
    ap.add_argument("--blip-thr", type=float, default=0.2, help="retention < this = a 'blip'")
    ap.add_argument("--big-surprise", type=float, default=10.0,
                    help="|surprise| >= this = a 'big' surprise (release-native units: Bcf for NG, Mbbl for CL)")
    ap.add_argument("--surprise-file", default=None,
                    help="historical seasonal-proxy surprise JSON from eia_surprise.py (fallback when the "
                         "forward consensus is absent, so historical windows split beat/miss x big/small)")
    ap.add_argument("--min-cell", type=int, default=3, help="min events to report a cell")
    ap.add_argument("--depth", action="store_true",
                    help="consume the MBP-10 depth tape (imbalance/thinning/exhaustion run-length read)")
    ap.add_argument("--tape-dir", default=MBP10_DIR, help="depth tape dir (with --depth)")
    ap.add_argument("--emit-events", action="store_true", help="include the per-event rows in the JSON")
    ap.add_argument("--out", default=None)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(0 if selftest() else 1)

    cfg = {"pre_s": args.pre_s, "post_s": args.post_s, "min_pre_ticks": args.min_pre_ticks,
           "max_anchor_gap_s": args.max_anchor_gap_s, "run_thr": args.run_thr, "blip_thr": args.blip_thr,
           "big_surprise": args.big_surprise, "min_cell": args.min_cell, "emit_events": args.emit_events,
           "fast_s": args.fast_s, "depth": args.depth, "depth_dir": args.tape_dir,
           "surprise_file": args.surprise_file}
    res = build(args.symbol, args.series, cfg)
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        json.dump(res, open(args.out, "w"), indent=2)
    if res["status"] != "OK":
        print(f"[{res['symbol']}] {res['status']}: {res.get('msg', '')}")
        return
    print(f"[{res['symbol']}/{res['series']}] events={res['n_events']} over {res['tape_days']} tape-days "
          f"({res['ticks']} ticks)  tick_source={res['tick_source']}  "
          f"leakage_pass={res['leakage_pass']} (fails={res['leakage_fails']})")
    if res["tick_source"].get("reference_unverified"):
        print(f"  WARNING {res['tick_source']['reference_unverified']} event(s) fell back to the UNVERIFIED "
              f"reference tick — extend {TAPE_DIR}/{sym_root(res['symbol'])}_definitions.jsonl earlier "
              "(databento_backfill.py defs) so every event has a preceding definition.")
    print(f"  cells reported (>= {args.min_cell}): {res['n_cells_reported']}")
    for k, d in res["cells"].items():
        print(f"\n  CELL {k}  n={d['n']}")
        print(f"    peak_bps p50={d['peak_bps']['p50']} p90={d['peak_bps']['p90']} max={d['peak_bps']['max']}  "
              f"peak_ticks p50={d['peak_ticks']['p50']}  "
              f"peak_usd p50={d['peak_usd']['p50'] if d['peak_usd'] else 'n/a'}")
        print(f"    time_to_peak_s p50={d['time_to_peak_s']['p50']}  sustain_s p50={d['sustain_s']['p50']}  "
              f"retention p50={d['retention']['p50']}")
        print(f"    FAST(<={int(res['cfg']['fast_s'])}s) bps p50={d['fast_bps']['p50']} p90={d['fast_bps']['p90']} "
              f"max={d['fast_bps']['max']}  ${d['fast_usd']['p50'] if d['fast_usd'] else 'n/a'}(p50) "
              f"captures {d['fast_capture_of_peak']['p50']} of peak  peaked_fast={d['peaked_fast_frac']}")
        print(f"    shape_mix={d['shape_mix']}  dir_mix={d['dir_mix']}")
    if res.get("depth"):
        print("\n  === MBP-10 DEPTH read (imbalance / thinning / exhaustion — provisional, small-n) ===")
        for k, dd in res["depth"].items():
            de = dd["direction_pre_event"]
            rc = dd["run_length_contrast"]
            print(f"\n  DEPTH {k}  n={dd['n']}")
            print(f"    DIRECTION (pre-event, leakage-safe): book imbalance at R leans the move "
                  f"{de['imb_R_leans_move_frac']} of the time  (aligned_imb_R p50={de['aligned_imb_R']['p50']})")
            print(f"    aligned_imb_push p50={dd['aligned_imb_push']['p50']}  "
                  f"exhaustion p50={dd['exhaustion']['p50']}  far_thinning p50={dd['far_thinning']['p50']}")
            lr, sr = rc["long_run"], rc["short_run"]
            print(f"    RUN-LENGTH (split @ sustain={rc['sustain_median_s']}s): "
                  f"long(n={lr['n']}) exhaustion={lr['exhaustion']} aligned_pk={lr['aligned_imb_push']} thin={lr['far_thinning']}"
                  f"  |  short(n={sr['n']}) exhaustion={sr['exhaustion']} aligned_pk={sr['aligned_imb_push']} thin={sr['far_thinning']}")
            print(f"    Spearman vs sustain: exhaustion={dd['spearman_vs_sustain']['exhaustion']} "
                  f"aligned_imb_push={dd['spearman_vs_sustain']['aligned_imb_push']} "
                  f"far_thinning={dd['spearman_vs_sustain']['far_thinning']}")
    if res.get("volume"):
        print("\n  === PRE/POST-RELEASE VOLUME (the primed/coiled read — provisional, small-n, per-cell normal) ===")
        for k, vd in res["volume"].items():
            cs = vd["coiled_split"]
            print(f"\n  VOLUME {k}  n={vd['n']}")
            print(f"    pre_vol p50={vd['pre_vol']['p50']} (coiled_ratio p50={vd['coiled_ratio']['p50']}, <1=drying up)  "
                  f"surge_ratio p50={vd['surge_ratio']['p50'] if vd['surge_ratio'] else 'n/a'}")
            print(f"    COILED split @ pre_vol median={cs['median_pre_vol']}: "
                  f"quiet(n={cs['quiet']['n']}) peak_bps={cs['quiet']['peak_bps']}  |  "
                  f"active(n={cs['active']['n']}) peak_bps={cs['active']['peak_bps']}")
            print(f"    Spearman vs peak_bps (coiled=>NEGATIVE): pre_vol={vd['spearman_vs_peak_bps']['pre_vol']} "
                  f"coiled_ratio={vd['spearman_vs_peak_bps']['coiled_ratio']}")
    pf = res["pooled_footnote"]
    print(f"\n  [footnote, pooled — never the headline] n={pf['n']} peak_bps p50={pf['peak_bps']['p50']} "
          f"shape_mix={pf['shape_mix']}")
    print("  expectation-setting only — distributions not means, per-cell, leakage-gated. NOT a trade-fire signal.")


if __name__ == "__main__":
    main()
