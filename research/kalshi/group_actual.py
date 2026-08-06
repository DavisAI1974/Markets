"""group_actual.py - build ANY group's two-leg ACTUAL curve from per-contract MBO trades, config-driven.
    python research/kalshi/group_actual.py g18
Reads group_config.GROUPS; loads each day's leg via leg_for(); removes the roll-seam offset (never-traded);
flags DST-transition days (session 23h spring / 25h fall) so the ET grid is not misaligned. tz_convert is
DST-aware, so continuous-curve wall times are already correct. Writes renders/ng_refine_s95/<gid>_actual.json.
Per-contract day-files are expected local under data/ng_mbo_g17/<store>_<day>.dbn.zst (staged by stage_group).
"""
import os, sys, json
import numpy as np, pandas as pd
import databento as db
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import group_config as gc

HERE = os.path.dirname(os.path.abspath(__file__))
LEG_DIR = os.path.join(HERE, "..", "..", "data", "ng_mbo_g17")   # shared local per-contract cache
RENDER_DIR = os.path.join(HERE, "renders", "ng_refine_s95")
ET = "America/New_York"; MULT = gc.MULT


def load_trades(store, day):
    path = os.path.join(LEG_DIR, f"{store}_{day}.dbn.zst")
    s = db.DBNStore.from_file(path)
    rows = []
    for r in s:
        if type(r).__name__ != "MBOMsg":
            continue
        if str(getattr(r.action, "value", r.action)) != "T":
            continue
        p = r.price
        if p in (None, 9223372036854775807, -9223372036854775808):
            continue
        rows.append((int(r.ts_event) / 1e9, p / 1e9))
    rows.sort()
    return np.array([x[0] for x in rows]), np.array([x[1] for x in rows])


def build(gid):
    g = gc.GROUPS[gid]
    anchor = g["anchor"]
    if anchor is None:
        raise SystemExit(f"{gid}: anchor is None - resolve it from the prior group's actual close first "
                         f"(anchor_date {g['anchor_date']}).")
    seam = g.get("seam")
    recs, cont_t, cont_p, cum_seam = [], [], [], 0.0
    prev_close = anchor
    for d in g["days"]:
        store = gc.leg_for(gid, d)
        ts, px = load_trades(store, d)
        if px.size == 0:
            print(f"  WARN {d}: no trades ({store})"); continue
        o, c = float(px[0]), float(px[-1])
        if d == seam:
            cum_seam += round(o - prev_close, 3)
        gap = 0 if d == seam else round((o - prev_close) * MULT)
        net = round((c - o) * MULT)
        rec = {"date": d, "dow": gc._dow(d), "leg": store, "owner": gc.owner_map(gid)[d],
               "open": round(o, 3), "close": round(c, 3), "net_usd": net, "gap_usd": gap,
               "day_move_usd": (net if d == seam else gap + net),
               "cum_from_anchor_usd": round((c - anchor - cum_seam) * MULT)}
        if gc.dst_flag(d):
            rec["dst"] = gc.dst_flag(d)
        if d in g.get("holidays", []):
            rec["holiday"] = gc.HOLIDAYS.get(d, {"name": "holiday"})
        recs.append(rec)
        idx = np.linspace(0, len(px) - 1, min(len(px), 400)).astype(int)
        cont_t.extend(ts[idx].tolist()); cont_p.extend((px[idx] - cum_seam).tolist())
        prev_close = c
    return {"group": gid, "anchor": anchor, "seam": seam, "seam_offset": round(cum_seam, 4),
            "basis": g["basis"], "days": recs, "continuous": [[t, p] for t, p in zip(cont_t, cont_p)]}


if __name__ == "__main__":
    gid = sys.argv[1]
    out = build(gid)
    os.makedirs(RENDER_DIR, exist_ok=True)
    json.dump(out, open(os.path.join(RENDER_DIR, f"{gid}_actual.json"), "w"))
    print(f"{gid}  anchor {out['anchor']}  seam_offset {out['seam_offset']:+.4f}")
    print(f"{'date':10} {'dow':4} {'own':3} {'leg':14} {'open':>7} {'close':>7} {'gap':>7} {'net':>7} {'day_move':>9} {'cum':>8} mark")
    for r in out["days"]:
        mark = " ".join([k for k in ("dst", "holiday") if k in r])
        print(f"{r['date']:10} {r['dow']:4} {r['owner']:3} {r['leg']:14} {r['open']:7.3f} {r['close']:7.3f} "
              f"{r['gap_usd']:7d} {r['net_usd']:7d} {r['day_move_usd']:9d} {r['cum_from_anchor_usd']:8d} {mark}")
    print(f"\n{gid} actual cum-from-anchor at last close: {out['days'][-1]['cum_from_anchor_usd']:+d} USD")
