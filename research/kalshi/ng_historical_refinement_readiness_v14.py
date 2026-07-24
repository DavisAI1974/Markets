#!/usr/bin/env python3
"""Canonical v14 readiness requiring compiler-backed exact G16 final artifacts.

V13 preserves exact replay-byte/event-window proof and locked G15 lesson lineage
through the G16 curve lock and scored publication. V14 additionally requires
standalone deterministic attestations proving that both final artifacts were built
through the fingerprinted context compiler, with the pre-outcome lock attestation
bound into the post-lock publication attestation.
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
import ng_historical_refinement_readiness_v13 as v13

SCHEMA = "ng_historical_refinement_readiness.v14"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V13_OVERALL_STATUS = v13._overall_status

_LOCK_ATTESTATION = StageSpec(
    "g16_exact_lock_context_compilation",
    "g16_exact_lock_context_compilation_attestation.json",
    "ng_g16_exact_context_compilation_attestation.v1",
    "fingerprint",
    frozenset({"EXACT_G16_LOCK_CONTEXT_COMPILATION_ATTESTED"}),
    "ng_g16_exact_context_compilation_gate",
    ("validate_attestation",),
    "Reconstruct the pre-outcome exact G16 lock from its spec, resolved context, reference bytes, and compiler receipt before fixed outcomes may open.",
    required_fields=(
        "artifact_fingerprint",
        "compiler_receipt_fingerprint",
        "reference_set_fingerprint",
    ),
    pre_outcome=True,
)

_PUBLICATION_ATTESTATION = StageSpec(
    "g16_exact_publication_context_compilation",
    "g16_exact_publication_context_compilation_attestation.json",
    "ng_g16_exact_context_compilation_attestation.v1",
    "fingerprint",
    frozenset({"EXACT_G16_PUBLICATION_CONTEXT_COMPILATION_ATTESTED"}),
    "ng_g16_exact_context_compilation_gate",
    ("validate_attestation",),
    "Reconstruct the post-lock exact G16 publication from its compiler inputs and bind it to the attested pre-outcome lock.",
    required_fields=(
        "artifact_fingerprint",
        "compiler_receipt_fingerprint",
        "reference_set_fingerprint",
        "lock_context_compilation_attestation_fingerprint",
        "source_lock_artifact_fingerprint",
    ),
    pre_outcome=False,
)


def _insert_attestations() -> tuple[StageSpec, ...]:
    stages: list[StageSpec] = []
    for spec in v13.STAGES:
        stages.append(spec)
        if spec.key == "g16_counterfactual_curve_lock":
            stages.append(_LOCK_ATTESTATION)
        if spec.key == "g16_counterfactual_publication":
            stages.append(_PUBLICATION_ATTESTATION)
    return tuple(stages)


STAGES = _insert_attestations()
LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    *v13.LINK_RULES,
    (
        "g16_counterfactual_curve_lock",
        "lock_fingerprint",
        "g16_exact_lock_context_compilation",
        "artifact_fingerprint",
    ),
    (
        "g16_counterfactual_publication",
        "completion_fingerprint",
        "g16_exact_publication_context_compilation",
        "artifact_fingerprint",
    ),
    (
        "g16_exact_lock_context_compilation",
        "fingerprint",
        "g16_exact_publication_context_compilation",
        "lock_context_compilation_attestation_fingerprint",
    ),
    (
        "g16_counterfactual_curve_lock",
        "lock_fingerprint",
        "g16_exact_publication_context_compilation",
        "source_lock_artifact_fingerprint",
    ),
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
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V14"
    if (
        "g16_counterfactual_publication" in ready_keys
        and "g16_exact_publication_context_compilation" not in ready_keys
    ):
        return "G16_EXACT_PUBLICATION_COMPLETE_COMPILER_ATTESTATION_INCOMPLETE"
    if (
        "g16_exact_lock_context_compilation" in ready_keys
        and "g16_counterfactual_publication" not in ready_keys
    ):
        return "G16_EXACT_LOCK_COMPILER_ATTESTED_FIXED_SCORING_INCOMPLETE"
    if (
        "g16_counterfactual_curve_lock" in ready_keys
        and "g16_exact_lock_context_compilation" not in ready_keys
    ):
        return "G16_EXACT_LOCK_COMPLETE_COMPILER_ATTESTATION_INCOMPLETE"
    return _V13_OVERALL_STATUS(ready_keys)


@contextmanager
def _v13_contract() -> Iterator[None]:
    saved = (v13.SCHEMA, v13.STAGES, v13.LINK_RULES, v13._overall_status)
    v13.SCHEMA = SCHEMA
    v13.STAGES = STAGES
    v13.LINK_RULES = LINK_RULES
    v13._overall_status = _overall_status
    try:
        yield
    finally:
        v13.SCHEMA, v13.STAGES, v13.LINK_RULES, v13._overall_status = saved


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]]
    | None = None,
) -> dict[str, Any]:
    with _v13_contract():
        report = v13.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    lock_attested = "g16_exact_lock_context_compilation" in ready
    publication_attested = "g16_exact_publication_context_compilation" in ready
    report["g16_exact_lock_built_through_context_compiler"] = lock_attested
    report["g16_exact_publication_built_through_context_compiler"] = (
        publication_attested
    )
    report["g16_publication_compiler_attestation_binds_pre_outcome_lock"] = (
        publication_attested
    )
    report["note"] = (
        "Readiness v14 requires standalone deterministic compiler attestations for "
        "the exact G16 pre-outcome lock and post-lock publication. The publication "
        "attestation must embed and bind the exact lock attestation."
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
            "readiness v14 report schema or fingerprint mismatch"
        )
    with _v13_contract():
        v13.validate_readiness_report(value)

    ready = list(value.get("ready_stages") or [])
    lock_ready = "g16_counterfactual_curve_lock" in ready
    lock_attested = "g16_exact_lock_context_compilation" in ready
    publication_ready = "g16_counterfactual_publication" in ready
    publication_attested = "g16_exact_publication_context_compilation" in ready
    summaries = {
        "g16_exact_lock_built_through_context_compiler": lock_attested,
        "g16_exact_publication_built_through_context_compiler": publication_attested,
        "g16_publication_compiler_attestation_binds_pre_outcome_lock": publication_attested,
    }
    for field, expected in summaries.items():
        if value.get(field) is not expected:
            raise HistoricalRefinementReadinessError(
                f"readiness v14 {field} summary mismatch"
            )
    if lock_attested and not lock_ready:
        raise HistoricalRefinementReadinessError(
            "lock compiler attestation may not bypass the exact curve lock"
        )
    if publication_ready and not lock_attested:
        raise HistoricalRefinementReadinessError(
            "fixed G16 publication may not bypass lock compiler attestation"
        )
    if publication_attested and not publication_ready:
        raise HistoricalRefinementReadinessError(
            "publication compiler attestation may not bypass exact publication"
        )
    if publication_attested and not lock_attested:
        raise HistoricalRefinementReadinessError(
            "publication compiler attestation may not bypass lock compiler attestation"
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
                f"readiness v14 must keep {field}=false"
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


def _attestation_fixture(
    *,
    mode: str,
    artifact_fingerprint: str,
    lock_attestation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema": "ng_g16_exact_context_compilation_attestation.v1",
        "mode": mode,
        "status": (
            "EXACT_G16_LOCK_CONTEXT_COMPILATION_ATTESTED"
            if mode == "lock"
            else "EXACT_G16_PUBLICATION_CONTEXT_COMPILATION_ATTESTED"
        ),
        "artifact_fingerprint": artifact_fingerprint,
        "compiler_receipt_fingerprint": f"{mode}-receipt",
        "reference_set_fingerprint": f"{mode}-references",
        "lock_context_compilation_attestation_fingerprint": (
            lock_attestation.get("fingerprint") if lock_attestation else None
        ),
        "source_lock_artifact_fingerprint": (
            lock_attestation.get("artifact_fingerprint") if lock_attestation else None
        ),
        "actual_g16_outcomes_used": mode == "complete",
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
    }
    value["fingerprint"] = _fingerprint(value)
    return value


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    values = v13._linked_fixture_chain()
    lock = values["g16_counterfactual_curve_lock"]
    lock_attestation = _attestation_fixture(
        mode="lock", artifact_fingerprint=lock["lock_fingerprint"]
    )
    values["g16_exact_lock_context_compilation"] = lock_attestation
    publication = values["g16_counterfactual_publication"]
    values["g16_exact_publication_context_compilation"] = _attestation_fixture(
        mode="complete",
        artifact_fingerprint=publication["completion_fingerprint"],
        lock_attestation=lock_attestation,
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
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V14"
        assert complete["g16_exact_lock_built_through_context_compiler"] is True
        assert complete["g16_exact_publication_built_through_context_compiler"] is True

        (root / _LOCK_ATTESTATION.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == "g16_exact_lock_context_compilation"
        publication = next(
            row
            for row in blocked["stages"]
            if row["key"] == "g16_counterfactual_publication"
        )
        assert publication["effective_status"] == "BLOCKED_BY_UPSTREAM"
    print("[ng_historical_refinement_readiness_v14] selftest PASS")
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
    output = args.out or args.artifact_dir / "ng_historical_refinement_readiness_v14.json"
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
