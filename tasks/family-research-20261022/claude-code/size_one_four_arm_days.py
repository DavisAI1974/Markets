"""Size-one four arms on every onset of a session, mirroring size_one_four_arm.py (October 18, 1,012 episodes).

Population: every size-one onset derived from the group export (size_one_from_groups.py), with the tape
mechanics from size_one_tape_pass.py. Predictors are all as of the onset close:
  baseline   side x how the one-lot best arose (NEW_BEST / STANDING_BEST_SHRANK)
  + flow     reduction at the standing price in the onset group: fill-linked / unlinked / none
  + book     next displayed level size (< 10 / >= 10) and prior touch order count (<= 2 / > 2)
  + both     the cross
Outcome: the first end (RETREATED vs SIZE_RECOVERED_AT_SAME_PRICE vs IMPROVED), with the episodes still
open at the assumed 1 ms entry reported separately (the actionable subset). Cells reported for the whole
session, the 13:00 UTC hour, and on October 18 the ledger's own window (13:07:15 to 13:19:08 UTC) so the
section 4 numbers can be checked like for like. Retreat share is over all episodes in the cell. No trade cost.
"""

import gzip
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from export_paths import SESSIONS  # noqa: E402

LEDGER_WINDOW = (1697634435798352007, 1697635148507329111)


def cell(ev):
    n = len(ev)
    ret = sum(1 for e in ev if e["outcome"] == "RETREATED")
    rec = sum(1 for e in ev if e["outcome"] == "SIZE_RECOVERED_AT_SAME_PRICE")
    opn = [e for e in ev if e["end_vs_entry"] == "AFTER_ENTRY"]
    ro = sum(1 for e in opn if e["outcome"] == "RETREATED")
    return dict(episodes=n, retreats=ret, recoveries=rec, improved=sum(1 for e in ev if e["outcome"] == "IMPROVED"),
                retreat_share=round(ret / n, 3) if n else None, open_at_entry=len(opn), retreats_after_entry=ro,
                retreat_share_after_entry=round(ro / len(opn), 3) if opn else None,
                median_ms_to_first_end=round(median((e["end_ns"] - e["onset_ns"]) / 1e6 for e in ev if e["end_ns"]), 1) if any(e["end_ns"] for e in ev) else None)


def tables(rows):
    def table(keyfn):
        g = defaultdict(list)
        for r in rows:
            g[keyfn(r)].append(r)
        return {"|".join(k): cell(v) for k, v in sorted(g.items())}
    return dict(
        episodes=len(rows), flow_counts=dict(Counter(r["flow"] for r in rows)),
        baseline=table(lambda r: (r["side"], r["onset"])),
        baseline_plus_flow=table(lambda r: (r["side"], r["onset"], r["flow"])),
        baseline_plus_book_next=table(lambda r: (r["side"], r["onset"], r["book_next"])),
        baseline_plus_book_prior_orders=table(lambda r: (r["side"], r["onset"], r["book_prior_orders"])),
        baseline_plus_both=table(lambda r: (r["side"], r["onset"], r["flow"], r["book_next"])),
        standing_only_both_prior_orders=table(lambda r: (r["side"], r["flow"], r["book_prior_orders"]) if r["onset"] == "STANDING_BEST_SHRANK" else ("new_best",)),
        # side-pooled views for the cross-day table
        flow_pooled=table(lambda r: (r["onset"], r["flow"])),
        book_next_pooled=table(lambda r: (r["onset"], r["book_next"])),
        prior_orders_pooled=table(lambda r: (r["onset"], r["book_prior_orders"])),
    )


def main():
    tag = os.environ.get("NG_TAG", "oct18")
    eps = [json.loads(l) for l in gzip.open(HERE / f"size-one-episodes-{tag}.jsonl.gz", "rt")]
    tape = [json.loads(l) for l in gzip.open(HERE / f"size-one-tape-{tag}.jsonl.gz", "rt")]
    rows = []
    for e, t in zip(eps, tape):
        if t.get("missing") or e["outcome"] == "CENSORED":
            continue
        r = dict(e)
        r["flow"] = "fill_linked" if t["reductions_fill_linked"] else "unlinked_reduction" if t["reductions_unlinked"] else "no_reduction"
        nxt = t["next_level"]
        r["book_next"] = "next_lt10" if nxt and nxt[1] < 10 else "next_ge10" if nxt else "no_next"
        r["next_gap_ticks"] = abs(e["original_price_raw"] - nxt[0]) // 1_000_000 if nxt else None
        pt = e["prior_touch"]
        r["book_prior_orders"] = "prior_orders_le2" if pt[2] <= 2 else "prior_orders_gt2"
        rows.append(r)
    out = dict(session=tag, export_scope=SESSIONS[tag]["export_scope"], all=tables(rows), hour13=tables([r for r in rows if r["hour_utc"] == 13]))
    if tag == "oct18":
        out["ledger_window"] = tables([r for r in rows if LEDGER_WINDOW[0] <= r["onset_ns"] <= LEDGER_WINDOW[1]])
    out["next_gap_ticks"] = dict(Counter(r["next_gap_ticks"] for r in rows))
    (HERE / f"size-one-four-arm-{tag}-summary.json").write_text(json.dumps(out, indent=2, default=str) + "\n")
    with gzip.open(HERE / f"size-one-four-arm-{tag}-rows.jsonl.gz", "wt") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    for scope in ([k for k in ("ledger_window", "hour13", "all") if k in out]):
        T = out[scope]
        print(f"\n==== {tag} {scope}: episodes {T['episodes']} flow {T['flow_counts']}")
        for name in ("baseline", "flow_pooled", "book_next_pooled", "prior_orders_pooled", "baseline_plus_both"):
            print(f"  -- {name}")
            for k, v in T[name].items():
                if v["episodes"] >= 20:
                    print(f"     {k:<58} n={v['episodes']:>5} retreat={v['retreat_share']} | open@entry={v['open_at_entry']:>5} retreat_after={v['retreat_share_after_entry']} med_ms={v['median_ms_to_first_end']}")


if __name__ == "__main__":
    main()
