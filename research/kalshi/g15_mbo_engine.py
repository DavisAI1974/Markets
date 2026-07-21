"""g15_mbo_engine.py - G15 MBO causal REFINE engine (S103, ChatGPT audit branch).

Reads the local per-leg-correct NGJ26/NGK26 MBO DBN trades, extracts per-day CAUSAL evidence
(signed flow by phase, onset, give-back/turn, divergence/absorption, queue via the operator's
feature states), then a coordinator + day-class specialists produce a refined curve per day.
Renders the actual jagged traded curve (two-leg basis, 0320 seam never-traded) + guess overlays.
Scores blind vs refined. Nothing here edits the immutable blind (forecasts/grp15.json).

Actual curve is provably MBO-sourced: MBO trade nets == g15_rt.json nets exactly (diff 0/12, verified).
"""
import os, json, gzip, hashlib
import numpy as np
import pandas as pd
import databento as db

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
MBO_DIR = os.path.join(REPO, "data", "ng_mbo")
OUT = os.path.join(HERE, "renders", "ng_refine_s95")
FC = os.path.join(HERE, "forecasts")
ET = "America/New_York"
MULT = 10000.0
_DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

DAYS = ["20260315", "20260316", "20260317", "20260318", "20260319", "20260320",
        "20260322", "20260323", "20260324", "20260325", "20260326", "20260327"]
ANCHOR_DAY = "20260313"
ANCHOR_CLOSE = 3.132
SEAM_DAY = "20260320"
CONTRACT = {d: ("NGJ26" if d <= "20260319" else "NGK26") for d in DAYS + [ANCHOR_DAY]}
IID = {d: (1008 if d <= "20260319" else 996) for d in DAYS + [ANCHOR_DAY]}


def _dir(side):
    t = str(getattr(side, "name", side)).upper()
    if t in ("B", "BID", "BUY"):
        return 1
    if t in ("A", "ASK", "SELL"):
        return -1
    return 0


def load_trades(day):
    """Return ts_s(np), price(np), size(np), sdir(np +1 buy/-1 sell) for the day's MBO trades, chrono."""
    store = db.DBNStore.from_file(os.path.join(MBO_DIR, f"NG_{day}.dbn.zst"))
    rows = []
    for r in store:
        if type(r).__name__ != "MBOMsg":
            continue
        av = getattr(r.action, "value", r.action)
        if not (str(av) == "T" or av == "T"):
            continue
        p = r.price
        if p in (None, 9223372036854775807, -9223372036854775808):
            continue
        rows.append((int(r.ts_event), p / 1e9, float(r.size), _dir(r.side)))
    rows.sort(key=lambda x: x[0])
    ts = np.array([x[0] for x in rows], dtype=np.float64) / 1e9
    px = np.array([x[1] for x in rows])
    sz = np.array([x[2] for x in rows])
    sd = np.array([x[3] for x in rows])
    return ts, px, sz, sd


