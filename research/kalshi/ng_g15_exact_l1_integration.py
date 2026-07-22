#!/usr/bin/env python3
"""Normalize and promote downloaded exact-contract G15 L1 into a truthful corpus bundle.

This module closes the seam after ``ng_g15_exact_l1_recovery.py`` downloads raw
NGJ26 MBP-1 bytes. It does not download data and it never treats a download
receipt as proof of market identity. Promotion requires all of the following:

* a fingerprint-valid recovery plan and download receipt;
* an explicitly confirmed file-to-session map covering every blocked G15 day
  exactly once;
* observed definition identity for the exact raw contract;
* successful trade-only normalization of every raw file;
* unchanged raw file hashes before and after normalization;
* a regenerated corpus-basis report equal to ``MATCHED_L1_MBO_READY``.

The integration is first published as an atomic, independently verifiable bundle.
Replacing the canonical inventory is a separate, explicit promotion operation
that verifies the existing inventory still matches the source fingerprint and
writes a backup before atomic replacement.

No actual outcomes are read. No blind forecast, posterior, brain, or execution
authority is touched.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import math
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from ng_g15_corpus_basis_gate import EXPECTED, evaluate_manifest, validate_report
from ng_g15_exact_l1_recovery import validate_plan, validate_receipt
from ng_historical_normalize import normalize_file

DAY_MAP_SCHEMA = "ng_g15_exact_l1_day_map.v1"
BUNDLE_SCHEMA = "ng_g15_exact_l1_integration_bundle.v1"
RECEIPT_SCHEMA = "ng_g15_exact_l1_integration_receipt.v1"
DATASET = "GLBX.MDP3"
_DATE_TOKEN = re.compile(r"(?<!\d)(20\d{2})[-_]?([01]\d)[-_]?([0-3]\d)(?!\d)")


class ExactL1IntegrationError(ValueError):
    """Raised when exact-contract L1 cannot be truthfully integrated."""


def _sha(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _finite(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ExactL1IntegrationError(f"invalid {name}: {value!r}") from error
    if not math.isfinite(number):
        raise ExactL1IntegrationError(f"invalid {name}: {value!r}")
    return number


def _iso_utc(seconds: float) -> str:
    return dt.datetime.fromtimestamp(seconds, tz=dt.timezone.utc).isoformat()


def _request_for_receipt(plan: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    matches = [
        row for row in plan.get("requests") or []
        if row.get("dataset") == receipt.get("dataset")
        and row.get("schema") == receipt.get("schema_requested")
        and row.get("stype_in") == receipt.get("stype_in")
        and row.get("symbol") == receipt.get("symbol_requested")
        and row.get("start") == receipt.get("start")
        and row.get("end_exclusive") == receipt.get("end_exclusive")
    ]
    if len(matches) != 1:
        raise ExactL1IntegrationError("download receipt does not match exactly one recovery request")
    return copy.deepcopy(matches[0])


def _candidate_day(relative_path: str, allowed_days: set[str]) -> str | None:
    candidates = set()
    for match in _DATE_TOKEN.finditer(relative_path):
        day = "".join(match.groups())
        if day in allowed_days:
            candidates.add(day)
    return next(iter(candidates)) if len(candidates) == 1 else None


def build_day_map_template(plan: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    """Build a non-authoritative review template from receipt filenames."""
    validate_plan(plan)
    validate_receipt(receipt, verify_files=False)
    request = _request_for_receipt(plan, receipt)
    allowed = set(request["canonical_days"])
    entries = []
    for row in receipt["files"]:
        relative = str(row.get("relative_path") or "")
        candidate = _candidate_day(relative, allowed)
        entries.append({
            "relative_path": relative,
            "candidate_session_day": candidate,
            "session_day": candidate,
            "confirmed": False,
        })
    template = {
        "schema": DAY_MAP_SCHEMA,
        "status": "REVIEW_REQUIRED",
        "plan_fingerprint": plan["fingerprint"],
        "receipt_fingerprint": receipt["fingerprint"],
        "request_symbol": request["symbol"],
        "required_session_days": list(request["canonical_days"]),
        "entries": entries,
        "filename_dates_are_non_authoritative": True,
        "requires_explicit_confirmation": True,
        "execution_authority": False,
    }
    template["fingerprint"] = _sha(template)
    return template


def validate_day_map(
    day_map: dict[str, Any],
    *,
    plan: dict[str, Any],
    receipt: dict[str, Any],
    require_confirmed: bool = True,
) -> dict[str, str]:
    validate_plan(plan)
    validate_receipt(receipt, verify_files=False)
    request = _request_for_receipt(plan, receipt)
    candidate = copy.deepcopy(day_map)
    observed = candidate.pop("fingerprint", None)
    if candidate.get("schema") != DAY_MAP_SCHEMA:
        raise ExactL1IntegrationError("unexpected exact-L1 day-map schema")
    if observed != _sha(candidate):
        raise ExactL1IntegrationError("exact-L1 day-map fingerprint mismatch")
    if candidate.get("plan_fingerprint") != plan.get("fingerprint"):
        raise ExactL1IntegrationError("day map references a different recovery plan")
    if candidate.get("receipt_fingerprint") != receipt.get("fingerprint"):
        raise ExactL1IntegrationError("day map references a different download receipt")
    if candidate.get("execution_authority") is not False:
        raise ExactL1IntegrationError("day map cannot grant execution authority")

    receipt_paths = {str(row.get("relative_path") or "") for row in receipt["files"]}
    entries = candidate.get("entries")
    if not isinstance(entries, list):
        raise ExactL1IntegrationError("day-map entries must be a list")
    mapping: dict[str, str] = {}
    seen_days: set[str] = set()
    for entry in entries:
        relative = str(entry.get("relative_path") or "")
        day = str(entry.get("session_day") or "")
        if relative not in receipt_paths:
            raise ExactL1IntegrationError(f"day map contains an unknown receipt file: {relative}")
        if relative in mapping:
            raise ExactL1IntegrationError(f"day map duplicates receipt file: {relative}")
        if day not in request["canonical_days"]:
            raise ExactL1IntegrationError(f"day map assigns non-requested session day: {day!r}")
        if day in seen_days:
            raise ExactL1IntegrationError(f"day map assigns session day more than once: {day}")
        if require_confirmed and entry.get("confirmed") is not True:
            raise ExactL1IntegrationError(f"day map entry is not explicitly confirmed: {relative}")
        mapping[relative] = day
        seen_days.add(day)
    if set(mapping) != receipt_paths:
        missing = sorted(receipt_paths - set(mapping))
        raise ExactL1IntegrationError("day map does not cover receipt files: " + ", ".join(missing))
    required_days = set(request["canonical_days"])
    if seen_days != required_days:
        missing = sorted(required_days - seen_days)
        extra = sorted(seen_days - required_days)
        raise ExactL1IntegrationError(f"day map coverage mismatch; missing={missing} extra={extra}")
    return mapping


def validate_definition_observation(definition: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    candidate = copy.deepcopy(definition)
    if candidate.get("dataset") != DATASET:
        raise ExactL1IntegrationError("definition dataset must be GLBX.MDP3")
    if str(candidate.get("raw_symbol") or "") != request["symbol"]:
        raise ExactL1IntegrationError("definition raw symbol differs from recovery request")
    try:
        instrument_id = int(candidate.get("instrument_id"))
        publisher_id = int(candidate.get("publisher_id"))
    except (TypeError, ValueError, OverflowError) as error:
        raise ExactL1IntegrationError("definition publisher/instrument identity is invalid") from error
    if instrument_id != int(request["expected_instrument_id"]):
        raise ExactL1IntegrationError("definition instrument differs from canonical request identity")
    if publisher_id <= 0:
        raise ExactL1IntegrationError("definition publisher_id must be positive")
    definition_date = str(candidate.get("definition_date") or "")
    if not definition_date:
        raise ExactL1IntegrationError("definition_date is required")
    start = _finite(candidate.get("definition_start_s"), "definition_start_s")
    end = _finite(candidate.get("definition_end_s"), "definition_end_s")
    if end < start:
        raise ExactL1IntegrationError("definition validity period moves backward")
    return {
        "dataset": DATASET,
        "publisher_id": publisher_id,
        "instrument_id": instrument_id,
        "raw_symbol": request["symbol"],
        "definition_date": definition_date,
        "definition_start_s": start,
        "definition_end_s": end,
        "observed_at": candidate.get("observed_at"),
        "source": candidate.get("source"),
        "source_fingerprint": _sha(candidate),
    }


def _receipt_file_rows(receipt: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in receipt["files"]:
        relative = str(row.get("relative_path") or "")
        if not relative or relative in rows:
            raise ExactL1IntegrationError("download receipt has missing or duplicate relative paths")
        rows[relative] = copy.deepcopy(row)
    return rows


def _inventory_by_day(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        raise ExactL1IntegrationError("source inventory must be a list")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        day = str(row.get("date") or "").replace("-", "")
        if day in result:
            raise ExactL1IntegrationError(f"source inventory duplicates day {day}")
        result[day] = row
    missing = sorted(set(EXPECTED) - set(result))
    if missing:
        raise ExactL1IntegrationError("source inventory is missing G15 days: " + ", ".join(missing))
    return result


def build_integration_bundle(
    *,
    inventory_rows: list[dict[str, Any]],
    plan: dict[str, Any],
    receipt: dict[str, Any],
    day_map: dict[str, Any],
    definition: dict[str, Any],
    bundle_dir: Path,
) -> dict[str, Any]:
    """Create an atomic verified bundle; do not replace the canonical inventory."""
    if bundle_dir.exists():
        raise ExactL1IntegrationError(f"bundle directory already exists: {bundle_dir}")
    validate_plan(plan)
    validate_receipt(receipt, verify_files=True)
    request = _request_for_receipt(plan, receipt)
    mapping = validate_day_map(day_map, plan=plan, receipt=receipt, require_confirmed=True)
    identity = validate_definition_observation(definition, request)

    source_before = copy.deepcopy(inventory_rows)
    source_fingerprint = _sha(source_before)
    _inventory_by_day(source_before)
    basis_before = evaluate_manifest(source_before)
    validate_report(basis_before)
    if basis_before.get("mbo_specific_leg_ready") is not True:
        raise ExactL1IntegrationError("specific-leg MBO basis must be ready before exact-L1 integration")
    if sorted(basis_before.get("l1_blocked_days") or []) != sorted(request["canonical_days"]):
        raise ExactL1IntegrationError("recovery request no longer matches the inventory's blocked L1 days")

    root = Path(str(receipt.get("output_dir") or "")).resolve()
    receipt_rows = _receipt_file_rows(receipt)
    bundle_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{bundle_dir.name}.", dir=str(bundle_dir.parent)))
    normalized_dir = staging / "normalized"
    reports: list[dict[str, Any]] = []
    try:
        for relative, day in sorted(mapping.items(), key=lambda item: item[1]):
            raw_path = (root / relative).resolve()
            try:
                raw_path.relative_to(root)
            except ValueError as error:
                raise ExactL1IntegrationError("mapped raw file escapes receipt output directory") from error
            receipt_row = receipt_rows[relative]
            raw_hash_before = _file_sha256(raw_path)
            if raw_hash_before != receipt_row.get("sha256"):
                raise ExactL1IntegrationError(f"raw file hash differs from download receipt: {relative}")
            output = normalized_dir / f"{day}_{request['symbol']}_l1_trades.jsonl"
            report = normalize_file(
                raw_path,
                kind="trade",
                dataset=identity["dataset"],
                publisher_id=identity["publisher_id"],
                instrument_id=identity["instrument_id"],
                raw_symbol=identity["raw_symbol"],
                definition_date=identity["definition_date"],
                session_day=day,
                output=output,
                skip_nonmatching=True,
            )
            report = copy.deepcopy(report)
            report["input"] = relative
            report["output"] = str(output.relative_to(staging))
            report["path_basis"] = "integration_bundle_relative"
            event_start = _finite(report.get("event_start_s"), "event_start_s")
            event_end = _finite(report.get("event_end_s"), "event_end_s")
            if event_start < identity["definition_start_s"] or event_end > identity["definition_end_s"]:
                raise ExactL1IntegrationError(f"{day}: normalized events fall outside observed definition period")
            if event_end < event_start:
                raise ExactL1IntegrationError(f"{day}: normalized event range moves backward")
            if _file_sha256(raw_path) != raw_hash_before:
                raise ExactL1IntegrationError(f"normalization changed raw input bytes: {relative}")
            reports.append({
                "session_day": day,
                "raw_relative_path": relative,
                "raw_size_bytes": int(receipt_row["size_bytes"]),
                "raw_sha256": raw_hash_before,
                "normalized_relative_path": str(output.relative_to(staging)),
                "normalization_report": report,
            })

        patched = copy.deepcopy(source_before)
        patched_by_day = _inventory_by_day(patched)
        for row in reports:
            day = row["session_day"]
            target = patched_by_day[day]
            report = row["normalization_report"]
            target.update({
                "l1_present": True,
                "l1_readable": True,
                "l1_bytes": row["raw_size_bytes"],
                "l1_instrument_id": [identity["instrument_id"]],
                "l1_n_rows": int(report["input_record_count"]),
                "l1_n_trades": int(report["record_count"]),
                "l1_basis_correct": True,
                "l1_raw_symbol": identity["raw_symbol"],
                "l1_definition_date": identity["definition_date"],
                "l1_first_event_utc": _iso_utc(float(report["event_start_s"])),
                "l1_last_event_utc": _iso_utc(float(report["event_end_s"])),
                "l1_source_kind": "exact_raw_contract_mbp1_trade_events",
                "l1_raw_relative_path": row["raw_relative_path"],
                "l1_raw_sha256": row["raw_sha256"],
                "l1_normalized_relative_path": row["normalized_relative_path"],
                "l1_normalized_sha256": report["sha256"],
                "l1_inventory_observed": True,
            })

        untouched_days = sorted(set(EXPECTED) - set(request["canonical_days"]))
        original_by_day = _inventory_by_day(source_before)
        for day in untouched_days:
            if patched_by_day[day] != original_by_day[day]:
                raise ExactL1IntegrationError(f"integration changed an unrequested inventory day: {day}")

        basis_after = evaluate_manifest(patched)
        validate_report(basis_after)
        if basis_after.get("status") != "MATCHED_L1_MBO_READY":
            raise ExactL1IntegrationError(
                f"integrated inventory did not reach MATCHED_L1_MBO_READY: {basis_after.get('status')}"
            )
        if inventory_rows != source_before:
            raise ExactL1IntegrationError("integration mutated source inventory")

        _atomic_json(staging / "candidate_g15_mbo_l1_manifest.json", patched)
        _atomic_json(staging / "candidate_g15_corpus_basis_report.json", basis_after)
        integration_receipt = {
            "schema": RECEIPT_SCHEMA,
            "group": 15,
            "status": "MATCHED_L1_MBO_READY_CANDIDATE",
            "source_inventory_fingerprint": source_fingerprint,
            "source_basis_report_fingerprint": basis_before["fingerprint"],
            "recovery_plan_fingerprint": plan["fingerprint"],
            "download_receipt_fingerprint": receipt["fingerprint"],
            "day_map_fingerprint": day_map["fingerprint"],
            "definition_observation": identity,
            "integrated_session_days": list(request["canonical_days"]),
            "normalization_reports": reports,
            "candidate_inventory_fingerprint": _sha(patched),
            "candidate_basis_report_fingerprint": basis_after["fingerprint"],
            "raw_files_immutable": True,
            "actual_outcomes_used": False,
            "may_change_blind_forecast": False,
            "may_change_posterior": False,
            "may_update_ng_brain": False,
            "execution_authority": False,
        }
        integration_receipt["fingerprint"] = _sha(integration_receipt)
        _atomic_json(staging / "integration_receipt.json", integration_receipt)
        bundle_index = {
            "schema": BUNDLE_SCHEMA,
            "status": "VERIFIED_CANDIDATE_NOT_PROMOTED",
            "integration_receipt_fingerprint": integration_receipt["fingerprint"],
            "files": {
                str(path.relative_to(staging)): {
                    "size_bytes": path.stat().st_size,
                    "sha256": _file_sha256(path),
                }
                for path in sorted(staging.rglob("*")) if path.is_file()
            },
            "canonical_inventory_replaced": False,
            "execution_authority": False,
        }
        bundle_index["fingerprint"] = _sha(bundle_index)
        _atomic_json(staging / "bundle_index.json", bundle_index)
        staging.rename(bundle_dir)
        return {
            "bundle_dir": str(bundle_dir),
            "status": bundle_index["status"],
            "integrated_session_days": list(request["canonical_days"]),
            "candidate_basis_status": basis_after["status"],
            "bundle_fingerprint": bundle_index["fingerprint"],
        }
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def validate_bundle(bundle_dir: Path) -> dict[str, Any]:
    index_path = bundle_dir / "bundle_index.json"
    if not index_path.is_file():
        raise ExactL1IntegrationError("integration bundle is missing bundle_index.json")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    candidate = copy.deepcopy(index)
    observed = candidate.pop("fingerprint", None)
    if candidate.get("schema") != BUNDLE_SCHEMA or observed != _sha(candidate):
        raise ExactL1IntegrationError("integration bundle index is invalid or tampered")
    if candidate.get("execution_authority") is not False:
        raise ExactL1IntegrationError("integration bundle cannot grant execution authority")
    for relative, expected in candidate.get("files", {}).items():
        path = (bundle_dir / relative).resolve()
        try:
            path.relative_to(bundle_dir.resolve())
        except ValueError as error:
            raise ExactL1IntegrationError("bundle index path escapes bundle directory") from error
        if not path.is_file():
            raise ExactL1IntegrationError(f"integration bundle file is missing: {relative}")
        if path.stat().st_size != int(expected.get("size_bytes") or -1):
            raise ExactL1IntegrationError(f"integration bundle file size changed: {relative}")
        if _file_sha256(path) != expected.get("sha256"):
            raise ExactL1IntegrationError(f"integration bundle file hash changed: {relative}")
    receipt = json.loads((bundle_dir / "integration_receipt.json").read_text(encoding="utf-8"))
    receipt_candidate = copy.deepcopy(receipt)
    receipt_observed = receipt_candidate.pop("fingerprint", None)
    if receipt_candidate.get("schema") != RECEIPT_SCHEMA or receipt_observed != _sha(receipt_candidate):
        raise ExactL1IntegrationError("integration receipt is invalid or tampered")
    manifest = json.loads((bundle_dir / "candidate_g15_mbo_l1_manifest.json").read_text(encoding="utf-8"))
    report = evaluate_manifest(manifest)
    validate_report(report)
    if report.get("status") != "MATCHED_L1_MBO_READY":
        raise ExactL1IntegrationError("candidate manifest no longer passes exact-basis gate")
    if _sha(manifest) != receipt.get("candidate_inventory_fingerprint"):
        raise ExactL1IntegrationError("candidate inventory fingerprint differs from integration receipt")
    return {"index": index, "receipt": receipt, "manifest": manifest, "basis_report": report}


def promote_bundle(
    *,
    bundle_dir: Path,
    canonical_inventory: Path,
    confirm_promote: bool,
) -> dict[str, Any]:
    if not confirm_promote:
        raise ExactL1IntegrationError("promotion requires --confirm-promote")
    validated = validate_bundle(bundle_dir)
    if not canonical_inventory.is_file():
        raise ExactL1IntegrationError("canonical inventory does not exist")
    current = json.loads(canonical_inventory.read_text(encoding="utf-8"))
    expected_source = validated["receipt"]["source_inventory_fingerprint"]
    if _sha(current) != expected_source:
        raise ExactL1IntegrationError("canonical inventory changed after the integration bundle was built")
    backup = canonical_inventory.with_name(
        canonical_inventory.name + f".pre_exact_l1.{expected_source[:12]}.json"
    )
    if backup.exists():
        raise ExactL1IntegrationError(f"promotion backup already exists: {backup}")
    shutil.copy2(canonical_inventory, backup)
    try:
        _atomic_json(canonical_inventory, validated["manifest"])
    except Exception:
        shutil.copy2(backup, canonical_inventory)
        raise
    final = evaluate_manifest(json.loads(canonical_inventory.read_text(encoding="utf-8")))
    validate_report(final)
    if final.get("status") != "MATCHED_L1_MBO_READY":
        shutil.copy2(backup, canonical_inventory)
        raise ExactL1IntegrationError("promoted inventory failed exact-basis verification; restored backup")
    return {
        "status": "PROMOTED_MATCHED_L1_MBO_READY",
        "canonical_inventory": str(canonical_inventory),
        "backup": str(backup),
        "basis_report_fingerprint": final["fingerprint"],
        "execution_authority": False,
    }


def selftest() -> int:
    allowed = {"20260313", "20260315", "20260316", "20260317", "20260318", "20260319"}
    assert _candidate_day("GLBX-20260318.mbp-1.dbn.zst", allowed) == "20260318"
    assert _candidate_day("undated.dbn.zst", allowed) is None
    assert _candidate_day("20260318_20260319.dbn.zst", allowed) is None
    print("[ng_g15_exact_l1_integration] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Integrate downloaded exact-contract G15 L1 safely")
    sub = parser.add_subparsers(dest="mode", required=True)

    map_parser = sub.add_parser("map-template")
    map_parser.add_argument("--plan", type=Path, required=True)
    map_parser.add_argument("--receipt", type=Path, required=True)
    map_parser.add_argument("--out", type=Path, required=True)

    integrate_parser = sub.add_parser("integrate")
    integrate_parser.add_argument("--inventory", type=Path, required=True)
    integrate_parser.add_argument("--plan", type=Path, required=True)
    integrate_parser.add_argument("--receipt", type=Path, required=True)
    integrate_parser.add_argument("--day-map", type=Path, required=True)
    integrate_parser.add_argument("--definition", type=Path, required=True)
    integrate_parser.add_argument("--bundle-dir", type=Path, required=True)

    verify_parser = sub.add_parser("verify-bundle")
    verify_parser.add_argument("--bundle-dir", type=Path, required=True)

    promote_parser = sub.add_parser("promote")
    promote_parser.add_argument("--bundle-dir", type=Path, required=True)
    promote_parser.add_argument("--canonical-inventory", type=Path, required=True)
    promote_parser.add_argument("--confirm-promote", action="store_true")

    sub.add_parser("selftest")
    args = parser.parse_args()
    if args.mode == "selftest":
        return selftest()
    if args.mode == "map-template":
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
        template = build_day_map_template(plan, receipt)
        _atomic_json(args.out, template)
        print(json.dumps({"status": template["status"], "entries": len(template["entries"]), "out": str(args.out)}, indent=2))
        return 0
    if args.mode == "integrate":
        result = build_integration_bundle(
            inventory_rows=json.loads(args.inventory.read_text(encoding="utf-8")),
            plan=json.loads(args.plan.read_text(encoding="utf-8")),
            receipt=json.loads(args.receipt.read_text(encoding="utf-8")),
            day_map=json.loads(args.day_map.read_text(encoding="utf-8")),
            definition=json.loads(args.definition.read_text(encoding="utf-8")),
            bundle_dir=args.bundle_dir,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.mode == "verify-bundle":
        result = validate_bundle(args.bundle_dir)
        print(json.dumps({
            "status": result["index"]["status"],
            "basis_status": result["basis_report"]["status"],
            "bundle": str(args.bundle_dir),
        }, indent=2))
        return 0
    result = promote_bundle(
        bundle_dir=args.bundle_dir,
        canonical_inventory=args.canonical_inventory,
        confirm_promote=args.confirm_promote,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
