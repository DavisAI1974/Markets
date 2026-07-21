"""replay_g15_mbo.py - thin DRIVER (S103) that feeds historical NG MBO records through the EXISTING
causal engine (ng_live_operator.NGLiveOperator + ng_rt_feature_state.build_feature_state). It does NOT
reimplement microstructure - it only reads DBN, normalizes records, and drives the operator, emitting
compact feature states at material boundaries. Historical/live parity comes from using the same operator.

Usage:
  python replay_g15_mbo.py --anchor 20260313 --day 20260315   # pilot: one session + the locked anchor
Outputs (append/merge):
  renders/ng_refine_s95/g15_anchor.json                (locked Friday anchor, from --anchor last hour)
  renders/ng_refine_s95/g15_mbo_l1_manifest.json       (per-session data verification)
  renders/ng_refine_s95/g15_mbo_feature_states.jsonl   (compact causal states)
"""
import argparse, gzip, json, os, hashlib
import numpy as np
import pandas as pd
import databento as db

import ng_live_operator as OP
from ng_rt_feature_state import build_feature_state

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "renders", "ng_refine_s95")
MBO_DIR = os.path.join(HERE, "..", "..", "data", "ng_mbo")
L1_DIR = os.path.join(HERE, "..", "..", "data", "ng_l1")
ET = "America/New_York"
# G15 contract map (brief): NGJ26 through 03-19, NGK26 from 03-20 (seam not a traded move).
CONTRACT = {d: ("NGJ26" if d <= "20260319" else "NGK26")
            for d in ["20260313", "20260315", "20260316", "20260317", "20260318", "20260319",
                      "20260320", "20260322", "20260323", "20260324", "20260325", "20260326", "20260327"]}


def _read_mbo(day):
    """Yield normalized MBO records in chronological order: (ts_s, action, side, size, order_id, price, flags, is_trade, tprice, tsize)."""
    path = os.path.join(MBO_DIR, f"NG_{day}.dbn.zst")
    store = db.DBNStore.from_file(path)
    ident = {"dataset": store.metadata.dataset, "publisher_id": None, "instrument_id": None,
             "raw_symbol": CONTRACT.get(day), "definition_date": f"{day[:4]}-{day[4:6]}-{day[6:]}",
             "continuous_symbol": "NG.n.0", "roll_rule": "open_interest"}
    recs = []
    for r in store:
        if type(r).__name__ != "MBOMsg":
            continue
        ts_s = int(r.ts_event) / 1e9
        raw_p = r.price
        price = float(raw_p) / 1e9 if raw_p not in (None, 9223372036854775807, -9223372036854775808) else None
        act = r.action        # raw databento Action enum; operator normalizes via _action/_enum
        side = r.side          # raw Side enum
        if ident["instrument_id"] is None:
            ident["instrument_id"] = int(r.instrument_id); ident["publisher_id"] = int(r.publisher_id)
        av = getattr(act, "value", act)
        is_trade = (av == "T" or av == ord("T") or str(av) == "T")
        recs.append((ts_s, act, side, float(r.size), int(r.order_id), price, int(r.flags), is_trade))
    recs.sort(key=lambda x: x[0])
    return recs, ident, store


def _et(ts_s):
    return pd.Timestamp(ts_s, unit="s", tz="UTC").tz_convert(ET)


def build_anchor(anchor_day):
    recs, ident, store = _read_mbo(anchor_day)
    # trades only (action T) for the last traded hour
    trades = [(ts, p, sz, sd) for (ts, a, sd, sz, oid, p, fl, isT) in recs if isT and p is not None]
    if not trades:
        raise SystemExit(f"anchor {anchor_day}: no trades found")
    last_ts = trades[-1][0]
    hr = [t for t in trades if t[0] >= last_ts - 3600]
    prices = [t[1] for t in hr]
    buy = sum(t[2] for t in hr if OP._trade_direction(t[3]) == "BUY")
    sell = sum(t[2] for t in hr if OP._trade_direction(t[3]) == "SELL")
    first_p, last_p = prices[0], prices[-1]
    anchor = {
        "date": anchor_day, "contract": CONTRACT[anchor_day], "instrument_id": ident["instrument_id"],
        "raw_symbol": ident["raw_symbol"], "definition_date": ident["definition_date"],
        "hour_start_event_ns": int(hr[0][0] * 1e9), "hour_end_event_ns": int(hr[-1][0] * 1e9),
        "first_price": round(first_p, 4), "last_price": round(last_p, 4),
        "high_price": round(max(prices), 4), "low_price": round(min(prices), 4),
        "net_usd": round((last_p - first_p) * 10000), "direction": "up" if last_p > first_p else "down",
        "buy_volume": buy, "sell_volume": sell, "signed_flow": buy - sell,
        "trade_count": len(hr), "activity_rate": round(len(hr) / 60.0, 2),
        "data_quality": {"n_trades_session": len(trades), "hour_span_min": round((hr[-1][0] - hr[0][0]) / 60, 1)},
    }
    os.makedirs(OUT, exist_ok=True)
    json.dump(anchor, open(os.path.join(OUT, "g15_anchor.json"), "w"), indent=1)
    return anchor


