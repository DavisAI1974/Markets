"""g17_refine_coordinate.py - COORDINATOR for the G17 MBO 5-specialist REFINE (round 1, S105).
SELECT owner per day (guard + Friday sign-off), assemble grp17_mbo_refined.json from the specialist
posteriors' expected_magnitude_usd (verbatim, never averaged/scaled), score refined vs actual and vs
the immutable blind, render actual + refined p50 path only.
"""
import os, json, glob
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
FC = os.path.join(HERE, "forecasts")
RENDER_DIR = os.path.join(HERE, "renders", "ng_refine_s95")
ACTUAL = os.path.join(RENDER_DIR, "g17_actual.json")
BLIND = os.path.join(FC, "grp17.json")
MULT = 10000.0
DAYS = ["20260413","20260414","20260415","20260416","20260417","20260420","20260421","20260422","20260423","20260424"]
SEAM = "20260421"
OWNER = {"20260413":"B","20260420":"B","20260414":"C","20260415":"C","20260422":"C",
         "20260416":"D","20260423":"D","20260417":"E","20260421":"E","20260424":"E"}
WEEKEND_FEEDING = {"20260417","20260424"}
_DOW = ("Mon","Tue","Wed","Thu","Fri","Sat","Sun")


def load_spec(tag):
    p = os.path.join(FC, f"grp17_mbo_specialist_{tag}.json")
    if not os.path.exists(p):
        return None
    d = json.load(open(p))
    days = d.get("days", [])
    return {str(x["date"]).replace("-", ""): x for x in days}


def num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def guard_assemble():
    specs = {t: load_spec(t) for t in ("B", "C", "D", "E")}
    errs, block = [], []
    for d in DAYS:
        owner = OWNER[d]; sp = specs.get(owner)
        if sp is None:
            errs.append(f"{d}: owner {owner} file missing"); continue
        day = sp.get(d)
        if day is None:
            errs.append(f"{d}: owner {owner} did not refine this day"); continue
        dm = day.get("expected_magnitude_usd")
        if not num(dm):
            errs.append(f"{d}: owner {owner} expected_magnitude_usd non-numeric ({dm!r})"); continue
        if d in WEEKEND_FEEDING and "handoff_out" not in day:
            errs.append(f"{d}: FRIDAY SIGN-OFF FAIL - weekend-feeding, owner {owner} no handoff_out")
        block.append({"date": d, "dow": _DOW[pd.Timestamp(f'{d[:4]}-{d[4:6]}-{d[6:]}').weekday()],
                      "owner": owner, "refined_day_move_usd": int(round(dm)),
                      "path_p50": day.get("path_p50_curve", []),
                      "weight_assigned": day.get("weight_assigned"),
                      "handoff_out": day.get("handoff_out"),
                      "mbo_verdict": day.get("mbo_verdict")})
    if errs:
        raise SystemExit("REFINE COORDINATOR GUARD FAILED:\n  " + "\n  ".join(errs))
    return block


def score(block, actual, blind_days):
    amap = {r["date"]: r for r in actual["days"]}
    bmap = {r["date"]: r for r in blind_days}
    rows, sabs, dh = [], 0, 0
    for b in block:
        a = amap[b["date"]]; am = a["day_move_usd"]; rm = b["refined_day_move_usd"]
        err = rm - am; hit = (rm > 0) == (am > 0) or (rm == 0 and am == 0)
        sabs += abs(err); dh += int(hit)
        bl = bmap.get(b["date"], {})
        rows.append({**b, "actual_day_move_usd": am, "refined_err_usd": err, "dir_hit": hit,
                     "blind_day_move_usd": bl.get("guess_day_move_usd"), "blind_err_usd": bl.get("err_usd"),
                     "blind_dir_hit": bl.get("dir_hit")})
    return rows, sabs, dh


