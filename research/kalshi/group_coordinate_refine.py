"""group_coordinate_refine.py - GENERIC refine coordinator (S105), config-driven:
    python research/kalshi/group_coordinate_refine.py g18 [--r2]

SELECT owner per day under the GUARD (+ Friday sign-off), assemble grp<n>_mbo_refined[_r2].json from the
specialist posteriors' expected_magnitude_usd (verbatim), score refined vs actual AND vs the immutable
blind. RENDER (Greg S105): the actual PRICE CURVE + the BLIND (1st pass, one color) + the REFINE (last
pass, another color) on one chart. group_config-driven; g17_refine_coordinate.py kept as the G17 record.
"""
import os, sys, json
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import group_config as gc

HERE = os.path.dirname(os.path.abspath(__file__))
FC = os.path.join(HERE, "forecasts")
RENDER_DIR = os.path.join(HERE, "renders", "ng_refine_s95")
MULT = gc.MULT
_DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _find_report(fname):
    """Autonomous-safe report routing: find the file wherever the agent wrote it."""
    for d in (FC, os.path.join(HERE, "..", "..", "forecasts")):
        p = os.path.join(d, fname)
        if os.path.exists(p):
            return p
    return None


def load_spec(gid, tag, rnd):
    suffix = "_r2" if rnd == 2 else ""
    p = _find_report(f"grp{gid[1:]}_mbo_specialist_{tag}{suffix}.json")
    if p is None:
        return None
    return {str(x["date"]).replace("-", ""): x for x in json.load(open(p)).get("days", [])}


def num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def guard_assemble(gid, rnd):
    g = gc.GROUPS[gid]; days = g["days"]; owner = gc.owner_map(gid)
    weekend_feeding = {d for d in days if _DOW[pd.Timestamp(f"{d[:4]}-{d[4:6]}-{d[6:]}").weekday()] == "Fri"}
    specs = {t: load_spec(gid, t, rnd) for t in ("B", "C", "D", "E")}
    errs, block = [], []
    for d in days:
        o = owner[d]
        if o == "A":
            errs.append(f"{d}: owner A holiday reopen - handle separately"); continue
        sp = specs.get(o)
        if sp is None or sp.get(d) is None:
            errs.append(f"{d}: owner {o} posterior missing"); continue
        day = sp[d]; dm = day.get("expected_magnitude_usd")
        if not num(dm):
            errs.append(f"{d}: owner {o} expected_magnitude_usd non-numeric ({dm!r})"); continue
        if d in weekend_feeding and "handoff_out" not in day:
            errs.append(f"{d}: FRIDAY SIGN-OFF FAIL - {o} no handoff_out")
        block.append({"date": d, "dow": _DOW[pd.Timestamp(f'{d[:4]}-{d[4:6]}-{d[6:]}').weekday()],
                      "owner": o, "refined_day_move_usd": int(round(dm)),
                      "path_p50": day.get("path_p50_curve", [])})
    if errs:
        raise SystemExit("REFINE COORDINATOR GUARD FAILED:\n  " + "\n  ".join(errs))
    return block


