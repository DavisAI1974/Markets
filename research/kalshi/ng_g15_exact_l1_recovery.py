#!/usr/bin/env python3
"""Plan and safely acquire the exact raw-contract L1 corpus missing from G15.

The committed G15 basis gate distinguishes a useful specific-leg MBO replay from
an exact matched L1+MBO replay. This module closes only the acquisition seam:

* read the truthful committed inventory;
* identify canonical G15 days whose L1 leg is absent or on the wrong contract;
* group those days by exact raw contract;
* emit cost-first Databento ``mbp-1`` batch requests using
  ``stype_in=raw_symbol``;
* optionally submit and download those historical requests behind an explicit
  paid-pull confirmation and maximum-cost gate.

Downloaded DBN files are preserved raw. A download receipt proves only which
bytes were downloaded; it deliberately does not claim publisher, instrument,
definition-period, or event-time correctness. Those claims remain blocked until
the existing normalizer, inventory, and corpus-basis gate inspect the files.

No live-data assumption, execution authority, manifest mutation, or brain
mutation is granted here.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from ng_g15_corpus_basis_gate import (
    CANONICAL_DATES,
    EXPECTED,
    evaluate_manifest,
    validate_report,
)

PLAN_SCHEMA = "ng_g15_exact_l1_recovery_plan.v1"
RECEIPT_SCHEMA = "ng_g15_exact_l1_download_receipt.v1"
DATASET = "GLBX.MDP3"
SCHEMA = "mbp-1"
STYPE_IN = "raw_symbol"
_ALLOWED_SYMBOL = re.compile(r"^NG[A-Z][0-9]{2}$")


class L1RecoveryError(ValueError):
    """Raised for malformed plans, receipts, or unsafe acquisition requests."""


def _sha(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_range(start: str, end: str) -> None:
    try:
        start_day = date.fromisoformat(start[:10])
        end_day = date.fromisoformat(end[:10])
    except (TypeError, ValueError) as error:
        raise L1RecoveryError("start/end must begin with ISO calendar dates") from error
    if end_day <= start_day:
        raise L1RecoveryError("end must be strictly after start")
    if (end_day - start_day).days > 31:
        raise L1RecoveryError("one exact-L1 recovery request may not exceed 31 days")


def _next_day(day: str) -> str:
    parsed = date(int(day[:4]), int(day[4:6]), int(day[6:8]))
    return (parsed + timedelta(days=1)).isoformat()


def _iso_day(day: str) -> str:
    return f"{day[:4]}-{day[4:6]}-{day[6:8]}"


def _request_for_contract(contract: str, days: list[str]) -> dict[str, Any]:
    if not _ALLOWED_SYMBOL.fullmatch(contract):
        raise L1RecoveryError(f"unsafe or non-NG raw symbol: {contract!r}")
    ordered = sorted(set(days))
    if not ordered:
        raise L1RecoveryError("cannot build an empty recovery request")
    instrument_ids = {int(EXPECTED[day]["instrument_id"]) for day in ordered}
    if len(instrument_ids) != 1:
        raise L1RecoveryError(f"{contract}: canonical days map to multiple instrument IDs")
    start = _iso_day(ordered[0])
    end_exclusive = _next_day(ordered[-1])
    slug = contract.lower()
    out_dir = f"data/nymex_l1_exact/g15/{slug}"
    cost_command = (
        "python research/kalshi/ng_g15_exact_l1_recovery.py cost "
        f"--symbol {contract} --start {start} --end {end_exclusive}"
    )
    pull_command = (
        "python research/kalshi/ng_g15_exact_l1_recovery.py pull "
        f"--symbol {contract} --start {start} --end {end_exclusive} "
        f"--output-dir {out_dir} --confirm-paid-pull --max-cost <LIMIT_USD>"
    )
    return {
        "dataset": DATASET,
        "schema": SCHEMA,
        "stype_in": STYPE_IN,
        "symbol": contract,
        "expected_instrument_id": next(iter(instrument_ids)),
        "canonical_days": ordered,
        "start": start,
        "end_exclusive": end_exclusive,
        "output_dir": out_dir,
        "cost_command": cost_command,
        "pull_command": pull_command,
        "identity_claim_after_download": "UNKNOWN_UNTIL_NORMALIZED_AND_INVENTORIED",
        "raw_files_immutable": True,
    }


def build_recovery_plan(inventory_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a cost-first exact-contract acquisition plan from observed inventory."""
    source_before = copy.deepcopy(inventory_rows)
    basis = evaluate_manifest(inventory_rows)
    validate_report(basis)
    if inventory_rows != source_before:
        raise L1RecoveryError("basis evaluation mutated source inventory")

    blocked_days = list(basis.get("l1_blocked_days") or [])
    wrong_basis_days = list(basis.get("l1_wrong_basis_days") or [])
    requests: list[dict[str, Any]] = []
    if basis["status"] == "MATCHED_L1_MBO_READY":
        status = "NO_RECOVERY_REQUIRED"
    elif not basis.get("mbo_specific_leg_ready"):
        status = "BLOCKED"
    else:
        by_contract: dict[str, list[str]] = {}
        for day in blocked_days:
            if day not in EXPECTED:
                raise L1RecoveryError(f"basis report contains noncanonical day {day}")
            by_contract.setdefault(str(EXPECTED[day]["contract"]), []).append(day)
        requests = [
            _request_for_contract(contract, days)
            for contract, days in sorted(by_contract.items())
        ]
        status = "RECOVERY_PLAN_READY" if requests else "BLOCKED"

    plan = {
        "schema": PLAN_SCHEMA,
        "group": 15,
        "status": status,
        "basis_report_fingerprint": basis["fingerprint"],
        "basis_status": basis["status"],
        "canonical_dates": list(CANONICAL_DATES),
        "blocked_l1_days": blocked_days,
        "wrong_basis_l1_days": wrong_basis_days,
        "requests": requests,
        "next_validation_chain": [
            "download raw DBN without modification",
            "normalize with exact dataset/publisher/instrument/raw_symbol/definition identity",
            "rebuild g15_mbo_l1_manifest.json from observed files",
            "run ng_g15_corpus_basis_gate.py",
            "require MATCHED_L1_MBO_READY before relabeling the replay",
        ],
        "remote_presence_claimed": False,
        "paid_pull_authority": False,
        "may_mutate_source_inventory": False,
        "may_update_manifest_without_observation": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
    }
    plan["fingerprint"] = _sha(plan)
    return plan


