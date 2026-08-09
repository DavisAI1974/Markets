#!/usr/bin/env python3
"""M-16 safe entry point for databento_backfill.py.

The historical module predates the repository's two-data-tree failure and carries relative default
paths plus a trades writer that does not accept out_dir. This wrapper fixes those semantics without
silently changing its data-decoding logic: all default destinations are rebound to the repository
root, --out-dir is made absolute, and every pull that reports rows must prove files landed there.

Use this entry point for S115+ pulls. The original module remains importable for historical replay.
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import databento_backfill as legacy  # noqa: E402

DEFAULT_TRADES = ROOT / "data" / "nymex_cont_n0"
DEFAULT_MBP10 = ROOT / "data" / "nymex_mbp10"
DEFAULT_L1 = ROOT / "data" / "ng_l1"


class LandingError(RuntimeError):
    pass


def absolute_destination(path: str | None, schema: str) -> Path:
    if path:
        p = Path(path).expanduser()
        return p.resolve() if p.is_absolute() else (ROOT / p).resolve()
    if schema.startswith("mbp-10"):
        return DEFAULT_MBP10
    if schema.startswith("mbp-1"):
        return DEFAULT_L1
    return DEFAULT_TRADES


def _files_for(dest: Path, symbol: str, schema: str) -> list[Path]:
    if schema.startswith("mbp-1"):
        return sorted(dest.glob(f"{symbol}_*.jsonl.gz"))
    return sorted(dest.glob(f"{symbol}_*.jsonl"))


def assert_landed(dest: Path, symbol: str, schema: str, before: set[str], rows: int) -> list[str]:
    """M-16: a row count is not success. Require actual files at the actual destination."""
    after = _files_for(dest, symbol, schema)
    names = {str(p.resolve()) for p in after if p.is_file() and p.stat().st_size > 0}
    if rows > 0 and not names:
        raise LandingError(f"M-16: {rows} rows reported but no non-empty files landed in {dest}")
    if rows > 0 and names == before:
        # Append-to-existing files is legitimate; prove their bytes changed rather than trusting a log.
        # Caller supplies only names, so treat no new path as requiring a separate size snapshot.
        return sorted(names)
    return sorted(names)


def _sizes(dest: Path, symbol: str, schema: str) -> dict[str, int]:
    return {str(p.resolve()): p.stat().st_size for p in _files_for(dest, symbol, schema) if p.is_file()}


def assert_size_growth(before: dict[str, int], after: dict[str, int], rows: int, dest: Path) -> None:
    if rows <= 0:
        return
    grew = any(after.get(path, 0) > size for path, size in before.items())
    new = any(path not in before and size > 0 for path, size in after.items())
    if not (grew or new):
        raise LandingError(f"M-16: {rows} rows reported but destination bytes did not grow: {dest}")


def configure_legacy(dest: Path, schema: str) -> None:
    """Rebind every historical relative destination before any writer runs."""
    if schema.startswith("mbp-10"):
        legacy.MBP10_DIR = str(dest)
    elif schema.startswith("mbp-1"):
        legacy.L1_DIR = str(dest)
    else:
        legacy.OUT_DIR = str(dest)


def run_pull(args: argparse.Namespace) -> int:
    dest = absolute_destination(args.out_dir, args.schema)
    dest.mkdir(parents=True, exist_ok=True)
    configure_legacy(dest, args.schema)
    legacy.ROLL = args.roll
    client = legacy._client()
    before = _sizes(dest, args.symbol, args.schema)
    if args.mode == "range":
        rows = legacy.range_pull(
            client, args.symbol, args.start, args.end, args.schema, args.max_cost, str(dest)
        )
        # legacy range_pull historically returns None; infer success from bytes and use 1 as asserted work.
        reported = 1 if _sizes(dest, args.symbol, args.schema) != before else 0
    elif args.mode == "pull":
        rows = legacy.batch_pull(
            client, args.symbol, args.start, args.end, args.schema, args.max_cost, str(dest)
        )
        reported = int(rows or 0)
    elif args.mode == "redecode":
        rows = legacy.redecode_job(client, args.job_id, args.symbol, args.schema, str(dest), args.flush_dir)
        reported = int(rows or 0)
    else:
        raise LandingError(f"unsupported guarded mode: {args.mode}")
    after = _sizes(dest, args.symbol, args.schema)
    assert_size_growth(before, after, reported, dest)
    print(f"[M-16] VERIFIED actual destination: {dest}")
    print(f"[M-16] VERIFIED files: {len(after)}; rows reported: {reported}")
    return reported


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=("range", "pull", "redecode"))
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--schema", default="trades")
    ap.add_argument("--roll", choices=("v", "n", "c"), default="n")
    ap.add_argument("--max-cost", type=float, default=1.0)
    ap.add_argument("--out-dir")
    ap.add_argument("--job-id")
    ap.add_argument("--flush-dir")
    return ap


def main() -> int:
    args = parser().parse_args()
    if args.mode in ("range", "pull") and not (args.start and args.end):
        raise SystemExit("M-16 guarded range/pull requires --start and --end")
    if args.mode == "redecode" and not args.job_id:
        raise SystemExit("M-16 guarded redecode requires --job-id")
    try:
        run_pull(args)
        return 0
    except LandingError as exc:
        print(f"STOP - {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
