"""Parallel runner for top20-winner + bottom20-loser extracts across all 12 pairs.

Two phases:
  PHASE A (BUILD ALL):  for each pair, generate top20 win + bottom20 lose
                        list files. Fast (~5s each). If any list build fails,
                        the script aborts BEFORE any pipeline runs are
                        started so issues surface up front.
  PHASE B (RUN ALL):    run ALL 24 buckets (12 pairs x win/lose) in PARALLEL,
                        each bucket as an independent worker. Each worker
                        processes --batch-size trades at a time (default 100),
                        archives the evidence graph to 3 KBs after each batch,
                        clears only THAT bucket's evidence file (never * glob),
                        then resumes with the next batch until no trades remain.

Evidence graph archiving (3-KB policy):
  After each batch, the evidence graph is archived as a snapshot JSON
  (evidence_snapshot_batch_NNN.json with metadata: domain, trade count,
  timestamp) to ALL 3 knowledge bases:
    1. OD KB     — E:\\refrag\\discoveries\\evidence_snapshots\\
    2. Refrag KB — E:\\refrag\\docs\\evidence_snapshots\\
    3. Factory KB — F:\\Factory\\knowledge\\evidence_snapshots\\
  Then the per-domain evidence graph file is cleared (only that bucket's
  file, not a glob) to reset per-trade cost to ~2.3s.

Parallelism:
  Each bucket writes to its own domain evidence file — no cross-bucket
  contamination. index.json tolerates concurrent last-writer-wins races
  (rebuildable via directory scan). --workers controls concurrency
  (default: CPU count, capped at 24).

Pre-entry mode (--pre-entry):
  Filter passes --pre-entry to _eligible_cross_section.py so bucket files
  contain entries with the [entry_ts - 30m, entry_ts] window (no exit leak).
  Adapter call adds --domain-suffix preentry so discoveries land in
  markets_<asset>_<venue>_<side>_<outcome>_preentry/ — isolated from the
  canonical post-hoc dataset. Output dir also forked to keep summary.json
  separate. List filenames carry a .preentry infix.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

PAIRS = [
    "markets_btc_bybit_buy",     "markets_btc_bybit_sell",
    "markets_btc_coinbase_buy",  "markets_btc_coinbase_sell",
    "markets_btc_kraken_buy",    "markets_btc_kraken_sell",
    "markets_eth_bybit_buy",     "markets_eth_bybit_sell",
    "markets_eth_coinbase_buy",  "markets_eth_coinbase_sell",
    "markets_eth_kraken_buy",    "markets_eth_kraken_sell",
]

REFRAG = Path(r"E:\refrag")
MARKETS = Path(r"E:\Markets")
PER_BUCKET = MARKETS / "research" / "strategy_evolution" / "per_bucket_clean"  # S29: deduped fixed-ts pools
LOGS_DIR = MARKETS / "_pipeline_logs"
DEFAULT_TARGET_N = 20
DEFAULT_BATCH_SIZE = 100
PREENTRY_SUFFIX = "preentry"
PREENTRY_MINUTES = 30
PREENTRY_OUT_DIR = MARKETS / "_full_pipeline_winners_preentry"

# 3-KB evidence archive destinations (Greg's policy: 3 identical copies, no exceptions)
EVIDENCE_GRAPHS_DIR = REFRAG / "discoveries" / "evidence_graphs"
KB_SNAPSHOT_DIRS = [
    REFRAG / "discoveries" / "evidence_snapshots",   # OD KB
    REFRAG / "docs" / "evidence_snapshots",           # Refrag KB
    Path(r"F:\Factory\knowledge") / "evidence_snapshots",  # Factory KB
]


def _domain_from_bucket(pair: str, outcome: str, domain_suffix: str) -> str:
    """Derive the evidence graph domain key from pair + outcome + suffix.

    Must match markets_refrag_adapter.winner_domain() output.
    E.g. pair='markets_btc_bybit_buy', outcome='win', suffix='preentry_cs100'
    -> 'markets_btc_bybit_buy_win_preentry_cs100'
    """
    base = f"{pair}_{outcome}"
    if domain_suffix:
        return f"{base}_{domain_suffix}"
    return base


def _archive_evidence_graph(domain: str, batch_num: int) -> bool:
    """Archive the per-domain evidence graph JSON to all 3 KBs, then delete it.

    Returns True if an evidence graph existed and was archived.
    """
    src = EVIDENCE_GRAPHS_DIR / f"{domain}_evidence.json"
    if not src.exists():
        return False

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot_name = f"{domain}_batch_{batch_num:03d}_{ts}.json"

    # Read and wrap with metadata
    try:
        with open(src, "r", encoding="utf-8") as f:
            graph_data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"    WARN: could not read evidence graph {src}: {e}", flush=True)
        return False

    snapshot = {
        "domain": domain,
        "batch_num": batch_num,
        "archived_at": ts,
        "source_path": str(src),
        "n_nodes": len(graph_data.get("nodes", [])),
        "n_edges": len(graph_data.get("edges", [])),
        "evidence_graph": graph_data,
    }

    # Write to all 3 KBs
    for kb_dir in KB_SNAPSHOT_DIRS:
        kb_dir.mkdir(parents=True, exist_ok=True)
        dst = kb_dir / snapshot_name
        try:
            with open(dst, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2)
        except OSError as e:
            print(f"    WARN: failed to write snapshot to {dst}: {e}", flush=True)

    # Clear only THIS bucket's evidence graph (never * glob)
    try:
        src.unlink()
    except OSError:
        pass

    print(f"    archived {snapshot_name} "
          f"({snapshot['n_nodes']} nodes, {snapshot['n_edges']} edges) -> 3 KBs",
          flush=True)
    return True


def _count_summary_results(summary_path: Path) -> int:
    """Read the number of results in a summary.json (0 if missing/corrupt)."""
    if not summary_path.exists():
        return 0
    try:
        with open(summary_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return len(data.get("results", []))
    except (json.JSONDecodeError, OSError):
        return 0


def _count_bucket_entries(bucket_json: Path) -> int:
    """Read the total number of entries in a per-bucket JSON."""
    if not bucket_json.exists():
        return 0
    try:
        with open(bucket_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        return len(data.get("entries", []))
    except (json.JSONDecodeError, OSError):
        return 0


def run_bucket_loop(
    bucket_json: Path,
    outcome: str,
    domain_suffix: str,
    batch_size: int,
    extra_adapter_args: list[str],
    log_dir: Path,
) -> dict:
    """Run one bucket to completion in batch_size-trade chunks.

    After each batch: archive evidence graph to 3 KBs, clear that bucket's
    evidence file, then resume. Continues until no new trades are processed.

    Returns a dict with {pair, outcome, batches, total_processed, errors}.
    """
    # Extract the canonical pair name from the bucket filename
    # e.g. markets_btc_bybit_buy_win.preentry.cross100.json -> markets_btc_bybit_buy
    m = re.match(r"^(markets_\w+?_\w+?_\w+?_(?:buy|sell))_(?:win|lose)", bucket_json.stem)
    if m:
        pair = m.group(1)
    else:
        pair = bucket_json.stem.split("_win")[0].split("_lose")[0]

    domain = _domain_from_bucket(pair, outcome, domain_suffix)
    total_entries = _count_bucket_entries(bucket_json)

    # Each bucket gets its own out-dir to avoid summary.json races when
    # running in parallel. Per-bucket dir: <base_out_dir>/<domain>/
    base_out_dir = None
    for i, arg in enumerate(extra_adapter_args):
        if arg == "--out-dir" and i + 1 < len(extra_adapter_args):
            base_out_dir = Path(extra_adapter_args[i + 1])
            break
    if base_out_dir is None:
        base_out_dir = MARKETS / "_full_pipeline_winners"
    bucket_out_dir = base_out_dir / domain
    bucket_out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = bucket_out_dir / "summary.json"

    # Override --out-dir in the adapter args for this bucket
    bucket_adapter_args = list(extra_adapter_args)
    replaced = False
    for i, arg in enumerate(bucket_adapter_args):
        if arg == "--out-dir" and i + 1 < len(bucket_adapter_args):
            bucket_adapter_args[i + 1] = str(bucket_out_dir)
            replaced = True
            break
    if not replaced:
        bucket_adapter_args += ["--out-dir", str(bucket_out_dir)]

    batch_num = 0
    total_new = 0
    errors = 0
    t_start = time.time()

    print(f"  [{pair}_{outcome}] starting: {total_entries} entries, "
          f"batch_size={batch_size}, domain={domain}", flush=True)

    while True:
        batch_num += 1
        results_before = _count_summary_results(summary_path)

        log_path = log_dir / f"_bucket_{pair}_{outcome}_batch{batch_num:03d}.log"

        cmd = [
            "python", "adapters/arch_workflow.py",
            "--winner-json", str(bucket_json),
            "--outcome", outcome,
            "--resume",
            "--limit", str(batch_size),
            "--no-promote-synthesized-manifests",
            *bucket_adapter_args,
        ]

        label = f"[{pair}_{outcome}] batch {batch_num}"
        print(f"\n>>> [{time.strftime('%H:%M:%S')}] {label}", flush=True)
        t_batch = time.time()
        with open(log_path, "w", encoding="utf-8", errors="replace") as f:
            p = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=REFRAG)
        elapsed = time.time() - t_batch

        if p.returncode != 0:
            errors += 1
            print(f"    {label}: FAILED ({elapsed:.0f}s, code {p.returncode})  "
                  f"log={log_path}", flush=True)
            break

        results_after = _count_summary_results(summary_path)
        new_this_batch = results_after - results_before
        total_new += max(0, new_this_batch)

        print(f"    {label}: OK ({elapsed:.0f}s, +{new_this_batch} trades, "
              f"total={results_after}/{total_entries})", flush=True)

        # Archive evidence graph to 3 KBs, then clear this bucket's file
        _archive_evidence_graph(domain, batch_num)

        # If no new trades were processed, bucket is done
        if new_this_batch <= 0:
            print(f"  [{pair}_{outcome}] DONE: no new trades in batch {batch_num}. "
                  f"Total processed: {results_after}/{total_entries} "
                  f"({time.time()-t_start:.0f}s total)", flush=True)
            break

    return {
        "pair": pair,
        "outcome": outcome,
        "domain": domain,
        "batches": batch_num,
        "total_processed": total_new,
        "errors": errors,
        "elapsed_s": round(time.time() - t_start, 1),
    }


def run(cmd, log_path, label):
    print(f"\n>>> [{time.strftime('%H:%M:%S')}] {label}", flush=True)
    t0 = time.time()
    with open(log_path, "w", encoding="utf-8", errors="replace") as f:
        p = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=REFRAG)
    elapsed = time.time() - t0
    if p.returncode != 0:
        print(f"    !! FAILED ({elapsed:.0f}s, code {p.returncode})  log={log_path}", flush=True)
        return False
    print(f"    OK ({elapsed:.0f}s)  log={log_path}", flush=True)
    return True

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pre-entry", action="store_true",
                    help="Pre-entry validation mode. Filter uses [entry_ts - 30m, entry_ts] "
                         "bar window (no exit leak); adapter uses domain_suffix=preentry "
                         "so discoveries land in a separate domain folder; out_dir forks "
                         "to _full_pipeline_winners_preentry/.")
    ap.add_argument("--only-pair", type=str, default="",
                    help="Run a single pair (e.g. 'markets_btc_bybit_buy') and stop. "
                         "Useful for canary runs before full sweep.")
    ap.add_argument("--target-size", type=int, default=DEFAULT_TARGET_N,
                    help="Per-side target count (default 20). Use 100 for the eligible100 "
                         "broader-population sweep.")
    ap.add_argument("--cross-section", action="store_true",
                    help="Use --mode cross-section for BOTH sides (evenly-spaced sample "
                         "from eligible pool, not just top/bottom net_bps extremes). "
                         "Filename infix becomes .cross{N} instead of .top{N}/.bottom{N}, "
                         "and the domain suffix appends _cs{N} so discoveries are isolated "
                         "from the extremes-only dataset.")
    ap.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                    help="Trades per batch before evidence graph archive+clear (default 100). "
                         "Each bucket runs back-to-back batches until all trades are done.")
    ap.add_argument("--workers", type=int, default=0,
                    help="Max parallel bucket workers (default: CPU count, capped at 24). "
                         "Each bucket gets its own worker; they share no evidence graph "
                         "files so there is no conflict.")
    ap.add_argument("--sequential", action="store_true",
                    help="Run buckets one at a time (old behavior). Overrides --workers.")
    args = ap.parse_args()

    pre_entry = bool(args.pre_entry)
    target_n = int(args.target_size)
    cs = bool(args.cross_section)
    batch_size = int(args.batch_size)
    win_mode = "cross-section" if cs else "top"
    lose_mode = "cross-section" if cs else "bottom"
    win_infix = f".cross{target_n}" if cs else f".top{target_n}"
    lose_infix = f".cross{target_n}" if cs else f".bottom{target_n}"
    domain_suffix = PREENTRY_SUFFIX + (f"_cs{target_n}" if cs else "") + "_clean"  # S29: isolate from broken cs1075

    max_workers = args.workers if args.workers > 0 else min(os.cpu_count() or 4, 24)
    if args.sequential:
        max_workers = 1

    file_infix = f".{PREENTRY_SUFFIX}" if pre_entry else ""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    pairs_to_run = [args.only_pair] if args.only_pair else PAIRS
    if args.only_pair and args.only_pair not in PAIRS:
        print(f"ERROR: --only-pair {args.only_pair!r} not in PAIRS list", flush=True)
        return 1

    extra_filter_args: list[str] = []
    extra_adapter_args: list[str] = []
    if pre_entry:
        extra_filter_args += ["--pre-entry", "--pre-entry-minutes", str(PREENTRY_MINUTES)]
        preentry_out_dir = MARKETS / (
            f"_full_pipeline_winners_{domain_suffix}"
            if cs else "_full_pipeline_winners_preentry"
        )
        preentry_out_dir.mkdir(parents=True, exist_ok=True)
        extra_adapter_args += ["--domain-suffix", domain_suffix,
                                "--out-dir", str(preentry_out_dir),
                                "--pre-entry-minutes", str(PREENTRY_MINUTES)]

    # PHASE A: build all list files first (fast, sequential, abort on failure)
    mode_tag = ("PRE-ENTRY" if pre_entry else "POST-HOC") + (f"/CS{target_n}" if cs else f"/N{target_n}")
    print(f"\n========== PHASE A: BUILD LISTS ({len(pairs_to_run)} pair(s), mode={mode_tag}) ==========",
          flush=True)

    bucket_jobs: list[tuple[Path, str]] = []  # (bucket_json, outcome)
    for pair in pairs_to_run:
        win_src = PER_BUCKET / f"{pair}_win.json"
        lose_src = PER_BUCKET / f"{pair}_lose.json"
        win_out = PER_BUCKET / f"{pair}_win{file_infix}{win_infix}.json"
        lose_out = PER_BUCKET / f"{pair}_lose{file_infix}{lose_infix}.json"

        if not win_out.exists():
            if not run(
                ["python", str(MARKETS / "_eligible_cross_section.py"),
                 "--input", str(win_src),
                 "--output", str(win_out),
                 "--target-size", str(target_n),
                 "--mode", win_mode,
                 "--min-returns", "192",
                 *extra_filter_args],
                LOGS_DIR / f"_eligible_{pair}_win{win_infix}{file_infix}.log",
                f"BUILD {win_out.name}",
            ):
                return 1
        else:
            print(f"  ({win_out.name} already exists, skip build)", flush=True)

        if not lose_out.exists():
            if not run(
                ["python", str(MARKETS / "_eligible_cross_section.py"),
                 "--input", str(lose_src),
                 "--output", str(lose_out),
                 "--target-size", str(target_n),
                 "--mode", lose_mode,
                 "--min-returns", "192",
                 *extra_filter_args],
                LOGS_DIR / f"_eligible_{pair}_lose{lose_infix}{file_infix}.log",
                f"BUILD {lose_out.name}",
            ):
                return 1
        else:
            print(f"  ({lose_out.name} already exists, skip build)", flush=True)

        bucket_jobs.append((win_out, "win"))
        bucket_jobs.append((lose_out, "lose"))

    # PHASE B: run ALL buckets in parallel, each doing back-to-back batch_size
    # batches with evidence graph archive+clear between batches
    print(f"\n========== PHASE B: PARALLEL RUN ({len(bucket_jobs)} buckets, "
          f"workers={max_workers}, batch_size={batch_size}) ==========", flush=True)
    t_phase_b = time.time()

    all_results: list[dict] = []
    total_errors = 0

    if max_workers == 1:
        # Sequential mode (--sequential or --workers 1)
        for bucket_json, outcome in bucket_jobs:
            result = run_bucket_loop(
                bucket_json, outcome, domain_suffix, batch_size,
                extra_adapter_args, LOGS_DIR,
            )
            all_results.append(result)
            total_errors += result["errors"]
    else:
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            futures = {}
            for bucket_json, outcome in bucket_jobs:
                fut = pool.submit(
                    run_bucket_loop,
                    bucket_json, outcome, domain_suffix, batch_size,
                    extra_adapter_args, LOGS_DIR,
                )
                futures[fut] = (bucket_json.stem, outcome)

            for fut in as_completed(futures):
                key = futures[fut]
                try:
                    result = fut.result()
                    all_results.append(result)
                    total_errors += result["errors"]
                except Exception as e:
                    total_errors += 1
                    print(f"  FATAL ERROR on {key}: {type(e).__name__}: {e}", flush=True)

    elapsed_total = time.time() - t_phase_b
    print(f"\n========== ALL BUCKETS DONE ==========")
    print(f"  buckets: {len(all_results)}/{len(bucket_jobs)}")
    print(f"  total trades processed: {sum(r.get('total_processed', 0) for r in all_results)}")
    print(f"  total batches: {sum(r.get('batches', 0) for r in all_results)}")
    print(f"  errors: {total_errors}")
    print(f"  elapsed: {elapsed_total:.0f}s ({elapsed_total/60:.1f}m)")
    for r in sorted(all_results, key=lambda x: x.get("pair", "")):
        print(f"    {r['pair']}_{r['outcome']}: "
              f"{r['batches']} batches, {r['total_processed']} trades, "
              f"{r['elapsed_s']}s", flush=True)

    return 1 if total_errors > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