def validate_plan(plan: dict[str, Any]) -> None:
    candidate = copy.deepcopy(plan)
    observed = candidate.pop("fingerprint", None)
    if candidate.get("schema") != PLAN_SCHEMA:
        raise L1RecoveryError("unexpected recovery-plan schema")
    if observed != _sha(candidate):
        raise L1RecoveryError("recovery-plan fingerprint mismatch")
    if candidate.get("execution_authority") is not False:
        raise L1RecoveryError("recovery plan cannot grant execution authority")
    if candidate.get("paid_pull_authority") is not False:
        raise L1RecoveryError("plan itself cannot authorize a paid pull")
    if candidate.get("may_update_manifest_without_observation") is not False:
        raise L1RecoveryError("plan cannot update manifest without observation")
    requests = candidate.get("requests")
    if not isinstance(requests, list):
        raise L1RecoveryError("recovery requests must be a list")
    seen_days: set[str] = set()
    for request in requests:
        if request.get("dataset") != DATASET:
            raise L1RecoveryError("request dataset mismatch")
        if request.get("schema") != SCHEMA or request.get("stype_in") != STYPE_IN:
            raise L1RecoveryError("request must use exact raw-contract mbp-1")
        symbol = str(request.get("symbol") or "")
        if not _ALLOWED_SYMBOL.fullmatch(symbol):
            raise L1RecoveryError("request raw symbol is invalid")
        days = request.get("canonical_days")
        if not isinstance(days, list) or not days:
            raise L1RecoveryError("request canonical_days is empty")
        for day in days:
            if day not in EXPECTED or EXPECTED[day]["contract"] != symbol:
                raise L1RecoveryError(f"{day}: request contract is not canonical")
            if day in seen_days:
                raise L1RecoveryError(f"{day}: duplicate recovery ownership")
            seen_days.add(day)
    status = candidate.get("status")
    blocked_days = sorted(candidate.get("blocked_l1_days") or [])
    if status == "RECOVERY_PLAN_READY":
        if sorted(seen_days) != blocked_days:
            raise L1RecoveryError("requests do not cover blocked L1 days exactly once")
    elif requests:
        raise L1RecoveryError(f"{status}: recovery requests are not permitted")


def _historical_client():
    try:
        import databento as db
    except ImportError as error:
        raise L1RecoveryError("databento package is required for cost/pull modes") from error
    key = os.environ.get("DATABENTO_API_KEY")
    if not key:
        raise L1RecoveryError("DATABENTO_API_KEY is required for cost/pull modes")
    return db.Historical(key)


def _estimate_cost(client: Any, *, symbol: str, start: str, end: str) -> float:
    _validate_range(start, end)
    if not _ALLOWED_SYMBOL.fullmatch(symbol):
        raise L1RecoveryError("only exact NG raw contracts are permitted")
    value = client.metadata.get_cost(
        dataset=DATASET,
        symbols=[symbol],
        stype_in=STYPE_IN,
        schema=SCHEMA,
        start=start,
        end=end,
    )
    cost = float(value)
    if cost < 0:
        raise L1RecoveryError("Databento returned a negative cost")
    return cost


