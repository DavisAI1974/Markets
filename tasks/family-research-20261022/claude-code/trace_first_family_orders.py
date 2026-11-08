"""Order-level trace of first-family events 375 and 391 from the pinned October 18 MBO tape.

Replays the October 18 UTC member from its opening snapshot with the same Book semantics as
audit_october18_touch_mechanisms.py (fill-to-reduction linkage by order and price). For each
requested event it records every message between (decision boundary - before) and
(decision boundary + after), the as-of book (top levels with order queues) at the strict
boundary, and summaries per 250 ms bin: adds, cancels, modifies, fills and trades by side,
split into "at the pre-event touch price", "better than the touch" and "deeper", plus the
fixed-price displayed size path at the pre-event bid and ask prices.
"""

import argparse
import gzip
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import databento as db

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from audit_october18_touch_mechanisms import Book, F_LAST, INSTRUMENT, OCTOBER18_UTC_OFFSET, TAPE, TAPE_FILE, git_blob  # noqa: E402

NS = 1_000_000_000
TICK = 1_000_000


def top_levels(book, side, depth):
    prices = sorted((p for (s, p), orders in book.levels.items() if s == side and orders), reverse=side == "B")[:depth]
    return [dict(price_raw=p, size=sum(book.levels[(side, p)].values()), orders=len(book.levels[(side, p)]),
                 queue=[[oid, sz] for oid, sz in book.levels[(side, p)].items()]) for p in prices]


def best(book, side):
    prices = [p for (s, p), orders in book.levels.items() if s == side and orders]
    return (max(prices) if side == "B" else min(prices)) if prices else None


GROUPS = HERE.parents[2] / ("research/kalshi/adaptive_wavepacket_20261108/markets_bridge/tasks/"
                            "root-bounded-replay/retained/october18-standalone-inputs/groups.jsonl.gz")


def saved_groups(cursors):
    found = {}
    with gzip.open(GROUPS, "rt", encoding="utf-8") as stream:
        for line in stream:
            g = json.loads(line)
            if g["close_cursor"] in cursors:
                found[g["close_cursor"]] = g
            if len(found) == len(cursors):
                break
    return found


def trace(events, before_s, after_s, depth):
    windows = {name: (e["cutoff_ns"] - int(before_s * NS), e["cutoff_ns"] + int(after_s * NS), e) for name, e in events.items()}
    pre_groups = saved_groups({e["pre_input_cursor"] for e in events.values()} | {e["cursor_cap"] + 1 for e in events.values()})
    pre_by_cursor = {e["pre_input_cursor"]: name for name, e in events.items()}
    book = Book()
    pending = Counter()
    capture = {name: dict(messages=[], asof=None, fixed_path=[], snapshots={}) for name in events}
    done = set()
    for index, record in enumerate(db.DBNStore.from_bytes(git_blob(TAPE, TAPE_FILE))):
        cursor = index + OCTOBER18_UTC_OFFSET
        if record.instrument_id != INSTRUMENT:
            raise ValueError(f"unexpected instrument at {cursor}")
        ts = record.ts_recv
        action = str(record.action)
        for name, (lo, hi, e) in windows.items():
            if name in done or ts < lo:
                continue
            if ts > hi:
                done.add(name); continue
            cap = capture[name]
            before_state = book.orders.get(record.order_id)
            cap["messages"].append(dict(cursor=cursor, ts_recv=ts, ts_event=record.ts_event, action=action, side=str(record.side),
                                        price_raw=record.price if record.price < 2**62 else None, size=record.size,
                                        order_id=record.order_id, flags=int(record.flags),
                                        before=list(before_state) if before_state else None))
        # apply once for everybody
        muts = []
        book.apply(record, cursor, pending, muts)
        if cursor in pre_by_cursor:
            name = pre_by_cursor[cursor]
            g = pre_groups[cursor]
            if g["receive_ns"] != ts or not int(record.flags) & F_LAST:
                raise ValueError(f"pre-event cursor {cursor} does not close a saved group at this clock")
            asof = dict(cursor=cursor, receive_ns=ts, bid=top_levels(book, "B", depth), ask=top_levels(book, "A", depth))
            if [asof["bid"][0]["price_raw"], asof["bid"][0]["size"], asof["bid"][0]["orders"]] != g["bid"] or \
               [asof["ask"][0]["price_raw"], asof["ask"][0]["size"], asof["ask"][0]["orders"]] != g["ask"]:
                raise ValueError(f"as-of touch differs from the saved group at {cursor}")
            capture[name]["asof"] = asof
            capture[name]["asof_saved_group"] = g
        for name, (lo, hi, e) in windows.items():
            if name in done or ts < lo or ts > hi:
                continue
            cap = capture[name]
            if muts:
                cap["messages"][-1]["linked_display_reduction"] = muts[-1]["linked_display_reduction"]
                cap["messages"][-1]["linked_fill_unchanged_display"] = muts[-1]["linked_fill_unchanged_display"]
                cap["messages"][-1]["after"] = list(muts[-1]["after"]) if muts[-1]["after"] else None
            if int(record.flags) & F_LAST:
                b, a = best(book, "B"), best(book, "A")
                cap["fixed_path"].append(dict(
                    cursor=cursor, ts_recv=ts, best_bid=b, best_ask=a,
                    bid_size_at_pre_bid=sum(book.level("B", e["pre_bid_raw"]).values()),
                    bid_orders_at_pre_bid=len(book.level("B", e["pre_bid_raw"])),
                    ask_size_at_pre_ask=sum(book.level("A", e["pre_ask_raw"]).values()),
                    ask_orders_at_pre_ask=len(book.level("A", e["pre_ask_raw"])),
                    bid_size_at_next=sum(book.level("B", e["pre_bid_raw"] - TICK).values()),
                    ask_size_at_next=sum(book.level("A", e["pre_ask_raw"] + TICK).values()),
                ))
                for label, off in (("plus_1s", 1), ("plus_5s", 5)):
                    if label not in cap["snapshots"] and ts >= e["cutoff_ns"] + off * NS:
                        cap["snapshots"][label] = dict(cursor=cursor, ts_recv=ts, bid=top_levels(book, "B", depth), ask=top_levels(book, "A", depth))
        if int(record.flags) & F_LAST:
            pending.clear()
        if len(done) == len(windows):
            break
    return capture


