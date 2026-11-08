"""Mechanism cohort for all 749 first-family events: what the family group itself did, and how the book
answered in the next second, read from the pinned October 18 MBO tape.

For each event the family group is the message span (pre_input_cursor, cursor_cap + 1]. The script records,
per event: trade prints in the family group by wire aggressor side and the number of distinct price levels
printed; resting orders filled, and whether any order that printed as aggressor also appeared as a new
resting order in the same group (a remainder posted at the touch, as in instance 391); then, in the first
250 ms and the first 1 s after the family group close, by side: fills on resting orders, unlinked
cancellations (no matching fill in the same completed group), adds, and reprices, split by price relative
to the pre-event touch. Outcomes come from the four-arm events file. Every predictor here is observable only
once the family group has closed, so the table describes mechanisms, not an entry rule.
"""

import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import databento as db

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from audit_october18_touch_mechanisms import Book, F_LAST, INSTRUMENT, OCTOBER18_UTC_OFFSET, TAPE, TAPE_FILE, git_blob  # noqa: E402

NS = 1_000_000_000
TICK = 1_000_000
AFTER_SHORT = 250_000_000
AFTER_LONG = NS


def main():
    events = [json.loads(l) for l in gzip.open(HERE / "first-family-four-arm-events.jsonl.gz", "rt")]
    events.sort(key=lambda e: e["cutoff_ns"])
    for e in events:
        e["family_lo"] = e["pre_close_cursor"] + 1
        e["family_hi"] = e["pre_close_cursor"]  # set when the first F_LAST after the cutoff is seen
        e["phase"] = "pre"
        e["c"] = Counter()
        e["aggressor_ids"] = set()
        e["printed_prices"] = set()
        e["family_close_ns"] = None
    # the October 18 UTC member begins at 00:00 UTC; events before that (October 17 evening) have no tape here
    oct18_start = 1697587200 * NS
    active = []
    pending_idx = 0
    book = Book()
    pending = Counter()
    for index, record in enumerate(db.DBNStore.from_bytes(git_blob(TAPE, TAPE_FILE))):
        cursor = index + OCTOBER18_UTC_OFFSET
        if record.instrument_id != INSTRUMENT:
            raise ValueError(f"unexpected instrument at {cursor}")
        ts = record.ts_recv
        action = str(record.action)
        while pending_idx < len(events) and events[pending_idx]["cutoff_ns"] - NS <= ts:
            active.append(events[pending_idx]); pending_idx += 1
        before = book.orders.get(record.order_id)
        muts = []
        book.apply(record, cursor, pending, muts)
        linked = muts[-1]["linked_display_reduction"] if muts else 0
        after = muts[-1]["after"] if muts else None
        still = []
        for e in active:
            if ts < e["cutoff_ns"] - NS:
                still.append(e); continue
            if e["phase"] == "pre" and cursor >= e["family_lo"]:
                e["phase"] = "family"
            if e["phase"] == "family" and e["family_close_ns"] is not None and ts > e["family_close_ns"]:
                e["phase"] = "post"
            if e["phase"] == "post" and ts > e["family_close_ns"] + AFTER_LONG:
                continue  # finished
            phase = e["phase"]
            if phase == "post":
                phase = "post250" if ts <= e["family_close_ns"] + AFTER_SHORT else "post1s"
            side = str(record.side)
            price = record.price if record.price < 2**62 else None
            c = e["c"]
            if action == "T":
                c[f"{phase}:T:{side}"] += record.size
                if phase == "family":
                    e["aggressor_ids"].add(record.order_id)
                    e["printed_prices"].add(price)
            elif action in ("A", "C", "M", "F") and side in ("B", "A") and price is not None:
                ref = e["pre_bid_raw"] if side == "B" else e["pre_ask_raw"]
                where = "touch" if price == ref else ("better" if ((price > ref) if side == "B" else (price < ref)) else "deeper")
                if action == "F":
                    c[f"{phase}:F:{side}:{where}"] += record.size
                elif action == "A":
                    c[f"{phase}:A:{side}:{where}"] += record.size
                    if phase == "family" and record.order_id in e["aggressor_ids"]:
                        c["family:remainder_posted"] += record.size
                elif action == "C":
                    c[f"{phase}:C_linked:{side}:{where}"] += linked
                    c[f"{phase}:C_unlinked:{side}:{where}"] += record.size - linked
                elif action == "M":
                    if before and after and before[1] == after[1]:
                        d = after[2] - before[2]
                        c[f"{phase}:M_{'down' if d < 0 else 'up'}:{side}:{where}"] += abs(d)
                    elif before and after:
                        c[f"{phase}:M_reprice:{side}"] += after[2]
            if int(record.flags) & F_LAST and e["phase"] == "family" and ts > e["cutoff_ns"] and e["family_close_ns"] is None:
                e["family_close_ns"] = ts
                e["family_hi"] = cursor
            still.append(e)
        active = still
        if int(record.flags) & F_LAST:
            pending.clear()
        if pending_idx >= len(events) and not active:
            break
    out = []
    for e in events:
        c = e["c"]
        recent = e["recent"]
        hit = "B" if recent < 0 else "A" if recent > 0 else None
        opp = "A" if hit == "B" else "B" if hit == "A" else None
        row = dict(instance=e["instance"], start_recv_ns=e["start_recv_ns"], recent=recent, has_tape=e["cutoff_ns"] >= oct18_start,
                   family_cursors=[e["family_lo"], e["family_hi"]], family_close_ns=e["family_close_ns"],
                   family_print_lots_sell=c["family:T:A"], family_print_lots_buy=c["family:T:B"], family_print_lots_unknown=c["family:T:N"],
                   family_levels_printed=len(e["printed_prices"]), family_aggressor_orders=len(e["aggressor_ids"]),
                   family_remainder_posted_lots=c["family:remainder_posted"],
                   counters={k: v for k, v in sorted(c.items()) if v},
                   move_ticks={int(k): v for k, v in e["move_ticks"].items()})
        if hit:
            row["hit_side"] = hit
            row["post250_hit_side_unlinked_cancels_deeper"] = c[f"post250:C_unlinked:{hit}:deeper"]
            row["post250_hit_side_adds_deeper"] = c[f"post250:A:{hit}:deeper"]
            row["post250_hit_side_adds_touch_or_better"] = c[f"post250:A:{hit}:touch"] + c[f"post250:A:{hit}:better"]
            row["post250_opp_side_adds_better"] = c[f"post250:A:{opp}:better"]
            row["post250_opp_side_fills_better_or_touch"] = c[f"post250:F:{opp}:better"] + c[f"post250:F:{opp}:touch"]
            row["post250_hit_side_fills"] = c[f"post250:F:{hit}:touch"] + c[f"post250:F:{hit}:better"] + c[f"post250:F:{hit}:deeper"]
            row["post1s_opp_side_fills_better_or_touch"] = c[f"post1s:F:{opp}:better"] + c[f"post1s:F:{opp}:touch"] + row["post250_opp_side_fills_better_or_touch"]
            row["post1s_hit_side_unlinked_cancels_deeper"] = c[f"post1s:C_unlinked:{hit}:deeper"] + row["post250_hit_side_unlinked_cancels_deeper"]
        out.append(row)
    with gzip.open(HERE / "sweep-cohort-events.jsonl.gz", "wt", encoding="utf-8") as stream:
        for row in out:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
    print("events", len(out), "with tape", sum(1 for r in out if r["has_tape"]))


if __name__ == "__main__":
    main()
