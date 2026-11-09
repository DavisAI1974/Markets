"""Tape-side mechanics for every size-one onset of a session: next displayed level and fill-linked reductions.

For each episode from size_one_from_groups.py, replay the raw tape with the audit Book (fill-to-reduction
linkage by order and price) and record, at the onset group's close, the next displayed level on the onset
side (price, size), the touch order count (checked against the export), and the onset group's mutations at
the original price on that side: additions, reductions with a fill link (linked_display_reduction > 0),
reductions without one, and reprices in or out. These are the operands of the October 18 ledger's flow and
book arms (onset_next_level, onset_touch.additions / reductions). Validated on October 18 against the
ledger's 1,012 episodes. Export cursors are record indices plus a per-member offset; the offset is detected
from the first groups (the close record of every completed group carries F_LAST). No trade cost.
"""

import gzip
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import databento as db

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
from export_paths import SESSIONS  # noqa: E402
from audit_october18_touch_mechanisms import Book, F_LAST, INSTRUMENT, TAPE, TAPE_FILE, git_blob  # noqa: E402
import exhaustion_clock_reanalysis_oct18 as X  # noqa: E402

# export cursor = record index + offset, per member (day, offset, commit); October 18 from the audit script,
# single-member days at 0, October 3 (warm-up on the October 2 member) detected below.
MEMBERS = {
    "oct18": [("20231017", -841601, TAPE), ("20231018", 17375, TAPE)],
    "oct17": [("20231017", 0, TAPE)],
    "oct02": [("20231002", 0, TAPE)],
    "oct03": None,
}


def records(members):
    for day, off, commit in members:
        path = TAPE_FILE.replace("20231018", day)
        for i, r in enumerate(db.DBNStore.from_bytes(git_blob(commit, path))):
            yield i + off, r


def detect_oct03(close_cursors):
    """October 3's export starts at 21:00 UTC October 2 inside the October 2 member (cursor 0 = the first record at or
    after the session open there) and continues into the October 3 member, exactly as October 18's cursor 0 is the first
    record at or after 21:00 UTC October 17 in the October 17 member (offset -841601, then +17375 for the 18 member)."""
    open_ns = 1696280400 * 1_000_000_000
    m2 = list(db.DBNStore.from_bytes(git_blob(TAPE, TAPE_FILE.replace("20231018", "20231002"))))
    k = next(i for i, r in enumerate(m2) if r.ts_recv >= open_ns)
    members = [("20231002", -k, TAPE), ("20231003", len(m2) - k, TAPE)]
    m3 = list(db.DBNStore.from_bytes(git_blob(TAPE, TAPE_FILE.replace("20231018", "20231003"))))
    want = sorted(close_cursors)
    hits = 0
    for c in want[:400] + want[-400:]:
        if c + k < len(m2):
            hits += bool(int(m2[c + k].flags) & F_LAST)
        else:
            hits += bool(int(m3[c - (len(m2) - k)].flags) & F_LAST)
    print("october 3 members", [(d, o) for d, o, _ in members], "F_LAST hits", hits, "of 800")
    if hits < 800:
        raise SystemExit("october 3 cursor mapping failed")
    return members


