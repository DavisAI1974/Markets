"""group_he24_he1_handoff.py - GENERIC HE24->HE1 day-boundary handoff chain (S105). Config-driven:
    python research/kalshi/group_he24_he1_handoff.py g17

The boundary handoff carries STATE, never the day-net. Built from the ACTUAL prior-day MBO tape (objective
exit state) + the prior owner's round-1 exit READ (verbatim). Precomputed once, injected into the round-2
specialist re-run so the block is ONE continuous coordinated path (HE24 exit -> HE1 open), not siloed days.
Writes <gid>_he24_he1_handoffs.json under forecasts/. The original he24_he1_handoff.py stays the G15 record.
"""
import os, sys, json
import numpy as np, pandas as pd, databento as db
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import group_config as gc

HERE = os.path.dirname(os.path.abspath(__file__))
LEG_DIR = os.path.join(HERE, "..", "..", "data", "ng_mbo_g17")
FC = os.path.join(HERE, "forecasts")
ET = "America/New_York"; MULT = 10000.0
_DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def load_trades(gid, day):
    store = db.DBNStore.from_file(os.path.join(LEG_DIR, f"{gc.leg_for(gid, day)}_{day}.dbn.zst"))
    ts, px, sd = [], [], []
    for r in store:
        if type(r).__name__ != "MBOMsg" or str(getattr(r.action, "value", r.action)) != "T":
            continue
        p = r.price
        if p in (None, 9223372036854775807, -9223372036854775808):
            continue
        s = getattr(r.side, "value", r.side)
        ts.append(int(r.ts_event) / 1e9); px.append(p / 1e9)
        sd.append(1 if str(s) in ("B", "Bid") else (-1 if str(s) in ("A", "Ask") else 0))
    o = np.argsort(ts)
    return np.asarray(ts)[o], np.asarray(px)[o], np.asarray(sd)[o]


def prior_owner_verdict(gid, prior_date, owner):
    n = gid[1:]
    f = os.path.join(FC, f"grp{n}_mbo_specialist_{owner}.json")
    if not os.path.exists(f):
        return None
    d = json.load(open(f)); entries = d.get("days") or (d if isinstance(d, list) else list(d.values()))
    for e in entries:
        if isinstance(e, dict) and str(e.get("date", "")).replace("-", "") == prior_date:
            return {"owner": owner, "continuation_vs_reversal": e.get("continuation_vs_reversal"),
                    "turn_time_et": e.get("turn_time_et"), "trend_vs_chop": e.get("trend_vs_chop"),
                    "mbo_verdict": (e.get("mbo_verdict") or "")[:300], "confidence": e.get("confidence")}
    return None


def exit_state(gid, day):
    ts, px, sd = load_trades(gid, day)
    if px.size == 0:
        return None
    et = pd.to_datetime(ts, unit="s", utc=True).tz_convert(ET)
    o, c = float(px[0]), float(px[-1])
    lo_i, hi_i = int(np.argmin(px)), int(np.argmax(px))
    mask = ts >= (ts[-1] - 3600); lh_px = px[mask]; lh_sd = sd[mask]
    lhd = int(np.sign(lh_px[-1] - lh_px[0])) if lh_px.size > 1 else 0
    lhf = int(np.sign(lh_sd.sum())) if lh_sd.size else 0
    rng = float(px.max() - px.min()); off_low = round((c - float(px.min())) / rng, 2) if rng > 1e-9 else 0.0
    return {"close_px": round(c, 3), "open_px": round(o, 3), "day_move_usd": round((c - o) * MULT),
            "last_hour_dir": lhd, "last_hour_signed_flow": lhf,
            "low_et": et[lo_i].strftime("%H:%M"), "high_et": et[hi_i].strftime("%H:%M"),
            "close_off_low_frac": off_low,
            "low_late": bool(et[lo_i] >= et[-1] - pd.Timedelta(hours=3)),
            "high_late": bool(et[hi_i] >= et[-1] - pd.Timedelta(hours=3))}


def _date(d):
    return pd.Timestamp(f"{d[:4]}-{d[4:6]}-{d[6:]}")


def exit_state_blind(gid, day, blind_days, prev_close):
    """Forecast exit state from the assembled blind grp<n>.json (walled - no actual tape). Uses the
    day's forecast day-move + its p50 path for last-hour dir + close_off_low. Signed flow is UNKNOWN
    in the blind (null) - the blind handoff carries forecast STATE, direction still from the D-1 tilt."""
    e = blind_days.get(day)
    if e is None:
        return None
    dm = e.get("guess_day_move_usd", 0)
    seam = gc.GROUPS[gid].get("seam")
    gap = 0 if day == seam else (e.get("overnight_gap_usd", 0) or 0)
    net = dm - (0 if day == seam else gap)
    open_px = round(prev_close + gap / MULT, 3)
    close_px = round(open_px + net / MULT, 3)
    path = [(h, v) for h, v in (e.get("path_p50") or []) if h is not None and v is not None]
    if len(path) >= 2:
        lhd = int(np.sign(path[-1][1] - path[-2][1])) or int(np.sign(net))
        vals = [v for _, v in path]
        rng = max(vals) - min(vals)
        off_low = round((path[-1][1] - min(vals)) / rng, 2) if rng > 1e-9 else 0.5
    else:
        lhd = int(np.sign(net)); off_low = 1.0 if net > 0 else 0.0
    return {"close_px": close_px, "open_px": open_px, "day_move_usd": dm,
            "last_hour_dir": lhd, "last_hour_signed_flow": None,   # unknown in the blind
            "low_et": None, "high_et": None, "close_off_low_frac": off_low,
            "low_late": None, "high_late": None, "source": "forecast"}


