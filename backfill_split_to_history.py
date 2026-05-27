"""
backfill_split_to_history.py

Splits single-file backfill bin output (the {ts_str: bin_dict} JSON format
written by backfill_coinbase_spot.py / backfill_kraken_spot.py /
backfill_binance_vision.py) into the date-partitioned JSONL-per-line format
that markets_bar_loader.py reads from live_data_history/<YYYY-MM-DD>/.

Why this exists: the backfill scripts write the legacy live_data/ snapshot
format. The live collectors write the durable JSONL archive format. Without
this splitter, backfilled history never reaches the archive that refrag
adapters and markets_bar_loader actually consume.

Merge semantics: JSONL bins already in live_data_history ALWAYS win. They
come from the live collector with richer fields (explicit bid/ask, qty,
last_aggressor). Backfill bins only fill timestamps the archive doesn't
already have.

Idempotent: safe to re-run. Re-runs are no-ops if backfill source hasn't
changed.

Usage:
    # Split everything in a staging dir:
    python backfill_split_to_history.py --staging-dir backfill_staging

    # Or named files:
    python backfill_split_to_history.py --files btc_coinbase_bins.json eth_coinbase_bins.json

    # Dry run first (recommended):
    python backfill_split_to_history.py --staging-dir backfill_staging --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

MARKETS_ROOT = Path(r"E:\Markets")
HISTORY_ROOT = MARKETS_ROOT / "live_data_history"


def parse_asset_venue_from_filename(name: str) -> tuple[str, str] | None:
    """
    Given a filename like btc_coinbase_bins.json or btc_bybit_perp_bins.json,
    return ("btc", "coinbase") or ("btc", "bybit_perp"). The output is the
    file STEM that markets_bar_loader expects — preserves the "_perp" suffix
    for venues that are perp markets.
    """
    stem = name
    if stem.endswith(".json"):
        stem = stem[: -len(".json")]
    if stem.endswith(".jsonl"):
        stem = stem[: -len(".jsonl")]
    if not stem.endswith("_bins"):
        return None
    stem = stem[: -len("_bins")]
    parts = stem.split("_", 1)
    if len(parts) != 2:
        return None
    asset, venue_stem = parts
    return asset, venue_stem


def utc_date_of(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def load_existing_jsonl_ts(path: Path) -> set[float]:
    """Set of ts already present in a JSONL archive file (skip-list for dedup)."""
    out: set[float] = set()
    if not path.exists():
        return out
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                bar = json.loads(line)
            except json.JSONDecodeError:
                continue
            try:
                out.add(float(bar.get("ts")))
            except (TypeError, ValueError):
                continue
    return out


def split_one_file(
    src_path: Path,
    *,
    dry_run: bool,
    history_root: Path,
) -> dict:
    """
    Read one backfill JSON file, split bins by UTC date, append novel bins
    to live_data_history/<date>/<stem>_bins.jsonl. Returns a per-file report.
    """
    report: dict = {
        "src": str(src_path),
        "ok": False,
        "asset_venue": None,
        "src_bins_total": 0,
        "by_date": {},
        "errors": [],
    }

    av = parse_asset_venue_from_filename(src_path.name)
    if av is None:
        report["errors"].append("could not parse asset_venue from filename")
        return report
    asset, venue_stem = av
    report["asset_venue"] = f"{asset}_{venue_stem}"

    try:
        with src_path.open() as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        report["errors"].append(f"could not load source: {e}")
        return report

    if not isinstance(raw, dict):
        report["errors"].append(f"source is not a dict (got {type(raw).__name__})")
        return report

    bins_by_date: dict[str, list[dict]] = defaultdict(list)
    n_total = 0
    for ts_str, bin_payload in raw.items():
        try:
            ts = float(ts_str)
        except (TypeError, ValueError):
            continue
        if not isinstance(bin_payload, dict):
            continue
        if ts <= 0:
            continue
        n_total += 1
        # Ensure the bin payload carries its own ts (live collector writes ts
        # into the bin object; backfill scripts key it in the outer dict).
        payload_out = dict(bin_payload)
        payload_out.setdefault("ts", ts)
        bins_by_date[utc_date_of(ts)].append(payload_out)

    report["src_bins_total"] = n_total

    target_stem = f"{asset}_{venue_stem}"

    for date_str in sorted(bins_by_date.keys()):
        bins = bins_by_date[date_str]
        bins.sort(key=lambda b: float(b["ts"]))
        date_dir = history_root / date_str
        target_path = date_dir / f"{target_stem}_bins.jsonl"

        existing_ts = load_existing_jsonl_ts(target_path)
        novel = [b for b in bins if float(b["ts"]) not in existing_ts]

        report["by_date"][date_str] = {
            "src_bins_for_date": len(bins),
            "existing_ts_in_archive": len(existing_ts),
            "novel_bins_written": len(novel),
            "target": str(target_path),
        }

        if dry_run or not novel:
            continue

        date_dir.mkdir(parents=True, exist_ok=True)
        with target_path.open("a") as f:
            for b in novel:
                f.write(json.dumps(b, separators=(",", ":")) + "\n")

    report["ok"] = True
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--staging-dir", type=Path,
                   help="directory of *_bins.json backfill outputs to split")
    g.add_argument("--files", type=Path, nargs="+",
                   help="explicit files to split")
    ap.add_argument("--history-root", type=Path, default=HISTORY_ROOT,
                    help="destination root (default: %(default)s)")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be written without writing")
    ap.add_argument("--report-path", type=Path, default=None,
                    help="write JSON report to this path in addition to stdout")
    args = ap.parse_args()

    if args.staging_dir is not None:
        if not args.staging_dir.exists():
            print(f"staging dir does not exist: {args.staging_dir}", file=sys.stderr)
            return 2
        sources = sorted(p for p in args.staging_dir.iterdir()
                         if p.is_file() and p.name.endswith("_bins.json"))
    else:
        sources = list(args.files)

    if not sources:
        print("no source files found", file=sys.stderr)
        return 1

    print(f"splitting {len(sources)} file(s) "
          f"{'(DRY RUN)' if args.dry_run else ''} -> {args.history_root}")

    all_reports = []
    total_novel = 0
    for src in sources:
        r = split_one_file(src, dry_run=args.dry_run, history_root=args.history_root)
        all_reports.append(r)
        file_novel = sum(d["novel_bins_written"] for d in r["by_date"].values())
        total_novel += file_novel
        status = "ok" if r["ok"] else "FAIL"
        print(f"  [{status}] {src.name}: {r['src_bins_total']} src bins, "
              f"{len(r['by_date'])} dates, {file_novel} novel bins written")
        if r["errors"]:
            for e in r["errors"]:
                print(f"      error: {e}")

    print(f"\ntotal novel bins written: {total_novel}"
          f"{' (dry-run, nothing written)' if args.dry_run else ''}")

    if args.report_path:
        with args.report_path.open("w") as f:
            json.dump({"reports": all_reports, "total_novel": total_novel}, f, indent=2)
        print(f"report saved: {args.report_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