def summarize(name, e, cap, bin_ms):
    bins = defaultdict(Counter)
    for m in cap["messages"]:
        rel = (m["ts_recv"] - e["cutoff_ns"]) / 1e6
        b = int(rel // bin_ms) * bin_ms
        side = m["side"]
        price = m["price_raw"]
        if m["action"] == "T":
            # aggressor side on the wire; relation to the pre-event quotes
            where = "at_pre_bid" if price == e["pre_bid_raw"] else "at_pre_ask" if price == e["pre_ask_raw"] else \
                    "below_pre_bid" if price is not None and price < e["pre_bid_raw"] else "above_pre_ask" if price is not None and price > e["pre_ask_raw"] else "inside"
            bins[b][f"T:{side}:{where}"] += m["size"]
            continue
        if side not in ("B", "A") or price is None:
            bins[b][f"{m['action']}:other"] += 1
            continue
        ref = e["pre_bid_raw"] if side == "B" else e["pre_ask_raw"]
        better = (price > ref) if side == "B" else (price < ref)
        where = "at_touch" if price == ref else "better" if better else "deeper"
        qty = m["size"]
        if m["action"] == "C":
            fl = m.get("linked_display_reduction", 0)
            bins[b][f"C_fill_linked:{side}:{where}"] += fl
            bins[b][f"C_unlinked:{side}:{where}"] += qty - fl
        elif m["action"] == "A":
            bins[b][f"A:{side}:{where}"] += qty
        elif m["action"] == "M":
            bef = m.get("before"); aft = m.get("after")
            if bef and aft and bef[1] == aft[1]:
                d = aft[2] - bef[2]
                bins[b][f"M_size_{'up' if d > 0 else 'down' if d < 0 else 'same'}:{side}:{where}"] += abs(d) if d else 1
            elif bef and aft:
                bins[b][f"M_reprice:{side}:{where}"] += aft[2]
            else:
                bins[b][f"M:{side}:{where}"] += qty
        elif m["action"] == "F":
            bins[b][f"F:{side}:{where}"] += qty
    return {str(k): dict(v) for k, v in sorted(bins.items())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=float, default=3.0)
    parser.add_argument("--after", type=float, default=5.0)
    parser.add_argument("--depth", type=int, default=5)
    parser.add_argument("--bin-ms", type=int, default=250)
    args = parser.parse_args()
    events_in = json.loads((HERE / "trace-events.json").read_text())
    cap = trace(events_in, args.before, args.after, args.depth)
    out = {}
    for name, e in events_in.items():
        c = cap[name]
        fam = [m for m in c["messages"] if e["pre_input_cursor"] < m["cursor"] <= e["cursor_cap"] + 1]
        out[name] = dict(event=e, asof_book=c["asof"], asof_saved_group=c.get("asof_saved_group"),
                         family_group_cursors=[e["pre_input_cursor"] + 1, e["cursor_cap"] + 1],
                         family_group_messages=fam, snapshots=c["snapshots"],
                         message_count=len(c["messages"]), bins=summarize(name, e, c, args.bin_ms),
                         fixed_price_path=c["fixed_path"])
        (HERE / f"trace-{name}-messages.jsonl.gz").write_bytes(gzip.compress(
            "".join(json.dumps(m, sort_keys=True) + "\n" for m in c["messages"]).encode(), mtime=0))
    (HERE / "trace-first-family-summary.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    for name, o in out.items():
        print(f"\n### {name}: {o['message_count']} messages; as-of cursor {o['asof_book']['cursor']} (saved pre-event group verified)")
        print(f"family group messages ({len(o['family_group_messages'])}):")
        for m in o["family_group_messages"]:
            print("   ", m["cursor"], m["action"], m["side"], m["price_raw"], m["size"], m["order_id"], "before", m.get("before"), "after", m.get("after"), "fl", m.get("linked_display_reduction"))
        for lab, snap in o["snapshots"].items():
            print(lab, "bid", [(l['price_raw'], l['size'], l['orders']) for l in snap["bid"]], "ask", [(l['price_raw'], l['size'], l['orders']) for l in snap["ask"]])
        print("as-of bid", [(l['price_raw'], l['size'], l['orders']) for l in o["asof_book"]["bid"]])
        print("as-of ask", [(l['price_raw'], l['size'], l['orders']) for l in o["asof_book"]["ask"]])
        for b, v in o["bins"].items():
            print(f"  bin {b:>7} ms:", {k: n for k, n in sorted(v.items()) if n})


if __name__ == "__main__":
    main()