def main(gid, source="actual"):
    g = gc.GROUPS[gid]; DAYS = g["days"]; SEAM = g.get("seam"); ANCHOR = g["anchor"]; OWNER = gc.owner_map(gid)
    blind_days = {}
    if source == "blind":
        n = gid[1:]
        bpath = os.path.join(FC, f"grp{n}.json")
        blind_days = {str(r["date"]).replace("-", ""): r for r in json.load(open(bpath)).get("days", [])}

    def _exit(day, prev_close):
        return exit_state_blind(gid, day, blind_days, prev_close) if source == "blind" else exit_state(gid, day)

    moves, cum_by, exits, prev_close, cum = {}, {}, {}, ANCHOR, 0.0
    for d in DAYS:
        st = _exit(d, prev_close)
        if st is None:
            continue
        exits[d] = st
        gap = 0 if d == SEAM else round((st["open_px"] - prev_close) * MULT)
        moves[d] = gap + round((st["close_px"] - st["open_px"]) * MULT)
        cum += moves[d]; cum_by[d] = round(cum); prev_close = st["close_px"]
    ordered = [d for d in DAYS if d in moves]

    def chain_state(upto):
        seq = [moves[ordered[j]] for j in range(upto + 1)]
        pol = int(np.sign(sum(seq[-3:]))) or int(np.sign(seq[-1])); age = 0
        for m in reversed(seq):
            if int(np.sign(m)) == pol or m == 0:
                age += 1
            else:
                break
        return pol, age

    handoffs = {}
    for i, d in enumerate(ordered):
        if i == 0:
            handoffs[d] = {"note": f"block open - no prior in-block session; anchor to {ANCHOR} down/flat."}
            continue
        pd_ = ordered[i - 1]; pol, age = chain_state(i - 1); st = exit_state(gid, pd_)
        weekend = (_date(d) - _date(pd_)).days > 1
        handoffs[d] = {"prior_date": pd_, "prior_dow": _DOW[_date(pd_).weekday()],
                       "prior_owner": OWNER.get(pd_), "receiving_owner": OWNER.get(d),
                       "boundary_kind": ("weekend_reopen" if weekend else ("post_seam" if pd_ == SEAM else "overnight")),
                       "prior_exit_state": st, "chain_polarity": pol, "chain_age_sessions": age,
                       "cum_from_anchor_usd": cum_by[pd_], "prior_owner_read": prior_owner_verdict(gid, pd_, OWNER.get(pd_)),
                       "carry_rules": [
                           "Start from your blind + prior posterior; use this STATE to size/time, not to override direction.",
                           "Direction stays with the D-1 trade tilt; a turn realizing in the overnight seam is sized by the PRIOR-day exhaustion read, not front-run.",
                           ("Weekend: Monday inherits the Friday CLOSE + chain state, not the Friday day-move; reopen gap SIGN is noise." if weekend else
                            "Seam: leg change never-traded; anchor to the new leg's close, offset scoring-only." if pd_ == SEAM else
                            "Read your open RELATIVE to the prior close's exit condition (close_off_low, low_late, last_hour_dir/flow).")]}
    out = os.path.join(FC, f"{gid}_he24_he1_handoffs.json")
    json.dump({"spec": "he24->he1 boundary handoff (STATE not day-net); brain s102.6", "group": gid, "days": handoffs},
              open(out, "w"), indent=1)
    print("wrote", os.path.relpath(out, HERE))
    for d in ordered:
        h = handoffs[d]
        if "prior_date" not in h:
            print(f"{d} {OWNER[d]}  [block open]"); continue
        st = h["prior_exit_state"]
        print(f"{d} {OWNER[d]} <- {h['prior_date']}({h['prior_owner']}) {h['boundary_kind']:14} "
              f"pol{h['chain_polarity']:+d} age{h['chain_age_sessions']} cum{h['cum_from_anchor_usd']:+5d} | "
              f"prior close {st['close_px']} off_low {st['close_off_low_frac']} lh_dir{st['last_hour_dir']:+d} "
              f"lh_flow{st['last_hour_signed_flow']:+d} low@{st['low_et']}{' LATE' if st['low_late'] else ''}")


if __name__ == "__main__":
    main(sys.argv[1])
