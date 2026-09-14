"""g17_actual.py - build the G17 two-leg ACTUAL curve from per-contract MBO trades.
May/NGK26 for 0413-0420, June/NGM26 for 0421-0424; 0421 May->June roll seam removed (never-traded).
Anchor = 2026-04-10 close 2.653 (NGK26). Mirrors coordinate_g15_mbo.build_actual exactly.
Writes renders/ng_refine_s95/g17_actual.json {anchor, seam, seam_offset, days:[...], continuous:[[t,p],...]}.
"""
import os, json
import numpy as np, pandas as pd
import databento as db

HERE = os.path.dirname(os.path.abspath(__file__))
LEG_DIR = os.path.join(HERE, "..", "..", "data", "ng_mbo_g17")
OUT = os.path.join(HERE, "renders", "ng_refine_s95", "g17_actual.json")
ET = "America/New_York"; MULT = 10000.0
ANCHOR = 2.653
DAYS = ["20260413","20260414","20260415","20260416","20260417","20260420","20260421","20260422","20260423","20260424"]
SEAM = "20260421"                                   # May/NGK26 -> June/NGM26, never traded
LEG = {d: ("ng_mbo_ngm26" if d >= "20260421" else "ng_mbo_ngk26") for d in DAYS}
_DOW = ("Mon","Tue","Wed","Thu","Fri","Sat","Sun")


def load_trades(day):
    path = os.path.join(LEG_DIR, f"{LEG[day]}_{day}.dbn.zst")
    store = db.DBNStore.from_file(path)
    rows = []
    for r in store:
        if type(r).__name__ != "MBOMsg":
            continue
        av = getattr(r.action, "value", r.action)
        if str(av) != "T":
            continue
        p = r.price
        if p in (None, 9223372036854775807, -9223372036854775808):
            continue
        rows.append((int(r.ts_event) / 1e9, p / 1e9))
    rows.sort()
    return np.array([x[0] for x in rows]), np.array([x[1] for x in rows])


def build_actual():
    recs, cont_t, cont_p, cum_seam = [], [], [], 0.0
    prev_close = ANCHOR
    for d in DAYS:
        ts, px = load_trades(d)
        if px.size == 0:
            print(f"  WARN {d}: no trades"); continue
        o, c = float(px[0]), float(px[-1])
        if d == SEAM:
            cum_seam += round(o - prev_close, 3)                       # May->June offset, never traded
        gap = 0 if d == SEAM else round((o - prev_close) * MULT)
        net = round((c - o) * MULT)
        recs.append({"date": d, "dow": _DOW[pd.Timestamp(f"{d[:4]}-{d[4:6]}-{d[6:]}").weekday()],
                     "leg": LEG[d], "open": round(o, 3), "close": round(c, 3),
                     "net_usd": net, "gap_usd": gap,
                     "day_move_usd": (net if d == SEAM else gap + net),
                     "cum_from_anchor_usd": round((c - ANCHOR - cum_seam) * MULT)})
        idx = np.linspace(0, len(px) - 1, min(len(px), 400)).astype(int)
        cont_t.extend(ts[idx].tolist()); cont_p.extend((px[idx] - cum_seam).tolist())
        prev_close = c
    return recs, cont_t, cont_p, cum_seam


if __name__ == "__main__":
    recs, ct, cp, seam = build_actual()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"anchor": ANCHOR, "seam": SEAM, "seam_offset": round(seam, 4),
               "days": recs, "continuous": [[t, p] for t, p in zip(ct, cp)]}, open(OUT, "w"))
    print(f"anchor {ANCHOR}  seam_offset {seam:+.4f} (never traded)")
    print(f"{'date':10} {'dow':4} {'leg':14} {'open':>7} {'close':>7} {'gap':>7} {'net':>7} {'day_move':>9} {'cum':>8}")
    for r in recs:
        print(f"{r['date']:10} {r['dow']:4} {r['leg']:14} {r['open']:7.3f} {r['close']:7.3f} "
              f"{r['gap_usd']:7d} {r['net_usd']:7d} {r['day_move_usd']:9d} {r['cum_from_anchor_usd']:8d}")
    print(f"\nactual block cum-from-anchor (2.653) at 0424 close: {recs[-1]['cum_from_anchor_usd']:+d} USD")
