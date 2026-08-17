#!/usr/bin/env python3
"""Build Part 1 of the NG dipole-family Frankie experiment.

Scratch only. Nothing in Frankie's permanent brain/schema/roles/workflow is changed.

Protocol
--------
1. Recreate the frozen roll-20 dipole-first event universe.
2. Recreate the three candidate render families, but expose them downstream only as F1/F2/F3.
   The source labels are never written into Frankie's packet.
3. Assign every event to the nearest candidate pre-flip prototype using ONLY t<=0 dipole geometry.
4. Freeze a deterministic 50/50 split independently inside F1/F2/F3.
5. PART 1 writes full outcomes only for the revealed half: dipole, MBP-10-derived tape/book/flow,
   full corresponding 3t/5t price legs, and exact-date MBO one-second event dynamics where proven.
6. The held-out manifest contains event identity + family only. It contains NO held-out price,
   post-dipole, MBO future, duration, displacement, pivot, or outcome data.

Important: candidate prototype discovery predates this experiment and was selected by post-dipole
exhaustion for visualization, NOT by price. That provenance is recorded outside the Frankie-facing
packet. Family assignment in this script itself uses pre-flip geometry only.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from ng_dipole_runway_audit import TICK, load_day, zigzag_legs
from ng_dipole_native_shape_audit import event_rows, choose_exhaustion_archetypes

SEED = "NG_FAMILY_REVEAL_20260816_V1"
ROLL = 20
PRE = 60
POST = 60
FAMILY_SOURCE_ORDER = ("long", "short", "very_short")  # provenance only; never exposed to Frankie
FAMILY_IDS = ("F1", "F2", "F3")
MBO_WINDOW = 60


def finite(x):
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def q(xs, p):
    vals = sorted(float(x) for x in xs if finite(x))
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    z = p * (len(vals) - 1)
    i = int(math.floor(z)); j = min(i + 1, len(vals) - 1); w = z - i
    return vals[i] * (1 - w) + vals[j] * w


def event_id(r):
    return f"{r['day']}:{int(r['flip_s']):05d}:r{ROLL}"


def pre_vector(r):
    peak = float(r["pre_raw"][-1])
    if abs(peak) < 1e-12:
        return np.zeros(len(r["pre_raw"]), dtype=float)
    return np.asarray(r["pre_raw"], dtype=float) / peak


def pre_distance(r, proto):
    a = pre_vector(r); b = pre_vector(proto)
    shape = float(np.sqrt(np.mean((a - b) ** 2)))
    ea = abs(float(r.get("pre_excursion") or 0.0)); eb = abs(float(proto.get("pre_excursion") or 0.0))
    amp = abs(math.log1p(ea) - math.log1p(eb))
    return shape + 0.15 * amp


def family_assignment(rows):
    arch = choose_exhaustion_archetypes(rows)
    protos = [arch[name]["prototype"] for name in FAMILY_SOURCE_ORDER]
    assignments = []
    for r in rows:
        ds = [pre_distance(r, p) for p in protos]
        order = np.argsort(ds)
        best = int(order[0]); second = int(order[1])
        assignments.append({
            "row": r,
            "family": FAMILY_IDS[best],
            "distance": float(ds[best]),
            "margin_to_second": float(ds[second] - ds[best]),
        })
    provenance = {
        "prototype_origin": "existing three candidate render exemplars; selected by post-dipole exhaustion only, never by price",
        "frankie_exposed_source_names": False,
        "family_assignment_fields": "t<=0 oriented roll20 dipole curve + pre excursion amplitude only",
        "prototypes": {
            FAMILY_IDS[i]: {
                "day": protos[i]["day"], "flip_s": int(protos[i]["flip_s"]),
                "pre_curve": [float(x) for x in pre_vector(protos[i])],
                "pre_excursion": float(protos[i]["pre_excursion"]),
            }
            for i in range(3)
        },
    }
    return assignments, provenance


def freeze_split(assignments):
    by = defaultdict(list)
    for a in assignments:
        r = a["row"]
        digest = hashlib.sha256(f"{SEED}|{event_id(r)}".encode()).hexdigest()
        by[a["family"]].append((digest, a))
    split = {}
    for fam in FAMILY_IDS:
        arr = sorted(by[fam], key=lambda z: z[0])
        ntrain = len(arr) // 2
        train = {event_id(a["row"]) for _, a in arr[:ntrain]}
        for _, a in arr:
            split[event_id(a["row"])] = "REVEALED_TRAIN" if event_id(a["row"]) in train else "HELDOUT_BLIND"
    return split


def containing_leg(legs, t):
    for leg in legs:
        if leg["start"] <= t <= leg["end"]:
            return leg
    return None


def price_path(day, start, end):
    start = max(0, int(start)); end = min(len(day.price) - 1, int(end))
    vals = day.price[start:end + 1]
    first = next((float(x) for x in vals if finite(x)), None)
    if first is None:
        return {"start_s": start, "end_s": end, "price": [], "ticks_from_start": []}
    px = [None if not finite(x) else float(x) for x in vals]
    ticks = [None if x is None else (x - first) / TICK for x in px]
    return {"start_s": start, "end_s": end, "price": px, "ticks_from_start": ticks}


def outcome_for_event(day, r, legs_by_th):
    t0 = int(r["flip_s"])
    event_px = price_path(day, t0 - PRE, t0 + POST)
    p0 = day.price[t0] if 0 <= t0 < len(day.price) and finite(day.price[t0]) else None
    event_px["t0_s"] = t0
    event_px["t0_price"] = None if p0 is None else float(p0)
    event_px["ticks_from_t0"] = [None if p0 is None or x is None else (x - p0) / TICK for x in event_px["price"]]
    legs = {}
    for th in (3, 5):
        leg = containing_leg(legs_by_th[th], t0)
        if leg is None:
            legs[f"{th}t"] = None
            continue
        path = price_path(day, leg["start"], leg["end"])
        legs[f"{th}t"] = {
            "start_s": int(leg["start"]), "end_s": int(leg["end"]),
            "duration_s": int(leg["duration"]), "direction": int(leg["dir"]),
            "ticks": float(leg["ticks"]), "remaining_from_t0_s": int(max(0, leg["end"] - t0)),
            "t0_offset_from_leg_start_s": int(t0 - leg["start"]),
            "price_path": path,
        }
    return event_px, legs


def mbp10_context(day, t0):
    lo = t0 - PRE; hi = t0 + POST
    def sl(a):
        out=[]
        for t in range(lo, hi + 1):
            if t < 0 or t >= len(a): out.append(None)
            else:
                v=a[t]; out.append(float(v) if finite(v) else None)
        return out
    return {
        "offset_s": list(range(-PRE, POST + 1)),
        "book_imbalance": sl(day.book),
        "buy_aggressor_volume": sl(day.buy_vol),
        "sell_aggressor_volume": sl(day.sell_vol),
        "trade_price": sl(day.price),
    }


def side_sign(side):
    s = str(getattr(side, "name", getattr(side, "value", side))).upper()
    if s in {"B", "BID", "BUY"}: return 1
    if s in {"A", "ASK", "SELL"}: return -1
    return 0


def action_name(action):
    return str(getattr(action, "value", action)).upper()


def load_mbo_second_bins(path):
    """Loss-minimized 1s MBO dynamics. Raw order ids are intentionally omitted; action/side/size/price are retained in aggregate."""
    import databento as db
    bins = defaultdict(lambda: {
        "msg_count": 0, "add_bid_qty": 0.0, "add_ask_qty": 0.0,
        "cancel_bid_qty": 0.0, "cancel_ask_qty": 0.0,
        "modify_bid_qty": 0.0, "modify_ask_qty": 0.0,
        "trade_bid_qty": 0.0, "trade_ask_qty": 0.0,
        "trade_count": 0, "trade_signed_qty": 0.0,
        "trade_last_price": None,
    })
    store = db.DBNStore.from_file(path)
    for msg in store:
        if type(msg).__name__ != "MBOMsg":
            continue
        sec = int(int(msg.ts_event) / 1_000_000_000) % 86400
        b = bins[sec]; b["msg_count"] += 1
        act = action_name(msg.action); sg = side_sign(msg.side)
        sz = float(getattr(msg, "size", 0.0) or 0.0)
        side = "bid" if sg > 0 else ("ask" if sg < 0 else None)
        if act == "A" and side: b[f"add_{side}_qty"] += sz
        elif act in {"C", "D"} and side: b[f"cancel_{side}_qty"] += sz
        elif act in {"M", "R"} and side: b[f"modify_{side}_qty"] += sz
        elif act == "T":
            b["trade_count"] += 1; b["trade_signed_qty"] += sg * sz
            if side: b[f"trade_{side}_qty"] += sz
            p = getattr(msg, "price", None)
            if p not in (None, 9223372036854775807, -9223372036854775808):
                b["trade_last_price"] = float(p) / 1e9
    return dict(bins)


def mbo_context(bins, t0, source_key):
    if bins is None:
        return {"available": False, "source": None, "offset_s": [], "seconds": []}
    empty = {
        "msg_count": 0, "add_bid_qty": 0.0, "add_ask_qty": 0.0,
        "cancel_bid_qty": 0.0, "cancel_ask_qty": 0.0,
        "modify_bid_qty": 0.0, "modify_ask_qty": 0.0,
        "trade_bid_qty": 0.0, "trade_ask_qty": 0.0,
        "trade_count": 0, "trade_signed_qty": 0.0, "trade_last_price": None,
    }
    offsets = list(range(-MBO_WINDOW, MBO_WINDOW + 1))
    return {
        "available": True, "source": source_key, "offset_s": offsets,
        "seconds": [dict(bins.get(t0 + dt, empty)) for dt in offsets],
    }


def summary_stats(entries):
    out = {}
    for fam in FAMILY_IDS:
        ee = [e for e in entries if e["family"] == fam]
        f = {"n": len(ee)}
        for th in (3, 5):
            legs = [e["price_legs"][f"{th}t"] for e in ee if e["price_legs"][f"{th}t"] is not None]
            for field in ("duration_s", "remaining_from_t0_s", "ticks"):
                vals = [x[field] for x in legs]
                f[f"price_{th}t_{field}"] = {
                    "n": len(vals), "p10": q(vals,.10), "p25": q(vals,.25), "median": q(vals,.50),
                    "p75": q(vals,.75), "p90": q(vals,.90),
                }
            aligns = [1 if int(x["direction"]) == int(e["dipole_polarity"]) else 0
                      for e in ee for x in [e["price_legs"][f"{th}t"]] if x is not None]
            f[f"price_{th}t_direction_matches_dipole_fraction"] = (sum(aligns)/len(aligns) if aligns else None)
        for field in ("exh_t50_s", "exh_t25_s", "exh_t10_s", "exh_zero_s"):
            vals = [61 if e[field] is None else e[field] for e in ee]
            f[field] = {"median_censored61": q(vals,.5), "p25": q(vals,.25), "p75": q(vals,.75)}
        mbo = [e for e in ee if e["mbo"]["available"]]
        f["mbo_available_n"] = len(mbo)
        if mbo:
            def wsum(e, lo, hi, key):
                offs=e["mbo"]["offset_s"]; secs=e["mbo"]["seconds"]
                return sum(float(s.get(key) or 0.0) for o,s in zip(offs,secs) if lo <= o <= hi)
            for key in ("trade_signed_qty","add_bid_qty","add_ask_qty","cancel_bid_qty","cancel_ask_qty"):
                for name,lo,hi in (("pre60",-60,-1),("pre20",-20,-1),("post20",1,20),("post60",1,60)):
                    vals=[wsum(e,lo,hi,key) for e in mbo]
                    f[f"mbo_{key}_{name}"]={"median":q(vals,.5),"p25":q(vals,.25),"p75":q(vals,.75)}
        out[fam] = f
    return out


def render(entries, outpath):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(3, 2, figsize=(14, 12), sharex="col")
    rng = np.random.default_rng(20260816)
    x = np.arange(-60, 61)
    for i, fam in enumerate(FAMILY_IDS):
        ee=[e for e in entries if e["family"]==fam]
        take=rng.choice(len(ee),size=min(80,len(ee)),replace=False) if ee else []
        for j in take:
            e=ee[int(j)]
            dip=np.asarray(e["dipole_pre"] + e["dipole_post"][1:],dtype=float)
            axs[i,0].plot(x,dip,alpha=.07,lw=.7)
            px=np.asarray([np.nan if v is None else v for v in e["price_event_window"]["ticks_from_t0"]],dtype=float)
            axs[i,1].plot(x,px,alpha=.07,lw=.7)
        axs[i,0].axvline(0,ls="--",lw=1); axs[i,0].axhline(0,lw=.6)
        axs[i,1].axvline(0,ls="--",lw=1); axs[i,1].axhline(0,lw=.6)
        axs[i,0].set_ylabel(f"{fam} dipole")
        axs[i,1].set_ylabel(f"{fam} price ticks")
        axs[i,0].set_title(f"{fam}: revealed dipole curves")
        axs[i,1].set_title(f"{fam}: corresponding revealed price around t0")
    axs[-1,0].set_xlabel("seconds from dipole t0"); axs[-1,1].set_xlabel("seconds from dipole t0")
    fig.suptitle("Frankie Part 1 REVEALED half — anonymous dipole families + price (training only)")
    fig.tight_layout(rect=[0,0,1,.97]); fig.savefig(outpath,dpi=160); plt.close(fig)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("days", nargs=4)
    ap.add_argument("--mbo", action="append", default=[], help="DAY=S3-downloaded-local-file::SOURCEKEY")
    args=ap.parse_args()

    days=[load_day(p) for p in args.days]
    dmap={d.day:d for d in days}
    rows=[]
    for d in days: rows.extend(event_rows(d,ROLL))
    assignments, provenance = family_assignment(rows)
    split=freeze_split(assignments)

    mbo_cfg={}
    for item in args.mbo:
        day, rest=item.split("=",1); path, source=rest.split("::",1)
        mbo_cfg[day]=(path,source)
    mbo_bins={}
    for day,(path,source) in mbo_cfg.items():
        mbo_bins[day]=(load_mbo_second_bins(path),source)

    legs_by_day={d.day:{3:zigzag_legs(d.price,3),5:zigzag_legs(d.price,5)} for d in days}
    revealed=[]; heldout=[]
    family_counts=Counter(); train_counts=Counter(); blind_counts=Counter()
    for a in assignments:
        r=a["row"]; eid=event_id(r); fam=a["family"]; family_counts[fam]+=1
        if split[eid] == "HELDOUT_BLIND":
            blind_counts[fam]+=1
            heldout.append({"event_id":eid,"day":r["day"],"flip_s":int(r["flip_s"]),"family":fam})
            continue
        train_counts[fam]+=1
        d=dmap[r["day"]]; event_px, legs=outcome_for_event(d,r,legs_by_day[r["day"]])
        mbins,msource=mbo_bins.get(r["day"],(None,None))
        revealed.append({
            "event_id":eid,"day":r["day"],"flip_s":int(r["flip_s"]),"family":fam,
            "family_pre_distance":a["distance"],"family_margin_to_second":a["margin_to_second"],
            "dipole_polarity":int(r["dipole_polarity"]),"dipole_peak_abs":float(r["peak_abs"]),
            "dipole_pre_prominence":float(r["pre_prominence"]),"dipole_pre_base10":float(r["pre_base10"]),
            "dipole_pre_excursion":float(r["pre_excursion"]),
            "dipole_pre":[float(x) for x in r["pre_raw"]],"dipole_post":[float(x) for x in r["post_raw"]],
            "exh_t50_s":r["exh_t50_s"],"exh_t25_s":r["exh_t25_s"],"exh_t10_s":r["exh_t10_s"],"exh_zero_s":r["exh_zero_s"],
            "mbp10":mbp10_context(d,int(r["flip_s"])),
            "mbo":mbo_context(mbins,int(r["flip_s"]),msource),
            "price_event_window":event_px,"price_legs":legs,
        })

    split_manifest={
        "seed_sha256":hashlib.sha256(SEED.encode()).hexdigest(),
        "protocol":"fixed deterministic 50/50 within each anonymous family before Frankie Part 1",
        "family_counts":dict(family_counts),"revealed_counts":dict(train_counts),"heldout_counts":dict(blind_counts),
        "heldout_contains_outcome":False,
        "heldout_events":heldout,
    }
    Path("ng_frankie_part1_split_manifest.json").write_text(json.dumps(split_manifest,indent=2,sort_keys=True)+"\n")
    with gzip.open("ng_frankie_part1_revealed_events.jsonl.gz","wt") as f:
        for e in revealed: f.write(json.dumps(e,separators=(",",":"),allow_nan=False)+"\n")

    summary={
        "status":"PART1_REVEALED_READY_FOR_FRANKIE",
        "scratch_only":True,
        "permanent_frankie_modified":False,
        "family_ids":["F1","F2","F3"],
        "family_names_or_expected_price_behavior_exposed_to_frankie":False,
        "revealed_only":True,
        "n_revealed":len(revealed),
        "n_heldout":len(heldout),
        "split":split_manifest,
        "data_sources":{
            "all_days":"continuous MBP-10-derived book imbalance + aggressor flow + trade price",
            "20250717_mbo":"UNAVAILABLE; MBP-10 only",
            "20250923_mbo":"nymex/ng_mbo_ngv25/NG_20250923.dbn.zst",
            "20250930_mbo":"nymex/ng_mbo_ngx25/NG_20250930.dbn.zst",
            "20251001_mbo":"nymex/ng_mbo_ngx25/NG_20251001.dbn.zst",
            "mbo_representation":"complete one-second action/side/size/trade dynamics over -60..+60; raw order ids omitted",
        },
        "revealed_family_summary":summary_stats(revealed),
        "frankie_task":(
            "Study all three anonymous dipole families together using only the REVEALED_TRAIN events. "
            "Full price outcomes are intentionally visible in Part 1. Discover repeatable mappings between "
            "dipole/exhaustion geometry, post-flip variants, MBP-10/MBO behavior, and price-leg direction, "
            "shape, magnitude, and duration. Do not assume a short/medium/long ordering. Identify exceptions "
            "and conditional modifiers. Freeze explicit predictions/rules that can later be applied to the "
            "HELDOUT_BLIND events without seeing their price outcomes. Do not modify brain/schema/roles/plays."
        ),
    }
    Path("ng_frankie_part1_revealed_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    Path("ng_frankie_part1_family_provenance_NOT_FOR_FRANKIE.json").write_text(json.dumps(provenance,indent=2,sort_keys=True)+"\n")
    Path("ng_frankie_part1_prompt.txt").write_text(summary["frankie_task"]+"\n")
    render(revealed,"ng_frankie_part1_revealed_montage.png")
    print(json.dumps({"status":summary["status"],"family_counts":dict(family_counts),"revealed":dict(train_counts),"heldout":dict(blind_counts),"n_revealed":len(revealed)},indent=2))


if __name__ == "__main__":
    main()
