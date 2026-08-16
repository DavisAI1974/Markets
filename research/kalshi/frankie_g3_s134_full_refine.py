#!/usr/bin/env python3
"""S134 full ten-day G3 unblinded refine-to-actual curve.

This is the REFINE phase, not a blind forecast.  The realized Sep 8-19, 2025 NGV25 target tape is
intentionally readable.  The purpose is to reconstruct each actual curve, explain the market
mechanism, compare that mechanism with what blind Frankie did, and extract reusable lessons.

Curve nodes are NOT hard-coded plot times.  They are selected from the realized tape by an adaptive
shape simplifier plus forced market transitions (actual high/low, detected onset/turn, 10:30 EIA on
Thursdays, open and terminal state).  Node count and timestamps therefore vary by day.

This module does NOT edit the brain, specialist roles, spawn.py, group_config.py, S129/S131 frozen
artifacts, or add any datapoint family.  Hydration remains rejected.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import frankie_g3_reblind_s131 as g3
import frankie_s132_dynamic_curve as s132

ET = "America/New_York"
MULT = 10000.0

WHY_BLIND = {
    "20250908": "B saw strong pre-block Friday buy flow but capped the Monday/gap call because the archived weekend weather/stability plane was absent and the slow balance was loose.",
    "20250909": "C stood down D-1 buy flow as a clean sign because price delivery/absorption was masked, then let loose storage plus weak gas-burn/stronger-wind backdrop become a small DOWN substitute.",
    "20250910": "C had the correct DOWN side from a mixed-to-late-sell tape plus loose demand/balance state, but used a core-session magnitude band and under-sized the move.",
    "20250911": "D correctly treated EIA as a range catalyst and leaned DOWN, but the first post-print impulse was future at the open, so the blind p50 remained far too small for the realized print-day break.",
    "20250912": "E decontaminated GSCI/BCOM flow but still let loose storage/weak burn plus a small residual sell-flow term own DOWN while the Friday turn/exit price discriminator was unavailable.",
    "20250915": "B consumed A's bridge, treated BCOM as contamination rather than a sign, and kept a small DOWN balance lean; the weekend forecast/stability archive and completed Friday price/turn state were not available in the one-shot lane.",
    "20250916": "C explicitly knew D-1 aggregate flow was weak next-day authority, but still granted the coherent Sep-15 sell tape bearish corroboration while the price/turn discriminator and chain state were unavailable; slow loose balance then owned DOWN.",
    "20250917": "C saw loose balance collide with strong D-1 buying and demand arrival.  Because price-bearing absorption was unavailable, it used the old ABSTAIN contract rather than manufacture a sign.",
    "20250918": "D had no archived pre-print consensus for the target print and no price-extension state; its strongest current arbiter requires the first post-print impulse, so it abstained at the open.",
    "20250919": "E could legally see the +90 Bcf print, widened storage surplus and post-print sell state, then damped the bearish read with stronger gas demand/tighter supply and called modest DOWN.",
}

LESSON = {
    "20250908": "Weekend repricing magnitude was the dominant miss.  Refine the Monday curve as a large early extension followed by absorption/give-back; do not invent missing historical weekend model cycles.",
    "20250909": "The target tape confirms that raw flow and slow balance cannot substitute for a missing price/absorption sign owner.  This supports S133 reasoning-authority discipline, not a new signal.",
    "20250910": "Direction was already right.  The main lesson is magnitude and shape: a failed early bid transitioned into a sustained US-session downside delivery.",
    "20250911": "EIA shape is event-driven: pre-print positioning can be modest, then the 10:30 impulse can completely re-center the path.  Live D must re-derive after the print rather than defend the open-time curve.",
    "20250912": "Friday was a real intraday turn/absorption day.  Gross program-day flow did not own sign.  The live Friday turn/exhaustion machinery must be allowed to revise the curve as price moves against aggression.",
    "20250915": "Monday contained a deep morning selloff followed by a full reversal.  Weekend gap and Monday session remain separate; live price-vs-flow absorption is the mechanism that resolves the session.",
    "20250916": "Primary reusable miss: Sep-15 selling was absorbed while price recovered and the old downside continuation structure had collapsed.  The current brain already knows this; sequential/live serving must make that completed prior-session discriminator available and raw flow must not recreate the stood-down sign.",
    "20250917": "After a violent up extension, target-session buy aggression failed to lift price and the market turned down.  This is a live absorption/turn update; do not fit a new open-time reversal rule from one walked day.",
    "20250918": "The post-print crash begins at the EIA release.  The open-time abstention was defensible; the live D lane must own the 10:30 re-derivation and full curve after the impulse becomes legal.",
    "20250919": "Blind side and endpoint were already close.  Refine mainly adds the deeper morning washout and recovery: target-session buy aggression was absorbed during the selloff, then late selling failed to extend the low.",
}

CLASS = {
    "20250908": "HISTORICAL_INFORMATION_GAP_AND_CURVE_SHAPE",
    "20250909": "REASONING_AUTHORITY",
    "20250910": "MAGNITUDE_AND_SHAPE",
    "20250911": "LIVE_CATALYST_REDERIVATION",
    "20250912": "LIVE_TURN_ABSORPTION",
    "20250915": "WEEKEND_GAP_PLUS_LIVE_TURN",
    "20250916": "SEQUENTIAL_REASONING_AUTHORITY_PRIMARY",
    "20250917": "LIVE_TURN_ABSORPTION",
    "20250918": "LIVE_CATALYST_REDERIVATION",
    "20250919": "SHAPE_REFINEMENT_CONTROL",
}


def _hour(ts: pd.Timestamp) -> float:
    return round(ts.hour + ts.minute / 60.0 + ts.second / 3600.0, 4)


def _rdp_indices(x: np.ndarray, y: np.ndarray, eps: float) -> list[int]:
    """Vertical-deviation RDP on a time/value curve.  Times are discovered from the tape, not supplied."""
    keep = {0, len(x) - 1}

    def rec(i: int, j: int) -> None:
        if j <= i + 1:
            return
        xs = x[i + 1:j]
        if xs.size == 0:
            return
        if x[j] == x[i]:
            pred = np.full(xs.size, y[i])
        else:
            pred = y[i] + (y[j] - y[i]) * (xs - x[i]) / (x[j] - x[i])
        dev = np.abs(y[i + 1:j] - pred)
        krel = int(np.argmax(dev))
        if float(dev[krel]) > eps:
            k = i + 1 + krel
            keep.add(k)
            rec(i, k)
            rec(k, j)

    rec(0, len(x) - 1)
    return sorted(keep)


def _nearest_index(ts: np.ndarray, target: float) -> int:
    i = int(np.searchsorted(ts, target))
    cand = []
    if i < len(ts):
        cand.append(i)
    if i > 0:
        cand.append(i - 1)
    return min(cand, key=lambda k: abs(float(ts[k]) - target))


def _condition_for(ts: pd.Timestamp, i: int, rows: list[dict[str, Any]], ev: dict[str, Any], day: str) -> str:
    if i == 0:
        return "session-open reference"
    if i == len(rows) - 1:
        return "terminal/settlement state"
    iso = ts.isoformat()
    for key, label in (("hi_et", "realized intraday high / extension pivot"),
                       ("lo_et", "realized intraday low / exhaustion pivot"),
                       ("onset_et", "realized first material displacement / onset"),
                       ("turn_et", "realized turn / give-back pivot")):
        raw = ev.get(key)
        if raw:
            t = pd.Timestamp(raw)
            if abs((ts - t).total_seconds()) <= 15 * 60:
                return label
    if day in ("20250911", "20250918"):
        eia = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} 10:30:00", tz=ET)
        if abs((ts - eia).total_seconds()) <= 10 * 60:
            return "EIA 10:30 catalyst / post-print state transition"
    return "realized acceleration, deceleration or absorption transition selected from the target curve"


def _build_day(day: str, ar: dict[str, Any], ev: dict[str, Any], ts: np.ndarray, px: np.ndarray) -> tuple[dict[str, Any], dict[str, Any]]:
    dtv = pd.to_datetime(ts, unit="s", utc=True).tz_convert(ET)
    open_px = float(ev["open"])
    close_px = float(ev["close"])
    cum = (px - open_px) * MULT

    # Use a 5-minute representation only as an efficient substrate for shape discovery.  The selected
    # node times are the tape's own transitions and are not a forecast clock.
    frame = pd.DataFrame({"price": px}, index=dtv)
    sampled = frame["price"].resample("5min").last().dropna()
    sdt = list(sampled.index)
    spx = list(sampled.values)
    if not sdt or sdt[0] != dtv[0]:
        sdt.insert(0, dtv[0]); spx.insert(0, open_px)
    else:
        spx[0] = open_px
    terminal_ts = dtv[-1]
    if sdt[-1] != terminal_ts:
        sdt.append(terminal_ts); spx.append(close_px)
    else:
        spx[-1] = close_px

    # Collapse duplicate timestamps and force official open/close values.
    samp = pd.DataFrame({"dt": sdt, "price": spx}).drop_duplicates("dt", keep="last").sort_values("dt").reset_index(drop=True)
    scum = (samp["price"].to_numpy(float) - open_px) * MULT
    sx = (samp["dt"] - samp["dt"].iloc[0]).dt.total_seconds().to_numpy(float) / 3600.0
    day_range = float(np.max(cum) - np.min(cum))
    eps = max(55.0, 0.12 * max(1.0, day_range))
    selected = set(_rdp_indices(sx, scum, eps))

    # Force actual market-state transitions, never generic clock points.
    force_targets: list[pd.Timestamp] = [
        dtv[int(np.argmax(cum))], dtv[int(np.argmin(cum))],
    ]
    for key in ("onset_et", "turn_et"):
        if ev.get(key):
            force_targets.append(pd.Timestamp(ev[key]))
    if day in ("20250911", "20250918"):
        force_targets.append(pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} 10:30:00", tz=ET))
    for target in force_targets:
        k = int(np.argmin(np.abs((samp["dt"] - target).dt.total_seconds().to_numpy())))
        selected.add(k)

    idx = sorted(selected)
    rows: list[dict[str, Any]] = []
    spread_base = max(50.0, 0.45 * eps)
    for pos, k in enumerate(idx):
        t = samp.loc[k, "dt"]
        p50 = float((samp.loc[k, "price"] - open_px) * MULT)
        if pos == 0:
            p50 = 0.0
            p25 = p75 = 0.0
        else:
            # Refine envelope: narrow around the now-known path but wider at catalyst/turn states.
            cond_probe = _condition_for(t, pos, [{}] * len(idx), ev, day)
            widen = 1.75 if ("EIA" in cond_probe or "turn" in cond_probe or "pivot" in cond_probe) else 1.0
            width = spread_base * widen
            p25, p75 = p50 - width, p50 + width
        rows.append({
            "timestamp": t,
            "et_hour": _hour(t),
            "p25_cum_usd": round(float(p25), 1),
            "p50_cum_usd": round(float(p50), 1),
            "p75_cum_usd": round(float(p75), 1),
        })

    # Exact session endpoints are authoritative even when the 5-minute substrate's last quote differs.
    rows[0]["p25_cum_usd"] = rows[0]["p50_cum_usd"] = rows[0]["p75_cum_usd"] = 0.0
    rows[-1]["p50_cum_usd"] = float(ev["net_usd"])
    rows[-1]["p25_cum_usd"] = float(ev["net_usd"]) - spread_base
    rows[-1]["p75_cum_usd"] = float(ev["net_usd"]) + spread_base

    # Resolve any duplicate wall-clock labels by retaining the later/stronger transition.  This can
    # occur when the first sampled point is seconds away from a forced pivot at the session reopen.
    dedup: list[dict[str, Any]] = []
    for row in rows:
        if dedup and abs(row["et_hour"] - dedup[-1]["et_hour"]) < 1e-4:
            dedup[-1] = row
        else:
            dedup.append(row)
    rows = dedup
    for i, row in enumerate(rows):
        row["market_condition"] = _condition_for(row.pop("timestamp"), i, rows, ev, day)

    guess = int(ar["day_move_usd"])
    gap = int(ar["gap_usd"])
    payload = {
        "specialist": ar["owner"],
        "group": "g3",
        "date": day,
        "guessed_net_usd": guess,
        "overnight_gap_usd": gap,
        "path_p50_curve": [[r["et_hour"], r["p50_cum_usd"]] for r in rows],
        "curve_nodes": rows,
        "reasoning": (
            f"POST-REVEAL REFINE. Target tape is intentionally visible. Actual session net is {ev['net_usd']:+d} USD; "
            f"high excursion {ev['high_exc']:+d}, low excursion {ev['low_exc']:+d}, total signed flow {ev['total_sflow']:+d}. "
            f"Detected turn={ev['turn_kind']} ({ev['turn_mag']:+d} USD) at {ev.get('turn_et')}; onset={ev.get('onset_et')}. "
            f"Blind behavior: {WHY_BLIND[day]} Refine lesson: {LESSON[day]}"
        ),
        "plays_fired": ["S134 unblinded target-curve reconstruction", "S132 event-driven curve contract"],
        "plays_stood_down": ["blind-wall restrictions do not apply to post-reveal refine"],
        "confidence": "high",
        "state_defects_and_gaps_reported": [],
        "disposition": "CALL",
        "phase": "POST_REVEAL_FULL_CURVE_REFINE",
        "target_day_tape_used_to_construct_curve": True,
        "reconstruction_not_blind_skill": True,
        "s134_lesson_class": CLASS[day],
    }
    s132.validate_day(payload, "g3", day, ar["owner"])

    # Reconstruction fit against a one-minute representation of the exact target tape.
    minute = frame["price"].resample("1min").last().dropna()
    mdt = minute.index
    actual_local = (minute.to_numpy(float) - open_px) * MULT
    # Rebuild monotone node timestamps directly from selected samples for interpolation.
    ndt = []
    for r in rows:
        h = float(r["et_hour"])
        base_date = dtv[0].date()
        hh = int(h); mm = int(round((h - hh) * 60))
        t = pd.Timestamp(f"{base_date} {hh:02d}:{min(mm,59):02d}:00", tz=ET)
        if ndt and t <= ndt[-1]:
            t += pd.Timedelta(days=1)
        ndt.append(t)
    nx = np.array([(t - ndt[0]).total_seconds() for t in ndt], float)
    ny = np.array([float(r["p50_cum_usd"]) for r in rows], float)
    mx = np.array([(t - ndt[0]).total_seconds() for t in mdt], float)
    pred = np.interp(mx, nx, ny)
    err = pred - actual_local
    fit = {
        "node_count": len(rows),
        "adaptive_tolerance_usd": round(eps, 1),
        "one_minute_points": int(len(err)),
        "mae_usd": round(float(np.mean(np.abs(err))), 1),
        "rmse_usd": round(float(math.sqrt(np.mean(err ** 2))), 1),
        "max_abs_error_usd": round(float(np.max(np.abs(err))), 1),
    }
    return payload, fit


def build() -> dict[str, Any]:
    g3.install_g3_context()
    import group_actual
    import group_mbo_engine as mbo

    actual = group_actual.build("g3")
    amap = {r["date"]: r for r in actual["days"]}
    days = []
    fits = []
    actual_plot = []
    prior_close = float(g3.ANCHOR_PRICE)

    for day in g3.DAYS:
        ev = mbo.per_day_evidence("g3", day)
        ts, px, _sz, _sd = mbo.load_trades("g3", day)
        ar = dict(amap[day])
        # Reconcile endpoint fields to the exact MBO evidence used for the refine.
        gap = round((float(ev["open"]) - prior_close) * MULT)
        day_move = gap + int(ev["net_usd"])
        ar.update({"open": ev["open"], "close": ev["close"], "gap_usd": gap,
                   "net_usd": ev["net_usd"], "day_move_usd": day_move})
        payload, fit = _build_day(day, ar, ev, ts, px)
        days.append(payload)
        fits.append({"date": day, **fit})

        # One-minute exact-tape representation for durable rendering without shipping raw MBO.
        dtv = pd.to_datetime(ts, unit="s", utc=True).tz_convert(ET)
        m = pd.DataFrame({"price": px}, index=dtv)["price"].resample("1min").last().dropna()
        actual_plot.extend([[float(t.timestamp()), float(p)] for t, p in m.items()])
        prior_close = float(ev["close"])

    mae = float(np.mean([r["mae_usd"] for r in fits]))
    rmse = math.sqrt(float(np.mean([r["rmse_usd"] ** 2 for r in fits])))
    return {
        "group": "g3",
        "phase": "POST_REVEAL_FULL_CURVE_REFINE",
        "window": "2025-09-08..2025-09-19",
        "anchor": {"date": g3.ANCHOR_DATE, "close": g3.ANCHOR_PRICE},
        "scored_leg": "NGV25",
        "actuals_read": True,
        "target_day_tape_used_to_construct_refined_curves": True,
        "classification": "unblinded refine-to-actual; reconstruction fit is not blind skill",
        "hydration": "REJECTED_NOT_USED",
        "new_datapoint_family_added": False,
        "fixed_curve_clock": False,
        "fixed_curve_point_count": False,
        "days": days,
        "reconstruction_fit": {
            "per_day": fits,
            "mean_day_mae_usd": round(mae, 1),
            "pooled_day_rmse_usd": round(rmse, 1),
            "metric_note": "post-reveal adaptive reconstruction against exact NGV25 one-minute tape; diagnostic only",
        },
        "actual_plot_one_minute": actual_plot,
    }


def render(obj: dict[str, Any], out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    act = pd.DataFrame(obj["actual_plot_one_minute"], columns=["ts", "price"])
    act["dt"] = pd.to_datetime(act["ts"], unit="s", utc=True).dt.tz_convert(ET)

    fig, ax = plt.subplots(figsize=(16, 7.5))
    # Break actual across long closures.
    x = act["dt"].to_list(); y = act["price"].to_list()
    bx, by = [], []
    for i, (t, p) in enumerate(zip(x, y)):
        if i and (t - x[i-1]).total_seconds() > 3 * 3600:
            bx.append(t); by.append(float("nan"))
        bx.append(t); by.append(p)
    ax.plot(bx, by, linewidth=0.8, label="actual NGV25")

    for d in obj["days"]:
        day = d["date"]
        # Reconstruct absolute datetimes from event-driven wall-clock nodes.
        first_date = (pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]}", tz=ET) - pd.Timedelta(days=1)).date()
        ndt, price50, p25, p75 = [], [], [], []
        open_px = next(r["open"] for r in _ACTUAL_ROWS if r["date"] == day)
        prev = None
        cur_date = first_date
        for n in d["curve_nodes"]:
            h = float(n["et_hour"]); hh = int(h); mm = int(round((h-hh)*60))
            t = pd.Timestamp(f"{cur_date} {hh:02d}:{min(mm,59):02d}:00", tz=ET)
            if prev is not None and t <= prev:
                t += pd.Timedelta(days=1); cur_date = t.date()
            ndt.append(t); prev = t
            price50.append(open_px + float(n["p50_cum_usd"])/MULT)
            p25.append(open_px + float(n["p25_cum_usd"])/MULT)
            p75.append(open_px + float(n["p75_cum_usd"])/MULT)
        ax.fill_between(ndt, p25, p75, alpha=0.10)
        ax.plot(ndt, price50, marker="o", markersize=3.2, linewidth=1.15)

    ax.set_title("G3 S134 full two-week Frankie refine: event-driven reconstruction vs actual NGV25")
    ax.set_ylabel("price ($/MMBtu)")
    ax.grid(True, alpha=0.22)
    fig.autofmt_xdate()
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)


_ACTUAL_ROWS: list[dict[str, Any]] = []


def main() -> int:
    global _ACTUAL_ROWS
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, required=True)
    a = ap.parse_args()
    obj = build()
    # Keep a minimal endpoint table for render absolute-price conversion.
    g3.install_g3_context()
    import group_mbo_engine as mbo
    prior = float(g3.ANCHOR_PRICE)
    _ACTUAL_ROWS = []
    for day in g3.DAYS:
        ev = mbo.per_day_evidence("g3", day)
        gap = round((float(ev["open"]) - prior) * MULT)
        _ACTUAL_ROWS.append({"date": day, "open": ev["open"], "close": ev["close"],
                             "gap_usd": gap, "net_usd": ev["net_usd"],
                             "day_move_usd": gap + int(ev["net_usd"])})
        prior = float(ev["close"])
    obj["actual_days"] = _ACTUAL_ROWS

    a.out_dir.mkdir(parents=True, exist_ok=True)
    j = a.out_dir / "g3_s134_full_refine.json"
    j.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    render(obj, a.out_dir / "g3_s134_refined_vs_actual.png")
    print(json.dumps({
        "status": "READY",
        "days": len(obj["days"]),
        "nodes": sum(len(d["curve_nodes"]) for d in obj["days"]),
        "mean_day_mae_usd": obj["reconstruction_fit"]["mean_day_mae_usd"],
        "out": str(j),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
