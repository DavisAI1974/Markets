"""Per-second tape activity inside each case window, for the liquidity-response view.

For every case of cases-10.json on the session NG_TAG, replays the tape with the audit Book over
[t0-300 s, t0+600 s] and records, per receive second: adds / cancels / modifies / fills by side (counts and
lots), prints (count, lots, buy-aggressor lots, sell-aggressor lots), the touch after the last group close
of the second (bid and ask price, size, order count), 10-level depth by side and the spread. Also keeps
every individual print with its receive clock, cursor, price, size and aggressor side (the trade rows for
the event-sequence view). Writes case-tape-<tag>.json keyed by case t0. Nothing is aggregated beyond the
second, and every second carries its absolute clock.
"""

import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import databento as db

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
from audit_october18_touch_mechanisms import Book, F_LAST, INSTRUMENT  # noqa: E402
from size_one_tape_pass import MEMBERS, detect_oct03, records  # noqa: E402

NS = 1_000_000_000
TICK = 1_000_000
DAY0 = {"oct02": 1696194000, "oct03": 1696280400, "oct17": 1697490000, "oct18": 1697576400}
PRE, POST = 300, 600


def main():
    tag = os.environ.get("NG_TAG", "oct18")
    cases = [c for c in json.load(open(HERE / "cases-10.json")) if c["tag"] == tag]
    if not cases:
        return
    day0 = DAY0[tag]
    windows = [(c["t0"] - PRE, c["t0"] + POST, c["t0"]) for c in cases]
    lo_all, hi_all = min(w[0] for w in windows), max(w[1] for w in windows)
    members = MEMBERS[tag] or detect_oct03([])  # cursor offsets do not matter here; cursors are reported as record indices plus offset
    if tag == "oct03":
        members = [("20231002", -808453, MEMBERS["oct18"][0][2]), ("20231003", 4889, MEMBERS["oct18"][0][2])]
    book, pending = Book(), Counter()
    per_sec = {w[2]: defaultdict(lambda: Counter()) for w in windows}
    touches = {w[2]: {} for w in windows}
    prints = {w[2]: [] for w in windows}
    last_sec = None
    for cursor, r in records(members):
        if r.instrument_id != INSTRUMENT:
            continue
        sec = r.ts_recv // NS - day0
        if sec > hi_all + 1:
            break
        act, side = str(r.action), str(r.side)
        active = [w[2] for w in windows if w[0] <= sec <= w[1]]
        if active:
            key = None
            if act == "A":
                key = f"add_{side}"
            elif act == "C":
                key = f"cancel_{side}"
            elif act == "M":
                key = f"modify_{side}"
            elif act == "F":
                key = f"fill_{side}"
            elif act == "T":
                key = "print"
            for t0 in active:
                if key:
                    per_sec[t0][sec][key] += 1
                    per_sec[t0][sec][key + "_lots"] += r.size
                if act == "T":
                    bids = [p for (s, p), o in book.levels.items() if s == "B" and o]
                    asks = [p for (s, p), o in book.levels.items() if s == "A" and o]
                    aggr = None
                    if bids and asks and r.price > 0:
                        mid = 0.5 * (max(bids) + min(asks))
                        aggr = "buy" if r.price > mid else "sell" if r.price < mid else "mid"
                    per_sec[t0][sec][f"aggr_{aggr}_lots"] += r.size
                    prints[t0].append(dict(ts_recv_ns=r.ts_recv, cursor=cursor, sec=sec, epoch_s=day0 + sec, price_raw=r.price, size=r.size, aggressor=aggr))
        book.apply(r, cursor, pending, None)
        if int(r.flags) & F_LAST:
            pending.clear()
            if active:
                bids = sorted((p for (s, p), o in book.levels.items() if s == "B" and o), reverse=True)
                asks = sorted(p for (s, p), o in book.levels.items() if s == "A" and o)
                if bids and asks:
                    snap = dict(bid=[bids[0], sum(book.level("B", bids[0]).values()), len(book.level("B", bids[0]))],
                                ask=[asks[0], sum(book.level("A", asks[0]).values()), len(book.level("A", asks[0]))],
                                bid_depth10=sum(sum(book.levels[("B", p)].values()) for p in bids[:10]),
                                ask_depth10=sum(sum(book.levels[("A", p)].values()) for p in asks[:10]),
                                spread_ticks=(asks[0] - bids[0]) // TICK, cursor=cursor, ts_recv_ns=r.ts_recv)
                    for t0 in active:
                        touches[t0][sec] = snap
    out = {}
    for c in cases:
        t0 = c["t0"]
        out[str(t0)] = dict(case=c, window=[t0 - PRE, t0 + POST], day0=day0,
                            per_second={str(s): dict(v) for s, v in sorted(per_sec[t0].items())},
                            touch_by_second={str(s): v for s, v in sorted(touches[t0].items())},
                            prints=prints[t0])
    (HERE / f"case-tape-{tag}.json").write_text(json.dumps(out) + "\n")
    print(tag, "cases", len(cases), {str(c["t0"]): (len(per_sec[c["t0"]]), len(prints[c["t0"]])) for c in cases})


if __name__ == "__main__":
    main()