def render(rows, actual):
    fig, ax = plt.subplots(figsize=(15, 7))
    ct = np.array([t for t, _ in actual["continuous"]]); cp = np.array([p for _, p in actual["continuous"]])
    adt = pd.to_datetime(ct, unit="s", utc=True).tz_convert("America/New_York")
    ax.plot(adt, cp, color="#1f6feb", lw=0.8, label="actual (two-leg NGK26->NGM26, MBO trades)", zorder=3)
    anchor = actual["anchor"]; run = 0.0; labelled = False
    for b in rows:
        d = b["date"]; gap = 0 if d == SEAM else 0
        net = b["refined_day_move_usd"]
        day0 = pd.Timestamp(f"{d[:4]}-{d[4:6]}-{d[6:]}", tz="America/New_York")
        path = [(h, v) for h, v in (b["path_p50"] or []) if h is not None and v is not None]
        sx, sy = [], []
        if path:
            for h, v in path:
                ts = (day0 - pd.Timedelta(days=1) + pd.Timedelta(hours=h)) if h >= 18 else (day0 + pd.Timedelta(hours=h))
                sx.append(ts); sy.append(anchor + (run + v) / MULT)
        else:
            sx = [day0 + pd.Timedelta(hours=8), day0 + pd.Timedelta(hours=16)]
            sy = [anchor + run / MULT, anchor + (run + net) / MULT]
        ax.plot(sx, sy, color="#1a7f37", lw=1.3, zorder=4,
                label=("refined p50 path (MBO posterior)" if not labelled else None)); labelled = True
        run += net
    ax.axhline(anchor, color="#999", lw=0.7, ls="--")
    sd = pd.Timestamp(f"{SEAM[:4]}-{SEAM[4:6]}-{SEAM[6:]}", tz="America/New_York")
    ax.axvline(sd, color="#999", lw=0.8, ls=":"); ax.text(sd, ax.get_ylim()[0], f" roll seam {actual['seam_offset']:+.3f} (never traded)", fontsize=7, color="#666", va="bottom")
    ax.set_title("NG G17 REFINED (5-specialist MBO posterior, s102.6) vs actual - Sun 2026-04-12 .. Fri 2026-04-24", fontsize=10, fontweight="bold")
    ax.set_ylabel("price ($/MMBtu, seam-adjusted)"); ax.legend(fontsize=8); ax.grid(True, color="#eee"); ax.set_axisbelow(True)
    out = os.path.join(RENDER_DIR, "g17_refined_vs_actual.png")
    fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(out, dpi=130); plt.close(fig); return out


if __name__ == "__main__":
    actual = json.load(open(ACTUAL)); blind = json.load(open(BLIND))
    block = guard_assemble()
    rows, sabs, dh = score(block, actual, blind["days"])
    bl_dh = sum(1 for r in rows if r["blind_dir_hit"]); bl_sabs = sum(abs(r["blind_err_usd"]) for r in rows if r["blind_err_usd"] is not None)
    json.dump({"group": "g17", "phase": "mbo_refined_r1", "brain_version": "s102.6", "anchor": actual["anchor"],
               "sum_abs_err_usd": sabs, "mean_abs_err_usd": round(sabs/len(rows)), "dir_hits": dh, "n": len(rows),
               "blind_dir_hits": bl_dh, "blind_sum_abs_err_usd": bl_sabs, "days": rows},
              open(os.path.join(FC, "grp17_mbo_refined.json"), "w"), indent=1)
    print(f"{'date':10} {'dow':4} {'own':4} {'blind':>7} {'refined':>8} {'actual':>7} {'r_err':>7} {'dir':>4}")
    for r in rows:
        print(f"{r['date']:10} {r['dow']:4} {r['owner']:4} {str(r['blind_day_move_usd']):>7} "
              f"{r['refined_day_move_usd']:8d} {r['actual_day_move_usd']:7d} {r['refined_err_usd']:7d} {'OK' if r['dir_hit'] else 'X':>4}")
    print(f"\nBLIND:   {bl_dh}/{len(rows)} dir, sum abs {bl_sabs}")
    print(f"REFINED: {dh}/{len(rows)} dir, mean abs err {round(sabs/len(rows))}, sum abs {sabs}")
    try:
        print("render ->", render(rows, actual))
    except Exception as e:
        print(f"[render skipped: {e}]")