def manifest_entry(day):
    mbo = os.path.join(MBO_DIR, f"NG_{day}.dbn.zst")
    l1 = os.path.join(L1_DIR, f"NG_{day}.jsonl.gz")
    e = {"date": day, "contract": CONTRACT.get(day),
         "mbo_present": os.path.exists(mbo), "l1_present": os.path.exists(l1),
         "mbo_bytes": os.path.getsize(mbo) if os.path.exists(mbo) else 0,
         "l1_bytes": os.path.getsize(l1) if os.path.exists(l1) else 0}
    if e["mbo_present"]:
        recs, ident, store = _read_mbo(day)
        acts = {}
        for (_, a, *_rest) in recs:
            k = str(a); acts[k] = acts.get(k, 0) + 1
        ts = [r[0] for r in recs]
        e.update({"dataset": ident["dataset"], "publisher_id": ident["publisher_id"],
                  "instrument_id": ident["instrument_id"], "raw_symbol": ident["raw_symbol"],
                  "n_mbo": len(recs), "first_event_utc": str(_et(ts[0]).tz_convert("UTC")) if ts else None,
                  "last_event_utc": str(_et(ts[-1]).tz_convert("UTC")) if ts else None,
                  "action_counts": acts, "chronological_ok": all(ts[i] <= ts[i + 1] for i in range(len(ts) - 1)),
                  "flow_usable": sum(1 for r in recs if r[7]) > 20,
                  "queue_usable": len(recs) > 100})
    return e


def replay_day(day, anchor):
    recs, ident, store = _read_mbo(day)
    op = OP.NGLiveOperator()
    # blind prior direction dist from grp15.json day (immutable read)
    g = json.load(open(os.path.join(HERE, "forecasts", "grp15.json")))
    gd = {d["date"].replace("-", ""): d for d in g["days"]}.get(day, {})
    net = gd.get("guessed_net_usd", 0)
    prior = {"up": 0.34, "flat": 0.32, "down": 0.34}
    if net > 100: prior = {"up": 0.5, "flat": 0.3, "down": 0.2}
    elif net < -100: prior = {"up": 0.2, "flat": 0.3, "down": 0.5}
    prior_fp = hashlib.sha1(json.dumps(gd, sort_keys=True).encode()).hexdigest()[:12]
    anchor_fp = hashlib.sha1(json.dumps(anchor, sort_keys=True).encode()).hexdigest()[:12]

    if not recs:
        return []
    t0 = recs[0][0]
    # material boundaries: open, +60s, +5m, +15m, 2h grid, close
    close_ts = recs[-1][0]
    marks = sorted(set([t0, t0 + 60, t0 + 300, t0 + 900] +
                       [t0 + 7200 * k for k in range(1, int((close_ts - t0) / 7200) + 2)] + [close_ts]))
    states, mi, seq = [], 0, 0
    for (ts_s, act, side, size, oid, price, flags, isT) in recs:
        if isT and price is not None:
            op.on_trade(ts_s, price, size, side)
        op.on_mbo(ts_s, act, side, size, oid, price, flags)
        while mi < len(marks) and ts_s >= marks[mi]:
            snap = op.snapshot(marks[mi])
            try:
                fs = build_feature_state(blind_prior=prior, operator_snapshot=snap,
                                         instrument_identity=ident, decision_cutoff_s=marks[mi],
                                         horizon="intraday", source_mode="historical_replay", sequence=seq)
                fs["date"] = day; fs["blind_prior_fingerprint"] = prior_fp; fs["anchor_fingerprint"] = anchor_fp
                fs["et"] = str(_et(marks[mi]))
                states.append(fs); seq += 1
            except Exception as ex:
                states.append({"date": day, "et": str(_et(marks[mi])), "stand_down": str(ex)[:120], "sequence": seq}); seq += 1
            mi += 1
    return states


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--anchor", required=True)
    ap.add_argument("--day", required=True)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    anchor = build_anchor(a.anchor)
    print("ANCHOR:", json.dumps({k: anchor[k] for k in ("date", "contract", "instrument_id", "raw_symbol", "last_price", "direction", "net_usd", "trade_count")}))
    man = [manifest_entry(a.anchor), manifest_entry(a.day)]
    json.dump(man, open(os.path.join(OUT, "g15_mbo_l1_manifest.json"), "w"), indent=1)
    print("MANIFEST:", json.dumps([{k: m.get(k) for k in ("date", "raw_symbol", "n_mbo", "flow_usable", "queue_usable", "chronological_ok")} for m in man]))
    states = replay_day(a.day, anchor)
    with open(os.path.join(OUT, "g15_mbo_feature_states.jsonl"), "w") as fh:
        for s in states:
            fh.write(json.dumps(s) + "\n")
    print(f"FEATURE STATES for {a.day}: {len(states)} emitted -> g15_mbo_feature_states.jsonl")
    if states:
        print("first state keys:", list(states[0].keys())[:20])
