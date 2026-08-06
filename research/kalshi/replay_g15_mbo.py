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


# expected Kalshi-underlying instrument per leg (NGJ26/April 1008 pre-roll, NGK26/May 996 post-roll)
EXPECT_IID = {d: (1008 if d <= "20260319" else 996) for d in CONTRACT}


def _l1_probe(day):
    """Read the L1 jsonl.gz header rows: presence, readability, instrument_id, trade count, basis check."""
    l1 = os.path.join(L1_DIR, f"NG_{day}.jsonl.gz")
    out = {"l1_present": os.path.exists(l1),
           "l1_bytes": os.path.getsize(l1) if os.path.exists(l1) else 0,
           "l1_readable": False, "l1_instrument_id": None, "l1_n_rows": 0,
           "l1_n_trades": 0, "l1_basis_correct": None}
    if not out["l1_present"]:
        return out
    try:
        iids, nrows, ntr = set(), 0, 0
        with gzip.open(l1, "rt") as fh:
            for line in fh:
                nrows += 1
                if '"action": "T"' in line:
                    ntr += 1
                if nrows <= 200000:  # sample instrument ids from a bounded head for speed
                    try:
                        r = json.loads(line)
                        if r.get("instrument_id") is not None:
                            iids.add(int(r["instrument_id"]))
                    except json.JSONDecodeError:
                        pass
        out["l1_readable"] = True
        out["l1_n_rows"] = nrows
        out["l1_n_trades"] = ntr
        out["l1_instrument_id"] = sorted(iids)
        out["l1_basis_correct"] = (iids == {EXPECT_IID.get(day)}) if iids else None
    except Exception as ex:
        out["l1_error"] = str(ex)[:120]
    return out


