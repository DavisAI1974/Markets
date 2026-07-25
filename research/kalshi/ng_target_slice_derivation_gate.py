#!/usr/bin/env python3
"""Attest that every inspected target-day shard is deterministically derived from its verified broad source.

The target-to-broad lineage gate proves unique ancestry by source identity. This module
adds the missing content proof: it re-streams each definition-byte-bound parent object,
normalizes only the requested UTC day through the same historical replay normalizer used
by the target slicer, and requires the reconstructed JSONL bytes to match the selected and
independently inspected target shard exactly.

The gate is historical-first and outcome-blind. It never random-shuffles time series,
mutates blind forecasts or posterior state, writes ``knowledge/ng_brain.json``, grants
execution authority, promotes CME event contracts beyond SHADOW, or starts options work.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

import ng_corpus_basis_inventory_regeneration as basis
import ng_corpus_inspection as inspection
import ng_historical_normalize as normalize
import ng_target_slice_broad_lineage_gate as lineage
import ng_corpus_target_day_slicer as slicer

SCHEMA = "ng_target_slice_derivation_gate.v1"
READY_STATUS = "TARGET_SLICE_DERIVATION_ATTESTED"
BLOCKED_STATUS = "TARGET_SLICE_DERIVATION_BLOCKED"
ALGORITHM = "historical_normalize_v1_canonical_jsonl_sha256"


class TargetSliceDerivationError(ValueError):
    """Raised when target-shard derivation evidence is malformed or contradictory."""


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _authority_fields() -> dict[str, Any]:
    return {
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
    }


def _authority(value: Mapping[str, Any], *, label: str) -> None:
    for field in (
        "actual_outcomes_used",
        "paid_live_data_assumed",
        "random_shuffle_used",
        "may_change_blind_forecast",
        "may_change_posterior",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    ):
        if value.get(field) is not False:
            raise TargetSliceDerivationError(f"{label}: {field} must remain false")
    if value.get("one_signal_authority_preserved") is not True:
        raise TargetSliceDerivationError(f"{label}: one signal authority must be preserved")
    if value.get("blind_forecasts_immutable") is not True:
        raise TargetSliceDerivationError(f"{label}: blind forecasts must remain immutable")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise TargetSliceDerivationError(f"{label}: CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise TargetSliceDerivationError(f"{label}: brokerage must remain tastytrade, not IBKR")


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise TargetSliceDerivationError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise TargetSliceDerivationError(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _broad_source_map(gate: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    broad = gate.get("broad_definition_byte_binding_gate") or {}
    compiled = (broad.get("inventory_compiler_receipt") or {}).get("compiled_plan") or {}
    bindings = {
        str(row.get("source_id") or ""): copy.deepcopy(dict(row))
        for row in broad.get("bindings") or []
    }
    result: dict[str, dict[str, Any]] = {}
    for corpus_raw in compiled.get("corpora") or []:
        corpus = dict(corpus_raw)
        corpus_lane = str(corpus.get("lane") or "")
        for source_raw in corpus.get("sources") or []:
            source = copy.deepcopy(dict(source_raw))
            source_id = str(source.get("source_id") or "")
            if not source_id or source_id in result:
                raise TargetSliceDerivationError(
                    f"broad inventory has missing or duplicate source_id {source_id!r}"
                )
            binding = bindings.get(source_id)
            if binding is None:
                raise TargetSliceDerivationError(
                    f"broad definition-byte gate is missing source {source_id}"
                )
            source["lane"] = str(source.get("lane") or corpus_lane)
            source["definition"] = inspection.validate_definition(source.get("definition") or {})
            source["binding"] = binding
            result[source_id] = source
    if set(result) != set(bindings):
        raise TargetSliceDerivationError(
            "broad compiled source set differs from definition-byte binding set"
        )
    return result


def _target_maps(gate: Mapping[str, Any]) -> tuple[
    dict[tuple[str, str], dict[str, Any]], dict[str, dict[str, Any]]
]:
    slices = basis._validate_slice_envelope(gate.get("target_slice_bundle") or {})
    receipt = inspection.validate_receipt(gate.get("target_inspection_receipt") or {})
    if receipt.get("plan_fingerprint") != slices.get("inspection_plan_fingerprint"):
        raise TargetSliceDerivationError(
            "target inspection receipt does not belong to the slice-bundle plan"
        )
    selected = basis._selected_candidates(slices)
    entries = basis._catalog_entries(receipt.get("catalog") or {})
    expected_ids = {str(row.get("normalized_source_id") or "") for row in selected.values()}
    if set(entries) != expected_ids:
        raise TargetSliceDerivationError(
            "target inspection source set differs from selected target slices"
        )
    return selected, entries


def _normalized_lines(
    *,
    source_path: Path,
    source: Mapping[str, Any],
    day: str,
    lane: str,
) -> Iterable[bytes]:
    definition = inspection.validate_definition(source.get("definition") or {})
    event_kind = slicer.LANE_TO_KIND.get(lane)
    if event_kind is None:
        raise TargetSliceDerivationError(f"unsupported target lane {lane!r}")
    previous: tuple[float, int, int] | None = None
    shard_sequence = 0
    for input_count, raw in enumerate(slicer._iter_raw(source_path), 1):
        if not normalize.record_matches_kind(raw, event_kind):
            if lane == "l1_trades" or source.get("skip_nonmatching") is True:
                continue
            raise TargetSliceDerivationError(
                f"{source_path}: record {input_count} does not match lane {lane}"
            )
        timestamp = normalize.event_seconds(
            normalize._value(raw, "ts_event_s", "ts_event", "timestamp", "ts", "ts_recv")
        )
        sequence_raw = normalize._value(
            raw,
            "source_sequence",
            "sequence",
            "sequence_number",
            default=input_count,
        )
        try:
            source_sequence = int(sequence_raw)
        except (TypeError, ValueError, OverflowError):
            source_sequence = input_count
        key = (float(timestamp), source_sequence, input_count)
        if previous is not None and key < previous:
            raise TargetSliceDerivationError(
                f"source moved backwards at record {input_count}: {source_path}"
            )
        previous = key
        if timestamp < float(definition["definition_start_s"]) or timestamp > float(
            definition["definition_end_s"]
        ):
            raise TargetSliceDerivationError(
                f"record {input_count} falls outside observed definition period"
            )
        if slicer._utc_day(timestamp) != day:
            continue
        expected = slicer._target_identity(day)
        if expected is None:
            raise TargetSliceDerivationError(f"unexpected target day {day}")
        if (
            definition["raw_symbol"] != expected["raw_symbol"]
            or int(definition["instrument_id"]) != int(expected["instrument_id"])
        ):
            continue
        shard_sequence += 1
        event = normalize.normalize_record(
            raw,
            event_type=event_kind,
            dataset=str(definition["dataset"]),
            publisher_id=int(definition["publisher_id"]),
            instrument_id=int(definition["instrument_id"]),
            raw_symbol=str(definition["raw_symbol"]),
            definition_date=str(definition["definition_date"]),
            session_day=day,
            source_id=slicer._candidate_source_id(
                lane=lane, day=day, definition=definition
            ),
            ingest_sequence=shard_sequence,
        )
        yield (slicer._canonical_event(event) + "\n").encode("utf-8")


def _derive_one(
    *,
    source: Mapping[str, Any],
    candidate: Mapping[str, Any],
    target_entry: Mapping[str, Any],
    verify_files: bool,
) -> dict[str, Any]:
    day = str(candidate.get("day") or "")
    lane = str(candidate.get("lane") or "")
    path = Path(str(source.get("materialized_path") or "")).expanduser().resolve()
    blockers: list[str] = []
    binding = source.get("binding") or {}
    if binding.get("byte_identity_matches_definition") is not True:
        blockers.append("PARENT_SOURCE_NOT_DEFINITION_BYTE_BOUND")
    if binding.get("blockers"):
        blockers.append("PARENT_SOURCE_BINDING_HAS_BLOCKERS")

    derived_sha: str | None = None
    derived_size: int | None = None
    derived_count: int | None = None
    source_sha_before: str | None = None
    source_sha_after: str | None = None
    source_size_before: int | None = None
    source_size_after: int | None = None

    if verify_files:
        if not path.is_file():
            blockers.append("PARENT_SOURCE_FILE_MISSING")
        else:
            source_size_before = path.stat().st_size
            source_sha_before = _sha256(path)
            definition = source["definition"]
            if source_sha_before != str(definition.get("source_sha256") or "").lower():
                blockers.append("PARENT_SOURCE_SHA256_CHANGED")
            if source_size_before != int(definition.get("source_size_bytes") or 0):
                blockers.append("PARENT_SOURCE_SIZE_CHANGED")
            digest = hashlib.sha256()
            size = 0
            count = 0
            try:
                for encoded in _normalized_lines(
                    source_path=path, source=source, day=day, lane=lane
                ):
                    digest.update(encoded)
                    size += len(encoded)
                    count += 1
            except Exception as error:
                blockers.append(f"DERIVATION_ERROR:{type(error).__name__}:{error}")
            else:
                derived_sha = digest.hexdigest()
                derived_size = size
                derived_count = count
                if count == 0:
                    blockers.append("DERIVED_TARGET_EMPTY")
            source_size_after = path.stat().st_size
            source_sha_after = _sha256(path)
            if (source_size_before, source_sha_before) != (
                source_size_after,
                source_sha_after,
            ):
                blockers.append("PARENT_SOURCE_CHANGED_DURING_DERIVATION")
    else:
        derived_sha = str(target_entry.get("sha256") or "").lower()
        derived_size = int(target_entry.get("size_bytes") or 0)
        derived_count = int(target_entry.get("record_count") or candidate.get("record_count") or 0)

    expected_sha = str(target_entry.get("sha256") or "").lower()
    expected_size = int(target_entry.get("size_bytes") or 0)
    expected_count = int(target_entry.get("record_count") or candidate.get("record_count") or 0)
    if derived_sha is not None and derived_sha != expected_sha:
        blockers.append("DERIVED_SHA256_MISMATCH")
    if derived_size is not None and derived_size != expected_size:
        blockers.append("DERIVED_SIZE_BYTES_MISMATCH")
    if derived_count is not None and expected_count and derived_count != expected_count:
        blockers.append("DERIVED_RECORD_COUNT_MISMATCH")
    if candidate.get("sha256") not in (None, "") and expected_sha != str(
        candidate.get("sha256")
    ).lower():
        blockers.append("TARGET_CANDIDATE_SHA256_MISMATCH")
    if candidate.get("size_bytes") not in (None, "") and expected_size != int(
        candidate.get("size_bytes") or 0
    ):
        blockers.append("TARGET_CANDIDATE_SIZE_MISMATCH")
    if candidate.get("record_count") not in (None, "") and expected_count != int(
        candidate.get("record_count") or 0
    ):
        blockers.append("TARGET_CANDIDATE_RECORD_COUNT_MISMATCH")

    blocker_set = sorted(set(blockers))
    row = {
        "day": day,
        "lane": lane,
        "target": str(candidate.get("target") or ""),
        "target_candidate_id": candidate.get("candidate_id"),
        "target_candidate_fingerprint": candidate.get("candidate_fingerprint"),
        "target_source_id": candidate.get("normalized_source_id"),
        "target_inspection_fingerprint": target_entry.get("inspection_fingerprint"),
        "broad_source_id": source.get("source_id"),
        "broad_binding_fingerprint": binding.get("binding_fingerprint"),
        "broad_materialized_path": str(path),
        "definition_fingerprint": source["definition"].get("definition_fingerprint"),
        "expected_target_sha256": expected_sha,
        "expected_target_size_bytes": expected_size,
        "expected_target_record_count": expected_count,
        "derived_target_sha256": derived_sha,
        "derived_target_size_bytes": derived_size,
        "derived_target_record_count": derived_count,
        "parent_source_sha256_before": source_sha_before,
        "parent_source_sha256_after": source_sha_after,
        "parent_source_size_bytes_before": source_size_before,
        "parent_source_size_bytes_after": source_size_after,
        "derivation_algorithm": ALGORITHM,
        "derivation_exact": not blocker_set,
        "blockers": blocker_set,
    }
    row["derivation_fingerprint"] = _fp(row)
    return row


def _build(lineage_gate: Mapping[str, Any], *, verify_files: bool) -> dict[str, Any]:
    parent = lineage.validate_gate(lineage_gate)
    if parent.get("status") != lineage.READY_STATUS:
        raise TargetSliceDerivationError(
            "target-to-broad lineage must be ready before derivation attestation"
        )
    selected, entries = _target_maps(parent)
    broad_sources = _broad_source_map(parent)
    lineage_rows = {
        (str(row.get("day") or ""), str(row.get("lane") or "")): copy.deepcopy(dict(row))
        for row in parent.get("lineage_rows") or []
    }
    if len(lineage_rows) != len(parent.get("lineage_rows") or []):
        raise TargetSliceDerivationError("duplicate day/lane rows in lineage gate")

    rows: list[dict[str, Any]] = []
    blockers: set[str] = set()
    for key in sorted(selected):
        day, lane = key
        candidate = selected[key]
        line = lineage_rows.get(key)
        if line is None or line.get("lineage_unique") is not True:
            blockers.add(f"{day}:{lane}:LINEAGE_ROW_NOT_READY")
            continue
        if line.get("target_candidate_fingerprint") != candidate.get(
            "candidate_fingerprint"
        ):
            blockers.add(f"{day}:{lane}:LINEAGE_CANDIDATE_MISMATCH")
            continue
        source_id = str(line.get("broad_source_id") or "")
        source = broad_sources.get(source_id)
        if source is None:
            blockers.add(f"{day}:{lane}:LINEAGE_PARENT_SOURCE_MISSING")
            continue
        entry = entries[str(candidate.get("normalized_source_id") or "")]
        basis._validate_entry_against_candidate(
            entry, candidate, verify_files=verify_files
        )
        row = _derive_one(
            source=source,
            candidate=candidate,
            target_entry=entry,
            verify_files=verify_files,
        )
        rows.append(row)
        blockers.update(f"{day}:{lane}:{item}" for item in row["blockers"])

    expected_count = int(parent.get("expected_target_source_count") or 0)
    if len(rows) != expected_count:
        blockers.add(
            f"TARGET_DERIVATION_COUNT_MISMATCH:expected={expected_count}:observed={len(rows)}"
        )
    blocker_list = sorted(blockers)
    ready = expected_count > 0 and len(rows) == expected_count and not blocker_list
    value = {
        "schema": SCHEMA,
        "status": READY_STATUS if ready else BLOCKED_STATUS,
        "target_slice_broad_lineage_fingerprint": parent["fingerprint"],
        "broad_definition_byte_binding_fingerprint": parent[
            "broad_definition_byte_binding_fingerprint"
        ],
        "target_slice_bundle_fingerprint": parent["target_slice_bundle_fingerprint"],
        "target_inspection_receipt_fingerprint": parent[
            "target_inspection_receipt_fingerprint"
        ],
        "target_catalog_fingerprint": parent["target_catalog_fingerprint"],
        "target_audit_fingerprint": parent["target_audit_fingerprint"],
        "lineage_set_fingerprint": parent["lineage_set_fingerprint"],
        "derivation_algorithm": ALGORITHM,
        "expected_target_source_count": expected_count,
        "derived_target_source_count": len(rows),
        "exact_derivation_count": sum(row["derivation_exact"] for row in rows),
        "derivation_rows": rows,
        "derivation_set_fingerprint": _fp(rows),
        "blockers": blocker_list,
        "stand_down_required": not ready,
        "source_files_verified": bool(verify_files),
        "next_action": (
            "REGENERATE_G15_G16_BASIS_FROM_DERIVATION_ATTESTED_TARGET_SHARDS"
            if ready
            else "RESOLVE_TARGET_SLICE_DERIVATION_BLOCKERS"
        ),
        "target_slice_broad_lineage_gate": copy.deepcopy(parent),
        **_authority_fields(),
    }
    value["fingerprint"] = _fp(value)
    return value


def build_gate(
    lineage_gate: Mapping[str, Any], *, verify_files: bool = True
) -> dict[str, Any]:
    value = _build(lineage_gate, verify_files=verify_files)
    validate_gate(value, verify_files=verify_files)
    return value


def validate_gate(
    value: Mapping[str, Any], *, verify_files: bool = True
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise TargetSliceDerivationError(
            "target-slice derivation schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked, label="target-slice derivation gate")
    if checked.get("source_files_verified") is not bool(verify_files):
        raise TargetSliceDerivationError(
            "target-slice derivation file-verification mode mismatch"
        )
    rebuilt = _build(
        checked.get("target_slice_broad_lineage_gate") or {},
        verify_files=verify_files,
    )
    if _canonical(rebuilt) != _canonical(checked):
        raise TargetSliceDerivationError(
            "target-slice derivation gate does not match deterministic reconstruction"
        )
    return checked


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=False)
    build = sub.add_parser("build", help="build target-slice derivation gate")
    build.add_argument("--lineage-gate", type=Path, required=True)
    build.add_argument("--out", type=Path, required=True)
    validate = sub.add_parser("validate", help="validate a completed derivation gate")
    validate.add_argument("--gate", type=Path, required=True)
    validate.add_argument("--skip-file-verification", action="store_true")
    return parser


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    if args.command == "build":
        result = build_gate(_load(args.lineage_gate), verify_files=True)
        _write(args.out, result)
        print(
            json.dumps(
                {
                    "out": str(args.out),
                    "status": result["status"],
                    "derived_target_source_count": result[
                        "derived_target_source_count"
                    ],
                    "exact_derivation_count": result["exact_derivation_count"],
                    "blocker_count": len(result["blockers"]),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "validate":
        validate_gate(
            _load(args.gate), verify_files=not args.skip_file_verification
        )
        print("[ng_target_slice_derivation_gate] gate VALID")
        return 0
    parser.error("select build or validate")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
