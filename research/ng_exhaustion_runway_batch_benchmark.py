#!/usr/bin/env python3
"""Large-batch proof/benchmark for the isolated NG exhaustion runway clock V0.

This harness consumes the frozen *blind input* corpus only. It never opens realized
future price or post-reveal outcome data, and it does not retune the classifier,
runway baselines, or microstructure policy.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import time
from typing import Any, Iterable, Sequence

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))

from ng_exhaustion_runway_clock import (
    A_FAST_COLLAPSE,
    A_PERSISTENT,
    A_STATE_PENDING,
    A_STATE_UNAVAILABLE,
    B_UNRESOLVED,
    C_SCALE_TRANSITION_PROVISIONAL,
    ExhaustionRunwayClock,
    FROZEN_REVEAL_BASELINES_S,
    FrozenAClassifier,
    RunwayClockError,
    SCALES,
)

EXPECTED_INPUT_ARTIFACT_ID = 9274443976
EXPECTED_INPUT_ARTIFACT_SHA256 = "224be8b033c1a03d638d7b84aef849363067e1961e9945e72bc86b52c3d01c39"
EXPECTED_RECORDS = 1711
EXPECTED_FAMILY_COUNTS = {"A": 1616, "B": 35, "C": 60}
EXPECTED_A_COUNTS = {A_FAST_COLLAPSE: 831, A_PERSISTENT: 785}
EXPECTED_DAYS = {"20250717": 420, "20250923": 446, "20250930": 428, "20251001": 417}
CHECKPOINTS_S = (0.0, 30.0, 59.999, 60.0, 300.0, 900.0, 1802.0, 7200.0)

_WORKER_ENGINE: ExhaustionRunwayClock | None = None


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _pct(sorted_values: Sequence[int], p: float) -> float:
    if not sorted_values:
        return math.nan
    idx = int((len(sorted_values) - 1) * p)
    return sorted_values[idx] / 1000.0


def _compact_record(row: dict[str, Any]) -> tuple[str, str, int, str, tuple[float, ...] | None, str | None, tuple[float, float] | None]:
    family = row["family"]
    window = None
    expected_label = None
    expected_distances = None
    if family == "A":
        values = row["dipole_roll20_oriented_t_minus60_to_plus60"]
        _require(len(values) == 121, f"{row['blind_id']}: expected 121 dipole samples")
        window = tuple(float(x) for x in values[60:])
        frozen = row.get("frozen_post_state_assignment")
        _require(isinstance(frozen, dict), f"{row['blind_id']}: missing frozen A assignment")
        expected_label = frozen.get("label")
        expected_distances = (
            float(frozen["distance_fast_collapse"]),
            float(frozen["distance_persistent"]),
        )
    return (
        str(row["blind_id"]),
        str(row["day"]),
        int(row["t0_second_utc"]),
        family,
        window,
        expected_label,
        expected_distances,
    )


def _call(
    engine: ExhaustionRunwayClock,
    rec: tuple[str, str, int, str, tuple[float, ...] | None, str | None, tuple[float, float] | None],
    elapsed_s: float,
    microstructure: str = "unavailable",
    *,
    with_a_window: bool = True,
) -> dict[str, Any]:
    blind_id, day, t0, family, window, _, _ = rec
    a_window = window if family == "A" and elapsed_s >= 60.0 and with_a_window else None
    return engine.update(
        event_id=blind_id,
        session_id=day,
        t0=t0,
        family=family,
        elapsed_s=elapsed_s,
        a_t0_to_plus60=a_window,
        microstructure=microstructure,
        data_flags={"event_clock": True, "microstructure": microstructure != "unavailable"},
    )


def _validate_manifest(manifest: dict[str, Any]) -> None:
    _require(manifest.get("blind_n") == EXPECTED_RECORDS, "blind_n drift")
    _require(manifest.get("family_counts") == {"A": 1616, "C": 60, "B": 35}, "family_counts drift")
    _require(manifest.get("a_post_state_counts") == {"A-persistent": 785, "A-fast-collapse": 831}, "A count drift")
    _require(manifest.get("causal_price_anchor_served") is True, "causal anchor invariant failed")
    _require(manifest.get("future_price_or_price_bearing_window_served") is False, "future price was served")
    _require(manifest.get("blind_record_outcome_wall_scan") == "PASS", "outcome wall scan failed")
    _require(manifest.get("target_day_brain_leak_scan") == "PASS", "target-day brain leak scan failed")
    _require(manifest.get("source_brain_mutated") is False, "source brain mutation reported")


def validate_corpus(
    engine: ExhaustionRunwayClock,
    compact: list[tuple[str, str, int, str, tuple[float, ...] | None, str | None, tuple[float, float] | None]],
) -> dict[str, Any]:
    ids = [r[0] for r in compact]
    _require(len(ids) == EXPECTED_RECORDS and len(set(ids)) == EXPECTED_RECORDS, "record ID coverage drift")
    family_counts = Counter(r[3] for r in compact)
    day_counts = Counter(r[1] for r in compact)
    _require(dict(family_counts) == EXPECTED_FAMILY_COUNTS, f"family counts drift: {family_counts}")
    _require(dict(day_counts) == EXPECTED_DAYS, f"day counts drift: {day_counts}")

    a_counts: Counter[str] = Counter()
    label_mismatches = 0
    distance_mismatches = 0
    invalid_a = 0
    for rec in compact:
        if rec[3] != "A":
            continue
        try:
            cls = engine.classifier.classify_t0_to_plus60(rec[4] or ())
        except Exception:
            invalid_a += 1
            continue
        a_counts[cls.post_state] += 1
        if cls.post_state != rec[5]:
            label_mismatches += 1
        expected_d = rec[6]
        if expected_d is None or any(abs(a - b) > 1e-12 for a, b in zip(cls.distances, expected_d)):
            distance_mismatches += 1
    _require(invalid_a == 0, f"invalid A windows: {invalid_a}")
    _require(dict(a_counts) == EXPECTED_A_COUNTS, f"A classifier counts drift: {a_counts}")
    _require(label_mismatches == 0, f"A label mismatches: {label_mismatches}")
    _require(distance_mismatches == 0, f"A distance mismatches: {distance_mismatches}")

    outputs_checked = 0
    negative_remaining = 0
    future_price_flags = 0
    pre60_a_not_pending = 0
    confirmed_a_mismatch = 0
    monotonic_failures = 0
    for rec in compact:
        previous: dict[str, float] = {}
        for elapsed in CHECKPOINTS_S:
            out = _call(engine, rec, elapsed)
            outputs_checked += 1
            if out.get("future_price_accessed") is not False:
                future_price_flags += 1
            family = rec[3]
            if family == "A" and elapsed < 60.0:
                if out["post_state"] != A_STATE_PENDING:
                    pre60_a_not_pending += 1
            elif family == "A":
                if out["post_state"] != rec[5]:
                    confirmed_a_mismatch += 1
            elif family == "B":
                _require(out["post_state"] == B_UNRESOLVED, f"{rec[0]}: B state drift")
            else:
                _require(out["post_state"] == C_SCALE_TRANSITION_PROVISIONAL, f"{rec[0]}: C state drift")

            for scale in SCALES:
                remaining = out["runways"][scale]["remaining_s"]
                if remaining is None:
                    continue
                if remaining < 0.0:
                    negative_remaining += 1
                if scale in previous and remaining > previous[scale] + 1e-12:
                    monotonic_failures += 1
                previous[scale] = remaining
    _require(future_price_flags == 0, f"future_price_accessed drift: {future_price_flags}")
    _require(pre60_a_not_pending == 0, f"pre60 A legal-gate failures: {pre60_a_not_pending}")
    _require(confirmed_a_mismatch == 0, f"confirmed A mismatches: {confirmed_a_mismatch}")
    _require(negative_remaining == 0, f"negative runway values: {negative_remaining}")
    _require(monotonic_failures == 0, f"countdown monotonicity failures: {monotonic_failures}")

    # Full-corpus A data-gap sweep at the legal boundary: missing the classifier window
    # must block state/runway rather than guessing a partial classifier.
    data_gap_failures = 0
    gap_outputs = 0
    for rec in compact:
        if rec[3] != "A":
            continue
        out = _call(engine, rec, 60.0, with_a_window=False)
        gap_outputs += 1
        if out["post_state"] != A_STATE_UNAVAILABLE:
            data_gap_failures += 1
        if any(out["runways"][s]["remaining_s"] is not None for s in SCALES):
            data_gap_failures += 1
    _require(data_gap_failures == 0, f"A missing-window fail-closed failures: {data_gap_failures}")

    # Full-corpus proof that the confidence input cannot change seconds in V0.
    micro_seconds_failures = 0
    micro_outputs = 0
    for rec in compact:
        baseline = _call(engine, rec, 300.0, "mixed")
        for micro in ("same_side", "opposite", "unavailable"):
            out = _call(engine, rec, 300.0, micro)
            micro_outputs += 1
            for scale in SCALES:
                if out["runways"][scale]["remaining_s"] != baseline["runways"][scale]["remaining_s"]:
                    micro_seconds_failures += 1
    _require(micro_seconds_failures == 0, f"microstructure changed seconds: {micro_seconds_failures}")

    # One direct event-clock falsifier: should raise, not fabricate countdown time.
    probe = compact[0]
    try:
        engine.update(
            event_id=probe[0], session_id=probe[1], t0=probe[2], family=probe[3], elapsed_s=60.0,
            a_t0_to_plus60=probe[4], microstructure="unavailable", data_flags={"event_clock": False}
        )
    except RunwayClockError:
        event_clock_fail_closed = True
    else:
        event_clock_fail_closed = False
    _require(event_clock_fail_closed, "event_clock gap did not fail closed")

    return {
        "records": len(compact),
        "family_counts": dict(sorted(family_counts.items())),
        "day_counts": dict(sorted(day_counts.items())),
        "a_classifier_counts": dict(sorted(a_counts.items())),
        "a_invalid_windows": invalid_a,
        "a_label_mismatches": label_mismatches,
        "a_distance_mismatches": distance_mismatches,
        "timeline_outputs_checked": outputs_checked,
        "timeline_checkpoints_s": list(CHECKPOINTS_S),
        "pre60_a_pending_failures": pre60_a_not_pending,
        "confirmed_a_mismatches": confirmed_a_mismatch,
        "negative_remaining_failures": negative_remaining,
        "monotonic_countdown_failures": monotonic_failures,
        "future_price_accessed_flags": future_price_flags,
        "a_missing_window_outputs_checked": gap_outputs,
        "a_missing_window_fail_closed_failures": data_gap_failures,
        "microstructure_outputs_checked": micro_outputs,
        "microstructure_seconds_changed_failures": micro_seconds_failures,
        "event_clock_gap_fail_closed": event_clock_fail_closed,
    }


def _single_sweep(engine: ExhaustionRunwayClock, compact: list[tuple], elapsed: float) -> int:
    n = 0
    for rec in compact:
        _call(engine, rec, elapsed)
        n += 1
    return n


def _timeline_sweep(engine: ExhaustionRunwayClock, compact: list[tuple]) -> tuple[int, float]:
    n = 0
    checksum = 0.0
    for rec in compact:
        for elapsed in CHECKPOINTS_S:
            out = _call(engine, rec, elapsed)
            n += 1
            remaining = out["runways"]["8t"]["remaining_s"]
            if remaining is not None:
                checksum += float(remaining)
    return n, checksum


def _worker_init(classifier_path: str) -> None:
    global _WORKER_ENGINE
    _WORKER_ENGINE = ExhaustionRunwayClock(FrozenAClassifier.load(classifier_path))


def _worker_timeline(chunk: list[tuple]) -> tuple[int, float]:
    if _WORKER_ENGINE is None:
        raise RuntimeError("worker engine not initialized")
    return _timeline_sweep(_WORKER_ENGINE, chunk)


def _chunks(compact: list[tuple], workers: int) -> list[list[tuple]]:
    size = (len(compact) + workers - 1) // workers
    return [compact[i : i + size] for i in range(0, len(compact), size)]


def benchmark(
    engine: ExhaustionRunwayClock,
    compact: list[tuple],
    classifier_path: Path,
    *,
    repeats: int,
    latency_samples: int,
    parallel_workers: Iterable[int],
) -> dict[str, Any]:
    # Warm the interpreter and caches before timing compute-only sweeps.
    _single_sweep(engine, compact, 60.0)
    _timeline_sweep(engine, compact)

    single_times: list[float] = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        n_single = _single_sweep(engine, compact, 60.0)
        single_times.append(time.perf_counter() - t0)

    timeline_times: list[float] = []
    checksum = None
    for _ in range(repeats):
        t0 = time.perf_counter()
        n_timeline, checksum = _timeline_sweep(engine, compact)
        timeline_times.append(time.perf_counter() - t0)

    # Individual confirmed-A latency sample.
    a_probe = next(rec for rec in compact if rec[3] == "A")
    for _ in range(1000):
        _call(engine, a_probe, 60.0)
    latency_ns: list[int] = []
    for _ in range(latency_samples):
        t0 = time.perf_counter_ns()
        _call(engine, a_probe, 60.0)
        latency_ns.append(time.perf_counter_ns() - t0)
    latency_ns.sort()

    parallel: dict[str, Any] = {}
    for workers in parallel_workers:
        if workers <= 1:
            continue
        chunks = _chunks(compact, workers)
        # Persistent/warm pool: relevant if parallel workers are actually deployed.
        with ProcessPoolExecutor(max_workers=workers, initializer=_worker_init, initargs=(str(classifier_path),)) as pool:
            list(pool.map(_worker_timeline, chunks))
            warm_times: list[float] = []
            parallel_n = 0
            parallel_checksum = 0.0
            for _ in range(repeats):
                t0 = time.perf_counter()
                rows = list(pool.map(_worker_timeline, chunks))
                warm_times.append(time.perf_counter() - t0)
                parallel_n = sum(x[0] for x in rows)
                parallel_checksum = sum(x[1] for x in rows)
        # Cold pool: includes worker creation and classifier load.
        t0 = time.perf_counter()
        with ProcessPoolExecutor(max_workers=workers, initializer=_worker_init, initargs=(str(classifier_path),)) as pool:
            cold_rows = list(pool.map(_worker_timeline, chunks))
        cold_s = time.perf_counter() - t0
        cold_n = sum(x[0] for x in cold_rows)
        parallel[str(workers)] = {
            "warm_pool_median_s": statistics.median(warm_times),
            "warm_pool_updates_per_s": parallel_n / statistics.median(warm_times),
            "cold_pool_s": cold_s,
            "cold_pool_updates_per_s": cold_n / cold_s,
            "checksum_8t_remaining": parallel_checksum,
            "warm_times_s": warm_times,
        }

    single_median = statistics.median(single_times)
    timeline_median = statistics.median(timeline_times)
    return {
        "single_checkpoint": {
            "elapsed_s": 60.0,
            "updates": n_single,
            "median_s": single_median,
            "updates_per_s": n_single / single_median,
            "times_s": single_times,
        },
        "eight_checkpoint_timeline": {
            "updates": n_timeline,
            "median_s": timeline_median,
            "updates_per_s": n_timeline / timeline_median,
            "checksum_8t_remaining": checksum,
            "times_s": timeline_times,
        },
        "confirmed_a_call_latency_us": {
            "samples": len(latency_ns),
            "median": _pct(latency_ns, 0.50),
            "p95": _pct(latency_ns, 0.95),
            "p99": _pct(latency_ns, 0.99),
            "max": latency_ns[-1] / 1000.0,
            "mean": statistics.mean(latency_ns) / 1000.0,
        },
        "parallel_process_pool": parallel,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--classifier", type=Path, required=True)
    parser.add_argument("--input-artifact", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--latency-samples", type=int, default=20000)
    parser.add_argument("--parallel-workers", default="2,4")
    args = parser.parse_args()

    artifact_sha = None
    if args.input_artifact is not None:
        raw = args.input_artifact.read_bytes()
        artifact_sha = sha256(raw).hexdigest()
        _require(artifact_sha == EXPECTED_INPUT_ARTIFACT_SHA256, f"input artifact SHA drift: {artifact_sha}")

    t0 = time.perf_counter()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    _validate_manifest(manifest)
    rows = json.loads(args.records.read_text(encoding="utf-8"))
    input_parse_s = time.perf_counter() - t0
    _require(isinstance(rows, list) and len(rows) == EXPECTED_RECORDS, "blind record coverage drift")
    compact = [_compact_record(row) for row in rows]
    mbo_status_counts = dict(sorted(Counter(str(row.get("mbo_status")) for row in rows).items()))

    engine = ExhaustionRunwayClock(FrozenAClassifier.load(args.classifier))
    proof = validate_corpus(engine, compact)
    workers = [int(x) for x in args.parallel_workers.split(",") if x.strip()]
    perf = benchmark(
        engine,
        compact,
        args.classifier,
        repeats=max(1, args.repeats),
        latency_samples=max(1, args.latency_samples),
        parallel_workers=workers,
    )

    result = {
        "status": "PASS",
        "purpose": "large_batch_throughput_and_contract_proof_only_no_retuning",
        "input": {
            "artifact_id": EXPECTED_INPUT_ARTIFACT_ID,
            "artifact_sha256": artifact_sha,
            "expected_artifact_sha256": EXPECTED_INPUT_ARTIFACT_SHA256,
            "records_sha256": sha256(args.records.read_bytes()).hexdigest(),
            "manifest_sha256": sha256(args.manifest.read_bytes()).hexdigest(),
            "parse_manifest_plus_records_s": input_parse_s,
            "future_price_or_price_bearing_window_served": manifest["future_price_or_price_bearing_window_served"],
            "blind_record_outcome_wall_scan": manifest["blind_record_outcome_wall_scan"],
            "mbo_status_counts": mbo_status_counts,
            "records_bytes": args.records.stat().st_size,
        },
        "proof": proof,
        "performance": perf,
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
        },
        "policy": {
            "classifier_retuned": False,
            "runway_baselines_retuned": False,
            "scratch_price_curve_logic_used": False,
            "microstructure_mapping_learned_or_retuned": False,
            "microstructure_for_timed_sweeps": "unavailable",
            "future_price_accessed_by_clock": False,
            "permanent_frankie_mutated": False,
        },
    }
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
