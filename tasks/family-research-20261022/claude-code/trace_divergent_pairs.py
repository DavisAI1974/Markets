"""Concrete divergent pairs on a session, traced at order level (the 375 / 391 exercise for the other days).

From the size-one episodes with their tape mechanics and order identities, pick, inside the 13:00 UTC hour,
matched pairs with the same start and a different end: (a) a standing best eaten to one lot by fills on
the order's first appearance, both still open at the 1 ms entry, matched on prior touch size (within one
lot) and next-level bucket, one RETREATED and one SIZE_RECOVERED; (b) a fresh one-lot new best, matched on
next-level size bucket and the far-side touch size, one RETREATED and one recovered. Closest onsets in
time win. For each episode the tape is replayed and every message at the onset side's touch price and at
the far side's touch, from 250 ms before the onset to 50 ms after the first end, is written with its
cursor, clock offset, action, order id, size, fill linkage, and the touch and next level after it. The
narrative is written by hand from these dumps in the findings file; nothing here infers intent.
"""

import gzip
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import databento as db

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
from audit_october18_touch_mechanisms import Book, F_LAST, INSTRUMENT  # noqa: E402
from size_one_tape_pass import MEMBERS, detect_oct03, records  # noqa: E402

NS = 1_000_000_000
PRE_NS, POST_NS = 250_000_000, 50_000_000


def pick_pairs(rows, orders):
    o = {(r["onset_group"], r["side"]): r for r in orders}
    def key(r):
        return (r["onset_group"], r["side"])
    pairs = []
    # (a) standing, fill-linked, first appearance, open at entry, hour 13
    a = [r for r in rows if r["onset"] == "STANDING_BEST_SHRANK" and r["flow"] == "fill_linked" and r["end_vs_entry"] == "AFTER_ENTRY" and r["hour_utc"] == 13
         and key(r) in o and o[key(r)]["prior_onsets_by_order"] == 0]
    ret = [r for r in a if r["outcome"] == "RETREATED"]; rec = [r for r in a if r["outcome"] == "SIZE_RECOVERED_AT_SAME_PRICE"]
    best = None
    for x in ret:
        for y in rec:
            if x["side"] == y["side"] and abs(x["prior_touch"][1] - y["prior_touch"][1]) <= 1 and x["book_next"] == y["book_next"]:
                d = abs(x["onset_ns"] - y["onset_ns"])
                if best is None or d < best[0]:
                    best = (d, x, y)
    if best:
        pairs.append(dict(kind="standing_fill_linked_first_appearance", retreated=best[1], recovered=best[2]))
    # (b) new best, fresh add, open at entry, hour 13
    b = [r for r in rows if r["onset"] == "NEW_BEST" and r["flow"] == "no_reduction" and r["end_vs_entry"] == "AFTER_ENTRY" and r["hour_utc"] == 13
         and key(r) in o and o[key(r)]["origin"] == "fresh_add"]
    ret = [r for r in b if r["outcome"] == "RETREATED"]; rec = [r for r in b if r["outcome"] == "SIZE_RECOVERED_AT_SAME_PRICE"]
    best = None
    for x in ret:
        for y in rec:
            if x["side"] == y["side"] and x["book_next"] == y["book_next"] and abs(x["other_touch"][1] - y["other_touch"][1]) <= 2:
                d = abs(x["onset_ns"] - y["onset_ns"])
                if best is None or d < best[0]:
                    best = (d, x, y)
    if best:
        pairs.append(dict(kind="new_best_fresh_add", retreated=best[1], recovered=best[2]))
    for p in pairs:
        for k in ("retreated", "recovered"):
            p[k] = dict(p[k], order=o[key(p[k])])
    return pairs


