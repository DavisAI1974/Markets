from __future__ import annotations

import argparse
import subprocess
import sys
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path


FAMILIES = [
    "MEAN_REVERSION_CHOP",
    "NEWS_BREAKOUT",
    "LIQUIDITY_SQUEEZE",
    "VOL_BREAKOUT",
    "BASIS_DISLOCATION",
    "RELATIVE_STRENGTH",
]


def _root_name(start_hour: int, stride_minutes: int) -> str:
    prefix = "strategy_evolution_workflow_runs_loose5" if stride_minutes == 5 else "strategy_evolution_workflow_runs_loose"
    return f"{prefix}_h{start_hour}"


def _is_complete(root: Path) -> bool:
    return any(root.glob("slice_*/mock_replay_results.json"))


def _command(start_hour: int, stride_minutes: int, output_root: str) -> list[str]:
    return [
        sys.executable,
        "run_strategy_evolution_workflow.py",
        "--start-hour",
        str(start_hour),
        "--hours",
        "6",
        "--iterations",
        "1",
        "--all-families-until-hit",
        "--passes-per-family",
        "1",
        "--stride-minutes",
        str(stride_minutes),
        "--min-context-family-samples",
        "1",
        "--winner-pnl-r-floor",
        "0",
        "--winner-min-trades",
        "1",
        "--allow-promoted-context-rerun",
        "--allowed-strategies",
        ",".join(FAMILIES),
        "--output-root",
        output_root,
    ]


def _run_one(start_hour: int, stride_minutes: int, *, force: bool) -> dict[str, object]:
    output_root = _root_name(start_hour, stride_minutes)
    root_path = Path(output_root)
    if _is_complete(root_path) and not force:
        return {
            "status": "skipped_existing",
            "start_hour": start_hour,
            "stride_minutes": stride_minutes,
            "output_root": output_root,
        }
    root_path.mkdir(parents=True, exist_ok=True)
    log_path = root_path / f"_opportunity_evidence_h{start_hour}_{stride_minutes}m.log"
    cmd = _command(start_hour, stride_minutes, output_root)
    started = time.time()
    with log_path.open("w", encoding="utf-8") as log:
        log.write("+ " + " ".join(cmd) + "\n")
        log.flush()
        proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, text=True)
    return {
        "status": "completed" if proc.returncode == 0 else "failed",
        "returncode": proc.returncode,
        "start_hour": start_hour,
        "stride_minutes": stride_minutes,
        "output_root": output_root,
        "log_path": str(log_path),
        "elapsed_seconds": round(time.time() - started, 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the locked opportunity evidence sweeps: 15m loose and 5m dense for each 6h block."
    )
    parser.add_argument("--start-hour", type=int, default=0)
    parser.add_argument("--end-hour", type=int, default=12, help="Exclusive replay hour boundary.")
    parser.add_argument("--max-parallel", type=int, default=4)
    parser.add_argument("--force", action="store_true", help="Rerun output roots even if result files already exist.")
    args = parser.parse_args()

    starts = list(range(int(args.start_hour), int(args.end_hour), 6))
    jobs = [(start, stride) for start in starts for stride in (15, 5)]
    pending: set[Future[dict[str, object]]] = set()
    results: list[dict[str, object]] = []
    max_parallel = max(1, int(args.max_parallel))
    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        iterator = iter(jobs)
        while True:
            while len(pending) < max_parallel:
                try:
                    start, stride = next(iterator)
                except StopIteration:
                    break
                pending.add(pool.submit(_run_one, start, stride, force=bool(args.force)))
            if not pending:
                break
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                row = future.result()
                results.append(row)
                print(row, flush=True)
    failed = [row for row in results if row.get("status") == "failed"]
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
