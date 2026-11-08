"""Four-arm comparison on the 1,012 October 18 size-one onset episodes.

Inputs: the per-episode mechanism ledger (october18-size-one-mechanisms.jsonl.gz), which
records, as of the onset close, the onset actions at the standing price, the surviving
order's refresh history, the prior touch (price, size, order count) and the next displayed
level, plus the first end and whether it was visible by the assumed 1 ms entry.

Everything used as a predictor is available at the onset close. The outcome is the first
end (retreat, same-price recovery, improvement). Episodes whose end was already visible by
the entry are reported separately from those still open at entry.

  baseline   side and how the one-lot best arose (new best price / standing best shrank)
  + flow     onset reduction at the standing price linked to a fill (yes / no / no reduction)
  + book     displayed size at the next level at onset (below 10 / 10 or more) and the
             order count at the touch before the onset (2 or fewer / more)
  + both     the cross
"""

import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
LEDGER = HERE.parent / "october18-size-one-mechanisms.jsonl.gz"


def main():
    rows = [json.loads(line) for line in gzip.open(LEDGER, "rt", encoding="utf-8")]
    for r in rows:
        red = r["onset_touch"]["reductions"]
        r["flow"] = ("fill_linked" if red.get("FILL_LINKED") else "unlinked_reduction" if red else "no_reduction")
        nxt = r["onset_next_level"]
        r["next_size"] = nxt[1] if nxt else None
        r["next_gap_ticks"] = abs(r["original_price_raw"] - nxt[0]) // 1_000_000 if nxt else None
        r["book_next"] = "next_lt10" if nxt and nxt[1] < 10 else "next_ge10" if nxt else "no_next"
        pt = r["prior_touch"]
        r["prior_orders"] = pt[2] if pt else None
        r["book_prior_orders"] = "prior_orders_le2" if pt and pt[2] <= 2 else "prior_orders_gt2" if pt else "no_prior"
        surv = r["onset_orders"][0] if r["onset_orders"] else None
        r["survivor_refreshed_before"] = bool(surv and surv["last_unchanged_display_fill"])
        r["retreat"] = r["outcome"] == "RETREATED"
        r["after_entry"] = r["end_vs_entry"] == "AFTER_ENTRY"
        r["time_to_end_ms"] = (r["end_ns"] - r["onset_ns"]) / 1e6

    def cell(events):
        n = len(events)
        ret = sum(1 for e in events if e["retreat"])
        open_at_entry = [e for e in events if e["after_entry"]]
        return dict(episodes=n, retreats=ret, recoveries=sum(1 for e in events if e["outcome"] == "SIZE_RECOVERED_AT_SAME_PRICE"),
                    improved=sum(1 for e in events if e["outcome"] == "IMPROVED"),
                    still_open_at_entry=len(open_at_entry), retreats_after_entry=sum(1 for e in open_at_entry if e["retreat"]),
                    recoveries_after_entry=sum(1 for e in open_at_entry if e["outcome"] == "SIZE_RECOVERED_AT_SAME_PRICE"),
                    median_ms_to_first_end=median(e["time_to_end_ms"] for e in events) if events else None)

    def table(keyfn):
        groups = defaultdict(list)
        for r in rows:
            groups[keyfn(r)].append(r)
        return {("|".join(k) if isinstance(k, tuple) else k): cell(v) for k, v in sorted(groups.items())}

    summary = dict(
        episodes=len(rows),
        flow_counts=Counter(r["flow"] for r in rows), next_size_quantiles=dict(
            min=min(r["next_size"] for r in rows if r["next_size"] is not None),
            median=median(r["next_size"] for r in rows if r["next_size"] is not None),
            max=max(r["next_size"] for r in rows if r["next_size"] is not None)),
        next_gap_ticks=Counter(r["next_gap_ticks"] for r in rows),
        baseline=table(lambda r: (r["side"], r["onset"])),
        baseline_plus_flow=table(lambda r: (r["side"], r["onset"], r["flow"])),
        baseline_plus_book_next=table(lambda r: (r["side"], r["onset"], r["book_next"])),
        baseline_plus_book_prior_orders=table(lambda r: (r["side"], r["onset"], r["book_prior_orders"])),
        baseline_plus_both=table(lambda r: (r["side"], r["onset"], r["flow"], r["book_next"])),
        standing_only_both_prior_orders=table(lambda r: (r["side"], r["flow"], r["book_prior_orders"]) if r["onset"] == "STANDING_BEST_SHRANK" else ("new_best",)),
        survivor_refresh=table(lambda r: (r["side"], r["onset"], "refreshed_before" if r["survivor_refreshed_before"] else "no_recorded_refresh")),
        recorded_t_vs_fill_link=table(lambda r: (r["side"], r["onset"], f"T={r['recorded_t']}", r["flow"])),
        note="All predictors are as of the onset close. Retreats among episodes still open at the assumed 1 ms entry are the "
             "actionable subset; the all-episode counts describe the mechanism.",
    )
    (HERE / "size-one-four-arm-summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    for name in ("baseline", "baseline_plus_flow", "baseline_plus_book_next", "baseline_plus_book_prior_orders",
                 "baseline_plus_both", "standing_only_both_prior_orders", "survivor_refresh", "recorded_t_vs_fill_link"):
        print(f"\n== {name}")
        for k, v in summary[name].items():
            print(f"  {k:<60} n={v['episodes']:>3} ret={v['retreats']:>3} rec={v['recoveries']:>3} | open@entry={v['still_open_at_entry']:>3} ret_after={v['retreats_after_entry']:>3} rec_after={v['recoveries_after_entry']:>3} med_ms={v['median_ms_to_first_end']:.1f}")


if __name__ == "__main__":
    main()