def render(gid, rows, actual, blind_days):
    seam = gc.GROUPS[gid].get("seam"); anchor = actual["anchor"]
    fig, ax = plt.subplots(figsize=(15, 7))
    ct = np.array([t for t, _ in actual["continuous"]]); cp = np.array([p for _, p in actual["continuous"]])
    adt = pd.to_datetime(ct, unit="s", utc=True).tz_convert("America/New_York")
    ax.plot(adt, cp, color="#1f6feb", lw=1.0, label="actual PRICE CURVE (MBO trades)", zorder=2)
    bmap = {r["date"]: r for r in blind_days}

    def step_line(get_move, get_path, color, label, z):
        run = 0.0; lab = False
        for b in rows:
            d = b["date"]; gap = 0 if d == seam else 0
            net = get_move(b); day0 = pd.Timestamp(f"{d[:4]}-{d[4:6]}-{d[6:]}", tz="America/New_York")
            path = [(h, v) for h, v in (get_path(b) or []) if h is not None and v is not None]
            if path:
                sx = [(day0 - pd.Timedelta(days=1) + pd.Timedelta(hours=h)) if h >= 18 else (day0 + pd.Timedelta(hours=h)) for h, _ in path]
                sy = [anchor + (run + v) / MULT for _, v in path]
            else:
                sx = [day0 + pd.Timedelta(hours=8), day0 + pd.Timedelta(hours=16)]
                sy = [anchor + run / MULT, anchor + (run + net) / MULT]
            ax.plot(sx, sy, color=color, lw=1.3, zorder=z, label=(label if not lab else None)); lab = True
            run += net
    # 1st pass = BLIND (red), last pass = REFINE (green)
    step_line(lambda b: bmap.get(b["date"], {}).get("guess_day_move_usd", 0),
              lambda b: [(r.get("et_hr"), r.get("p50")) for r in (bmap.get(b["date"], {}).get("path_distribution") or [])] or None,
              "#d1242f", "BLIND (1st pass)", 3)
    step_line(lambda b: b["refined_day_move_usd"], lambda b: b["path_p50"], "#1a7f37", "REFINE (last pass)", 4)
    ax.axhline(anchor, color="#999", lw=0.7, ls="--")
    if seam:
        sd = pd.Timestamp(f"{seam[:4]}-{seam[4:6]}-{seam[6:]}", tz="America/New_York")
        ax.axvline(sd, color="#999", lw=0.8, ls=":")
    ax.set_title(f"NG {gid.upper()}: actual price + BLIND (1st) + REFINE (last) - s102.8", fontsize=10, fontweight="bold")
    ax.set_ylabel("price ($/MMBtu)"); ax.legend(fontsize=8); ax.grid(True, color="#eee"); ax.set_axisbelow(True)
    out = os.path.join(RENDER_DIR, f"{gid}_blind_vs_refine_vs_price.png")
    fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(out, dpi=130); plt.close(fig); return out


if __name__ == "__main__":
    gid = sys.argv[1]; rnd = 2 if "--r2" in sys.argv else 1; tag = "_r2" if rnd == 2 else ""
    actual = json.load(open(os.path.join(RENDER_DIR, f"{gid}_actual.json")))
    blind = json.load(open(os.path.join(FC, f"grp{gid[1:]}.json")))
    block = guard_assemble(gid, rnd)
    amap = {r["date"]: r for r in actual["days"]}; bmap = {r["date"]: r for r in blind["days"]}
    sabs = dh = 0; rows = []
    for b in block:
        am = amap[b["date"]]["day_move_usd"]; rm = b["refined_day_move_usd"]; err = rm - am
        hit = (rm > 0) == (am > 0) or (rm == 0 and am == 0); sabs += abs(err); dh += int(hit)
        rows.append({**b, "actual_day_move_usd": am, "refined_err_usd": err, "dir_hit": hit,
                     "blind_day_move_usd": bmap.get(b["date"], {}).get("guess_day_move_usd")})
    bl_dh = sum(1 for r in rows if (r["blind_day_move_usd"] or 0 > 0) == (r["actual_day_move_usd"] > 0))
    json.dump({"group": gid, "phase": f"mbo_refined_r{rnd}", "brain_version": "s102.8", "mean_abs_err_usd": round(sabs/len(rows)),
               "dir_hits": dh, "n": len(rows), "sum_abs_err_usd": sabs, "days": rows},
              open(os.path.join(FC, f"grp{gid[1:]}_mbo_refined{tag}.json"), "w"), indent=1)
    print(f"{'date':10} {'own':4} {'blind':>7} {'refined':>8} {'actual':>7} {'err':>7} {'dir':>4}")
    for r in rows:
        print(f"{r['date']:10} {r['owner']:4} {str(r['blind_day_move_usd']):>7} {r['refined_day_move_usd']:8d} "
              f"{r['actual_day_move_usd']:7d} {r['refined_err_usd']:7d} {'OK' if r['dir_hit'] else 'X':>4}")
    print(f"\n{gid.upper()} REFINE r{rnd}: {dh}/{len(rows)} dir, mean abs err {round(sabs/len(rows))}, sum abs {sabs}")
    try:
        print("render ->", render(gid, rows, actual, blind["days"]))
    except Exception as e:
        print(f"[render skipped: {e}]")
