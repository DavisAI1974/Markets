#!/usr/bin/env python3
"""Compile a canonical NG corpus-inspection plan from an explicit remote inventory.

This is the deterministic handoff between an AWS/S3 inventory export and
``ng_corpus_inspection.py``. It never infers identity from object names. Every
materialized source intended to count toward a complete inventory must carry an
observed, fingerprinted definition record for dataset, publisher, instrument,
raw symbol, and definition period.

The compiler is historical-first and outcome-blind. It cannot mutate forecasts,
posterior state, ``knowledge/ng_brain.json``, execution authority, or options.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

import ng_corpus_coverage_audit as coverage
import ng_corpus_inspection as inspection

SPEC_SCHEMA = "ng_corpus_inventory_spec.v1"
RECEIPT_SCHEMA = "ng_corpus_inventory_plan_compiler.v1"
READY_STATUS = "CORPUS_INSPECTION_PLAN_COMPILED_READY"
BLOCKED_STATUS = "CORPUS_INSPECTION_PLAN_COMPILED_WITH_BLOCKERS"


class CorpusInventoryPlanCompilerError(ValueError):
    """Raised when remote-inventory evidence is malformed or contradictory."""


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


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusInventoryPlanCompilerError(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise CorpusInventoryPlanCompilerError(
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
            raise CorpusInventoryPlanCompilerError(
                f"{label}: {field} must remain false"
            )
    if value.get("one_signal_authority_preserved") is not True:
        raise CorpusInventoryPlanCompilerError(
            f"{label}: one signal authority must be preserved"
        )
    if value.get("blind_forecasts_immutable") is not True:
        raise CorpusInventoryPlanCompilerError(
            f"{label}: blind forecasts must remain immutable"
        )
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise CorpusInventoryPlanCompilerError(
            f"{label}: CME event contracts must remain SHADOW"
        )
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise CorpusInventoryPlanCompilerError(
            f"{label}: brokerage must remain tastytrade, not IBKR"
        )


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


def _positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise CorpusInventoryPlanCompilerError(
            f"{label} must be a positive integer"
        )
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CorpusInventoryPlanCompilerError(
            f"{label} must be a positive integer"
        ) from error
    if number <= 0:
        raise CorpusInventoryPlanCompilerError(
            f"{label} must be a positive integer"
        )
    return number


def _day(value: Any, *, label: str) -> str:
    text = str(value or "").strip().replace("-", "")
    if len(text) != 8 or not text.isdigit():
        raise CorpusInventoryPlanCompilerError(
            f"{label}: invalid day {value!r}"
        )
    try:
        date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    except ValueError as error:
        raise CorpusInventoryPlanCompilerError(
            f"{label}: invalid day {value!r}"
        ) from error
    return text


def _inside_window(day: str, window: Mapping[str, str]) -> bool:
    parsed = date(int(day[:4]), int(day[4:6]), int(day[6:8]))
    return (
        date.fromisoformat(window["start"])
        <= parsed
        < date.fromisoformat(window["end_exclusive"])
    )


def _safe_reference(spec_dir: Path, reference: Any, *, label: str) -> Path:
    text = str(reference or "")
    if not text:
        raise CorpusInventoryPlanCompilerError(
            f"{label}: definition_path is required"
        )
    path = Path(text)
    if path.is_absolute():
        raise CorpusInventoryPlanCompilerError(
            f"{label}: definition_path must be relative"
        )
    root = spec_dir.resolve()
    resolved = (root / path).resolve()
    if resolved != root and root not in resolved.parents:
        raise CorpusInventoryPlanCompilerError(
            f"{label}: definition_path escapes the spec directory"
        )
    return resolved


def _definition_from_document(
    source: Mapping[str, Any],
    *,
    source_id: str,
    spec_dir: Path,
    embedded_documents: Mapping[str, Mapping[str, Any]] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    inline = source.get("definition")
    reference = source.get("definition_path")
    if inline not in (None, "") and reference not in (None, ""):
        raise CorpusInventoryPlanCompilerError(
            f"{source_id}: provide exactly one of definition or definition_path"
        )
    if inline not in (None, ""):
        if not isinstance(inline, Mapping):
            raise CorpusInventoryPlanCompilerError(
                f"{source_id}: definition must be an object"
            )
        return inspection.validate_definition(inline), None
    if reference in (None, ""):
        return None, None

    reference_text = str(reference)
    _safe_reference(spec_dir, reference_text, label=source_id)
    if embedded_documents is None:
        path = _safe_reference(spec_dir, reference_text, label=source_id)
        try:
            raw = path.read_bytes()
        except OSError as error:
            raise CorpusInventoryPlanCompilerError(
                f"{source_id}: cannot read definition document {path}: {error}"
            ) from error
        document = {
            "source_id": source_id,
            "reference": reference_text,
            "raw_text": raw.decode("utf-8"),
            "sha256": _sha256_bytes(raw),
            "size_bytes": len(raw),
        }
    else:
        document = copy.deepcopy(
            dict(embedded_documents.get(source_id) or {})
        )
        if (
            document.get("source_id") != source_id
            or document.get("reference") != reference_text
        ):
            raise CorpusInventoryPlanCompilerError(
                f"{source_id}: embedded definition document mismatch"
            )
        raw_text = str(document.get("raw_text") or "")
        raw = raw_text.encode("utf-8")
        if (
            document.get("sha256") != _sha256_bytes(raw)
            or document.get("size_bytes") != len(raw)
        ):
            raise CorpusInventoryPlanCompilerError(
                f"{source_id}: embedded definition bytes mismatch"
            )

    expected_sha = source.get("definition_sha256")
    if (
        expected_sha not in (None, "")
        and str(expected_sha).lower() != document["sha256"]
    ):
        raise CorpusInventoryPlanCompilerError(
            f"{source_id}: definition_sha256 mismatch"
        )
    try:
        parsed = json.loads(str(document["raw_text"]))
    except json.JSONDecodeError as error:
        raise CorpusInventoryPlanCompilerError(
            f"{source_id}: definition document is invalid JSON"
        ) from error
    if not isinstance(parsed, dict):
        raise CorpusInventoryPlanCompilerError(
            f"{source_id}: definition document must contain an object"
        )
    return inspection.validate_definition(parsed), document


def _resolve_spec(
    source_spec: Mapping[str, Any],
    *,
    spec_dir: Path,
    embedded_documents: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    spec = copy.deepcopy(dict(source_spec))
    if spec.get("schema") != SPEC_SCHEMA:
        raise CorpusInventoryPlanCompilerError(
            f"inventory spec schema must be {SPEC_SCHEMA}"
        )
    _authority(spec, label="inventory spec")
    allowed_roots = [str(root) for root in spec.get("allowed_roots") or []]
    if not allowed_roots:
        raise CorpusInventoryPlanCompilerError(
            "inventory spec requires at least one allowed_root"
        )
    if not str(spec.get("inventory_observed_at") or ""):
        raise CorpusInventoryPlanCompilerError(
            "inventory_observed_at is required"
        )

    documents_by_source = None
    if embedded_documents is not None:
        documents_by_source = {}
        for raw in embedded_documents:
            if not isinstance(raw, Mapping):
                raise CorpusInventoryPlanCompilerError(
                    "embedded definition document is not an object"
                )
            source_id = str(raw.get("source_id") or "")
            if not source_id or source_id in documents_by_source:
                raise CorpusInventoryPlanCompilerError(
                    "duplicate or missing embedded definition source_id"
                )
            documents_by_source[source_id] = raw

    corpora = list(spec.get("corpora") or [])
    if len(corpora) != len(coverage.EXPECTED_WINDOWS):
        raise CorpusInventoryPlanCompilerError(
            "inventory spec must contain both canonical corpora"
        )
    seen_corpora: set[str] = set()
    seen_sources: set[str] = set()
    resolved_corpora: list[dict[str, Any]] = []
    documents: list[dict[str, Any]] = []

    for raw_corpus in corpora:
        if not isinstance(raw_corpus, Mapping):
            raise CorpusInventoryPlanCompilerError(
                "inventory corpus is not an object"
            )
        corpus = copy.deepcopy(dict(raw_corpus))
        corpus_id = str(corpus.get("corpus_id") or "")
        expected = coverage.EXPECTED_WINDOWS.get(corpus_id)
        if expected is None or corpus_id in seen_corpora:
            raise CorpusInventoryPlanCompilerError(
                f"unexpected or duplicate corpus_id {corpus_id!r}"
            )
        seen_corpora.add(corpus_id)
        if corpus.get("lane", expected["lane"]) != expected["lane"]:
            raise CorpusInventoryPlanCompilerError(
                f"{corpus_id}: lane mismatch"
            )
        publisher_id = _positive_int(
            corpus.get("publisher_id"), label=f"{corpus_id}:publisher_id"
        )
        expected_days = [
            _day(day, label=f"{corpus_id}:expected_day")
            for day in corpus.get("expected_days") or []
        ]
        if len(expected_days) != len(set(expected_days)):
            raise CorpusInventoryPlanCompilerError(
                f"{corpus_id}: duplicate expected_days"
            )
        if any(not _inside_window(day, expected) for day in expected_days):
            raise CorpusInventoryPlanCompilerError(
                f"{corpus_id}: expected day outside canonical window"
            )
        expected_count_raw = corpus.get("expected_object_count")
        expected_count = (
            None
            if expected_count_raw in (None, "")
            else _positive_int(
                expected_count_raw,
                label=f"{corpus_id}:expected_object_count",
            )
        )
        sources: list[dict[str, Any]] = []
        for raw_source in corpus.get("sources") or []:
            if not isinstance(raw_source, Mapping):
                raise CorpusInventoryPlanCompilerError(
                    f"{corpus_id}: source is not an object"
                )
            source = copy.deepcopy(dict(raw_source))
            source_id = str(source.get("source_id") or "")
            if not source_id or source_id in seen_sources:
                raise CorpusInventoryPlanCompilerError(
                    f"duplicate or missing source_id {source_id!r}"
                )
            seen_sources.add(source_id)
            day = _day(source.get("day"), label=source_id)
            if not _inside_window(day, expected):
                raise CorpusInventoryPlanCompilerError(
                    f"{source_id}: day outside canonical window"
                )
            if source.get("lane", expected["lane"]) != expected["lane"]:
                raise CorpusInventoryPlanCompilerError(
                    f"{source_id}: lane mismatch"
                )
            if not str(source.get("location") or ""):
                raise CorpusInventoryPlanCompilerError(
                    f"{source_id}: location is required"
                )
            definition, document = _definition_from_document(
                source,
                source_id=source_id,
                spec_dir=spec_dir,
                embedded_documents=documents_by_source,
            )
            if definition is not None:
                if int(definition["publisher_id"]) != publisher_id:
                    raise CorpusInventoryPlanCompilerError(
                        f"{source_id}: definition publisher mismatch"
                    )
                if definition["dataset"] != coverage.DATASET:
                    raise CorpusInventoryPlanCompilerError(
                        f"{source_id}: definition dataset mismatch"
                    )
            compiled_source = {
                "source_id": source_id,
                "day": day,
                "lane": expected["lane"],
                "location": str(source["location"]),
                "materialized_path": source.get("materialized_path"),
                "definition": definition,
                "skip_nonmatching": source.get("skip_nonmatching") is True,
                "inventory_observed_at": str(
                    source.get("inventory_observed_at")
                    or spec["inventory_observed_at"]
                ),
            }
            sources.append(compiled_source)
            if document is not None:
                documents.append(document)

        resolved_corpora.append(
            {
                "corpus_id": corpus_id,
                "lane": expected["lane"],
                "publisher_id": publisher_id,
                "expected_days": expected_days,
                "expected_object_count": expected_count,
                "inventory_scope_verified": (
                    corpus.get("inventory_scope_verified") is True
                ),
                "inventory_complete_asserted": (
                    corpus.get("inventory_complete_asserted") is True
                ),
                "inventory_observed_at": str(
                    corpus.get("inventory_observed_at")
                    or spec["inventory_observed_at"]
                ),
                "sources": sources,
            }
        )

    if seen_corpora != set(coverage.EXPECTED_WINDOWS):
        raise CorpusInventoryPlanCompilerError(
            "inventory spec is missing a canonical corpus"
        )
    resolved = {
        "schema": SPEC_SCHEMA,
        "allowed_roots": allowed_roots,
        "inventory_observed_at": str(spec["inventory_observed_at"]),
        "corpora": resolved_corpora,
        **_authority_fields(),
    }
    return resolved, sorted(
        documents, key=lambda row: str(row["source_id"])
    )


def _build_from_resolved(
    resolved: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str], list[dict[str, Any]]]:
    _authority(resolved, label="resolved inventory spec")
    plan = inspection.plan_template(
        allowed_roots=list(resolved.get("allowed_roots") or [])
    )
    plan_corpora: list[dict[str, Any]] = []
    blockers: list[str] = []
    summaries: list[dict[str, Any]] = []
    for corpus in resolved.get("corpora") or []:
        corpus_id = str(corpus["corpus_id"])
        expected = coverage.EXPECTED_WINDOWS[corpus_id]
        sources = copy.deepcopy(list(corpus.get("sources") or []))
        expected_days = sorted(
            str(day) for day in corpus.get("expected_days") or []
        )
        source_days = sorted(
            {str(source.get("day") or "") for source in sources}
        )
        expected_count = corpus.get("expected_object_count")
        corpus_blockers: list[str] = []
        if corpus.get("inventory_scope_verified") is not True:
            corpus_blockers.append("REMOTE_INVENTORY_SCOPE_UNVERIFIED")
        if corpus.get("inventory_complete_asserted") is not True:
            corpus_blockers.append("INVENTORY_NOT_ASSERTED_COMPLETE")
        if not expected_days:
            corpus_blockers.append("EXPECTED_DAY_SET_EMPTY")
        if expected_count is None:
            corpus_blockers.append("EXPECTED_OBJECT_COUNT_UNDECLARED")
        elif int(expected_count) != len(sources):
            corpus_blockers.append("EXPECTED_OBJECT_COUNT_MISMATCH")
        missing_days = sorted(set(expected_days) - set(source_days))
        unexpected_days = sorted(set(source_days) - set(expected_days))
        if missing_days:
            corpus_blockers.append("EXPECTED_DAY_WITHOUT_SOURCE")
        if unexpected_days:
            corpus_blockers.append("SOURCE_DAY_NOT_DECLARED_EXPECTED")
        missing_materialized = sorted(
            str(source["source_id"])
            for source in sources
            if source.get("materialized_path") in (None, "")
        )
        missing_definitions = sorted(
            str(source["source_id"])
            for source in sources
            if not isinstance(source.get("definition"), Mapping)
        )
        if missing_materialized:
            corpus_blockers.append("SOURCE_NOT_MATERIALIZED")
        if missing_definitions:
            corpus_blockers.append("SOURCE_DEFINITION_MISSING")
        blockers.extend(
            f"{corpus_id}:{blocker}" for blocker in corpus_blockers
        )
        summaries.append(
            {
                "corpus_id": corpus_id,
                "lane": expected["lane"],
                "expected_day_count": len(expected_days),
                "source_count": len(sources),
                "expected_object_count": expected_count,
                "missing_expected_days": missing_days,
                "unexpected_source_days": unexpected_days,
                "unmaterialized_source_ids": missing_materialized,
                "missing_definition_source_ids": missing_definitions,
                "blockers": corpus_blockers,
            }
        )
        plan_corpora.append(
            {
                "corpus_id": corpus_id,
                "lane": expected["lane"],
                "declared_window": {
                    "start": expected["start"],
                    "end_exclusive": expected["end_exclusive"],
                },
                "publisher_id": int(corpus["publisher_id"]),
                "expected_days": expected_days,
                "expected_object_count": expected_count,
                "inventory_scope_verified": (
                    corpus.get("inventory_scope_verified") is True
                ),
                "inventory_complete_asserted": (
                    corpus.get("inventory_complete_asserted") is True
                ),
                "inventory_observed_at": str(
                    corpus.get("inventory_observed_at") or ""
                ),
                "sources": sources,
            }
        )
    plan["corpora"] = plan_corpora
    plan.pop("plan_fingerprint", None)
    plan["plan_fingerprint"] = inspection._fp(plan)
    inspection._validate_plan(plan)
    return plan, sorted(set(blockers)), summaries


def build_compiled_plan(
    source_spec: Mapping[str, Any],
    *,
    spec_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    resolved, documents = _resolve_spec(source_spec, spec_dir=spec_dir)
    plan, blockers, summaries = _build_from_resolved(resolved)
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "status": READY_STATUS if not blockers else BLOCKED_STATUS,
        "source_spec": copy.deepcopy(dict(source_spec)),
        "resolved_spec": resolved,
        "definition_documents": documents,
        "source_spec_fingerprint": _fp(source_spec),
        "resolved_spec_fingerprint": _fp(resolved),
        "plan_fingerprint": plan["plan_fingerprint"],
        "compiled_plan": plan,
        "corpus_summaries": summaries,
        "blockers": blockers,
        "next_action": (
            "RUN_BYTE_LEVEL_CORPUS_INSPECTION"
            if not blockers
            else "RESOLVE_INVENTORY_PLAN_BLOCKERS_BEFORE_BYTE_INSPECTION"
        ),
        **_authority_fields(),
    }
    receipt["receipt_fingerprint"] = _fp(receipt)
    validate_receipt(receipt)
    return plan, receipt


def validate_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("receipt_fingerprint", None)
    if (
        checked.get("schema") != RECEIPT_SCHEMA
        or observed != _fp(checked)
    ):
        raise CorpusInventoryPlanCompilerError(
            "compiler receipt schema or fingerprint mismatch"
        )
    checked["receipt_fingerprint"] = observed
    _authority(checked, label="compiler receipt")
    source_spec = copy.deepcopy(dict(checked.get("source_spec") or {}))
    if checked.get("source_spec_fingerprint") != _fp(source_spec):
        raise CorpusInventoryPlanCompilerError(
            "source spec fingerprint mismatch"
        )
    resolved, documents = _resolve_spec(
        source_spec,
        spec_dir=Path("."),
        embedded_documents=list(checked.get("definition_documents") or []),
    )
    if (
        resolved != checked.get("resolved_spec")
        or documents != checked.get("definition_documents")
    ):
        raise CorpusInventoryPlanCompilerError(
            "resolved inventory evidence mismatch"
        )
    if checked.get("resolved_spec_fingerprint") != _fp(resolved):
        raise CorpusInventoryPlanCompilerError(
            "resolved spec fingerprint mismatch"
        )
    plan, blockers, summaries = _build_from_resolved(resolved)
    if (
        plan != checked.get("compiled_plan")
        or checked.get("plan_fingerprint") != plan["plan_fingerprint"]
    ):
        raise CorpusInventoryPlanCompilerError(
            "compiled inspection plan mismatch"
        )
    if (
        blockers != list(checked.get("blockers") or [])
        or summaries != list(checked.get("corpus_summaries") or [])
    ):
        raise CorpusInventoryPlanCompilerError(
            "compiler blockers or summaries mismatch"
        )
    expected_status = READY_STATUS if not blockers else BLOCKED_STATUS
    expected_action = (
        "RUN_BYTE_LEVEL_CORPUS_INSPECTION"
        if not blockers
        else "RESOLVE_INVENTORY_PLAN_BLOCKERS_BEFORE_BYTE_INSPECTION"
    )
    if (
        checked.get("status") != expected_status
        or checked.get("next_action") != expected_action
    ):
        raise CorpusInventoryPlanCompilerError(
            "compiler status or next action mismatch"
        )
    return checked


def _self_test() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        allowed = root / "data"
        allowed.mkdir()
        definitions: dict[str, dict[str, Any]] = {}
        for source_id, symbol, instrument, day in (
            ("l1", "NGJ26", 1008, "20260315"),
            ("mbo", "NGJ26", 1008, "20260315"),
        ):
            payload = b"{}\n"
            path = allowed / f"{source_id}.jsonl"
            path.write_bytes(payload)
            definitions[source_id] = inspection.definition_observation(
                dataset=coverage.DATASET,
                publisher_id=1,
                instrument_id=instrument,
                raw_symbol=symbol,
                definition_date=day,
                definition_start_s=0.0,
                definition_end_s=1.0,
                observed_from="selftest",
                observed_at="2026-07-24T00:00:00Z",
                source_sha256=_sha256_bytes(payload),
                source_size_bytes=len(payload),
            )
        spec = {
            "schema": SPEC_SCHEMA,
            "allowed_roots": [str(allowed)],
            "inventory_observed_at": "2026-07-24T00:00:00Z",
            "corpora": [
                {
                    "corpus_id": coverage.L1_CORPUS_ID,
                    "publisher_id": 1,
                    "expected_days": ["20260315"],
                    "expected_object_count": 1,
                    "inventory_scope_verified": True,
                    "inventory_complete_asserted": True,
                    "sources": [
                        {
                            "source_id": "l1",
                            "day": "20260315",
                            "location": "selftest:l1",
                            "materialized_path": str(allowed / "l1.jsonl"),
                            "definition": definitions["l1"],
                        }
                    ],
                },
                {
                    "corpus_id": coverage.MBO_CORPUS_ID,
                    "publisher_id": 1,
                    "expected_days": ["20260315"],
                    "expected_object_count": 1,
                    "inventory_scope_verified": True,
                    "inventory_complete_asserted": True,
                    "sources": [
                        {
                            "source_id": "mbo",
                            "day": "20260315",
                            "location": "selftest:mbo",
                            "materialized_path": str(allowed / "mbo.jsonl"),
                            "definition": definitions["mbo"],
                        }
                    ],
                },
            ],
            **_authority_fields(),
        }
        _, receipt = build_compiled_plan(spec, spec_dir=root)
        assert receipt["status"] == READY_STATUS
        validate_receipt(receipt)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    subparsers = parser.add_subparsers(dest="command")
    compile_parser = subparsers.add_parser("compile")
    compile_parser.add_argument("--spec", type=Path, required=True)
    compile_parser.add_argument("--plan-out", type=Path, required=True)
    compile_parser.add_argument("--receipt-out", type=Path, required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--receipt", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.self_test:
        _self_test()
        return 0
    if args.command == "compile":
        spec = _load_json(args.spec)
        plan, receipt = build_compiled_plan(
            spec, spec_dir=args.spec.parent
        )
        _write(args.plan_out, plan)
        _write(args.receipt_out, receipt)
        return 0
    if args.command == "validate":
        validate_receipt(_load_json(args.receipt))
        return 0
    raise CorpusInventoryPlanCompilerError(
        "choose compile, validate, or --self-test"
    )


if __name__ == "__main__":
    raise SystemExit(main())
