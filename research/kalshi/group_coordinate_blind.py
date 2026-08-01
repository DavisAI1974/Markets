"""group_coordinate_blind.py - GENERIC blind coordinator (S105), config-driven:
    python research/kalshi/group_coordinate_blind.py g18

SELECT the owner per day under the GUARD (+ Friday sign-off), assemble grp<n>.json from the specialist
blind files' guessed_net_usd (verbatim, never averaged), score vs the two-leg actual, render actual +
own p50 path only. Reads group_config for days/owner/seam/anchor. Original g17_coordinate.py kept as the
G17 record.
"""
import os, sys, json
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import group_config as gc
import verify_gold
verify_gold.assert_gold_intact()   # the concrete wall - no blind coordinate on a violated gold vault

HERE = os.path.dirname(os.path.abspath(__file__))
FC = os.path.join(HERE, "forecasts")
RENDER_DIR = os.path.join(HERE, "renders", "ng_refine_s95")
MULT = gc.MULT
_DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _find_report(fname):
    """Autonomous-safe: find a specialist report wherever the agent wrote it (canonical FC, or a
    repo-root forecasts/ that a differently-cwd'd agent may have used). Report routing is the
    coordinator's job - we do not babysit paths."""
    for d in (FC, os.path.join(HERE, "..", "..", "forecasts")):
        p = os.path.join(d, fname)
        if os.path.exists(p):
            return p
    return None


def load_specialist(gid, tag):
    p = _find_report(f"grp{gid[1:]}_blind_{tag}.json")
    if p is None:
        return None
    return {str(x["date"]).replace("-", ""): x for x in json.load(open(p)).get("days", [])}


def num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def break_gaps(ct, cp, max_gap_h=3.0):
    """S104 RENDER RULE - never bridge a session gap with a straight line. Insert a NaN break
    wherever consecutive tape points are >max_gap_h apart (the weekend, holidays, multi-hour halts),
    so matplotlib lifts the pen instead of drawing a fake diagonal across untraded time."""
    ct = np.asarray(ct, float); cp = np.asarray(cp, float)
    if ct.size < 2:
        return ct, cp
    gi = np.where(np.diff(ct) > max_gap_h * 3600.0)[0]
    if gi.size == 0:
        return ct, cp
    return np.insert(ct, gi + 1, ct[gi]), np.insert(cp, gi + 1, np.nan)


def guard_assemble(gid):
    g = gc.GROUPS[gid]; days = g["days"]; owner = gc.owner_map(gid); seam = g.get("seam")
    weekend_feeding = {d for d in days if _DOW[pd.Timestamp(f"{d[:4]}-{d[4:6]}-{d[6:]}").weekday()] == "Fri"}
    # S107: A is a full owner. agents/README.md has always said "A owns holiday/extended-weekend
    # reopens ONLY"; the coordinator carried a TODO instead ("handle when it occurs") and hard-failed
    # the whole block on any A-owned day. It occurred on G20 (Memorial Day 20260525, a real if thin
    # session). A is now loaded and selected like any other owner - EVERY other guard is unchanged
    # (owner match, numeric day-move, Friday sign-off). A must emit a `days` array on a day it owns,
    # not only its bridge block.
    specs = {t: load_specialist(gid, t) for t in ("A", "B", "C", "D", "E")}
    errs, block = [], []
    for d in days:
        o = owner[d]
        sp = specs.get(o)
        if sp is None:
            errs.append(f"{d}: owner {o} file missing"); continue
        day = sp.get(d)
        if day is None:
            errs.append(f"{d}: owner {o} did not forecast this day"); continue
        dm = day.get("guessed_net_usd")
        if not num(dm):
            errs.append(f"{d}: owner {o} guessed_net_usd non-numeric ({dm!r})"); continue
        if d in weekend_feeding and "handoff_out" not in day:
            errs.append(f"{d}: FRIDAY SIGN-OFF FAIL - weekend-feeding, owner {o} no handoff_out")
        block.append({"date": d, "dow": _DOW[pd.Timestamp(f'{d[:4]}-{d[4:6]}-{d[6:]}').weekday()],
                      "owner": o, "guess_day_move_usd": int(dm),
                      "overnight_gap_usd": day.get("overnight_gap_usd", 0) or 0,
                      "path_p50": [(r.get("et_hr"), r.get("p50")) for r in day.get("path_distribution", [])]})
    if errs:
        raise SystemExit("BLIND COORDINATOR GUARD FAILED:\n  " + "\n  ".join(errs))
    return block, seam


