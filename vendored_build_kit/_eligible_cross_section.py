"""Pre-filter a bucket file to entries with REAL bar coverage >= min_returns,
then take an evenly-spaced cross-section of N entries from the eligible pool.

Why: the adapter skips entries with n_log_returns < window_size (default 192).
On lose-side cross-sections, that was 63% of samples — leaving us with the
"too short" tail and no way to backfill (real data only, no synthesis).

Solution: pre-filter the source bucket to only entries that we KNOW will
process through the pipeline (entries with >= min_returns log_returns in the
real bar archive), then cross-section sample from that pool.

Output mirrors the structure of _split_lose_bucket.py: same JSON schema as
the source, with split_metadata describing the eligible filter and the
cross-section indices used.

Usage:
    python E:/Markets/_eligible_cross_section.py \
        --input  <bucket>.json \
        --output <bucket>.eligible.crossN.json \
        --target-size 100 \
        --min-returns 192
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "refrag" / "adapters"))
from markets_bar_loader import load_closes, slice_closes, closes_to_log_returns  # type: ignore


def _bucket_entries(bucket_obj):
    if isinstance(bucket_obj, list):
        return bucket_obj
    return bucket_obj.get("entries", [])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--target-size", type=int, required=True,
                    help="Number of entries to keep.")
    ap.add_argument("--min-returns", type=int, default=192,
                    help="Eligibility threshold; entry must yield >= this many "
                         "log_returns in its [entry_ts, exit_ts] window.")
    ap.add_argument("--mode", choices=("cross-section", "top", "bottom"),
                    default="cross-section",
                    help="cross-section: evenly-spaced sample from eligible pool. "
                         "top: highest net_bps (best winners). "
                         "bottom: lowest net_bps (worst losers).")
    ap.add_argument("--pre-entry", action="store_true",
                    help="Pre-entry validation mode: eligibility window becomes "
                         "[entry_ts - pre_entry_minutes*60, entry_ts] instead of "
                         "[entry_ts, exit_ts]. Used to test whether the dipole "
                         "predicts on bars BEFORE the trade fires (no exit data leak).")
    ap.add_argument("--pre-entry-minutes", type=int, default=30,
                    help="Length in minutes of the pre-entry window ending at entry_ts. "
                         "Default 30 (per 2026-05-27 handoff TL;DR). At 1-sec bars this "
                         "gives ~1800 potential closes per trade, well above the "
                         "min-returns threshold for any densely covered window.")
    args = ap.parse_args()

    src_obj = json.load(args.input.open())
    entries = _bucket_entries(src_obj)
    n_src = len(entries)
    if n_src == 0:
        print(f"Source has 0 entries: {args.input}")
        return 1

    # Group by (asset, venue) so bar archive is loaded once per group.
    groups: dict[tuple[str, str], list[tuple[int, dict]]] = {}
    for i, e in enumerate(entries):
        key = (e.get("asset"), e.get("venue"))
        groups.setdefault(key, []).append((i, e))

    eligible_indices: list[int] = []
    per_entry_reason: dict[int, str] = {}
    n_no_coverage = 0
    n_too_short = 0
    n_eligible = 0

    # Match adapter's bar-loading: ±6h pad so entries near the boundaries
    # don't get falsely rejected for missing bars at exactly the edge.
    BUFFER_S = 6 * 3600
    pre_entry_s = int(args.pre_entry_minutes) * 60 if args.pre_entry else 0
    for (asset, venue), group_entries in groups.items():
        if args.pre_entry:
            ts_lo = min(float(e["entry_ts_utc"]) for _, e in group_entries) - pre_entry_s
            ts_hi = max(float(e["entry_ts_utc"]) for _, e in group_entries)
        else:
            ts_lo = min(float(e["entry_ts_utc"]) for _, e in group_entries)
            ts_hi = max(float(e["entry_ts_utc"]) + float(e.get("horizon_minutes") or 0) * 60.0
                        for _, e in group_entries)
        closes = load_closes(
            asset=asset, venue=venue,
            t_min=ts_lo - BUFFER_S,
            t_max=ts_hi + BUFFER_S,
        )
        if not closes:
            print(f"  {asset}/{venue}: NO BARS for window [{ts_lo}, {ts_hi}]")
            for idx, _ in group_entries:
                per_entry_reason[idx] = "no_bars_for_group"
                n_no_coverage += 1
            continue

        ts_min_bars, ts_max_bars = closes[0].ts, closes[-1].ts
        print(f"  {asset}/{venue}: {len(closes)} bars in archive, "
              f"checking {len(group_entries)} entries (min_returns={args.min_returns})")
        for idx, w in group_entries:
            entry_ts = float(w["entry_ts_utc"])
            if args.pre_entry:
                window_lo = entry_ts - pre_entry_s
                window_hi = entry_ts
            else:
                horizon_min = float(w.get("horizon_minutes") or 0)
                window_lo = entry_ts
                window_hi = entry_ts + horizon_min * 60.0
            if window_lo < ts_min_bars or window_hi > ts_max_bars:
                per_entry_reason[idx] = "no_coverage"
                n_no_coverage += 1
                continue
            sliced = slice_closes(closes, window_lo, window_hi)
            log_returns = closes_to_log_returns(sliced)
            if len(log_returns) < args.min_returns:
                per_entry_reason[idx] = f"too_short:{len(log_returns)}"
                n_too_short += 1
                continue
            per_entry_reason[idx] = f"eligible:{len(log_returns)}"
            eligible_indices.append(idx)
            n_eligible += 1

    eligible_indices.sort()
    print()
    print(f"Source         : {n_src} entries")
    print(f"  no_coverage  : {n_no_coverage}")
    print(f"  too_short    : {n_too_short}")
    print(f"  eligible     : {n_eligible}")

    if n_eligible == 0:
        print("ABORT: no eligible entries.")
        return 2

    target_n = args.target_size
    if target_n > n_eligible:
        print(f"  target_size {target_n} > eligible {n_eligible} -> using all eligible")
        target_n = n_eligible

    if args.mode == "top":
        # Highest net_bps first (best winners).
        ranked = sorted(eligible_indices,
                        key=lambda i: float(entries[i].get("net_bps") or 0.0),
                        reverse=True)
        picked_idx = sorted(ranked[:target_n])
    elif args.mode == "bottom":
        # Lowest (most negative) net_bps first (worst losers).
        ranked = sorted(eligible_indices,
                        key=lambda i: float(entries[i].get("net_bps") or 0.0))
        picked_idx = sorted(ranked[:target_n])
    else:
        # Evenly-spaced cross-section of `target_n` indices from the eligible pool.
        pick_positions = [round(i * (n_eligible - 1) / (target_n - 1)) for i in range(target_n)] \
            if target_n > 1 else [0]
        pick_positions = sorted(set(pick_positions))
        picked_idx = [eligible_indices[p] for p in pick_positions]

    out_obj = copy.deepcopy(src_obj) if isinstance(src_obj, dict) else {"entries": list(src_obj)}
    out_obj["entries"] = [entries[i] for i in picked_idx]
    out_obj.setdefault("split_metadata", {}).update({
        "slice": f"eligible {args.mode} ({len(picked_idx)} entries from {n_eligible} eligible / {n_src} source)",
        "min_returns_threshold": args.min_returns,
        "n_source": n_src,
        "n_eligible": n_eligible,
        "n_no_coverage": n_no_coverage,
        "n_too_short": n_too_short,
        "picked_source_indices": picked_idx,
        "window_mode": "pre-entry" if args.pre_entry else "post-hoc",
        "pre_entry_minutes": int(args.pre_entry_minutes) if args.pre_entry else None,
    })
    json.dump(out_obj, args.output.open("w"), indent=2)
    print(f"Wrote {len(picked_idx)} entries -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