def _job_value(job: Any, name: str) -> Any:
    if isinstance(job, dict):
        return job.get(name)
    return getattr(job, name, None)


def acquire_exact_l1(
    *,
    symbol: str,
    start: str,
    end: str,
    output_dir: Path,
    max_cost: float,
    confirm_paid_pull: bool,
    poll_s: float = 20.0,
    timeout_s: float = 5400.0,
    client: Any | None = None,
) -> dict[str, Any]:
    """Cost-gate, submit, and download raw exact-contract MBP-1 DBN files."""
    if not confirm_paid_pull:
        raise L1RecoveryError("pull mode requires --confirm-paid-pull")
    if max_cost < 0:
        raise L1RecoveryError("max_cost must be nonnegative")
    _validate_range(start, end)
    if not _ALLOWED_SYMBOL.fullmatch(symbol):
        raise L1RecoveryError("only exact NG raw contracts are permitted")
    if output_dir.exists():
        raise L1RecoveryError(f"output directory already exists: {output_dir}")

    client = client or _historical_client()
    cost = _estimate_cost(client, symbol=symbol, start=start, end=end)
    if cost > max_cost:
        raise L1RecoveryError(
            f"estimated historical cost ${cost:.4f} exceeds --max-cost ${max_cost:.4f}"
        )

    job = client.batch.submit_job(
        dataset=DATASET,
        symbols=[symbol],
        stype_in=STYPE_IN,
        schema=SCHEMA,
        start=start,
        end=end,
        encoding="dbn",
        compression="zstd",
        split_duration="day",
    )
    job_id = _job_value(job, "id")
    if not job_id:
        raise L1RecoveryError("Databento batch submission returned no job ID")

    waited = 0.0
    state = str(_job_value(job, "state") or "")
    while state != "done" and waited < timeout_s:
        if state in {"expired", "failed"}:
            raise L1RecoveryError(f"Databento batch job {job_id} ended in state {state}")
        time.sleep(poll_s)
        waited += poll_s
        details = client.batch.get_job_details(job_id)
        state = str(_job_value(details, "state") or "")
    if state != "done":
        raise L1RecoveryError(
            f"Databento batch job {job_id} not done after {int(timeout_s)}s (state {state})"
        )

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=str(output_dir.parent)))
    try:
        client.batch.download(job_id, output_dir=str(staging))
        files = sorted(
            path for path in staging.rglob("*")
            if path.is_file() and (path.name.endswith(".dbn") or path.name.endswith(".dbn.zst"))
        )
        if not files:
            raise L1RecoveryError("Databento download contained no DBN files")
        file_rows = [
            {
                "relative_path": str(path.relative_to(staging)),
                "size_bytes": path.stat().st_size,
                "sha256": _file_sha256(path),
            }
            for path in files
        ]
        if any(row["size_bytes"] <= 0 for row in file_rows):
            raise L1RecoveryError("Databento download contained an empty DBN file")
        staging.rename(output_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    receipt = {
        "schema": RECEIPT_SCHEMA,
        "dataset": DATASET,
        "schema_requested": SCHEMA,
        "stype_in": STYPE_IN,
        "symbol_requested": symbol,
        "start": start,
        "end_exclusive": end,
        "estimated_cost_usd": cost,
        "max_cost_usd": float(max_cost),
        "job_id": str(job_id),
        "output_dir": str(output_dir),
        "files": file_rows,
        "downloaded_bytes": sum(int(row["size_bytes"]) for row in file_rows),
        "identity_status": "UNKNOWN_UNTIL_NORMALIZED_AND_INVENTORIED",
        "remote_presence_claimed_before_download": False,
        "raw_files_immutable": True,
        "may_update_manifest_without_observation": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
    }
    receipt["fingerprint"] = _sha(receipt)
    return receipt


def validate_receipt(receipt: dict[str, Any], *, verify_files: bool = False) -> None:
    candidate = copy.deepcopy(receipt)
    observed = candidate.pop("fingerprint", None)
    if candidate.get("schema") != RECEIPT_SCHEMA:
        raise L1RecoveryError("unexpected download-receipt schema")
    if observed != _sha(candidate):
        raise L1RecoveryError("download-receipt fingerprint mismatch")
    if candidate.get("identity_status") != "UNKNOWN_UNTIL_NORMALIZED_AND_INVENTORIED":
        raise L1RecoveryError("download receipt cannot claim normalized identity")
    if candidate.get("execution_authority") is not False:
        raise L1RecoveryError("download receipt cannot grant execution authority")
    files = candidate.get("files")
    if not isinstance(files, list) or not files:
        raise L1RecoveryError("download receipt contains no files")
    if verify_files:
        root = Path(str(candidate.get("output_dir") or ""))
        for row in files:
            path = (root / str(row.get("relative_path") or "")).resolve()
            try:
                path.relative_to(root.resolve())
            except ValueError as error:
                raise L1RecoveryError("receipt file escapes output directory") from error
            if not path.is_file():
                raise L1RecoveryError(f"downloaded file is missing: {path}")
            if path.stat().st_size != int(row.get("size_bytes") or -1):
                raise L1RecoveryError(f"downloaded file size changed: {path}")
            if _file_sha256(path) != row.get("sha256"):
                raise L1RecoveryError(f"downloaded file hash changed: {path}")


def selftest() -> int:
    from ng_g15_corpus_basis_gate import _fixture_rows

    rows = _fixture_rows(wrong_pre_roll_l1=True)
    plan = build_recovery_plan(rows)
    validate_plan(plan)
    assert plan["status"] == "RECOVERY_PLAN_READY"
    assert len(plan["requests"]) == 1
    request = plan["requests"][0]
    assert request["symbol"] == "NGJ26"
    assert request["start"] == "2026-03-13"
    assert request["end_exclusive"] == "2026-03-20"
    assert request["stype_in"] == "raw_symbol"
    print("[ng_g15_exact_l1_recovery] selftest PASS")
    return 0


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan or acquire exact-contract G15 L1 history")
    sub = parser.add_subparsers(dest="mode", required=True)

    plan_parser = sub.add_parser("plan")
    plan_parser.add_argument("--manifest", type=Path, required=True)
    plan_parser.add_argument("--out", type=Path, required=True)

    cost_parser = sub.add_parser("cost")
    cost_parser.add_argument("--symbol", required=True)
    cost_parser.add_argument("--start", required=True)
    cost_parser.add_argument("--end", required=True)

    pull_parser = sub.add_parser("pull")
    pull_parser.add_argument("--symbol", required=True)
    pull_parser.add_argument("--start", required=True)
    pull_parser.add_argument("--end", required=True)
    pull_parser.add_argument("--output-dir", type=Path, required=True)
    pull_parser.add_argument("--receipt-out", type=Path)
    pull_parser.add_argument("--max-cost", type=float, required=True)
    pull_parser.add_argument("--confirm-paid-pull", action="store_true")
    pull_parser.add_argument("--poll-s", type=float, default=20.0)
    pull_parser.add_argument("--timeout-s", type=float, default=5400.0)

    verify_parser = sub.add_parser("verify-receipt")
    verify_parser.add_argument("--receipt", type=Path, required=True)
    verify_parser.add_argument("--verify-files", action="store_true")

    sub.add_parser("selftest")
    args = parser.parse_args()

    if args.mode == "selftest":
        return selftest()
    if args.mode == "plan":
        rows = json.loads(args.manifest.read_text(encoding="utf-8"))
        plan = build_recovery_plan(rows)
        validate_plan(plan)
        _write_json(args.out, plan)
        print(json.dumps({
            "status": plan["status"],
            "requests": len(plan["requests"]),
            "blocked_l1_days": plan["blocked_l1_days"],
            "out": str(args.out),
        }, indent=2))
        return 0 if plan["status"] != "BLOCKED" else 2
    if args.mode == "cost":
        client = _historical_client()
        cost = _estimate_cost(client, symbol=args.symbol, start=args.start, end=args.end)
        print(json.dumps({
            "dataset": DATASET,
            "schema": SCHEMA,
            "stype_in": STYPE_IN,
            "symbol": args.symbol,
            "start": args.start,
            "end_exclusive": args.end,
            "estimated_cost_usd": cost,
        }, indent=2))
        return 0
    if args.mode == "pull":
        receipt = acquire_exact_l1(
            symbol=args.symbol,
            start=args.start,
            end=args.end,
            output_dir=args.output_dir,
            max_cost=args.max_cost,
            confirm_paid_pull=args.confirm_paid_pull,
            poll_s=args.poll_s,
            timeout_s=args.timeout_s,
        )
        validate_receipt(receipt, verify_files=True)
        receipt_out = args.receipt_out or args.output_dir.with_name(args.output_dir.name + "_receipt.json")
        _write_json(receipt_out, receipt)
        print(json.dumps({
            "status": "DOWNLOADED_UNVALIDATED_IDENTITY",
            "job_id": receipt["job_id"],
            "files": len(receipt["files"]),
            "bytes": receipt["downloaded_bytes"],
            "receipt": str(receipt_out),
        }, indent=2))
        return 0

    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    validate_receipt(receipt, verify_files=args.verify_files)
    print(json.dumps({"status": "VALID", "receipt": str(args.receipt)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
