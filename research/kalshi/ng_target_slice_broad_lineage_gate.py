#!/usr/bin/env python3
"""Bind every selected target-day shard to the verified broad-corpus source bytes.

Readiness v16 separates broad-corpus inspection from target-slice inspection. This
module joins those lanes without claiming that derived target shards are byte-equal
to their parent objects. Each selected target shard must instead resolve to exactly
one broad source by remote location, lane, observed definition fingerprint, and the
parent source SHA-256/byte size carried by that definition. The independently
inspected target shard must also match the selected slice candidate exactly.

The gate is outcome-blind, chronological, SHADOW-only, and cannot mutate forecasts,
posterior state, ``knowledge/ng_brain.json``, execution authority, or options.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

import ng_corpus_basis_inventory_regeneration as basis
import ng_corpus_definition_byte_binding_gate as broad_binding
import ng_corpus_inspection as inspection
import ng_corpus_target_day_slicer as slicer

SCHEMA = "ng_target_slice_broad_lineage_gate.v1"
READY_STATUS = "TARGET_SLICE_BROAD_LINEAGE_READY"
BLOCKED_STATUS = "TARGET_SLICE_BROAD_LINEAGE_BLOCKED"


class TargetSliceBroadLineageError(ValueError):
    """Raised when target shards cannot be joined to verified broad source bytes."""


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
            raise TargetSliceBroadLineageError(f"{label}: {field} must remain false")
    if value.get("one_signal_authority_preserved") is not True:
        raise TargetSliceBroadLineageError(
            f"{label}: one signal authority must be preserved"
        )
    if value.get("blind_forecasts_immutable") is not True:
        raise TargetSliceBroadLineageError(
            f"{label}: blind forecasts must remain immutable"
        )
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise TargetSliceBroadLineageError(
            f"{label}: CME event contracts must remain SHADOW"
        )
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise TargetSliceBroadLineageError(
            f"{label}: brokerage must remain tastytrade, not IBKR"
        )


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise TargetSliceBroadLineageError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise TargetSliceBroadLineageError(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _broad_sources(gate: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    compiled = (gate.get("inventory_compiler_receipt") or {}).get("compiled_plan") or {}
    bindings = {
        str(row.get("source_id") or ""): copy.deepcopy(dict(row))
        for row in gate.get("bindings") or []
    }
    result: dict[str, dict[str, Any]] = {}
    for corpus_raw in compiled.get("corpora") or []:
        corpus = dict(corpus_raw)
        corpus_id = str(corpus.get("corpus_id") or "")
        corpus_lane = str(corpus.get("lane") or "")
        for source_raw in corpus.get("sources") or []:
            source = copy.deepcopy(dict(source_raw))
            source_id = str(source.get("source_id") or "")
            if not source_id or source_id in result:
                raise TargetSliceBroadLineageError(
                    f"broad inventory has missing or duplicate source_id {source_id!r}"
                )
            binding = bindings.get(source_id)
            if binding is None:
                raise TargetSliceBroadLineageError(
                    f"broad definition-byte gate is missing source {source_id}"
                )
            definition = inspection.validate_definition(source.get("definition") or {})
            result[source_id] = {
                "source_id": source_id,
                "corpus_id": corpus_id,
                "lane": str(source.get("lane") or corpus_lane),
                "location": str(source.get("location") or ""),
                "definition": definition,
                "definition_fingerprint": definition["definition_fingerprint"],
                "source_sha256": str(definition.get("source_sha256") or "").lower(),
                "source_size_bytes": int(definition.get("source_size_bytes") or 0),
                "binding_fingerprint": binding.get("binding_fingerprint"),
                "byte_identity_matches_definition": binding.get(
                    "byte_identity_matches_definition"
                ),
                "binding_blockers": list(binding.get("blockers") or []),
            }
    if set(result) != set(bindings):
        raise TargetSliceBroadLineageError(
            "broad compiled source set differs from definition-byte binding set"
        )
    return result


def _lineage_key_from_broad(source: Mapping[str, Any]) -> tuple[Any, ...]:
    definition = source["definition"]
    return (
        source["location"],
        source["lane"],
        source["definition_fingerprint"],
        source["source_sha256"],
        int(source["source_size_bytes"]),
        definition["dataset"],
        int(definition["publisher_id"]),
        int(definition["instrument_id"]),
        definition["raw_symbol"],
        definition["definition_date"],
        float(definition["definition_start_s"]),
        float(definition["definition_end_s"]),
    )


def _lineage_key_from_candidate(candidate: Mapping[str, Any]) -> tuple[Any, ...]:
    definition = inspection.validate_definition(candidate.get("definition") or {})
    return (
        str(candidate.get("source_location") or ""),
        str(candidate.get("lane") or ""),
        definition["definition_fingerprint"],
        str(definition.get("source_sha256") or "").lower(),
        int(definition.get("source_size_bytes") or 0),
        definition["dataset"],
        int(definition["publisher_id"]),
        int(definition["instrument_id"]),
        definition["raw_symbol"],
        definition["definition_date"],
        float(definition["definition_start_s"]),
        float(definition["definition_end_s"]),
    )


def _build(
    broad_gate: Mapping[str, Any],
    target_slice_bundle: Mapping[str, Any],
    target_inspection_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    broad = broad_binding.validate_gate(broad_gate)
    slices = basis._validate_slice_envelope(target_slice_bundle)
    target_receipt = inspection.validate_receipt(target_inspection_receipt)
    if broad.get("status") != broad_binding.READY_STATUS:
        raise TargetSliceBroadLineageError(
            "broad definition-byte binding must be ready before target lineage"
        )
    if target_receipt.get("plan_fingerprint") != slices.get(
        "inspection_plan_fingerprint"
    ):
        raise TargetSliceBroadLineageError(
            "target inspection receipt does not belong to the slice-bundle plan"
        )

    selected = basis._selected_candidates(slices)
    entries = basis._catalog_entries(target_receipt.get("catalog") or {})
    expected_target_ids = {
        str(candidate["normalized_source_id"]) for candidate in selected.values()
    }
    if set(entries) != expected_target_ids:
        raise TargetSliceBroadLineageError(
            "target inspection source set differs from selected target slices"
        )

    broad_sources = _broad_sources(broad)
    broad_by_key: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for source in broad_sources.values():
        broad_by_key.setdefault(_lineage_key_from_broad(source), []).append(source)

    rows: list[dict[str, Any]] = []
    blockers: set[str] = set()
    broad_source_ids_used: set[str] = set()
    for day, lane in sorted(selected):
        candidate = selected[(day, lane)]
        entry = entries[str(candidate["normalized_source_id"])]
        basis._validate_entry_against_candidate(entry, candidate, verify_files=False)
        matches = broad_by_key.get(_lineage_key_from_candidate(candidate), [])
        row_blockers: list[str] = []
        if not matches:
            row_blockers.append("NO_EXACT_BROAD_SOURCE_LINEAGE")
        elif len(matches) > 1:
            row_blockers.append("AMBIGUOUS_BROAD_SOURCE_LINEAGE")
        selected_broad = matches[0] if len(matches) == 1 else None
        if selected_broad is not None:
            if selected_broad.get("byte_identity_matches_definition") is not True:
                row_blockers.append("BROAD_SOURCE_BYTES_NOT_DEFINITION_BOUND")
            if selected_broad.get("binding_blockers"):
                row_blockers.append("BROAD_SOURCE_BINDING_HAS_BLOCKERS")
            broad_source_ids_used.add(str(selected_broad["source_id"]))
        definition = inspection.validate_definition(candidate.get("definition") or {})
        row = {
            "day": day,
            "lane": lane,
            "target": str(candidate.get("target") or ""),
            "target_candidate_id": candidate.get("candidate_id"),
            "target_candidate_fingerprint": candidate.get("candidate_fingerprint"),
            "target_source_id": candidate.get("normalized_source_id"),
            "target_inspection_fingerprint": entry.get("inspection_fingerprint"),
            "target_sha256": entry.get("sha256"),
            "target_size_bytes": entry.get("size_bytes"),
            "target_event_start_s": entry.get("event_start_s"),
            "target_event_end_s": entry.get("event_end_s"),
            "source_location": candidate.get("source_location"),
            "source_object_id": candidate.get("object_id"),
            "definition_fingerprint": candidate.get("definition_fingerprint"),
            "parent_source_sha256": definition.get("source_sha256"),
            "parent_source_size_bytes": definition.get("source_size_bytes"),
            "broad_source_id": (
                selected_broad.get("source_id") if selected_broad is not None else None
            ),
            "broad_binding_fingerprint": (
                selected_broad.get("binding_fingerprint")
                if selected_broad is not None
                else None
            ),
            "lineage_unique": selected_broad is not None and not row_blockers,
            "blockers": sorted(set(row_blockers)),
        }
        row["lineage_fingerprint"] = _fp(row)
        rows.append(row)
        blockers.update(f"{day}:{lane}:{item}" for item in row["blockers"])

    expected_count = 2 * len(slicer._target_days())
    if len(rows) != expected_count:
        blockers.add(
            f"TARGET_SOURCE_COUNT_MISMATCH:expected={expected_count}:observed={len(rows)}"
        )
    blocker_list = sorted(blockers)
    ready = len(rows) == expected_count and not blocker_list
    value = {
        "schema": SCHEMA,
        "status": READY_STATUS if ready else BLOCKED_STATUS,
        "broad_definition_byte_binding_fingerprint": broad["fingerprint"],
        "broad_inventory_compiler_receipt_fingerprint": broad[
            "inventory_compiler_receipt_fingerprint"
        ],
        "broad_inspection_receipt_fingerprint": broad[
            "inspection_receipt_fingerprint"
        ],
        "broad_binding_set_fingerprint": broad["binding_set_fingerprint"],
        "target_slice_bundle_fingerprint": slices["slice_bundle_fingerprint"],
        "target_inspection_plan_fingerprint": slices[
            "inspection_plan_fingerprint"
        ],
        "target_inspection_receipt_fingerprint": target_receipt[
            "receipt_fingerprint"
        ],
        "target_catalog_fingerprint": target_receipt["catalog_fingerprint"],
        "target_audit_fingerprint": target_receipt["audit_fingerprint"],
        "selected_target_source_count": len(rows),
        "expected_target_source_count": expected_count,
        "unique_lineage_count": sum(row["lineage_unique"] for row in rows),
        "broad_source_ids_used": sorted(broad_source_ids_used),
        "lineage_rows": rows,
        "lineage_set_fingerprint": _fp(rows),
        "blockers": blocker_list,
        "stand_down_required": not ready,
        "next_action": (
            "REGENERATE_G15_G16_BASIS_FROM_LINEAGE_BOUND_TARGET_SHARDS"
            if ready
            else "RESOLVE_TARGET_SLICE_BROAD_LINEAGE_BLOCKERS"
        ),
        "broad_definition_byte_binding_gate": copy.deepcopy(broad),
        "target_slice_bundle": copy.deepcopy(slices),
        "target_inspection_receipt": copy.deepcopy(target_receipt),
        **_authority_fields(),
    }
    value["fingerprint"] = _fp(value)
    return value


def build_gate(
    broad_gate: Mapping[str, Any],
    target_slice_bundle: Mapping[str, Any],
    target_inspection_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    value = _build(broad_gate, target_slice_bundle, target_inspection_receipt)
    validate_gate(value)
    return value


def validate_gate(value: Mapping[str, Any]) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise TargetSliceBroadLineageError(
            "target-slice broad-lineage schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked, label="target-slice broad-lineage gate")
    rebuilt = _build(
        checked.get("broad_definition_byte_binding_gate") or {},
        checked.get("target_slice_bundle") or {},
        checked.get("target_inspection_receipt") or {},
    )
    if _canonical(rebuilt) != _canonical(checked):
        raise TargetSliceBroadLineageError(
            "target-slice broad-lineage gate does not match deterministic reconstruction"
        )
    return checked


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=False)
    build = sub.add_parser("build", help="build target-slice broad-lineage gate")
    build.add_argument("--broad-definition-byte-gate", type=Path, required=True)
    build.add_argument("--target-slice-bundle", type=Path, required=True)
    build.add_argument("--target-inspection-receipt", type=Path, required=True)
    build.add_argument("--out", type=Path, required=True)
    validate = sub.add_parser("validate", help="validate a completed gate")
    validate.add_argument("--gate", type=Path, required=True)
    return parser


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    if args.command == "build":
        result = build_gate(
            _load(args.broad_definition_byte_gate),
            _load(args.target_slice_bundle),
            _load(args.target_inspection_receipt),
        )
        _write(args.out, result)
        print(
            json.dumps(
                {
                    "out": str(args.out),
                    "status": result["status"],
                    "selected_target_source_count": result[
                        "selected_target_source_count"
                    ],
                    "unique_lineage_count": result["unique_lineage_count"],
                    "blocker_count": len(result["blockers"]),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "validate":
        validate_gate(_load(args.gate))
        print("[ng_target_slice_broad_lineage_gate] gate VALID")
        return 0
    parser.error("select build or validate")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
