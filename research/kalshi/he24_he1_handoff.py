"""he24_he1_handoff.py - build the HE24->HE1 day-boundary handoff chain for the G15 MBO refine (S103).

Doctrine (brain s102.4 doctrine_tier3.mbo_refinement_g15_findings.he24_to_he1_handoff_spec): the boundary
handoff carries STATE, never the day-net number. Each specialist starts from the prior day's realized
MARKET CONDITION so the block is one continuous path, not siloed guesses. A live coach at HE1 legitimately
has the prior completed session's exit state - so this is built from the ACTUAL prior-day MBO tape (the
objective fields) plus the prior owner's own exit READ (passed through verbatim). It is independent of the
new posteriors, so the whole chain is precomputed once and injected into the parallel specialist re-run.

Writes forecasts/g15_he24_he1_handoffs.json : {date -> handoff_in}. Emits the objective exit state of the
PRIOR owned day + that owner's verdict text. Qualitative interpretation (exhaustion / conviction / flip)
stays with the receiving specialist, per the doctrine (it interprets, it is not handed a conclusion)."""
import os, json, glob
import numpy as np, pandas as pd
import databento as db

HERE = os.path.dirname(os.path.abspath(__file__))
MBO_DIR = os.path.join(HERE, "..", "..", "data", "ng_mbo"); ET = "America/New_York"; MULT = 10000.0
ANCHOR = 3.132
DAYS = ["20260315","20260316","20260317","20260318","20260319","20260320","20260322","20260323","20260324","20260325","20260326","20260327"]
SEAM = "20260320"
OWNER = {"20260315":"A","20260322":"A","20260316":"B","20260323":"B","20260317":"C","20260318":"C","20260324":"C","20260325":"C","20260319":"D","20260326":"D","20260320":"E","20260327":"E"}
_DOW = ("Mon","Tue","Wed","Thu","Fri","Sat","Sun")


def load_trades(day):
    store = db.DBNStore.from_file(os.path.join(MBO_DIR, f"NG_{day}.dbn.zst"))
    ts, px, sd = [], [], []
    for r in store:
        if type(r).__name__ != "MBOMsg":
            continue
        if str(getattr(r.action, "value", r.action)) != "T":
            continue
        p = r.price
        if p in (None, 9223372036854775807, -9223372036854775808):
            continue
        s = getattr(r.side, "value", r.side)
        ts.append(int(r.ts_event) / 1e9); px.append(p / 1e9)
        sd.append(1 if str(s) in ("B", "Bid") else (-1 if str(s) in ("A", "Ask") else 0))
    o = np.argsort(ts)
    return np.asarray(ts)[o], np.asarray(px)[o], np.asarray(sd)[o]


def prior_owner_verdict(prior_date):
    """pass the prior owner's own exit READ through verbatim (not parsed - the receiver interprets)."""
    own = OWNER.get(prior_date)
    if not own:
        return None
    f = os.path.join(HERE, "forecasts", f"grp15_mbo_specialist_{own}.json")
    if not os.path.exists(f):
        return None
    d = json.load(open(f))
    entries = d if isinstance(d, list) else (d.get("days") or list(d.values()))
    for e in entries:
        if isinstance(e, dict) and e.get("date", "").replace("-", "") == prior_date:
            return {"owner": own,
                    "continuation_vs_reversal": e.get("continuation_vs_reversal"),
                    "turn_time_et": e.get("turn_time_et"),
                    "trend_vs_chop": e.get("trend_vs_chop"),
                    "mbo_verdict": (e.get("mbo_verdict") or "")[:300],
                    "confidence": e.get("confidence")}
    return None


def exit_state(day):
    """objective realized exit state of a day from the MBO tape."""
    ts, px, sd = load_trades(day)
    if px.size == 0:
        return None
    et = pd.to_datetime(ts, unit="s", utc=True).tz_convert(ET)
    o, c = float(px[0]), float(px[-1])
    lo_i, hi_i = int(np.argmin(px)), int(np.argmax(px))
    # last trading hour of the session
    last_t = ts[-1]; mask = ts >= (last_t - 3600)
    lh_px = px[mask]; lh_sd = sd[mask]
    last_hour_dir = int(np.sign(lh_px[-1] - lh_px[0])) if lh_px.size > 1 else 0
    last_hour_flow = int(np.sign(lh_sd.sum())) if lh_sd.size else 0
    rng = float(px.max() - px.min())
    close_off_low = round((c - float(px.min())) / rng, 2) if rng > 1e-9 else 0.0   # 1.0 = closed at high, 0 = at low
    return {"close_px": round(c, 3), "open_px": round(o, 3),
            "day_move_usd": round((c - o) * MULT) + (0 if day == SEAM else 0),
            "last_hour_dir": last_hour_dir, "last_hour_signed_flow": last_hour_flow,
            "low_et": et[lo_i].strftime("%H:%M"), "high_et": et[hi_i].strftime("%H:%M"),
            "close_off_low_frac": close_off_low,
            "low_late": bool(et[lo_i] >= et[-1] - pd.Timedelta(hours=3)),
            "high_late": bool(et[hi_i] >= et[-1] - pd.Timedelta(hours=3))}


