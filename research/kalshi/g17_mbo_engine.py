"""g17_mbo_engine.py - G17 MBO causal evidence for the refine (S105). Same extraction as
g15_mbo_engine.per_day_evidence (signed flow by phase, onset, give-back/turn, divergence/absorption),
run on the local per-contract NGK26/NGM26 legs (data/ng_mbo_g17). Writes g17_mbo_evidence.json.
Config from group_config (G17: anchor 2.653, seam 0421 May/NGK26->June/NGM26 never-traded)."""
import os, sys, json
import numpy as np, pandas as pd, databento as db
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import group_config as gc

HERE = os.path.dirname(os.path.abspath(__file__))
LEG_DIR = os.path.join(HERE, "..", "..", "data", "ng_mbo_g17")
OUT = os.path.join(HERE, "renders", "ng_refine_s95")
ET = "America/New_York"; MULT = 10000.0
G = gc.GROUPS["g17"]; DAYS = G["days"]; SEAM_DAY = G["seam"]
IID = {"ng_mbo_ngk26": 996, "ng_mbo_ngm26": None}   # May/NGK26=996 (Kalshi underlying); June label only
_DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _dir(side):
    t = str(getattr(side, "name", side)).upper()
    return 1 if t in ("B", "BID", "BUY") else (-1 if t in ("A", "ASK", "SELL") else 0)


def load_trades(day):
    store = db.DBNStore.from_file(os.path.join(LEG_DIR, f"{gc.leg_for('g17', day)}_{day}.dbn.zst"))
    rows = []
    for r in store:
        if type(r).__name__ != "MBOMsg":
            continue
        if str(getattr(r.action, "value", r.action)) != "T":
            continue
        p = r.price
        if p in (None, 9223372036854775807, -9223372036854775808):
            continue
        rows.append((int(r.ts_event), p / 1e9, float(r.size), _dir(r.side)))
    rows.sort(key=lambda x: x[0])
    ts = np.array([x[0] for x in rows], dtype=np.float64) / 1e9
    return ts, np.array([x[1] for x in rows]), np.array([x[2] for x in rows]), np.array([x[3] for x in rows])


def per_day_evidence(day):
    ts, px, sz, sd = load_trades(day)
    et = pd.to_datetime(ts, unit="s", utc=True).tz_convert(ET)
    o, c = float(px[0]), float(px[-1]); net = round((c - o) * MULT)
    cum = (px - o) * MULT
    hi_i = int(np.argmax(cum)); lo_i = int(np.argmin(cum)); hi, lo = float(cum[hi_i]), float(cum[lo_i])
    net_sign = 1 if net > 0 else (-1 if net < 0 else 0)
    give_up = hi - net; give_dn = net - lo
    if give_dn >= give_up and give_dn > 300 and lo < -200:
        turn_kind, turn_i, turn_mag = "turn_up", lo_i, give_dn
    elif give_up > give_dn and give_up > 300 and hi > 200:
        turn_kind, turn_i, turn_mag = "turn_down", hi_i, give_up
    else:
        turn_kind, turn_i, turn_mag = "none", None, max(give_up, give_dn)
    turn_et = str(et[turn_i]) if turn_i is not None else None
    thr = max(250.0, 0.4 * max(abs(hi), abs(lo))); onset_i = None
    for i in range(len(cum)):
        if abs(cum[i]) >= thr:
            onset_i = i; break
    onset_et = str(et[onset_i]) if onset_i is not None else None
    onset_dir = ("up" if cum[onset_i] > 0 else "down") if onset_i is not None else None
    total_sflow = float((sd * sz).sum())
    t0, t1 = ts[0], ts[-1]; span = t1 - t0; ph = []
    for k in range(3):
        m = (ts >= t0 + span * k / 3) & (ts < t0 + span * (k + 1) / 3)
        if k == 2:
            m = (ts >= t0 + span * k / 3)
        pxc = round((float(px[m][-1]) - float(px[m][0])) * MULT) if m.any() else 0
        ph.append({"sflow": round(float((sd[m] * sz[m]).sum())), "pxchg": pxc, "vol": round(float(sz[m].sum()))})
    sflow_sign = 1 if total_sflow > 0 else (-1 if total_sflow < 0 else 0)
    absorb_session = bool(net_sign and sflow_sign and sflow_sign != net_sign
                          and abs(total_sflow) > 800 and abs(net) > 200)
    ph_absorb = [bool(p["sflow"] and p["pxchg"] and np.sign(p["sflow"]) != np.sign(p["pxchg"])
                 and abs(p["sflow"]) > 500) for p in ph]
    return {"date": day, "dow": _DOW[pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]}").weekday()],
            "contract": gc.leg_for("g17", day).replace("ng_mbo_", "").upper(),
            "instrument": IID[gc.leg_for("g17", day)], "owner": gc.owner_map("g17")[day],
            "open": round(o, 3), "close": round(c, 3), "net_usd": net, "n_trades": int(len(ts)),
            "session_min": round(span / 60, 1), "high_exc": round(hi), "low_exc": round(lo),
            "hi_et": str(et[hi_i]), "lo_et": str(et[lo_i]), "turn_kind": turn_kind,
            "turn_mag": round(turn_mag), "turn_et": turn_et, "onset_et": onset_et, "onset_dir": onset_dir,
            "total_sflow": round(total_sflow), "sflow_sign": sflow_sign, "absorb_session": absorb_session,
            "phases": ph, "ph_absorb": ph_absorb, "seam": (day == SEAM_DAY)}


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    print(f"{'day':>8} {'dow':>3} {'own':>3} {'net':>6} {'sflow':>7} {'abs?':>4} {'hi':>6} {'lo':>6} "
          f"{'turn':>9} {'tmag':>5} {'turn_et':>6} {'phases(sflow/pxchg)':>30}")
    ev = {}
    for d in DAYS:
        e = per_day_evidence(d); ev[d] = e
        ph = " ".join(f"[{p['sflow']:+d}/{p['pxchg']:+d}]" for p in e["phases"])
        te = (e["turn_et"] or "")[11:16]
        print(f"{d:>8} {e['dow']:>3} {e['owner']:>3} {e['net_usd']:>6} {e['total_sflow']:>7} "
              f"{str(e['absorb_session'])[:4]:>4} {e['high_exc']:>6} {e['low_exc']:>6} {e['turn_kind']:>9} "
              f"{e['turn_mag']:>5} {te:>6}  {ph}")
    json.dump(ev, open(os.path.join(OUT, "g17_mbo_evidence.json"), "w"), indent=1)
    print("\nwrote g17_mbo_evidence.json")