def main():
    tag = os.environ.get("NG_TAG", "oct18")
    eps = [json.loads(l) for l in gzip.open(HERE / f"size-one-episodes-{tag}.jsonl.gz", "rt")]
    members = MEMBERS[tag] or detect_oct03([e["onset_cursor"] for e in eps])
    by_close = defaultdict(list)
    for i, e in enumerate(eps):
        by_close[e["onset_cursor"]].append(i)
    starts = {}
    for i, e in enumerate(eps):
        starts.setdefault(e["onset_first_cursor"], []).append(i)
    book, pending = Book(), Counter()
    capture = None
    active = []           # episode indices whose onset group is open
    out = [None] * len(eps)
    seen = 0
    for cursor, r in records(members):
        if r.instrument_id != INSTRUMENT:
            continue
        if cursor in starts:
            active = starts[cursor]; capture = []
        book.apply(r, cursor, pending, capture)
        if int(r.flags) & F_LAST:
            if cursor in by_close:
                for i in by_close[cursor]:
                    e = eps[i]; side = e["side"]; p0 = e["original_price_raw"]
                    prices = sorted((pr for (s, pr), o in book.levels.items() if s == side and o), reverse=side == "B")
                    best = prices[0] if prices else None
                    lvl = book.level(side, best) if best is not None else {}
                    nxt = [prices[1], sum(book.level(side, prices[1]).values())] if len(prices) > 1 else None
                    adds = reds_linked = reds_unlinked = reprice_in = reprice_out = 0
                    for m in (capture or []):
                        b, a = m["before"], m["after"]
                        at_before = b is not None and b[0] == side and b[1] == p0
                        at_after = a is not None and a[0] == side and a[1] == p0
                        if m["action"] == "A" and at_after:
                            adds += 1
                        elif at_before and not at_after:
                            if a is None:
                                (reds_linked if m["linked_display_reduction"] else reds_unlinked).__class__  # no-op for clarity
                                if m["linked_display_reduction"]:
                                    reds_linked += 1
                                else:
                                    reds_unlinked += 1
                            else:
                                reprice_out += 1
                        elif at_before and at_after and a[2] < b[2]:
                            if m["linked_display_reduction"]:
                                reds_linked += 1
                            else:
                                reds_unlinked += 1
                        elif at_after and not at_before and m["action"] == "M":
                            reprice_in += 1
                    out[i] = dict(touch_check=[best, sum(lvl.values()), len(lvl)], next_level=nxt, additions=adds, reductions_fill_linked=reds_linked,
                                  reductions_unlinked=reds_unlinked, reprice_in=reprice_in, reprice_out=reprice_out, mutations_in_group=len(capture or []))
                    seen += 1
                capture = None; active = []
            pending.clear()
    missing = sum(1 for o in out if o is None)
    with gzip.open(HERE / f"size-one-tape-{tag}.jsonl.gz", "wt") as f:
        for e, o in zip(eps, out):
            f.write(json.dumps(dict(onset_group=e["onset_group"], side=e["side"], onset_cursor=e["onset_cursor"], **(o or {})) if o else dict(onset_group=e["onset_group"], side=e["side"], missing=True)) + "\n")
    summary = dict(session=tag, members=[(d, o) for d, o, _ in members], episodes=len(eps), captured=seen, missing=missing,
                   touch_check_mismatch=sum(1 for e, o in zip(eps, out) if o and o["touch_check"] != [e["original_price_raw"], 1, 1]),
                   next_level_missing=sum(1 for o in out if o and o["next_level"] is None),
                   flow_classes=dict(Counter(("fill_linked" if o["reductions_fill_linked"] else "unlinked" if o["reductions_unlinked"] else "no_reduction") for o in out if o)))
    if tag == "oct18":
        led = {(r["onset_group"], r["side"]): r for r in (json.loads(l) for l in gzip.open(HERE.parent / "october18-size-one-mechanisms.jsonl.gz", "rt"))}
        nl_agree = fl_agree = n = 0
        dis = Counter()
        for e, o in zip(eps, out):
            k = (e["onset_group"], e["side"])
            if k not in led or not o:
                continue
            n += 1
            L = led[k]
            nl_agree += (o["next_level"] == L["onset_next_level"])
            lr = L["onset_touch"]["reductions"]
            lclass = "fill_linked" if "FILL_LINKED" in lr else "unlinked" if any(k2.startswith("UNLINKED") for k2 in lr) else "no_reduction"
            mclass = "fill_linked" if o["reductions_fill_linked"] else "unlinked" if o["reductions_unlinked"] else "no_reduction"
            fl_agree += (lclass == mclass)
            if lclass != mclass:
                dis[f"{lclass}->{mclass}"] += 1
        summary["validation_oct18"] = dict(ledger_matched=n, next_level_agree=nl_agree, flow_class_agree=fl_agree, flow_disagreements=dict(dis))
    (HERE / f"size-one-tape-{tag}-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
