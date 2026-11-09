"""The orders behind the size-one onsets: origin, age, repetition and fate, four sessions.

Section 18 left one question open: is a one-lot new best a mechanical remainder or a behaviour (probing,
repeated repricing)? The MBO tape names every order, so for each size-one onset this pass records the one
order resting at the touch at the onset close and, from the Book's history, (a) how it got there in the
onset group: a fresh add (A) at that price, a reprice (M) of an existing order from another price, or an
older resting order left alone while the rest of the level was consumed or cancelled; (b) its age at the
onset (time since the order id was first seen); (c) how many size-one onsets the same order id has created
earlier in the session; (d) its fate after the onset: the next message on that id (cancel, fill, reprice
away, size change) and the delay to it. Classes are then crossed with the first-end outcome from
size_one_from_groups.py. Everything per session, no pooling across days as the final word. No trade cost.
"""

import gzip
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

import databento as db

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
from audit_october18_touch_mechanisms import Book, F_LAST, INSTRUMENT, TAPE, TAPE_FILE, git_blob  # noqa: E402
from size_one_tape_pass import MEMBERS, detect_oct03, records  # noqa: E402

NS = 1_000_000_000


def main():
    tag = os.environ.get("NG_TAG", "oct18")
    eps = [json.loads(l) for l in gzip.open(HERE / f"size-one-episodes-{tag}.jsonl.gz", "rt")]
    members = MEMBERS[tag] or detect_oct03([e["onset_cursor"] for e in eps])
    by_close = defaultdict(list)
    starts = defaultdict(list)
    for i, e in enumerate(eps):
        by_close[e["onset_cursor"]].append(i); starts[e["onset_first_cursor"]].append(i)
    book, pending = Book(), Counter()
    first_seen = {}                  # order_id -> (cursor, ts_recv)
    onsets_by_order = Counter()      # order_id -> number of onsets created so far
    open_fates = defaultdict(list)   # order_id -> list of episode indices awaiting their first post-onset message
    out = [dict() for _ in eps]
    capture = None
    for cursor, r in records(members):
        if r.instrument_id != INSTRUMENT:
            continue
        action, oid = str(r.action), r.order_id
        if action == "A" and oid not in first_seen:
            first_seen[oid] = (cursor, r.ts_recv)
        if action == "R":
            first_seen.clear(); open_fates.clear()
        # fate resolution: the first message on an order id after its onset close
        if oid in open_fates and action in ("C", "M", "F"):
            before = book.orders.get(oid)
            for i in open_fates.pop(oid):
                e = eps[i]
                kind = action
                if action == "M":
                    kind = "M_away" if r.price != e["original_price_raw"] else ("M_size_up" if before and r.size > before[2] else "M_same_price")
                out[i].update(fate=kind, fate_delay_ms=round((r.ts_recv - e["onset_ns"]) / 1e6, 3), fate_cursor=cursor)
        if cursor in starts:
            capture = []
        book.apply(r, cursor, pending, capture)
        if int(r.flags) & F_LAST:
            if cursor in by_close:
                for i in by_close[cursor]:
                    e = eps[i]; side = e["side"]; p0 = e["original_price_raw"]
                    lvl = book.level(side, p0)
                    if len(lvl) != 1:
                        out[i].update(error=f"touch holds {len(lvl)} orders"); continue
                    oid_t = next(iter(lvl))
                    origin = "older_resting"
                    for m in (capture or []):
                        if m["order_id"] != oid_t:
                            continue
                        a, b = m["after"], m["before"]
                        if a is not None and a[0] == side and a[1] == p0:
                            if m["action"] == "A":
                                origin = "fresh_add"
                            elif m["action"] == "M" and b is not None and b[1] != p0:
                                origin = "repriced_in"
                            elif m["action"] == "M" and b is not None and b[1] == p0 and a[2] < b[2]:
                                origin = "size_cut_in_place"
                            elif m["action"] == "C":
                                origin = "partial_cancel_in_place"
                    fs = first_seen.get(oid_t)
                    age_ms = None if fs is None else round((r.ts_recv - fs[1]) / 1e6, 3)
                    out[i].update(order_id=oid_t, origin=origin, age_ms=age_ms, prior_onsets_by_order=onsets_by_order[oid_t])
                    onsets_by_order[oid_t] += 1
                    open_fates[oid_t].append(i)
                capture = None
            pending.clear()
    rows = []
    for e, o in zip(eps, out):
        if "error" in o or "order_id" not in o:
            continue
        rows.append(dict(onset_group=e["onset_group"], side=e["side"], onset=e["onset"], outcome=e["outcome"], end_vs_entry=e["end_vs_entry"], hour_utc=e["hour_utc"],
                         end_ms=None if e["end_ns"] is None else round((e["end_ns"] - e["onset_ns"]) / 1e6, 3), **o))
    with gzip.open(HERE / f"size-one-orders-{tag}.jsonl.gz", "wt") as f:
        for r_ in rows:
            f.write(json.dumps(r_) + "\n")

    def cell(sub):
        n = len(sub)
        return dict(n=n, retreat_share=round(sum(1 for r_ in sub if r_["outcome"] == "RETREATED") / n, 3) if n else None,
                    median_age_ms=median(r_["age_ms"] for r_ in sub if r_["age_ms"] is not None) if any(r_["age_ms"] is not None for r_ in sub) else None,
                    fate=dict(Counter(r_.get("fate", "none_before_tape_end") for r_ in sub)),
                    median_fate_delay_ms=median(r_["fate_delay_ms"] for r_ in sub if "fate_delay_ms" in r_) if any("fate_delay_ms" in r_ for r_ in sub) else None,
                    cancelled_within_5ms=round(sum(1 for r_ in sub if r_.get("fate") == "C" and r_["fate_delay_ms"] <= 5) / n, 3) if n else None,
                    filled_first=round(sum(1 for r_ in sub if r_.get("fate") == "F") / n, 3) if n else None)
    def age_class(a):
        return "none" if a is None else "under_10ms" if a < 10 else "10ms_to_1s" if a < 1000 else "1s_to_60s" if a < 60000 else "over_60s"
    summary = dict(session=tag, episodes=len(eps), with_order=len(rows), errors=sum(1 for o in out if "error" in o))
    for onset in ("NEW_BEST", "STANDING_BEST_SHRANK"):
        sub = [r_ for r_ in rows if r_["onset"] == onset]
        summary[onset] = dict(n=len(sub), by_origin={k: cell([r_ for r_ in sub if r_["origin"] == k]) for k in sorted({r_["origin"] for r_ in sub})},
                              by_age={k: cell([r_ for r_ in sub if age_class(r_["age_ms"]) == k]) for k in ("under_10ms", "10ms_to_1s", "1s_to_60s", "over_60s")},
                              by_prior_onsets={k: cell([r_ for r_ in sub if min(r_["prior_onsets_by_order"], 3) == k]) for k in (0, 1, 2, 3)},
                              repeat_order_ids=dict(orders_with_2plus_onsets=sum(1 for oid, c in Counter(r_["order_id"] for r_ in sub).items() if c >= 2),
                                                    share_of_onsets_from_repeat_orders=round(sum(1 for r_ in sub if Counter(x["order_id"] for x in sub)[r_["order_id"]] >= 2) / len(sub), 3) if sub else None,
                                                    top_order_onset_counts=sorted(Counter(r_["order_id"] for r_ in sub).values(), reverse=True)[:10]),
                              origin_x_fate=dict(Counter(f"{r_['origin']}->{r_.get('fate', 'none')}" for r_ in sub)))
    (HERE / f"size-one-orders-{tag}-summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    print(json.dumps(dict(session=tag, episodes=len(eps), with_order=len(rows), errors=summary["errors"])))
    for onset in ("NEW_BEST", "STANDING_BEST_SHRANK"):
        S = summary[onset]
        print(f"== {onset} n {S['n']} repeat ids {S['repeat_order_ids']}")
        for grp in ("by_origin", "by_age", "by_prior_onsets"):
            for k, c in S[grp].items():
                if c["n"]:
                    print(f"   {grp:16s} {str(k):22s} n {c['n']:6d} retreat {c['retreat_share']} age_med {c['median_age_ms']} fate {c['fate']} cancel<=5ms {c['cancelled_within_5ms']} filled_first {c['filled_first']} fate_delay_med {c['median_fate_delay_ms']}")


if __name__ == "__main__":
    main()