def main():
    tag = os.environ.get("NG_TAG", "oct17")
    rows = [json.loads(l) for l in gzip.open(HERE / f"size-one-four-arm-{tag}-rows.jsonl.gz", "rt")]
    orders = [json.loads(l) for l in gzip.open(HERE / f"size-one-orders-{tag}.jsonl.gz", "rt")]
    pairs = pick_pairs(rows, orders)
    if not pairs:
        raise SystemExit("no pairs")
    episodes = [p[k] for p in pairs for k in ("retreated", "recovered")]
    windows = [(e["onset_ns"] - PRE_NS, (e["end_ns"] or e["onset_ns"]) + POST_NS, i) for i, e in enumerate(episodes)]
    members = MEMBERS[tag] or detect_oct03([e["onset_cursor"] for e in episodes])
    book, pending = Book(), __import__("collections").Counter()
    dumps = defaultdict(list)
    for cursor, r in records(members):
        if r.instrument_id != INSTRUMENT:
            continue
        ts = r.ts_recv
        active = [i for (lo, hi, i) in windows if lo <= ts <= hi]
        cap = [] if active else None
        book.apply(r, cursor, pending, cap)
        if active:
            for i in active:
                e = episodes[i]; side = e["side"]; p0 = e["original_price_raw"]
                far = "A" if side == "B" else "B"
                m = cap[-1] if cap else None
                touched = (m is not None and ((m["before"] and m["before"][1] == p0 and m["before"][0] == side) or (m["after"] and m["after"][1] == p0 and m["after"][0] == side))) or str(r.action) in ("T", "F")
                far_prices = sorted((pr for (s, pr), o in book.levels.items() if s == far and o), reverse=far == "B")
                near_prices = sorted((pr for (s, pr), o in book.levels.items() if s == side and o), reverse=side == "B")
                far_touch = [far_prices[0], sum(book.level(far, far_prices[0]).values()), len(book.level(far, far_prices[0]))] if far_prices else None
                near_best = [near_prices[0], sum(book.level(side, near_prices[0]).values()), len(book.level(side, near_prices[0]))] if near_prices else None
                nxt = [near_prices[1], sum(book.level(side, near_prices[1]).values())] if len(near_prices) > 1 else None
                far_touched = m is not None and ((m["before"] and m["before"][0] == far and far_prices and m["before"][1] == far_prices[0]) or (m["after"] and m["after"][0] == far and far_prices and m["after"][1] == far_prices[0]))
                if touched or far_touched or int(r.flags) & F_LAST and (cursor in (e["onset_cursor"], e["end_cursor"])):
                    dumps[i].append(dict(cursor=cursor, t_ms=round((ts - e["onset_ns"]) / 1e6, 3), action=str(r.action), side=str(r.side), price=r.price, size=r.size, order_id=r.order_id,
                                         flags_last=bool(int(r.flags) & F_LAST), linked_fill_reduction=(m or {}).get("linked_display_reduction", 0),
                                         before=(m or {}).get("before"), after=(m or {}).get("after"), near_best=near_best, next_level=nxt, far_touch=far_touch,
                                         marker=("ONSET_CLOSE" if cursor == e["onset_cursor"] else "END_CLOSE" if cursor == e["end_cursor"] else "")))
        if int(r.flags) & F_LAST:
            pending.clear()
        if ts > max(hi for (_, hi, _) in windows):
            break
    out = dict(session=tag, pairs=[])
    for p in pairs:
        entry = dict(kind=p["kind"])
        for k in ("retreated", "recovered"):
            i = episodes.index(p[k])
            e = p[k]
            entry[k] = dict(episode={kk: e[kk] for kk in ("onset_group", "side", "onset", "onset_ns", "onset_cursor", "original_price_raw", "prior_touch", "other_touch", "next_gap_ticks", "book_next", "outcome", "end_ns", "end_cursor", "ending_touch", "end_vs_entry")},
                            order={kk: e["order"].get(kk) for kk in ("order_id", "origin", "age_ms", "prior_onsets_by_order", "fate", "fate_delay_ms")},
                            messages=dumps[i])
        out["pairs"].append(entry)
    (HERE / f"divergent-pairs-{tag}.json").write_text(json.dumps(out, indent=1) + "\n")
    for p in out["pairs"]:
        print(f"== {tag} {p['kind']}")
        for k in ("retreated", "recovered"):
            e = p[k]["episode"]; o = p[k]["order"]
            print(f"  {k}: group {e['onset_group']} side {e['side']} price {e['original_price_raw']} prior_touch {e['prior_touch']} other {e['other_touch']} next_gap {e['next_gap_ticks']} {e['book_next']} end {e['outcome']} at +{(e['end_ns'] - e['onset_ns']) / 1e6:.3f} ms ending_touch {e['ending_touch']} | order {o['order_id']} {o['origin']} age {o['age_ms']} ms fate {o['fate']} +{o['fate_delay_ms']} ms | {len(p[k]['messages'])} messages")
            for m in p[k]["messages"][:60]:
                print(f"      {m['t_ms']:>9.3f} ms c{m['cursor']} {m['action']} {m['side']} {m['price']} x{m['size']} id {m['order_id']} link {m['linked_fill_reduction']} near {m['near_best']} next {m['next_level']} far {m['far_touch']} {m['marker']}")


if __name__ == "__main__":
    main()
