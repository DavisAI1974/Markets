"""g17_coordinate.py - COORDINATOR for the G17 5-specialist BLIND panel (S105).
SELECT the owner per day (never average/forecast/scale) under the guard + Friday sign-off; assemble
forecasts/grp17.json; score vs the two-leg actual (g17_actual.json); render actual + own p50 path only.

GUARD (Greg S104, ported): every emitted day-move is verbatim the owner's guessed_net_usd; a
missing/non-numeric/wrong-owner posterior is a HARD FAILURE, never a fallback. FRIDAY SIGN-OFF: a
weekend-feeding day (0417, 0424) whose owner day lacks handoff_out is not assemblable.
RENDER RULE (Greg S104): actual curve + the forecast's OWN p50 path only; no re-anchored/scaled lines,
NaN breaks across the closed market (no gap bridges).
"""
import os, json, glob
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
FC = os.path.join(HERE, "forecasts")
RENDER_DIR = os.path.join(HERE, "renders", "ng_refine_s95")
ACTUAL = os.path.join(RENDER_DIR, "g17_actual.json")
MULT = 10000.0
DAYS = ["20260413","20260414","20260415","20260416","20260417","20260420","20260421","20260422","20260423","20260424"]
SEAM = "20260421"
OWNER = {"20260413":"B","20260420":"B","20260414":"C","20260415":"C","20260422":"C",
         "20260416":"D","20260423":"D","20260417":"E","20260421":"E","20260424":"E"}
WEEKEND_FEEDING = {"20260417","20260424"}   # Fridays -> require handoff_out
_DOW = ("Mon","Tue","Wed","Thu","Fri","Sat","Sun")


def load_specialist(tag):
    p = os.path.join(FC, f"grp17_blind_{tag}.json")
    if not os.path.exists(p):
        return None
    d = json.load(open(p))
    return {str(day["date"]).replace("-", ""): day for day in d.get("days", [])}


def guard_and_assemble():
    specs = {t: load_specialist(t) for t in ("B", "C", "D", "E")}
    errs, block = [], []
    for d in DAYS:
        owner = OWNER[d]
        sp = specs.get(owner)
        if sp is None:
            errs.append(f"{d}: owner {owner} file missing"); continue
        day = sp.get(d)
        if day is None:
            errs.append(f"{d}: owner {owner} did not forecast this day (SELECT would emit a non-owned number)"); continue
        dm = day.get("guessed_net_usd")
        if not isinstance(dm, (int, float)):
            errs.append(f"{d}: owner {owner} guessed_net_usd non-numeric ({dm!r})"); continue
        if d in WEEKEND_FEEDING and "handoff_out" not in day:
            errs.append(f"{d}: FRIDAY SIGN-OFF FAIL - weekend-feeding day, owner {owner} emitted no handoff_out")
        block.append({"date": d, "dow": _DOW[__import__('pandas').Timestamp(f'{d[:4]}-{d[4:6]}-{d[6:]}').weekday()],
                      "owner": owner, "guess_day_move_usd": int(dm),
                      "overnight_gap_usd": day.get("overnight_gap_usd", 0) or 0,
                      "path_p50": [(r.get("et_hr"), r.get("p50")) for r in day.get("path_distribution", [])],
                      "handoff_out": day.get("handoff_out")})
    if errs:
        raise SystemExit("COORDINATOR GUARD FAILED:\n  " + "\n  ".join(errs))
    return block


def score(block, actual):
    amap = {r["date"]: r for r in actual["days"]}
    rows, sum_abs, dir_hits = [], 0, 0
    for b in block:
        a = amap[b["date"]]
        gm, am = b["guess_day_move_usd"], a["day_move_usd"]
        err = gm - am
        dir_hit = (gm > 0) == (am > 0) or (gm == 0 and am == 0)
        sum_abs += abs(err); dir_hits += int(dir_hit)
        rows.append({**b, "actual_day_move_usd": am, "err_usd": err, "dir_hit": dir_hit,
                     "actual_close": a["close"]})
    return rows, sum_abs, dir_hits