def main():
    # running chain state from realized day-moves (net+gap), anchor-referenced
    moves, cum = {}, 0.0
    prev_close = ANCHOR
    cum_by = {}
    for d in DAYS:
        st = exit_state(d)
        if st is None:
            continue
        gap = 0 if d == SEAM else round((st["open_px"] - prev_close) * MULT)
        net = round((st["close_px"] - st["open_px"]) * MULT)
        moves[d] = gap + net
        cum += moves[d]
        cum_by[d] = round(cum)
        prev_close = st["close_px"]

    ordered = [d for d in DAYS if d in moves]

    def chain_state(upto_idx):
        """polarity + age of the running chain as of the END of ordered[upto_idx]."""
        seq = [moves[ordered[j]] for j in range(upto_idx + 1)]
        pol = int(np.sign(sum(seq[-3:]))) or int(np.sign(seq[-1]))
        age = 0
        for m in reversed(seq):
            if int(np.sign(m)) == pol or m == 0:
                age += 1
            else:
                break
        return pol, age

    handoffs = {}
    for i, d in enumerate(ordered):
        if i == 0:
            handoffs[d] = {"note": "block open - no prior in-block session; anchor to the Friday anchor 3.132 (NGJ26) down."}
            continue
        pd_ = ordered[i - 1]
        pol, age = chain_state(i - 1)
        st = exit_state(pd_)
        weekend = OWNER.get(d) == "A"   # a Sunday reopen -> prior is the Friday close across the weekend
        handoffs[d] = {
            "prior_date": pd_, "prior_dow": _DOW[pd.Timestamp(f"{pd_[:4]}-{pd_[4:6]}-{pd_[6:]}").weekday()],
            "prior_owner": OWNER.get(pd_), "receiving_owner": OWNER.get(d),
            "boundary_kind": ("weekend_reopen" if weekend else ("post_seam" if pd_ == SEAM else "overnight")),
            "prior_exit_state": st,
            "chain_polarity": pol, "chain_age_sessions": age,
            "cum_from_anchor_usd": cum_by[pd_],
            "prior_owner_read": prior_owner_verdict(pd_),
            "carry_rules": [
                "Start from your blind + your prior posterior; use this state to size/time, not to override direction.",
                "Direction stays with the D-1 trade tilt; a turn realizing in the overnight seam is sized by the PRIOR day exhaustion read, not front-run.",
                ("Sunday inherits the Friday CLOSE + chain state, not the Friday day-move; reopen gap SIGN is noise - forecast the day-move from the anchor." if weekend else
                 "Seam: the leg change is never-traded; anchor to the new leg's close, offset is scoring-only." if pd_ == SEAM else
                 "Read your open RELATIVE to the prior close's exit condition (close_off_low, low_late, last_hour_dir/flow)."),
            ],
        }

    out = os.path.join(HERE, "forecasts", "g15_he24_he1_handoffs.json")
    json.dump({"spec": "he24->he1 boundary handoff (STATE not day-net); brain s102.4", "days": handoffs},
              open(out, "w"), indent=1)
    print("wrote", os.path.relpath(out, HERE))
    for d in ordered:
        h = handoffs[d]
        if "prior_date" not in h:
            print(f"{d} {OWNER[d]}  [block open]"); continue
        st = h["prior_exit_state"]
        print(f"{d} {OWNER[d]} <- {h['prior_date']}({h['prior_owner']}) {h['boundary_kind']:14} "
              f"chain pol{h['chain_polarity']:+d} age{h['chain_age_sessions']} cum{h['cum_from_anchor_usd']:+5d} "
              f"| prior close {st['close_px']} off_low {st['close_off_low_frac']} lh_dir {st['last_hour_dir']:+d} lh_flow {st['last_hour_signed_flow']:+d} low@{st['low_et']}{' LATE' if st['low_late'] else ''}")


if __name__ == "__main__":
    main()
