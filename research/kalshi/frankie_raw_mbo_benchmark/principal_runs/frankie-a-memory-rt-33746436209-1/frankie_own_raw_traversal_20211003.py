#!/usr/bin/env python3
"""My own traversal of the raw DBN, and the reconciliation of my book against the delivered one.

The delivered member ledger already carries a reconstructed book; this rebuilds it from the raw
source independently and compares, group by group, because one reconstruction is an assertion and
two that agree are evidence. Nothing here reads the delivered book before computing my own for the
same group: the comparison happens after my book has been advanced by that group's own messages.

What I add to the flat MBO stream, and nothing else:
  1. GROUPING - records into F_LAST-closed event groups on the venue's own last-message flag.
  2. THE BOOK - every message replayed into full depth on both sides.
  3. FIFO PRIORITY - per level, the resting order ids in arrival order with their sizes.

Reconciliation is exact and per group: best prices, full depth, order count, level count on both
sides, and the touch FIFO order-id sequence. Every disagreement is counted and the first ones are
kept with their group index; a silent wrong book is the failure mode this exists to catch.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any

import databento

SOURCE = Path("data/sunday_source/glbx-mdp3-20211003.mbo.dbn.zst")
MEMBER = Path("data/sunday_ledgers/exact_member_rows.jsonl")
OUT = Path("data/sunday_run/raw_traversal")
UNDEF = 9223372036854775807
F_LAST = 1 << 7  # DBN flag bit: last message of an event


class Book:
    """Full-depth book with per-level FIFO queues, keyed by raw integer price."""

    def __init__(self) -> None:
        self.levels: dict[str, dict[int, "OrderedDict[int, int]"]] = {"B": {}, "A": {}}
        self.orders: dict[int, tuple[str, int, int]] = {}  # order_id -> (side, price_raw, size)
        self.clears = 0
        self.missing_reference = Counter()
        self.snapshot_adds = 0

    def add(self, oid: int, side: str, price: int, size: int, snapshot: bool) -> None:
        if side not in ("B", "A") or price >= UNDEF or size <= 0:
            return
        if snapshot:
            self.snapshot_adds += 1
        lv = self.levels[side].setdefault(price, OrderedDict())
        lv[oid] = lv.get(oid, 0) + size
        self.orders[oid] = (side, price, lv[oid])

    def cancel(self, oid: int, side: str, price: int, size: int) -> None:
        rec = self.orders.get(oid)
        if rec is None:
            self.missing_reference["C"] += 1
            return
        s, p, cur = rec
        lv = self.levels[s].get(p)
        if lv is None or oid not in lv:
            self.missing_reference["C_level"] += 1
            self.orders.pop(oid, None)
            return
        left = lv[oid] - (size if size > 0 else lv[oid])
        if left > 0:
            lv[oid] = left
            self.orders[oid] = (s, p, left)
        else:
            del lv[oid]
            self.orders.pop(oid, None)
            if not lv:
                del self.levels[s][p]

    def modify(self, oid: int, side: str, price: int, size: int) -> None:
        rec = self.orders.get(oid)
        if rec is None:
            self.missing_reference["M"] += 1
            self.add(oid, side, price, size, False)
            return
        s, p, cur = rec
        lv = self.levels[s].get(p)
        if p != price or size > cur:
            # priority is lost: the order leaves its place and joins the back of the new level
            if lv is not None and oid in lv:
                del lv[oid]
                if not lv:
                    del self.levels[s][p]
            self.orders.pop(oid, None)
            self.add(oid, side if side in ("B", "A") else s, price, size, False)
        else:
            lv[oid] = size
            self.orders[oid] = (s, p, size)

    def fill(self, oid: int, side: str, size: int) -> None:
        rec = self.orders.get(oid)
        if rec is None:
            self.missing_reference["F"] += 1
            return
        s, p, cur = rec
        lv = self.levels[s].get(p)
        if lv is None or oid not in lv:
            self.missing_reference["F_level"] += 1
            return
        left = lv[oid] - size
        if left > 0:
            lv[oid] = left
            self.orders[oid] = (s, p, left)
        else:
            del lv[oid]
            self.orders.pop(oid, None)
            if not lv:
                del self.levels[s][p]

    def clear(self) -> None:
        self.levels = {"B": {}, "A": {}}
        self.orders = {}
        self.clears += 1

    def side_state(self, side: str) -> dict[str, Any]:
        lv = self.levels[side]
        if not lv:
            return {"best": None, "depth": 0, "orders": 0, "levels": 0, "touch_ids": []}
        best = max(lv) if side == "B" else min(lv)
        return {"best": best, "depth": sum(sum(q.values()) for q in lv.values()), "orders": sum(len(q) for q in lv.values()),
                "levels": len(lv), "touch_ids": list(lv[best].keys())}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    store = databento.DBNStore.from_file(SOURCE)
    book = Book()
    group: list[Any] = []
    gi = 0
    records = 0
    actions = Counter()
    cmp_counts = Counter()
    diffs: list[dict[str, Any]] = []
    per_group: list[dict[str, Any]] = []
    member = MEMBER.open("rb")
    groups_closed = 0
    action_of = {}

    def close(msgs: list[Any]) -> None:
        nonlocal gi, groups_closed
        line = member.readline()
        row = json.loads(line) if line else None
        state = {s: book.side_state(s) for s in ("B", "A")}
        rec = {"group_index": gi, "components": len(msgs), "recv_ns": int(msgs[-1].ts_recv), "action_string": "".join(action_of.get(m.action, m.action if isinstance(m.action, str) else chr(m.action)) for m in msgs)[:64]}
        if row is not None:
            bf = row["book_full"]
            delivered = {
                "B": {"best": (int(bf["bid_levels_full"][0]["price_raw"]) if bf.get("bid_levels_full") else None), "depth": int(bf["bid_depth_full"]), "orders": int(bf["bid_order_count_full"]),
                      "levels": int(bf["bid_price_level_count_full"]), "touch_ids": [int(o["order_id"]) for o in (bf["bid_levels_full"][0]["fifo_queue"] if bf.get("bid_levels_full") else [])]},
                "A": {"best": (int(bf["ask_levels_full"][0]["price_raw"]) if bf.get("ask_levels_full") else None), "depth": int(bf["ask_depth_full"]), "orders": int(bf["ask_order_count_full"]),
                      "levels": int(bf["ask_price_level_count_full"]), "touch_ids": [int(o["order_id"]) for o in (bf["ask_levels_full"][0]["fifo_queue"] if bf.get("ask_levels_full") else [])]},
            }
            rec["group_index_delivered"] = int(row["group_index"])
            rec["components_delivered"] = int(row["component_count"])
            cmp_counts["groups_compared"] += 1
            if rec["components"] != rec["components_delivered"]:
                cmp_counts["component_count_mismatch"] += 1
            for s in ("B", "A"):
                for field in ("best", "depth", "orders", "levels"):
                    same = state[s][field] == delivered[s][field]
                    cmp_counts[f"{field}_{s}_" + ("agree" if same else "differ")] += 1
                    if not same and len(diffs) < 40:
                        diffs.append({"group_index": gi, "side": s, "field": field, "mine": state[s][field], "delivered": delivered[s][field], "action_string": rec["action_string"]})
                same_q = state[s]["touch_ids"] == delivered[s]["touch_ids"]
                cmp_counts[f"touch_fifo_{s}_" + ("agree" if same_q else "differ")] += 1
                if not same_q and len(diffs) < 40:
                    diffs.append({"group_index": gi, "side": s, "field": "touch_fifo", "mine": state[s]["touch_ids"][:6], "delivered": delivered[s]["touch_ids"][:6], "action_string": rec["action_string"]})
        if gi < 5 or gi % 5000 == 0:
            per_group.append({**rec, "mine": state})
        gi += 1
        groups_closed += 1

    for msg in store:
        if not isinstance(msg, databento.MBOMsg):
            continue
        records += 1
        a = msg.action if isinstance(msg.action, str) else chr(msg.action)
        actions[a] += 1
        side = msg.side if isinstance(msg.side, str) else chr(msg.side)
        oid, price, size = int(msg.order_id), int(msg.price), int(msg.size)
        snapshot = bool(int(msg.flags) & (1 << 5))
        if a == "A":
            book.add(oid, side, price, size, snapshot)
        elif a == "C":
            book.cancel(oid, side, price, size)
        elif a == "M":
            book.modify(oid, side, price, size)
        elif a == "F":
            book.fill(oid, side, size)
        elif a == "R":
            book.clear()
        group.append(msg)
        if int(msg.flags) & F_LAST:
            close(group)
            group = []
        if records % 10000 == 0:
            print(f"{records} records, {groups_closed} groups, compared {cmp_counts['groups_compared']}", flush=True)
    if group:
        close(group)
    member.close()
    out = {"source": str(SOURCE), "records": records, "groups": groups_closed, "actions": dict(actions), "clears": book.clears, "snapshot_adds": book.snapshot_adds,
           "missing_reference": dict(book.missing_reference), "comparison": dict(cmp_counts), "first_disagreements": diffs, "sampled_groups": per_group[:40],
           "rule": "my book: A adds to the back of its level's FIFO, C removes (partial C reduces), M keeps place only when price is unchanged and size does not increase (else it re-joins the back), F consumes from the named order, R clears; comparison is against the delivered book_full AFTER the same group's messages"}
    (OUT / "raw_traversal_reconciliation.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k not in ("first_disagreements", "sampled_groups")}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
