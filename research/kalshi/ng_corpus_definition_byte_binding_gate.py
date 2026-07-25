#!/usr/bin/env python3
"""Bind every inspected NG corpus object to the exact bytes named by its definition.

``ng_corpus_inspection.py`` hashes each materialized object and separately validates
its observed definition. This gate joins those two proofs. A PRESENT object counts
only when its inspected SHA-256 and byte size exactly match the source byte identity
recorded in the definition observation that supplied dataset, publisher, instrument,
raw symbol, and definition-period metadata.

The gate is historical-first and outcome-blind. It exposes missing/corrupt objects
and byte mismatches as stand-down blockers. It cannot mutate forecasts, posterior
state, ``knowledge/ng_brain.json``, execution authority, CME event-contract mode,
or the options lane.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

import ng_corpus_inspection as inspection
import ng_corpus_inventory_plan_compiler as compiler

SCHEMA = "ng_corpus_definition_byte_binding_gate.v1"
READY_STATUS = "CORPUS_DEFINITION_BYTES_BOUND_READY"
BLOCKED_STATUS = "CORPUS_DEFINITION_BYTES_BOUND_BLOCKED"


class CorpusDefinitionByteBindingError(ValueError):
    """Raised when corpus definition/byte lineage is malformed or contradictory."""


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
            raise CorpusDefinitionByteBindingError(
                f"{label}: {field} must remain false"
            )
    if value.get("one_signal_authority_preserved") is not True:
        raise CorpusDefinitionByteBindingError(
            f"{label}: one signal authority must be preserved"
        )
    if value.get("blind_forecasts_immutable") is not True:
        raise CorpusDefinitionByteBindingError(
            f"{label}: blind forecasts must remain immutable"
        )
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise CorpusDefinitionByteBindingError(
            f"{label}: CME event contracts must remain SHADOW"
        )
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise CorpusDefinitionByteBindingError(
            f"{label}: brokerage must remain tastytrade, not IBKR"
        )


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusDefinitionByteBindingError(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise CorpusDefinitionByteBindingError(
            f"JSON artifact must be an object: {path}"
        )
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _plan_sources(plan: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for corpus in plan.get("corpora") or []:
        corpus_id = str(corpus.get("corpus_id") or "")
        lane = str(corpus.get("lane") or "")
        for raw in corpus.get("sources") or []:
            source = copy.deepcopy(dict(raw))
            source_id = str(source.get("source_id") or "")
            if not source_id or source_id in result:
                raise CorpusDefinitionByteBindingError(
                    f"duplicate or missing planned source_id {source_id!r}"
                )
            source["corpus_id"] = corpus_id
            source["lane"] = lane
            result[source_id] = source
    return result


def _inspection_entries(receipt: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    catalog = receipt.get("catalog") or {}
    for corpus in catalog.get("corpora") or []:
        corpus_id = str(corpus.get("corpus_id") or "")
        lane = str(corpus.get("lane") or "")
        for raw in corpus.get("entries") or []:
            entry = copy.deepcopy(dict(raw))
            source_id = str(entry.get("source_id") or "")
            if not source_id or source_id in result:
                raise CorpusDefinitionByteBindingError(
                    f"duplicate or missing inspected source_id {source_id!r}"
                )
            entry["corpus_id"] = corpus_id
            entry["lane"] = lane
            result[source_id] = entry
    return result


def _binding_row(
    source_id: str,
    source: Mapping[str, Any],
    entry: Mapping[str, Any],
) -> dict[str, Any]:
    blockers: list[str] = []
    status = str(entry.get("status") or "UNKNOWN")
    definition_raw = source.get("definition")
    definition: dict[str, Any] | None = None
    if not isinstance(definition_raw, Mapping):
        blockers.append("DEFINITION_MISSING")
    else:
        try:
            definition = inspection.validate_definition(definition_raw)
        except Exception as error:
            blockers.append(f"DEFINITION_INVALID:{error}")

    if status != "PRESENT":
        blockers.append(f"INSPECTION_STATUS_{status}")

    expected_sha = None if definition is None else str(
        definition.get("source_sha256") or ""
    ).lower()
    expected_size = None if definition is None else int(
        definition.get("source_size_bytes") or 0
    )
    observed_sha = (
        str(entry.get("sha256") or "").lower() if status == "PRESENT" else None
    )
    observed_size = (
        int(entry.get("size_bytes") or 0) if status == "PRESENT" else None
    )

    if definition is not None and status == "PRESENT":
        if observed_sha != expected_sha:
            blockers.append("SOURCE_SHA256_MISMATCH")
        if observed_size != expected_size:
            blockers.append("SOURCE_SIZE_BYTES_MISMATCH")
        if entry.get("definition_fingerprint") != definition.get(
            "definition_fingerprint"
        ):
            blockers.append("DEFINITION_FINGERPRINT_MISMATCH")
        for field in (
            "dataset",
            "publisher_id",
            "instrument_id",
            "raw_symbol",
            "definition_date",
            "definition_start_s",
            "definition_end_s",
        ):
            if entry.get(field) != definition.get(field):
                blockers.append(f"DEFINITION_FIELD_MISMATCH:{field}")
        if str(entry.get("day") or "") != str(source.get("day") or ""):
            blockers.append("SOURCE_DAY_MISMATCH")
        if str(entry.get("lane") or "") != str(source.get("lane") or ""):
            blockers.append("SOURCE_LANE_MISMATCH")
        if str(entry.get("location") or "") != str(source.get("location") or ""):
            blockers.append("SOURCE_LOCATION_MISMATCH")
        planned_path = source.get("materialized_path")
        if planned_path not in (None, ""):
            try:
                planned_resolved = str(
                    Path(str(planned_path)).expanduser().resolve()
                )
                observed_resolved = str(
                    Path(str(entry.get("materialized_path") or ""))
                    .expanduser()
                    .resolve()
                )
                if observed_resolved != planned_resolved:
                    blockers.append("MATERIALIZED_PATH_MISMATCH")
            except OSError:
                blockers.append("MATERIALIZED_PATH_INVALID")

    row = {
        "source_id": source_id,
        "corpus_id": str(source.get("corpus_id") or ""),
        "lane": str(source.get("lane") or ""),
        "day": str(source.get("day") or ""),
        "location": str(source.get("location") or ""),
        "inspection_status": status,
        "definition_fingerprint": (
            None if definition is None else definition["definition_fingerprint"]
        ),
        "inspection_fingerprint": entry.get("inspection_fingerprint"),
        "expected_source_sha256": expected_sha,
        "observed_source_sha256": observed_sha,
        "expected_source_size_bytes": expected_size,
        "observed_source_size_bytes": observed_size,
        "byte_identity_matches_definition": not blockers,
        "blockers": sorted(set(blockers)),
    }
    row["binding_fingerprint"] = _fp(row)
    return row


def _build(
    compiler_receipt: Mapping[str, Any],
    inspection_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    checked_compiler = compiler.validate_receipt(compiler_receipt)
    checked_inspection = inspection.validate_receipt(inspection_receipt)
    plan = copy.deepcopy(dict(checked_compiler.get("compiled_plan") or {}))
    if checked_inspection.get("plan_fingerprint") != plan.get(
        "plan_fingerprint"
    ):
        raise CorpusDefinitionByteBindingError(
            "inspection receipt was not produced from the compiled inventory plan"
        )

    planned = _plan_sources(plan)
    inspected = _inspection_entries(checked_inspection)
    if set(planned) != set(inspected):
        missing = sorted(set(planned) - set(inspected))
        unexpected = sorted(set(inspected) - set(planned))
        raise CorpusDefinitionByteBindingError(
            "planned/inspected source set mismatch: "
            f"missing={missing}, unexpected={unexpected}"
        )

    bindings = [
        _binding_row(source_id, planned[source_id], inspected[source_id])
        for source_id in sorted(planned)
    ]
    blockers = sorted(
        {
            f"{row['source_id']}:{blocker}"
            for row in bindings
            for blocker in row["blockers"]
        }
    )
    if checked_compiler.get("status") != compiler.READY_STATUS:
        blockers.append("INVENTORY_COMPILER_NOT_READY")
        blockers.extend(
            f"INVENTORY:{blocker}"
            for blocker in checked_compiler.get("blockers") or []
        )
        blockers = sorted(set(blockers))

    corpus_summaries: list[dict[str, Any]] = []
    for corpus in plan.get("corpora") or []:
        corpus_id = str(corpus.get("corpus_id") or "")
        rows = [row for row in bindings if row["corpus_id"] == corpus_id]
        corpus_summaries.append(
            {
                "corpus_id": corpus_id,
                "lane": str(corpus.get("lane") or ""),
                "planned_source_count": len(rows),
                "present_source_count": sum(
                    row["inspection_status"] == "PRESENT" for row in rows
                ),
                "byte_bound_source_count": sum(
                    row["byte_identity_matches_definition"] for row in rows
                ),
                "blocked_source_ids": sorted(
                    row["source_id"]
                    for row in rows
                    if not row["byte_identity_matches_definition"]
                ),
            }
        )

    ready = bool(bindings) and not blockers
    value = {
        "schema": SCHEMA,
        "status": READY_STATUS if ready else BLOCKED_STATUS,
        "inventory_compiler_receipt_fingerprint": checked_compiler[
            "receipt_fingerprint"
        ],
        "inspection_receipt_fingerprint": checked_inspection[
            "receipt_fingerprint"
        ],
        "plan_fingerprint": plan["plan_fingerprint"],
        "catalog_fingerprint": checked_inspection["catalog_fingerprint"],
        "audit_fingerprint": checked_inspection["audit_fingerprint"],
        "source_count": len(bindings),
        "byte_bound_source_count": sum(
            row["byte_identity_matches_definition"] for row in bindings
        ),
        "bindings": bindings,
        "binding_set_fingerprint": _fp(bindings),
        "corpus_summaries": corpus_summaries,
        "blockers": blockers,
        "stand_down_required": not ready,
        "next_action": (
            "RUN_BROAD_CORPUS_SCOPE_AND_EXACT_ALIGNMENT_GATES"
            if ready
            else "RESOLVE_CORPUS_DEFINITION_BYTE_BINDING_BLOCKERS"
        ),
        "inventory_compiler_receipt": copy.deepcopy(checked_compiler),
        "inspection_receipt": copy.deepcopy(checked_inspection),
        **_authority_fields(),
    }
    value["fingerprint"] = _fp(value)
    return value


def build_gate(
    compiler_receipt: Mapping[str, Any],
    inspection_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    value = _build(compiler_receipt, inspection_receipt)
    validate_gate(value)
    return value


def validate_gate(value: Mapping[str, Any]) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise CorpusDefinitionByteBindingError(
            "definition-byte gate schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked, label="definition-byte gate")
    rebuilt = _build(
        checked.get("inventory_compiler_receipt") or {},
        checked.get("inspection_receipt") or {},
    )
    if _canonical(rebuilt) != _canonical(checked):
        raise CorpusDefinitionByteBindingError(
            "definition-byte gate does not match deterministic reconstruction"
        )
    return checked


def _self_test() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        rows = [
            {
                "event_type": "trade",
                "ts_event_s": 10.0,
                "source_sequence": 1,
                "price": 3.0,
                "size": 1,
                "side": "B",
            }
        ]
        paths: dict[str, Path] = {}
        definitions: dict[str, dict[str, Any]] = {}
        for source_id, lane in (("l1", "l1_trades"), ("mbo", "mbo")):
            payload_rows = copy.deepcopy(rows)
            if lane == "mbo":
                payload_rows[0]["event_type"] = "mbo"
                payload_rows[0]["action"] = "A"
            path = root / f"{source_id}.jsonl"
            path.write_text(
                "".join(json.dumps(row) + "\n" for row in payload_rows),
                encoding="utf-8",
            )
            raw = path.read_bytes()
            paths[source_id] = path
            definitions[source_id] = inspection.definition_observation(
                dataset=inspection.DATASET,
                publisher_id=1,
                instrument_id=996,
                raw_symbol="NGK26",
                definition_date="20260330",
                definition_start_s=0.0,
                definition_end_s=100.0,
                observed_from=f"selftest:{source_id}",
                observed_at="2026-07-24T00:00:00Z",
                source_sha256=hashlib.sha256(raw).hexdigest(),
                source_size_bytes=len(raw),
            )
        spec = {
            "schema": compiler.SPEC_SCHEMA,
            "allowed_roots": [str(root)],
            "inventory_observed_at": "2026-07-24T00:00:00Z",
            "corpora": [
                {
                    "corpus_id": "ng_l1_dense_trades_one_year",
                    "publisher_id": 1,
                    "expected_days": ["20260330"],
                    "expected_object_count": 1,
                    "inventory_scope_verified": True,
                    "inventory_complete_asserted": True,
                    "sources": [
                        {
                            "source_id": "l1",
                            "day": "20260330",
                            "location": "selftest:l1",
                            "materialized_path": str(paths["l1"]),
                            "definition": definitions["l1"],
                        }
                    ],
                },
                {
                    "corpus_id": "ng_mbo_spring_summer",
                    "publisher_id": 1,
                    "expected_days": ["20260330"],
                    "expected_object_count": 1,
                    "inventory_scope_verified": True,
                    "inventory_complete_asserted": True,
                    "sources": [
                        {
                            "source_id": "mbo",
                            "day": "20260330",
                            "location": "selftest:mbo",
                            "materialized_path": str(paths["mbo"]),
                            "definition": definitions["mbo"],
                        }
                    ],
                },
            ],
            **_authority_fields(),
        }
        plan, compiler_receipt = compiler.build_compiled_plan(
            spec, spec_dir=root
        )
        _, _, inspection_receipt = inspection.build_catalog(plan)
        gate = build_gate(compiler_receipt, inspection_receipt)
        assert gate["status"] == READY_STATUS
        validate_gate(gate)



def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=False)
    build = sub.add_parser("build", help="build the definition-byte binding gate")
    build.add_argument("--compiler-receipt", type=Path, required=True)
    build.add_argument("--inspection-receipt", type=Path, required=True)
    build.add_argument("--out", type=Path, required=True)
    validate = sub.add_parser("validate", help="validate a completed gate")
    validate.add_argument("--gate", type=Path, required=True)
    parser.add_argument("--self-test", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.self_test:
        _self_test()
        print("[ng_corpus_definition_byte_binding_gate] selftest PASS")
        return 0
    if args.command == "build":
        value = build_gate(
            _load_json(args.compiler_receipt),
            _load_json(args.inspection_receipt),
        )
        _write(args.out, value)
        print(
            json.dumps(
                {
                    "out": str(args.out),
                    "status": value["status"],
                    "source_count": value["source_count"],
                    "byte_bound_source_count": value["byte_bound_source_count"],
                    "blocker_count": len(value["blockers"]),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "validate":
        validate_gate(_load_json(args.gate))
        print("[ng_corpus_definition_byte_binding_gate] gate VALID")
        return 0
    _parser().error("select a command or --self-test")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
