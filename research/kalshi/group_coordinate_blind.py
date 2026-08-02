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
import render_util as ru
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
    # S108: accept the ENGINE filename too. Blind and refine run the IDENTICAL rule files, so the blind
    # writes grp<N>_mbo_specialist_<X>.json like the refine does - but this coordinator only ever looked
    # for grp<N>_blind_<X>.json, which forced a hand-built alias file every single blind run. That alias
    # lived in the scratchpad, which does not survive a session, so it was re-authored from memory each
    # time - a per-run manual step sitting directly upstream of the guard. Legacy name is still tried
    # FIRST so every committed pre-S108 blind coordinates byte-identically.
    n = gid[1:]
    for fname in (f"grp{n}_blind_{tag}.json", f"grp{n}_mbo_specialist_{tag}.json"):
        p = _find_report(fname)
        if p is not None:
            return {str(x["date"]).replace("-", ""): x for x in json.load(open(p)).get("days", [])}
    return None


def num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def day_move(day):
    """The scored day-move. The engine emits expected_magnitude_usd; the older blind alias files emit
    guessed_net_usd. Same number, two names - accept both rather than making a human retype it."""
    for k in ("guessed_net_usd", "expected_magnitude_usd"):
        if num(day.get(k)):
            return day[k]
    return day.get("guessed_net_usd", day.get("expected_magnitude_usd"))   # non-numeric -> guard reports it


def day_path(day):
    """Intraday p50 path as [(et_hr, cum_usd), ...]. The engine emits path_p50_curve (pairs); the alias
    files emit path_distribution (records). S107 lost the blind curve to exactly this kind of key
    mismatch - the render asked for one name, the file carried the other, and the curve silently
    vanished from the chart whose entire point was blind-vs-refine-vs-price."""
    pts = day.get("path_distribution")
    if pts:
        return [(r.get("et_hr"), r.get("p50")) for r in pts]
    return [(h, v) for h, v in (day.get("path_p50_curve") or [])]


break_gaps = ru.break_gaps   # S107: one implementation, in render_util


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
        dm = day_move(day)
        if not num(dm):
            errs.append(f"{d}: owner {o} day-move non-numeric ({dm!r}) - needs guessed_net_usd or "
                        f"expected_magnitude_usd"); continue
        if d in weekend_feeding and "handoff_out" not in day:
            errs.append(f"{d}: FRIDAY SIGN-OFF FAIL - weekend-feeding, owner {o} no handoff_out")
        block.append({"date": d, "dow": _DOW[pd.Timestamp(f'{d[:4]}-{d[4:6]}-{d[6:]}').weekday()],
                      "owner": o, "guess_day_move_usd": int(dm),
                      "overnight_gap_usd": day.get("overnight_gap_usd", 0) or 0,
                      "path_p50": day_path(day)})
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
    anchor = actual["anchor"]; run = 0.0
    fx, fy = [], []                     # S107: accumulate the WHOLE block, then draw ONE polyline
    for b in rows:
        d = b["date"]; gap = 0 if d == seam else b["overnight_gap_usd"]
        open_cum = run + gap; net = b["guess_day_move_usd"] - (0 if d == seam else gap)
        day0 = pd.Timestamp(f"{d[:4]}-{d[4:6]}-{d[6:]}", tz="America/New_York")
        path = [(h, v) for h, v in b["path_p50"] if h is not None and v is not None]
        # S110 (Greg spotted it in the render; measured after): the running level advances by NET
        # while the LINE is drawn to the last path point. If a specialist emits its path as
        # cum-from-PRIOR-CLOSE (gap included) instead of cum-from-OPEN, the pen lands one whole gap
        # above where the next day starts - THAT is why the lines did not connect. Measured: g22
        # 0/10 mismatched, g23 8/10, both Mondays off by exactly their +400 gap. Announced, not
        # hard-failed: no SCORE is affected (scoring reads guess_day_move_usd, never the path), and
        # hard-failing would invalidate committed artifacts - see DECISIONS D27, Greg's call.
        if path and abs(path[-1][1] - net) > 1:
            print(f"  [render-continuity] {d}: path ends {path[-1][1]:+.0f} but the running level "
                  f"advances by net {net:+.0f} (delta {path[-1][1]-net:+.0f}, gap {gap:+.0f}) - the "
                  f"drawn line will not meet the next day. Path convention is cum-from-OPEN.")
        if path:
            sx = ru.path_times(day0, path)
            sy = [anchor + (open_cum + v) / MULT for _, v in path]
        else:
            sx = [day0 + pd.Timedelta(hours=8), day0 + pd.Timedelta(hours=16)]
            sy = [anchor + open_cum / MULT, anchor + (open_cum + net) / MULT]
        fx.extend(sx); fy.extend(sy)
        run = open_cum + net
    ru.plot_forecast(ax, fx, fy, color="#d1242f", label="blind p50 path", lw=1.2, z=4)
    ax.axhline(anchor, color="#999", lw=0.7, ls="--")
    if seam:
        sd = pd.Timestamp(f"{seam[:4]}-{seam[4:6]}-{seam[6:]}", tz="America/New_York")
        ax.axvline(sd, color="#999", lw=0.8, ls=":")
    ax.set_title(f"NG {gid.upper()} BLIND (5-specialist sequenced panel, brain {ru.brain_version()}) vs actual", fontsize=10, fontweight="bold")
    ax.set_ylabel("price ($/MMBtu)"); ax.legend(fontsize=8); ax.grid(True, color="#eee"); ax.set_axisbelow(True)
    out = os.path.join(RENDER_DIR, f"{gid}_blind_vs_actual.png")
    fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(out, dpi=130); plt.close(fig); return out


if __name__ == "__main__":
    gid = sys.argv[1]
    actual = json.load(open(os.path.join(RENDER_DIR, f"{gid}_actual.json")))
    block, seam = guard_assemble(gid)
    rows, sabs, dh = score(block, actual)
    json.dump({"group": gid, "phase": "blind", "brain_version": ru.brain_version(), "anchor": actual["anchor"],
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
