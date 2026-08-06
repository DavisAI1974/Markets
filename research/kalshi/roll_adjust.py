"""roll_adjust.py — contract-roll back-adjustment for the continuous NG.v.0 series (S95, Greg).

The Databento continuous NG.v.0 rolls to the next contract ~monthly (instrument_id changes). At a roll the
price JUMPS by the calendar spread (e.g. Sep24->25 Oct->Nov +0.30; Oct26->27 Nov->Dec +0.66) — NOT a
tradeable move. Left raw, the continuous curve gets a fake step and overnight gaps at a roll are spurious.

This detects rolls (instrument_id change day-over-day) and returns a per-day BACK-ADJUST offset: subtract it
from raw price so segments connect at the roll (intraday moves preserved, roll gaps removed). Anchored on the
FIRST day's contract (offset 0), later segments shifted to that level. Overnight gap AT a roll -> ~0 by
construction (you roll the position, you don't capture the spread).

Raw S3/npz data is never mutated — adjustment is applied at the continuous-series layer only.

  offs, rolls = roll_offsets("NG", ["20250908",...,"20251021"])   # {date: offset$/price}, [roll records]
  adj_price = raw_price - offs[date]                                # in price units
"""
import gzip, json, glob, os
import numpy as np
import fast_tape, event_move_baseline as emb

_META = os.path.join(emb.CONT_DIR, "roll_meta_NG.json")   # {date: {iid, first, last}} cache


def _load_meta():
    return json.load(open(_META)) if os.path.exists(_META) else {}


def _day_meta(root, day, meta):
    """Dominant instrument_id + first/last trade price for a day. iid from gz (first ~3000 trades);
    first/last price from the npz path (instant). Cached in roll_meta_NG.json."""
    if day in meta:
        return meta[day]
    ts, px = fast_tape.fast_load_day(root, day)           # ensures gz+npz cached
    if len(px) == 0:
        meta[day] = None; return None
    gz = glob.glob(os.path.join(emb.CONT_DIR, f"{root}_{day}*jsonl.gz"))[0]
    ct = {}; n = 0
    with gzip.open(gz, "rt") as f:
        for line in f:
            if '"action": "T"' in line:
                iid = json.loads(line).get("instrument_id"); ct[iid] = ct.get(iid, 0) + 1
                n += 1
                if n >= 3000:
                    break
    meta[day] = {"iid": int(max(ct, key=ct.get)), "first": float(px[0]), "last": float(px[-1])}
    return meta[day]


def roll_offsets(root, days):
    """Return ({date: back_adjust_offset_in_price}, [roll records]). Days must be in chronological order."""
    meta = _load_meta()
    offs, rolls = {}, []
    cum = 0.0; prev = None
    for d in days:
        m = _day_meta(root, d, meta)
        if m is None:
            offs[d] = cum; continue
        if prev is not None and m["iid"] != prev["iid"]:
            gap = m["first"] - prev["last"]               # boundary jump ~= calendar spread (roll)
            cum += gap
            rolls.append({"date": d, "from_iid": prev["iid"], "to_iid": m["iid"], "offset": round(gap, 4)})
        offs[d] = cum
        prev = m
    json.dump(meta, open(_META, "w"))
    return offs, rolls


if __name__ == "__main__":
    import sys
    days = sorted(sys.argv[1:])
    offs, rolls = roll_offsets("NG", days)
    print(f"rolls detected: {len(rolls)}")
    for r in rolls:
        print(f"  {r['date']}  iid {r['from_iid']}->{r['to_iid']}  roll offset {r['offset']:+.3f}")
    print("cumulative offsets:", {d: round(o, 3) for d, o in offs.items() if o})