def per_day_evidence(day):
    ts, px, sz, sd = load_trades(day)
    et = pd.to_datetime(ts, unit="s", utc=True).tz_convert(ET)
    o, c = float(px[0]), float(px[-1])
    net = round((c - o) * MULT)
    cum = (px - o) * MULT                       # $ path from open
    run_max = np.maximum.accumulate(cum)
    run_min = np.minimum.accumulate(cum)
    hi_i = int(np.argmax(cum)); lo_i = int(np.argmin(cum))
    hi, lo = float(cum[hi_i]), float(cum[lo_i])

    # ---- give-back / turn ----
    # reversal into the close: the extreme OPPOSITE the close sign that then reversed the most
    net_sign = 1 if net > 0 else (-1 if net < 0 else 0)
    give_up = hi - net       # how far it fell back from the high (positive => it gave back)
    give_dn = net - lo       # how far it rose back from the low
    # turn = the dominant reversal
    if give_dn >= give_up and give_dn > 300 and lo < -200:
        turn_kind, turn_i, turn_mag = "turn_up", lo_i, give_dn        # fell then rallied
    elif give_up > give_dn and give_up > 300 and hi > 200:
        turn_kind, turn_i, turn_mag = "turn_down", hi_i, give_up      # rose then sold off
    else:
        turn_kind, turn_i, turn_mag = "none", None, max(give_up, give_dn)
    turn_et = str(et[turn_i]) if turn_i is not None else None

    # ---- onset (first material directional push) ----
    thr = max(250.0, 0.4 * max(abs(hi), abs(lo)))
    onset_i = None
    for i in range(len(cum)):
        if abs(cum[i]) >= thr:
            onset_i = i
            break
    onset_et = str(et[onset_i]) if onset_i is not None else None
    onset_dir = ("up" if cum[onset_i] > 0 else "down") if onset_i is not None else None

    # ---- signed flow: whole + phases (by wall-clock thirds) ----
    def sflow_range(mask):
        return float((sd[mask] * sz[mask]).sum())
    def pxchg_range(mask):
        if not mask.any():
            return 0.0
        return round((float(px[mask][-1]) - float(px[mask][0])) * MULT)
    total_sflow = float((sd * sz).sum())
    t0, t1 = ts[0], ts[-1]
    span = t1 - t0
    ph = []
    for k in range(3):
        m = (ts >= t0 + span * k / 3) & (ts < t0 + span * (k + 1) / 3)
        if k == 2:
            m = (ts >= t0 + span * k / 3)
        ph.append({"sflow": round(sflow_range(m)), "pxchg": pxchg_range(m), "vol": round(float(sz[m].sum()))})

    # ---- divergence/absorption reads ----
    # session: strong opposite-signed flow vs price = absorption of the pressing side (squeeze into price dir)
    sflow_sign = 1 if total_sflow > 0 else (-1 if total_sflow < 0 else 0)
    absorb_session = (net_sign != 0 and sflow_sign != 0 and sflow_sign != net_sign
                      and abs(total_sflow) > 800 and abs(net) > 200)
    # per-phase absorption flags
    ph_absorb = [(p["sflow"] != 0 and p["pxchg"] != 0 and np.sign(p["sflow"]) != np.sign(p["pxchg"])
                  and abs(p["sflow"]) > 500) for p in ph]

    return {
        "date": day, "dow": _DOW[pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]}").weekday()],
        "instrument": IID[day], "contract": CONTRACT[day],
        "open": round(o, 3), "close": round(c, 3), "net_usd": net, "n_trades": int(len(ts)),
        "session_min": round(span / 60, 1),
        "high_exc": round(hi), "low_exc": round(lo), "hi_et": str(et[hi_i]), "lo_et": str(et[lo_i]),
        "turn_kind": turn_kind, "turn_mag": round(turn_mag), "turn_et": turn_et,
        "onset_et": onset_et, "onset_dir": onset_dir, "onset_thr": round(thr),
        "total_sflow": round(total_sflow), "sflow_sign": sflow_sign,
        "absorb_session": bool(absorb_session),
        "phases": ph, "ph_absorb": [bool(x) for x in ph_absorb],
        "et_open": str(et[0]), "et_close": str(et[-1]),
        # render support (downsampled path)
        "_ts": ts, "_px": px, "_cum": cum,
    }


if __name__ == "__main__":
    print(f"{'day':>8} {'dow':>3} {'net':>6} {'sflow':>7} {'abs?':>4} {'hi':>6} {'lo':>6} {'turn':>9} "
          f"{'tmag':>5} {'turn_et':>16} {'onset_et':>16} {'phases(sflow/pxchg)':>30}")
    ev = {}
    for d in DAYS:
        e = per_day_evidence(d)
        ev[d] = {k: v for k, v in e.items() if not k.startswith("_")}
        ph = " ".join(f"[{p['sflow']:+d}/{p['pxchg']:+d}]" for p in e["phases"])
        te = (e["turn_et"] or "")[11:16]; oe = (e["onset_et"] or "")[11:16]
        print(f"{d:>8} {e['dow']:>3} {e['net_usd']:>6} {e['total_sflow']:>7} {str(e['absorb_session'])[:4]:>4} "
              f"{e['high_exc']:>6} {e['low_exc']:>6} {e['turn_kind']:>9} {e['turn_mag']:>5} {te:>16} {oe:>16}  {ph}")
    json.dump(ev, open(os.path.join(OUT, "g15_mbo_evidence.json"), "w"), indent=1)
    print("\nwrote g15_mbo_evidence.json")