def manifest_entry(day):
    mbo = os.path.join(MBO_DIR, f"NG_{day}.dbn.zst")
    e = {"date": day, "contract": CONTRACT.get(day), "expected_instrument_id": EXPECT_IID.get(day),
         "mbo_present": os.path.exists(mbo),
         "mbo_bytes": os.path.getsize(mbo) if os.path.exists(mbo) else 0}
    e.update(_l1_probe(day))
    if e["mbo_present"]:
        recs, ident, store = _read_mbo(day)
        acts, n_trades = {}, 0
        for r in recs:
            a = r[1]
            k = getattr(a, "name", str(a)); acts[k] = acts.get(k, 0) + 1
            if r[7]:
                n_trades += 1
        ts = [r[0] for r in recs]
        e.update({"dataset": ident["dataset"], "publisher_id": ident["publisher_id"],
                  "instrument_id": ident["instrument_id"], "raw_symbol": ident["raw_symbol"],
                  "mbo_basis_correct": ident["instrument_id"] == EXPECT_IID.get(day),
                  "n_mbo": len(recs), "n_trades": n_trades,
                  "first_event_utc": str(_et(ts[0]).tz_convert("UTC")) if ts else None,
                  "last_event_utc": str(_et(ts[-1]).tz_convert("UTC")) if ts else None,
                  "action_counts": acts, "chronological_ok": all(ts[i] <= ts[i + 1] for i in range(len(ts) - 1)),
                  "flow_usable": n_trades > 20,
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
    # material boundaries: open, +60s, +5m, +15m, then a 30-min cadence through close (surfaces mid-session
    # divergence/exhaustion turns like the 0318 give-back), plus the 2h grid points and close.
    close_ts = recs[-1][0]
    grid_30 = [t0 + 1800 * k for k in range(1, int((close_ts - t0) / 1800) + 1)]
    grid_2h = [t0 + 7200 * k for k in range(1, int((close_ts - t0) / 7200) + 2)]
    marks = sorted(set([t0, t0 + 60, t0 + 300, t0 + 900] + grid_30 + grid_2h + [close_ts]))
    states, mi, seq = [], 0, 0
    prev_regime, prev_expect = None, None

    def _compact(fs, mark):
        """Reduce the full feature state to a compact MATERIAL record (evidence core + transitions)."""
        ev = fs.get("evidence", {}) or {}
        sf = ev.get("signed_flow") or {}
        de = ev.get("divergence_exhaustion") or {}
        mo = ev.get("move_onset_pressure") or {}
        q = ev.get("mbo_queue") or {}
        av = fs.get("availability", {}) or {}
        return {
            "date": day, "et": str(_et(mark)), "sequence": fs.get("sequence"),
            "as_of_s": fs.get("as_of_event_s"),
            "onset_regime": mo.get("regime"), "onset_pressure": mo.get("value"),
            "price_efficiency": mo.get("price_efficiency"), "activity_ratio": mo.get("activity_ratio"),
            "imb_level": sf.get("imb_level"), "imb_flow": sf.get("imb_flow"), "mi_flow": sf.get("mi_flow"),
            "div_expect": de.get("expect"), "div_aligned_flow": de.get("aligned_flow"),
            "div_exhausting": de.get("exhausting"), "div_conviction": de.get("reversal_conviction"),
            "consumed_side": q.get("consumed_side"), "far_side_recruitment": q.get("far_side_recruitment"),
            "book_complete": q.get("book_complete"),
            "flow_update_allowed": av.get("flow_update_allowed"),
            "queue_update_allowed": av.get("queue_update_allowed"),
            "stand_down_reasons": av.get("stand_down_reasons"),
            "blind_prior_fingerprint": prior_fp, "anchor_fingerprint": anchor_fp,
            "execution_authority": False,
        }

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
                rec = _compact(fs, marks[mi])
                # tag material transitions (regime change / divergence-expect change)
                rec["regime_transition"] = (rec["onset_regime"] != prev_regime)
                rec["div_transition"] = (rec["div_expect"] is not None and rec["div_expect"] != prev_expect)
                prev_regime, prev_expect = rec["onset_regime"], rec["div_expect"]
                states.append(rec); seq += 1
            except Exception as ex:
                states.append({"date": day, "et": str(_et(marks[mi])), "stand_down": str(ex)[:120], "sequence": seq}); seq += 1
            mi += 1
    return states


ALL_DAYS = ["20260315", "20260316", "20260317", "20260318", "20260319", "20260320",
            "20260322", "20260323", "20260324", "20260325", "20260326", "20260327"]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--anchor", required=True)
    ap.add_argument("--day", default=None)
    ap.add_argument("--all", action="store_true", help="loop all 13 G15 sessions -> full manifest + feature-state stream")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    anchor = build_anchor(a.anchor)

    if a.all:
        print("ANCHOR:", json.dumps({k: anchor[k] for k in ("date", "contract", "instrument_id", "raw_symbol", "last_price", "direction", "net_usd")}))
        man = [manifest_entry(a.anchor)] + [manifest_entry(d) for d in ALL_DAYS]
        json.dump(man, open(os.path.join(OUT, "g15_mbo_l1_manifest.json"), "w"), indent=1)
        print("MANIFEST rows:", len(man))
        for m in man:
            print(f"  {m['date']} {m.get('raw_symbol')} iid={m.get('instrument_id')} mbo_ok={m.get('mbo_basis_correct')} "
                  f"n_mbo={m.get('n_mbo')} n_tr={m.get('n_trades')} chrono={m.get('chronological_ok')} "
                  f"flow={m.get('flow_usable')} queue={m.get('queue_usable')} l1_ok={m.get('l1_basis_correct')} l1_iid={m.get('l1_instrument_id')}")
        allstates = []
        for d in ALL_DAYS:
            st = replay_day(d, anchor)
            allstates.extend(st)
            print(f"  states {d}: {len(st)}")
        with open(os.path.join(OUT, "g15_mbo_feature_states.jsonl"), "w") as fh:
            for s in allstates:
                fh.write(json.dumps(s) + "\n")
        print(f"FEATURE STATES total: {len(allstates)} -> g15_mbo_feature_states.jsonl")
        raise SystemExit(0)
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