def score(block, actual):
    amap = {r["date"]: r for r in actual["days"]}
    rows, sabs, dh = [], 0, 0
    for b in block:
        a = amap[b["date"]]; am = a["day_move_usd"]; gm = b["guess_day_move_usd"]
        err = gm - am; hit = (gm > 0) == (am > 0) or (gm == 0 and am == 0)
        sabs += abs(err); dh += int(hit)
        rows.append({**b, "actual_day_move_usd": am, "err_usd": err, "dir_hit": hit})
    return rows, sabs, dh


def render(gid, rows, actual, seam):
    fig, ax = plt.subplots(figsize=(15, 7))
    ct, cp = break_gaps([t for t, _ in actual["continuous"]], [p for _, p in actual["continuous"]])
    adt = pd.to_datetime(ct, unit="s", utc=True).tz_convert("America/New_York")
    ax.plot(adt, cp, color="#1f6feb", lw=0.8, label="actual (MBO trades)", zorder=3)
    anchor = actual["anchor"]; run = 0.0; labelled = False
    for b in rows:
        d = b["date"]; gap = 0 if d == seam else b["overnight_gap_usd"]
        open_cum = run + gap; net = b["guess_day_move_usd"] - (0 if d == seam else gap)
        day0 = pd.Timestamp(f"{d[:4]}-{d[4:6]}-{d[6:]}", tz="America/New_York")
        path = [(h, v) for h, v in b["path_p50"] if h is not None and v is not None]
        if path:
            sx = [(day0 - pd.Timedelta(days=1) + pd.Timedelta(hours=h)) if h >= 18 else (day0 + pd.Timedelta(hours=h)) for h, _ in path]
            sy = [anchor + (open_cum + v) / MULT for _, v in path]
        else:
            sx = [day0 + pd.Timedelta(hours=8), day0 + pd.Timedelta(hours=16)]
            sy = [anchor + open_cum / MULT, anchor + (open_cum + net) / MULT]
        ax.plot(sx, sy, color="#d1242f", lw=1.2, zorder=4, label=("blind p50 path" if not labelled else None)); labelled = True
        run = open_cum + net
    ax.axhline(anchor, color="#999", lw=0.7, ls="--")
    if seam:
        sd = pd.Timestamp(f"{seam[:4]}-{seam[4:6]}-{seam[6:]}", tz="America/New_York")
        ax.axvline(sd, color="#999", lw=0.8, ls=":")
    ax.set_title(f"NG {gid.upper()} BLIND (5-specialist sequenced panel, s102.8 kitchen-sink) vs actual", fontsize=10, fontweight="bold")
    ax.set_ylabel("price ($/MMBtu)"); ax.legend(fontsize=8); ax.grid(True, color="#eee"); ax.set_axisbelow(True)
    out = os.path.join(RENDER_DIR, f"{gid}_blind_vs_actual.png")
    fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(out, dpi=130); plt.close(fig); return out


if __name__ == "__main__":
    gid = sys.argv[1]
    actual = json.load(open(os.path.join(RENDER_DIR, f"{gid}_actual.json")))
    block, seam = guard_assemble(gid)
    rows, sabs, dh = score(block, actual)
    json.dump({"group": gid, "phase": "blind", "brain_version": "s102.8", "anchor": actual["anchor"],
               "sum_abs_err_usd": sabs, "mean_abs_err_usd": round(sabs / len(rows)), "dir_hits": dh,
               "n": len(rows), "days": rows}, open(os.path.join(FC, f"grp{gid[1:]}.json"), "w"), indent=1)
    print(f"{'date':10} {'dow':4} {'own':4} {'guess':>8} {'actual':>8} {'err':>7} {'dir':>4}")
    for r in rows:
        print(f"{r['date']:10} {r['dow']:4} {r['owner']:4} {r['guess_day_move_usd']:8d} "
              f"{r['actual_day_move_usd']:8d} {r['err_usd']:7d} {'OK' if r['dir_hit'] else 'X':>4}")
    print(f"\n{gid.upper()} BLIND: {dh}/{len(rows)} dir, mean abs err {round(sabs/len(rows))}, sum abs {sabs}")
    try:
        print("render ->", render(gid, rows, actual, seam))
    except Exception as e:
        print(f"[render skipped: {e}]")
