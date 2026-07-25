#!/usr/bin/env python3
"""Canonical v15 readiness requiring definition-to-byte corpus binding.

V14 requires compiler-attested exact G16 final artifacts. V15 additionally inserts
an outcome-blind corpus provenance wall immediately after byte-level coverage:
every inspected object must match the SHA-256, byte size, dataset, publisher,
instrument, raw symbol, and definition period carried by its observed definition
before basis regeneration, broad-scope alignment, G15 replay, or G16 work may
advance.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

import ng_historical_refinement_readiness as legacy
import ng_historical_refinement_readiness_v14 as v14

SCHEMA = "ng_historical_refinement_readiness.v15"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V14_OVERALL_STATUS = v14._overall_status

_DEFINITION_BYTE_BINDING = StageSpec(
    "corpus_definition_byte_binding",
    "ng_corpus_definition_byte_binding_gate.json",
    "ng_corpus_definition_byte_binding_gate.v1",
    "fingerprint",
    frozenset({"CORPUS_DEFINITION_BYTES_BOUND_READY"}),
    "ng_corpus_definition_byte_binding_gate",
    ("validate_gate",),
    "Bind every inspected corpus object to the exact source SHA-256, byte size, and observed definition identity before basis regeneration.",
    required_fields=(
        "inventory_compiler_receipt_fingerprint",
        "inspection_receipt_fingerprint",
        "plan_fingerprint",
        "catalog_fingerprint",
        "audit_fingerprint",
        "source_count",
        "byte_bound_source_count",
        "binding_set_fingerprint",
    ),
    pre_outcome=True,
)


def _insert_definition_byte_binding() -> tuple[StageSpec, ...]:
    stages: list[StageSpec] = []
    for spec in v14.STAGES:
        stages.append(spec)
        if spec.key == "corpus_coverage":
            stages.append(_DEFINITION_BYTE_BINDING)
    return tuple(stages)


STAGES = _insert_definition_byte_binding()
LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    (
        "corpus_coverage",
        "fingerprint",
        "corpus_definition_byte_binding",
        "audit_fingerprint",
    ),
    (
        "corpus_definition_byte_binding",
        "inspection_receipt_fingerprint",
        "broad_corpus_scope",
        "inspection_receipt_fingerprint",
    ),
    (
        "corpus_definition_byte_binding",
        "catalog_fingerprint",
        "broad_corpus_scope",
        "catalog_fingerprint",
    ),
    (
        "corpus_definition_byte_binding",
        "audit_fingerprint",
        "broad_corpus_scope",
        "coverage_audit_fingerprint",
    ),
    *v14.LINK_RULES,
)


def _fingerprint(value: Any) -> str:
    return legacy._fingerprint(value)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _overall_status(ready_keys: list[str]) -> str:
    if (
        "g16_exact_publication_context_compilation" in ready_keys
        and len(ready_keys) == len(STAGES)
    ):
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V15"
    if (
        "corpus_definition_byte_binding" in ready_keys
        and "basis_inventory_regeneration" not in ready_keys
    ):
        return "CORPUS_DEFINITION_BYTES_BOUND_BASIS_REGENERATION_INCOMPLETE"
    if (
        "corpus_coverage" in ready_keys
        and "corpus_definition_byte_binding" not in ready_keys
    ):
        return "CORPUS_COVERAGE_COMPLETE_DEFINITION_BYTE_BINDING_INCOMPLETE"
    return _V14_OVERALL_STATUS(
        [key for key in ready_keys if key != "corpus_definition_byte_binding"]
    )


@contextmanager
def _v14_contract() -> Iterator[None]:
    saved = (v14.SCHEMA, v14.STAGES, v14.LINK_RULES, v14._overall_status)
    v14.SCHEMA = SCHEMA
    v14.STAGES = STAGES
    v14.LINK_RULES = LINK_RULES
    v14._overall_status = _overall_status
    try:
        yield
    finally:
        v14.SCHEMA, v14.STAGES, v14.LINK_RULES, v14._overall_status = saved


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]]
    | None = None,
) -> dict[str, Any]:
    with _v14_contract():
        report = v14.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    bound = "corpus_definition_byte_binding" in ready
    report["corpus_definition_bytes_bound_before_basis_regeneration"] = bound
    report["definition_byte_binding_required_before_broad_alignment"] = True
    report["inspection_only_route_rejected"] = True
    report["note"] = (
        "Readiness v15 requires the inspected corpus catalog to be joined to the "
        "observed definition source bytes before basis regeneration, broad-scope "
        "alignment, exact G15 replay, or pre-cutoff G16 work may advance."
    )
    report.pop("fingerprint", None)
    report["fingerprint"] = _fingerprint(report)
    validate_readiness_report(report)
    return report


def validate_readiness_report(report: Mapping[str, Any]) -> None:
    value = copy.deepcopy(dict(report))
    observed = value.get("fingerprint")
    payload = copy.deepcopy(value)
    payload.pop("fingerprint", None)
    if value.get("schema") != SCHEMA or observed != _fingerprint(payload):
        raise HistoricalRefinementReadinessError(
            "readiness v15 report schema or fingerprint mismatch"
        )
    with _v14_contract():
        v14.validate_readiness_report(value)

    ready = list(value.get("ready_stages") or [])
    coverage_ready = "corpus_coverage" in ready
    binding_ready = "corpus_definition_byte_binding" in ready
    basis_ready = "basis_inventory_regeneration" in ready
    if value.get("corpus_definition_bytes_bound_before_basis_regeneration") is not binding_ready:
        raise HistoricalRefinementReadinessError(
            "readiness v15 definition-byte summary mismatch"
        )
    for field in (
        "definition_byte_binding_required_before_broad_alignment",
        "inspection_only_route_rejected",
    ):
        if value.get(field) is not True:
            raise HistoricalRefinementReadinessError(
                f"readiness v15 mandatory field mismatch: {field}"
            )
    if binding_ready and not coverage_ready:
        raise HistoricalRefinementReadinessError(
            "definition-byte binding may not bypass corpus coverage"
        )
    if basis_ready and not binding_ready:
        raise HistoricalRefinementReadinessError(
            "basis regeneration may not bypass definition-to-byte binding"
        )

    stage_rows = {str(row.get("key")): row for row in value.get("stages") or []}
    binding_row = stage_rows.get("corpus_definition_byte_binding") or {}
    if binding_ready and binding_row.get("effective_status") not in {
        "READY",
        "READY_WITH_STAND_DOWNS",
    }:
        raise HistoricalRefinementReadinessError(
            "definition-byte summary claims readiness while stage is not ready"
        )

    for field in (
        "remote_presence_inferred",
        "actual_outcome_paths_loaded",
        "paid_live_data_assumed",
        "random_shuffle_used",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    ):
        if value.get(field) is not False:
            raise HistoricalRefinementReadinessError(
                f"readiness v15 must keep {field}=false"
            )
    if value.get("one_signal_authority_preserved") is not True:
        raise HistoricalRefinementReadinessError(
            "one signal authority was not preserved"
        )
    if value.get("blind_forecasts_immutable") is not True:
        raise HistoricalRefinementReadinessError("blind forecasts were not preserved")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise HistoricalRefinementReadinessError(
            "CME event contracts must remain SHADOW"
        )
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise HistoricalRefinementReadinessError(
            "brokerage contract must remain tastytrade, not IBKR"
        )


def _binding_fixture(
    coverage: Mapping[str, Any], broad_scope: Mapping[str, Any]
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema": "ng_corpus_definition_byte_binding_gate.v1",
        "status": "CORPUS_DEFINITION_BYTES_BOUND_READY",
        "inventory_compiler_receipt_fingerprint": "inventory-compiler",
        "inspection_receipt_fingerprint": broad_scope[
            "inspection_receipt_fingerprint"
        ],
        "plan_fingerprint": "inspection-plan",
        "catalog_fingerprint": broad_scope["catalog_fingerprint"],
        "audit_fingerprint": coverage["fingerprint"],
        "source_count": 2,
        "byte_bound_source_count": 2,
        "bindings": [],
        "binding_set_fingerprint": "binding-set",
        "corpus_summaries": [],
        "blockers": [],
        "stand_down_required": False,
        "next_action": "RUN_BROAD_CORPUS_SCOPE_AND_EXACT_ALIGNMENT_GATES",
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
    value["fingerprint"] = _fingerprint(value)
    return value


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    values = v14._linked_fixture_chain()
    values["corpus_definition_byte_binding"] = _binding_fixture(
        values["corpus_coverage"], values["broad_corpus_scope"]
    )
    return values


def selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as tempdir:
        root = Path(tempdir)
        overrides = {spec.key: (lambda value: None) for spec in STAGES}
        missing = build_readiness_report(root, validator_overrides=overrides)
        assert missing["first_blocking_stage"] == "corpus_coverage"

        values = _linked_fixture_chain()
        for spec in STAGES:
            _atomic_json(root / spec.filename, values[spec.key])
        complete = build_readiness_report(root, validator_overrides=overrides)
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V15"
        assert complete["corpus_definition_bytes_bound_before_basis_regeneration"] is True

        (root / _DEFINITION_BYTE_BINDING.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == "corpus_definition_byte_binding"
        basis = next(
            row
            for row in blocked["stages"]
            if row["key"] == "basis_inventory_regeneration"
        )
        assert basis["effective_status"] == "BLOCKED_BY_UPSTREAM"
    print("[ng_historical_refinement_readiness_v15] selftest PASS")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-dir", type=Path, default=Path("renders/ng_refine_s95")
    )
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    report = build_readiness_report(args.artifact_dir)
    output = args.out or args.artifact_dir / "ng_historical_refinement_readiness_v15.json"
    _atomic_json(output, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "first_blocking_stage": report["first_blocking_stage"],
                "ready_stage_count": len(report["ready_stages"]),
                "total_stage_count": len(STAGES),
                "out": str(output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
