#!/usr/bin/env python3
"""Bounded three-month Frankie orchestration for the full post-V4 program.

This module changes orchestration only. It does not change Frankie event construction,
qualification, reasoning-lane order, adjudication, first-lock semantics, evidence content,
or any MBO/V4 scientific definition. The authorized source window is exactly the half-open
interval [2021-09-01, 2021-12-01).

The bounded runner:
- pins the current Frankie runtime/input Git blobs before queue access;
- proves that the effective cgroup/systemd CPU capacity can support four workers;
- runs a short four-process CPU canary and fails closed if execution is effectively serial;
- consumes up to four scientifically self-contained post-V4 Frankie events concurrently;
- leaves each event's existing causal_scientist -> trading_mechanics sequence untouched; and
- writes a deterministic temporal-canonical evidence manifest after the dedicated queue is empty.

It never launches upstream MBO/V4 work, never changes source duration, and never mutates
permanent Frankie state or scientific code.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import math
import multiprocessing as mp
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent

SOURCE_WINDOW_START = "2021-09-01"
SOURCE_WINDOW_END_EXCLUSIVE = "2021-12-01"
DEFAULT_WORKERS = 4
SCHEMA_VERSION = "NG_EXHAUSTION_FRANKIE_BOUNDED_3MO_PARALLEL_V1_20260823"

# Git blob identities on chatgpt/ng-exhaustion-step1-3mo-bounded-20260823 when this
# bounded orchestration was added. These are the existing Frankie runtime and durable inputs;
# the bounded runner refuses to execute if any of them drift.
EXPECTED_GIT_BLOBS: dict[str, str] = {
    "research/kalshi/agent_frankie.py": "57cd2762273b3cc72dc0e4cfe2254971148d1f14",
    "research/kalshi/frankie_engine.py": "49f0d867304e11c5baf05729d81f334f76fc0a70",
    "research/kalshi/frankie_core.py": "2e05001495bbd5f2a03584bb87559f98622f95e6",
    "research/kalshi/frankie_backends.py": "1c1233cf92e3b6dd9cf1ec80ce039c30b9a48300",
    "research/kalshi/frankie_cognition.py": "7dd777911a3adfd2b4d5ba1a8a748f9c961fcf8a",
    "research/kalshi/frankie_idempotency.py": "92a1c9d78aaf372ca2d7bee79976bfbd6680e64b",
    "research/kalshi/frankie_paper_manifest.json": "346a31e1504d1689bcbde6e92c877c384050fa82",
    "dashboard/novel_candidates.json": "453ceec2e574e578380ffb805761768ab73c1074",
}


class BoundedParallelError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def git_blob_sha(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    payload = b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
    return hashlib.sha1(payload).hexdigest()  # noqa: S324 - Git object identity.


def verify_runtime_pins(root: Path = ROOT) -> dict[str, str]:
    observed: dict[str, str] = {}
    mismatches: list[str] = []
    for relative, expected in EXPECTED_GIT_BLOBS.items():
        path = root / relative
        if not path.is_file():
            mismatches.append(f"missing {relative}")
            continue
        actual = git_blob_sha(path)
        observed[relative] = actual
        if actual != expected:
            mismatches.append(f"{relative}: expected {expected}, observed {actual}")
    if mismatches:
        raise BoundedParallelError("Frankie runtime/input pin drift: " + "; ".join(mismatches))
    return observed


def parse_cpu_list(raw: str) -> set[int]:
    cpus: set[int] = set()
    for token in raw.strip().split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            first, last = token.split("-", 1)
            start, end = int(first), int(last)
            if end < start:
                raise ValueError(f"invalid CPU range: {token}")
            cpus.update(range(start, end + 1))
        else:
            cpus.add(int(token))
    return cpus


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _self_cgroup_v2() -> Path | None:
    raw = _read_text(Path("/proc/self/cgroup"))
    if not raw:
        return None
    for line in raw.splitlines():
        parts = line.split(":", 2)
        if len(parts) == 3 and parts[0] == "0" and parts[1] == "":
            rel = parts[2].lstrip("/")
            return Path("/sys/fs/cgroup") / rel
    return None


def cgroup_cpu_details() -> dict[str, Any]:
    details: dict[str, Any] = {
        "version": None,
        "path": None,
        "cpu_max_raw": None,
        "quota_cores": None,
        "cpuset_raw": None,
        "cpuset_count": None,
    }
    group = _self_cgroup_v2()
    if group is not None and group.exists():
        details["version"] = 2
        details["path"] = str(group)
        cpu_max = _read_text(group / "cpu.max")
        details["cpu_max_raw"] = cpu_max
        if cpu_max:
            fields = cpu_max.split()
            if len(fields) >= 2 and fields[0] != "max":
                quota = int(fields[0])
                period = int(fields[1])
                if period > 0:
                    details["quota_cores"] = quota / period
        cpuset = _read_text(group / "cpuset.cpus.effective") or _read_text(group / "cpuset.cpus")
        details["cpuset_raw"] = cpuset
        if cpuset:
            details["cpuset_count"] = len(parse_cpu_list(cpuset))
        return details

    # Conservative cgroup-v1 fallback for older AMIs.
    raw = _read_text(Path("/proc/self/cgroup")) or ""
    controllers: dict[str, str] = {}
    for line in raw.splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        for controller in parts[1].split(","):
            controllers[controller] = parts[2].lstrip("/")
    cpu_rel = controllers.get("cpu") or controllers.get("cpuacct")
    if cpu_rel is not None:
        group = Path("/sys/fs/cgroup/cpu") / cpu_rel
        details["version"] = 1
        details["path"] = str(group)
        quota_raw = _read_text(group / "cpu.cfs_quota_us")
        period_raw = _read_text(group / "cpu.cfs_period_us")
        if quota_raw is not None and period_raw is not None:
            quota = int(quota_raw)
            period = int(period_raw)
            details["cpu_max_raw"] = f"{quota} {period}"
            if quota >= 0 and period > 0:
                details["quota_cores"] = quota / period
    cpuset_rel = controllers.get("cpuset")
    if cpuset_rel is not None:
        cpuset_group = Path("/sys/fs/cgroup/cpuset") / cpuset_rel
        cpuset = _read_text(cpuset_group / "cpuset.cpus")
        details["cpuset_raw"] = cpuset
        if cpuset:
            details["cpuset_count"] = len(parse_cpu_list(cpuset))
    return details


def nproc_count() -> int:
    try:
        completed = subprocess.run(
            ["nproc"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return int(completed.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return int(os.cpu_count() or 1)


def affinity_cpus() -> list[int]:
    try:
        return sorted(int(v) for v in os.sched_getaffinity(0))
    except (AttributeError, OSError):
        return list(range(nproc_count()))


def systemd_cpu_details(unit: str | None) -> dict[str, Any]:
    if not unit:
        return {"unit": None, "available": False, "raw": None, "error": "unit not supplied"}
    properties = (
        "CPUQuotaPerSecUSec",
        "AllowedCPUs",
        "EffectiveCPUs",
        "ControlGroup",
        "ActiveState",
    )
    command = ["systemctl", "show", unit, "--no-pager"]
    for prop in properties:
        command.append(f"--property={prop}")
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"unit": unit, "available": False, "raw": None, "error": f"{type(exc).__name__}: {exc}"}
    parsed: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            parsed[key] = value
    return {
        "unit": unit,
        "available": completed.returncode == 0,
        "returncode": completed.returncode,
        "properties": parsed,
        "stderr": completed.stderr.strip() or None,
    }


def service_active(unit: str) -> bool:
    try:
        completed = subprocess.run(
            ["systemctl", "is-active", "--quiet", unit],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def effective_cpu_capacity(
    *,
    nproc: int,
    affinity_count: int,
    cgroup: Mapping[str, Any],
) -> float:
    limits: list[float] = [float(nproc), float(affinity_count)]
    cpuset_count = cgroup.get("cpuset_count")
    if isinstance(cpuset_count, int) and cpuset_count > 0:
        limits.append(float(cpuset_count))
    quota_cores = cgroup.get("quota_cores")
    if isinstance(quota_cores, (int, float)) and math.isfinite(float(quota_cores)):
        limits.append(float(quota_cores))
    return min(limits) if limits else 0.0


def _cpu_burn(start_at: float, seconds: float) -> dict[str, Any]:
    while time.monotonic() < start_at:
        time.sleep(0.001)
    wall_start = time.monotonic()
    cpu_start = time.process_time()
    x = 0x12345678
    iterations = 0
    deadline = wall_start + seconds
    while time.monotonic() < deadline:
        # Deterministic integer work; separate processes avoid the Python GIL.
        for _ in range(20_000):
            x = ((x * 1664525) + 1013904223) & 0xFFFFFFFF
        iterations += 20_000
    return {
        "pid": os.getpid(),
        "wall_seconds": time.monotonic() - wall_start,
        "cpu_seconds": time.process_time() - cpu_start,
        "iterations": iterations,
        "checksum": x,
    }


def cpu_parallel_canary(workers: int, seconds: float) -> dict[str, Any]:
    if workers < 2:
        raise BoundedParallelError("parallel CPU canary requires at least two workers")
    ctx = mp.get_context("spawn")
    start_at = time.monotonic() + 1.0
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as pool:
        futures = [pool.submit(_cpu_burn, start_at, seconds) for _ in range(workers)]
        results = [future.result() for future in futures]
    total_cpu = sum(float(item["cpu_seconds"]) for item in results)
    max_wall = max(float(item["wall_seconds"]) for item in results)
    ratio = total_cpu / max(seconds, 1e-9)
    # This threshold is deliberately far above a single core but leaves room for EC2 steal time
    # and short-canary startup noise. Capacity checks separately require all four vCPUs.
    minimum_ratio = max(1.75, workers * 0.60)
    return {
        "workers": workers,
        "requested_seconds": seconds,
        "total_process_cpu_seconds": total_cpu,
        "max_worker_wall_seconds": max_wall,
        "parallel_cpu_ratio": ratio,
        "minimum_parallel_cpu_ratio": minimum_ratio,
        "passed": ratio >= minimum_ratio,
        "workers_detail": results,
    }


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def environment_checks(environ: Mapping[str, str], *, workers: int) -> dict[str, Any]:
    queue_url = environ.get("FRANKIE_QUEUE_URL")
    deterministic_only = _truthy(environ.get("FRANKIE_DETERMINISTIC_ONLY"))
    exclusive = _truthy(environ.get("FRANKIE_BOUNDED_QUEUE_EXCLUSIVE"))
    errors: list[str] = []
    if workers != DEFAULT_WORKERS:
        errors.append(f"bounded run requires exactly {DEFAULT_WORKERS} workers, got {workers}")
    if not queue_url:
        errors.append("FRANKIE_QUEUE_URL is required")
    if deterministic_only:
        errors.append("FRANKIE_DETERMINISTIC_ONLY must be false for the full Frankie run")
    if not exclusive:
        errors.append("FRANKIE_BOUNDED_QUEUE_EXCLUSIVE=1 is required")
    return {
        "queue_configured": bool(queue_url),
        "queue_url_sha256": hashlib.sha256(queue_url.encode("utf-8")).hexdigest() if queue_url else None,
        "deterministic_only": deterministic_only,
        "bounded_queue_exclusive_asserted": exclusive,
        "intended_worker_count": workers,
        "errors": errors,
    }


def build_preflight(
    *,
    workers: int,
    systemd_unit: str | None,
    require_systemd: bool,
    canary_seconds: float,
) -> dict[str, Any]:
    pins = verify_runtime_pins()
    nproc = nproc_count()
    affinity = affinity_cpus()
    cgroup = cgroup_cpu_details()
    systemd = systemd_cpu_details(systemd_unit)
    capacity = effective_cpu_capacity(nproc=nproc, affinity_count=len(affinity), cgroup=cgroup)
    env = environment_checks(os.environ, workers=workers)
    errors = list(env["errors"])
    if nproc < workers:
        errors.append(f"nproc={nproc} is below intended worker count {workers}")
    if len(affinity) < workers:
        errors.append(f"CPU affinity exposes {len(affinity)} CPUs, below intended {workers}")
    if capacity + 1e-9 < workers:
        errors.append(f"effective cgroup CPU capacity {capacity:.3f} is below intended {workers}")
    if require_systemd and not systemd.get("available"):
        errors.append(f"systemd properties unavailable for {systemd_unit}")
    # The normal serial service must not be consuming the same queue during the bounded batch.
    normal_active = service_active("markets-frankie.service") if require_systemd else False
    if normal_active:
        errors.append("markets-frankie.service is active; bounded queue exclusivity is not proven")

    canary: dict[str, Any] | None = None
    if not errors:
        canary = cpu_parallel_canary(workers, canary_seconds)
        if not canary["passed"]:
            errors.append(
                "parallel CPU canary is effectively serialized: "
                f"ratio={canary['parallel_cpu_ratio']:.3f}, "
                f"required={canary['minimum_parallel_cpu_ratio']:.3f}"
            )

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "PRE_RUN_CPU_ORCHESTRATION_CHECK",
        "status": "PASS" if not errors else "FAIL_CLOSED",
        "checked_at_utc": utc_now(),
        "source_window": {
            "start": SOURCE_WINDOW_START,
            "end_exclusive": SOURCE_WINDOW_END_EXCLUSIVE,
        },
        "scientific_change": False,
        "orchestration_change_only": True,
        "runtime_git_blobs": pins,
        "nproc": nproc,
        "sched_affinity_cpus": affinity,
        "sched_affinity_count": len(affinity),
        "cgroup": cgroup,
        "systemd": systemd,
        "normal_frankie_service_active": normal_active,
        "effective_cpu_capacity": capacity,
        "intended_worker_count": workers,
        "environment": env,
        "cpu_utilization_canary": canary,
        "errors": errors,
    }
    payload["receipt_sha256"] = sha256_json(payload)
    return payload


def _consume_one_worker() -> dict[str, Any]:
    # Import inside the child so no backend/AWS client state is inherited from the parent.
    from frankie_core import FrankieConfig
    from frankie_engine import consume_once

    return consume_once(config=FrankieConfig.from_env(), deterministic_only=False)


def canonical_delivery(result: Mapping[str, Any]) -> dict[str, Any]:
    if not result.get("received"):
        raise BoundedParallelError("cannot canonicalize an empty queue poll")
    if not result.get("processed"):
        raise BoundedParallelError("received queue delivery was not processed")
    decision = result.get("decision")
    evidence = result.get("evidence")
    if not isinstance(decision, Mapping) or not isinstance(evidence, Mapping):
        raise BoundedParallelError("processed result missing decision/evidence mappings")
    qualification = decision.get("qualification")
    if not isinstance(qualification, Mapping) or not qualification.get("event_hash"):
        raise BoundedParallelError("processed decision missing qualification.event_hash")
    required_decision = ("event_id", "candidate_id", "decision_hash")
    missing = [name for name in required_decision if not decision.get(name)]
    if missing:
        raise BoundedParallelError("processed decision missing: " + ", ".join(missing))
    required_evidence = ("local_path", "envelope_hash")
    missing_evidence = [name for name in required_evidence if not evidence.get(name)]
    if missing_evidence:
        raise BoundedParallelError("processed evidence missing: " + ", ".join(missing_evidence))
    evidence_path = Path(str(evidence["local_path"]))
    try:
        envelope = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BoundedParallelError(f"cannot verify evidence envelope {evidence_path}: {exc}") from exc
    if not isinstance(envelope, Mapping):
        raise BoundedParallelError(f"evidence envelope is not a mapping: {evidence_path}")
    claimed_envelope_hash = envelope.get("envelope_hash")
    if claimed_envelope_hash != evidence.get("envelope_hash"):
        raise BoundedParallelError(f"evidence envelope hash/reference mismatch: {evidence_path}")
    envelope_body = dict(envelope)
    envelope_body.pop("envelope_hash", None)
    if claimed_envelope_hash != sha256_json(envelope_body):
        raise BoundedParallelError(f"evidence envelope content hash mismatch: {evidence_path}")
    event = envelope.get("event")
    envelope_decision = envelope.get("decision")
    if not isinstance(event, Mapping):
        raise BoundedParallelError(f"evidence envelope missing event: {evidence_path}")
    if not isinstance(envelope_decision, Mapping):
        raise BoundedParallelError(f"evidence envelope missing decision: {evidence_path}")
    if str(event.get("event_id") or "") != str(decision["event_id"]):
        raise BoundedParallelError(f"evidence event identity mismatch: {evidence_path}")
    if str(envelope_decision.get("decision_hash") or "") != str(decision["decision_hash"]):
        raise BoundedParallelError(f"evidence decision identity mismatch: {evidence_path}")
    if str(envelope_decision.get("candidate_id") or "") != str(decision["candidate_id"]):
        raise BoundedParallelError(f"evidence candidate identity mismatch: {evidence_path}")
    if sha256_json(event) != str(qualification["event_hash"]):
        raise BoundedParallelError(f"evidence event hash mismatch: {evidence_path}")
    if not event.get("knowable_at") or not event.get("observed_at"):
        raise BoundedParallelError(f"evidence event missing causal clocks: {evidence_path}")
    return {
        "event_hash": str(qualification["event_hash"]),
        "event_id": str(decision["event_id"]),
        "candidate_id": str(decision["candidate_id"]),
        "knowable_at": str(event["knowable_at"]),
        "observed_at": str(event["observed_at"]),
        "decision_hash": str(decision["decision_hash"]),
        "local_path": str(evidence["local_path"]),
        "envelope_hash": str(evidence["envelope_hash"]),
        "s3_uri": evidence.get("s3_uri"),
        "deduplicated": bool(evidence.get("deduplicated")),
        "receive_count": result.get("receive_count"),
    }


def canonical_unique_events(deliveries: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_event: dict[str, dict[str, Any]] = {}
    delivery_counts: dict[str, int] = {}
    for item in deliveries:
        event_hash = str(item["event_hash"])
        delivery_counts[event_hash] = delivery_counts.get(event_hash, 0) + 1
        previous = by_event.get(event_hash)
        if previous is None:
            by_event[event_hash] = dict(item)
            continue
        immutable_fields = (
            "event_id",
            "candidate_id",
            "knowable_at",
            "observed_at",
            "decision_hash",
            "envelope_hash",
        )
        drift = [field for field in immutable_fields if previous.get(field) != item.get(field)]
        if drift:
            raise BoundedParallelError(
                f"first-lock inconsistency for event {event_hash}: " + ", ".join(drift)
            )
        # Prefer the non-deduplicated first-writer evidence path if both deliveries are present.
        if previous.get("deduplicated") and not item.get("deduplicated"):
            by_event[event_hash] = dict(item)
    out: list[dict[str, Any]] = []
    for event_hash, base in sorted(
        by_event.items(),
        key=lambda pair: (
            str(pair[1]["observed_at"]),
            str(pair[1]["knowable_at"]),
            str(pair[1]["event_id"]),
            pair[0],
        ),
    ):
        item = dict(base)
        item["transport_delivery_count"] = delivery_counts[event_hash]
        out.append(item)
    return out


def run_bounded_batch(
    *,
    workers: int,
    preflight: Mapping[str, Any],
    run_receipt_path: Path,
    canonical_manifest_path: Path,
) -> dict[str, Any]:
    if preflight.get("status") != "PASS":
        raise BoundedParallelError("preflight did not pass")
    started = utc_now()
    deliveries: list[dict[str, Any]] = []
    rounds = 0
    errors: list[str] = []
    ctx = mp.get_context("spawn")
    try:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as pool:
            while True:
                rounds += 1
                futures = [pool.submit(_consume_one_worker) for _ in range(workers)]
                round_results: list[dict[str, Any]] = []
                round_errors: list[str] = []
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                    except Exception as exc:  # child exceptions are data-safe: failed message is not deleted
                        round_errors.append(f"{type(exc).__name__}: {str(exc)[:2000]}")
                        continue
                    round_results.append(result)
                for result in round_results:
                    if result.get("received"):
                        deliveries.append(canonical_delivery(result))
                if round_errors:
                    errors.extend(round_errors)
                    break
                if round_results and all(not item.get("received") for item in round_results):
                    break
                if len(round_results) != workers:
                    errors.append(
                        f"worker round returned {len(round_results)} results for {workers} workers"
                    )
                    break
    except KeyboardInterrupt:
        errors.append("KeyboardInterrupt")

    unique_events = canonical_unique_events(deliveries)
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "CANONICAL_BOUNDED_3MO_FRANKIE_EVIDENCE",
        "status": "COMPLETE" if not errors else "PARTIAL_FAIL_CLOSED",
        "source_window": {
            "start": SOURCE_WINDOW_START,
            "end_exclusive": SOURCE_WINDOW_END_EXCLUSIVE,
        },
        "canonical_order": "observed_at_then_knowable_at_then_event_id_then_event_hash",
        "scientific_event_count": len(unique_events),
        "transport_delivery_count": len(deliveries),
        "duplicate_transport_delivery_count": len(deliveries) - len(unique_events),
        "events": unique_events,
    }
    manifest["manifest_sha256"] = sha256_json(manifest)
    atomic_write_json(canonical_manifest_path, manifest)

    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "BOUNDED_3MO_FRANKIE_PARALLEL_RUN",
        "status": "COMPLETE" if not errors else "FAIL_CLOSED",
        "started_at_utc": started,
        "finished_at_utc": utc_now(),
        "source_window": {
            "start": SOURCE_WINDOW_START,
            "end_exclusive": SOURCE_WINDOW_END_EXCLUSIVE,
        },
        "worker_count": workers,
        "parallelization_unit": "SCIENTIFICALLY_SELF_CONTAINED_POST_V4_FRANKIE_EVENT",
        "event_lane_order_changed": False,
        "event_scientific_calculation_changed": False,
        "event_identity_changed": False,
        "causal_clock_changed": False,
        "feature_definition_changed": False,
        "chain_or_case_retention_changed": False,
        "first_lock_semantics_changed": False,
        "provenance_or_integrity_rules_changed": False,
        "deterministic_adjudication_changed": False,
        "frankie_inputs_changed": False,
        "raw_mbo_or_v4_program_changed": False,
        "round_count": rounds,
        "transport_delivery_count": len(deliveries),
        "scientific_event_count": len(unique_events),
        "duplicate_transport_delivery_count": len(deliveries) - len(unique_events),
        "canonical_manifest_path": str(canonical_manifest_path),
        "canonical_manifest_sha256": manifest["manifest_sha256"],
        "preflight_receipt_sha256": preflight.get("receipt_sha256"),
        "runtime_git_blobs": preflight.get("runtime_git_blobs"),
        "errors": errors,
    }
    receipt["receipt_sha256"] = sha256_json(receipt)
    atomic_write_json(run_receipt_path, receipt)
    if errors:
        raise BoundedParallelError("bounded Frankie batch failed closed: " + "; ".join(errors))
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--systemd-unit", default=None)
    parser.add_argument("--require-systemd", action="store_true")
    parser.add_argument("--canary-seconds", type=float, default=2.0)
    parser.add_argument(
        "--preflight-receipt",
        type=Path,
        default=Path("/var/lib/markets/frankie/bounded-3mo/preflight.json"),
    )
    parser.add_argument(
        "--run-receipt",
        type=Path,
        default=Path("/var/lib/markets/frankie/bounded-3mo/run_receipt.json"),
    )
    parser.add_argument(
        "--canonical-manifest",
        type=Path,
        default=Path("/var/lib/markets/frankie/bounded-3mo/canonical_evidence.json"),
    )
    parser.add_argument("--preflight-only", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.workers != DEFAULT_WORKERS:
        print(
            json.dumps(
                {"status": "FAIL_CLOSED", "error": f"bounded run requires exactly {DEFAULT_WORKERS} workers"},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    try:
        preflight = build_preflight(
            workers=args.workers,
            systemd_unit=args.systemd_unit,
            require_systemd=args.require_systemd,
            canary_seconds=args.canary_seconds,
        )
        atomic_write_json(args.preflight_receipt, preflight)
        print(json.dumps(preflight, sort_keys=True), flush=True)
        if preflight["status"] != "PASS":
            return 2
        if args.preflight_only:
            return 0
        receipt = run_bounded_batch(
            workers=args.workers,
            preflight=preflight,
            run_receipt_path=args.run_receipt,
            canonical_manifest_path=args.canonical_manifest,
        )
        print(json.dumps(receipt, sort_keys=True), flush=True)
        return 0
    except BoundedParallelError as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": str(exc)[:4000]}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
