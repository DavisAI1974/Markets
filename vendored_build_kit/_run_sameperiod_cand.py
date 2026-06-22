"""S34 Direction-2 discovery driver — SEQUENTIAL (WinError race forces it).

Runs pre-entry discovery on the capped same-period candidate lists
(_sameperiod_cand/lists/markets_<pair>_cand.cap150.json), one cell at a time,
batch+resume, archiving+clearing the evidence graph between batches (keeps
per-trade cost ~2.3s). Coeffs land in an ISOLATED domain
markets_<pair>_win_cand_sp/ so the existing _win_preentry_cs2000_clean dirs are
untouched. Resume-safe: rerun to continue after an interrupt.

Sequential ONLY: parallel workers collide on E:\\refrag\\artifacts\\control_plane\\
lifecycle\\spectral_chunker.json (os.replace -> WinError 5) and crash before
writing coeffs. One process at a time = no race.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

spec = importlib.util.spec_from_file_location("rcr", r"E:\Markets\_run_clean_rerun.py")
rcr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rcr)

REFRAG = Path(r"E:\refrag")
MARKETS = Path(r"E:\Markets")
LISTS = MARKETS / "_sameperiod_cand" / "lists"
OUT_ROOT = MARKETS / "_full_pipeline_sameperiod_cand"
LOGS = MARKETS / "_pipeline_logs"
SUFFIX = "cand_sp"
BATCH = 100
PAIRS = ["btc_bybit_buy", "btc_bybit_sell", "btc_coinbase_buy", "btc_coinbase_sell",
         "btc_kraken_buy", "btc_kraken_sell", "eth_bybit_buy", "eth_bybit_sell",
         "eth_coinbase_buy", "eth_coinbase_sell", "eth_kraken_buy", "eth_kraken_sell"]


def run_cell(p: str) -> dict:
    list_fp = LISTS / f"markets_{p}_cand.cap150.json"
    if not list_fp.exists():
        print(f"  [{p}] SKIP: no list {list_fp.name}", flush=True)
        return {"pair": p, "skipped": True}
    domain = f"markets_{p}_win_{SUFFIX}"
    out_dir = OUT_ROOT / domain
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = out_dir / "summary.json"
    LOGS.mkdir(parents=True, exist_ok=True)
    extra = ["--domain-suffix", SUFFIX, "--out-dir", str(out_dir), "--pre-entry-minutes", "30"]
    batch_num = 0
    t0 = time.time()
    total_new = 0
    while True:
        batch_num += 1
        before = rcr._count_summary_results(summary)
        log = LOGS / f"_cand_{p}_batch{batch_num:03d}.log"
        cmd = ["python", "adapters/arch_workflow.py",
               "--winner-json", str(list_fp), "--outcome", "win", "--resume",
               "--limit", str(BATCH), "--no-promote-synthesized-manifests", *extra]
        tb = time.time()
        with open(log, "w", encoding="utf-8", errors="replace") as f:
            pr = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=REFRAG)
        if pr.returncode != 0:
            print(f"  [{p}] batch {batch_num} FAILED (code {pr.returncode}) -> {log}", flush=True)
            return {"pair": p, "batches": batch_num, "total_new": total_new, "error": True}
        after = rcr._count_summary_results(summary)
        new = after - before
        total_new += max(0, new)
        rcr._archive_evidence_graph(domain, batch_num)
        print(f"  [{p}] batch {batch_num}: +{new} (total {after}) {time.time()-tb:.0f}s", flush=True)
        if new <= 0:
            break
    print(f"[{p}] DONE: {total_new} new, {batch_num} batches, {time.time()-t0:.0f}s", flush=True)
    return {"pair": p, "batches": batch_num, "total_new": total_new}


def main() -> int:
    # args: [pair] [--workers N]   (parallel cells; resume-safe per cell)
    argv = sys.argv[1:]
    workers = 4
    if "--workers" in argv:
        i = argv.index("--workers")
        workers = int(argv[i + 1]); del argv[i:i + 2]
    only = argv[0] if argv else None
    pairs = [only] if only else PAIRS
    workers = max(1, min(workers, os.cpu_count() or 4, len(pairs)))
    t0 = time.time()
    results = []
    if workers == 1:
        for p in pairs:
            results.append(run_cell(p))
    else:
        print(f"PARALLEL: {workers} workers over {len(pairs)} cells "
              f"(storage.save_json retries os.replace on lock)", flush=True)
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futs = {pool.submit(run_cell, p): p for p in pairs}
            for fut in as_completed(futs):
                try:
                    results.append(fut.result())
                except Exception as e:
                    print(f"  FATAL {futs[fut]}: {type(e).__name__}: {e}", flush=True)
                    results.append({"pair": futs[fut], "error": True})
    print(f"\n===== ALL CELLS DONE ({time.time()-t0:.0f}s = {(time.time()-t0)/60:.1f}m) =====")
    print(f"total new coeffs: {sum(r.get('total_new', 0) for r in results)}")
    errs = [r['pair'] for r in results if r.get('error')]
    if errs:
        print(f"cells with errors: {errs}")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