def render(rows, actual):
    fig, ax = plt.subplots(figsize=(15, 7))
    # actual continuous (two-leg, seam removed)
    ct = np.array([t for t, _ in actual["continuous"]]); cp = np.array([p for _, p in actual["continuous"]])
    import pandas as pd
    adt = pd.to_datetime(ct, unit="s", utc=True).tz_convert("America/New_York")
    ax.plot(adt, cp, color="#1f6feb", lw=0.8, label="actual (two-leg NGK26->NGM26, MBO trades)", zorder=3)
    # own p50 path: per day, cum-from-anchor = running open_cum + intraday p50 (NaN break across close)
    anchor = actual["anchor"]; run_close_cum = 0.0
    labelled = False
    for b in rows:
        d = b["date"]
        gap = 0 if d == SEAM else b["overnight_gap_usd"]
        open_cum = run_close_cum + gap
        net = b["guess_day_move_usd"] - (0 if d == SEAM else gap)
        path = [(h, v) for h, v in b["path_p50"] if h is not None and v is not None]
        day0 = pd.Timestamp(f"{d[:4]}-{d[4:6]}-{d[6:]}", tz="America/New_York")
        sx, sy = [], []
        if path:
            for h, v in path:
                ts = (day0 - pd.Timedelta(days=1) + pd.Timedelta(hours=h)) if h >= 18 else (day0 + pd.Timedelta(hours=h))
                sx.append(ts); sy.append(anchor + (open_cum + v) / MULT)
        else:
            sx = [day0 + pd.Timedelta(hours=8), day0 + pd.Timedelta(hours=16)]
            sy = [anchor + open_cum / MULT, anchor + (open_cum + net) / MULT]
        ax.plot(sx, sy, color="#d1242f", lw=1.2, ls="-", zorder=4,
                label=("blind p50 path (own forecast)" if not labelled else None))
        labelled = True
        run_close_cum = open_cum + net
    ax.axhline(anchor, color="#999", lw=0.7, ls="--")
    # seam marker
    sd = pd.Timestamp(f"{SEAM[:4]}-{SEAM[4:6]}-{SEAM[6:]}", tz="America/New_York")
    ax.axvline(sd, color="#999", lw=0.8, ls=":")
    ax.text(sd, ax.get_ylim()[0], f" roll seam {actual['seam_offset']:+.3f} (never traded)", fontsize=7, color="#666", va="bottom")
    ax.set_title("NG G17 BLIND (5-specialist panel) vs actual - Sun 2026-04-12 .. Fri 2026-04-24  "
                 "(two-leg May/NGK26 -> June/NGM26, anchor 2.653)", fontsize=10, fontweight="bold")
    ax.set_ylabel("price ($/MMBtu, seam-adjusted)"); ax.legend(fontsize=8, loc="best")
    ax.grid(True, color="#eee"); ax.set_axisbelow(True)
    out = os.path.join(RENDER_DIR, "g17_blind_vs_actual.png")
    fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(out, dpi=130); plt.close(fig)
    return out


if __name__ == "__main__":
    actual = json.load(open(ACTUAL))
    block = guard_and_assemble()
    rows, sum_abs, dir_hits = score(block, actual)
    json.dump({"group": "g17", "phase": "blind", "brain_version": "s102.5", "anchor": actual["anchor"],
               "sum_abs_err_usd": sum_abs, "mean_abs_err_usd": round(sum_abs / len(rows)),
               "dir_hits": dir_hits, "n": len(rows), "days": rows},
              open(os.path.join(FC, "grp17.json"), "w"), indent=1)
    print(f"{'date':10} {'dow':4} {'own':4} {'guess_dm':>9} {'actual_dm':>10} {'err':>7} {'dir':>4}")
    for r in rows:
        print(f"{r['date']:10} {r['dow']:4} {r['owner']:4} {r['guess_day_move_usd']:9d} "
              f"{r['actual_day_move_usd']:10d} {r['err_usd']:7d} {'OK' if r['dir_hit'] else 'X':>4}")
    print(f"\nBLIND: {dir_hits}/{len(rows)} direction, mean abs err {round(sum_abs/len(rows))} USD, sum abs {sum_abs}")
    try:
        png = render(rows, actual); print(f"render -> {png}")
    except Exception as e:
        print(f"[render skipped: {e}]")
