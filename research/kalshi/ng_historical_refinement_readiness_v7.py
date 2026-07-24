#!/usr/bin/env python3
"""Canonical v7 readiness with exact source partitioning before G15 replay.

Readiness v6 proves exact L1/MBO identity and positive cross-lane event-time
overlap across the full shared corpus window.  V7 additionally requires every
daily lane inventory to be free of duplicate bytes, source reuse across days,
duplicate event ranges, and positive-duration same-lane source overlap.  This
prevents double-counted historical events from reaching exact G15 replay while
preserving the lock-first G15 scoring wall and counterfactual G16 lineage.
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
import ng_historical_refinement_readiness_v6 as v6

SCHEMA = "ng_historical_refinement_readiness.v7"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V6_OVERALL_STATUS = v6._overall_status

_BROAD_EXACT_PARTITION = StageSpec(
    "broad_corpus_exact_partition",
    "ng_broad_corpus_exact_partition_gate.json",
    "ng_broad_corpus_exact_partition_gate.v1",
    "fingerprint",
    frozenset({"BROAD_CORPUS_EXACT_PARTITION_VERIFIED"}),
    "ng_broad_corpus_exact_partition_gate",
    ("validate_gate",),
    "Verify that every shared-day lane is an exact non-overlapping source partition with no duplicate bytes or cross-day source reuse before G15 replay.",
    required_fields=(
        "exact_overlap_gate_fingerprint",
        "broad_scope_gate_fingerprint",
        "inspection_receipt_fingerprint",
        "catalog_fingerprint",
        "coverage_audit_fingerprint",
        "all_shared_days_exactly_partitioned",
        "g15_g16_days_included",
        "expected_day_count",
    ),
    pre_outcome=True,
)

STAGES: tuple[StageSpec, ...] = (
    *v6.STAGES[:5],
    _BROAD_EXACT_PARTITION,
    *v6.STAGES[5:],
)

LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    (
        "broad_corpus_exact_overlap",
        "fingerprint",
        "broad_corpus_exact_partition",
        "exact_overlap_gate_fingerprint",
    ),
    (
        "broad_corpus_scope",
        "fingerprint",
        "broad_corpus_exact_partition",
        "broad_scope_gate_fingerprint",
    ),
    (
        "broad_corpus_scope",
        "inspection_receipt_fingerprint",
        "broad_corpus_exact_partition",
        "inspection_receipt_fingerprint",
    ),
    (
        "broad_corpus_scope",
        "catalog_fingerprint",
        "broad_corpus_exact_partition",
        "catalog_fingerprint",
    ),
    (
        "corpus_coverage",
        "fingerprint",
        "broad_corpus_exact_partition",
        "coverage_audit_fingerprint",
    ),
    *v6.LINK_RULES,
)


def _fingerprint(value: Any) -> str:
    return legacy._fingerprint(value)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _overall_status(ready_keys: list[str]) -> str:
    if "g16_counterfactual_publication" in ready_keys and len(ready_keys) == len(STAGES):
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V7"
    if (
        "broad_corpus_exact_partition" in ready_keys
        and "g15_exact_replay" not in ready_keys
    ):
        return "BROAD_CORPUS_EXACT_PARTITION_VERIFIED_G15_REPLAY_INCOMPLETE"
    if (
        "broad_corpus_exact_overlap" in ready_keys
        and "broad_corpus_exact_partition" not in ready_keys
    ):
        return "BROAD_CORPUS_EXACT_OVERLAP_VERIFIED_SOURCE_PARTITION_INCOMPLETE"
    return _V6_OVERALL_STATUS(
        [key for key in ready_keys if key != "broad_corpus_exact_partition"]
    )


@contextmanager
def _v6_contract() -> Iterator[None]:
    saved = (v6.SCHEMA, v6.STAGES, v6.LINK_RULES, v6._overall_status)
    v6.SCHEMA = SCHEMA
    v6.STAGES = STAGES
    v6.LINK_RULES = LINK_RULES
    v6._overall_status = _overall_status
    try:
        yield
    finally:
        v6.SCHEMA, v6.STAGES, v6.LINK_RULES, v6._overall_status = saved


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]] | None = None,
) -> dict[str, Any]:
    with _v6_contract():
        report = v6.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    report["broad_corpus_exact_partition_verified"] = (
        "broad_corpus_exact_partition" in ready
    )
    report["note"] = (
        "Readiness v7 requires full-window exact L1/MBO identity overlap and exact "
        "same-lane source partitioning before G15 replay. Duplicate bytes, reused "
        "objects, duplicate event ranges, or positive-duration same-lane overlap "
        "remain visible blockers."
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
            "readiness v7 report schema or fingerprint mismatch"
        )
    with _v6_contract():
        v6.validate_readiness_report(value)
    ready = list(value.get("ready_stages") or [])
    expected_partition = "broad_corpus_exact_partition" in ready
    if value.get("broad_corpus_exact_partition_verified") is not expected_partition:
        raise HistoricalRefinementReadinessError(
            "readiness v7 exact-partition summary mismatch"
        )
    if "g15_exact_replay" in ready and not expected_partition:
        raise HistoricalRefinementReadinessError(
            "G15 replay may not be ready before broad-corpus exact source partition verification"
        )
    rows = {str(row.get("key")): row for row in value.get("stages") or []}
    if expected_partition:
        partition = rows.get("broad_corpus_exact_partition") or {}
        if partition.get("effective_status") not in {"READY", "READY_WITH_STAND_DOWNS"}:
            raise HistoricalRefinementReadinessError(
                "exact-partition summary claims readiness while stage is not ready"
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
                f"readiness v7 must keep {field}=false"
            )
    if value.get("one_signal_authority_preserved") is not True:
        raise HistoricalRefinementReadinessError("one signal authority was not preserved")
    if value.get("blind_forecasts_immutable") is not True:
        raise HistoricalRefinementReadinessError("blind forecasts were not preserved")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise HistoricalRefinementReadinessError("CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise HistoricalRefinementReadinessError(
            "brokerage contract must remain tastytrade, not IBKR"
        )


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    with _v6_contract():
        values = v6._linked_fixture_chain()
    overlap_value = values["broad_corpus_exact_overlap"]
    values["broad_corpus_exact_partition"] = {
        "schema": _BROAD_EXACT_PARTITION.schema,
        "status": "BROAD_CORPUS_EXACT_PARTITION_VERIFIED",
        "fingerprint": "partition-fixture",
        "exact_overlap_gate_fingerprint": overlap_value["fingerprint"],
        "broad_scope_gate_fingerprint": values["broad_corpus_scope"]["fingerprint"],
        "inspection_receipt_fingerprint": values["broad_corpus_scope"][
            "inspection_receipt_fingerprint"
        ],
        "catalog_fingerprint": values["broad_corpus_scope"]["catalog_fingerprint"],
        "coverage_audit_fingerprint": values["corpus_coverage"]["fingerprint"],
        "all_shared_days_exactly_partitioned": True,
        "g15_g16_days_included": True,
        "expected_day_count": 1,
    }
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
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V7"
        assert complete["broad_corpus_exact_partition_verified"] is True
        (root / _BROAD_EXACT_PARTITION.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == "broad_corpus_exact_partition"
        g15_row = next(row for row in blocked["stages"] if row["key"] == "g15_exact_replay")
        assert g15_row["effective_status"] == "BLOCKED_BY_UPSTREAM"
    print("[ng_historical_refinement_readiness_v7] selftest PASS")
    return 0


def _parse_stage_paths(values: Sequence[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    allowed = {spec.key for spec in STAGES}
    for raw in values:
        if "=" not in raw:
            raise HistoricalRefinementReadinessError("--stage-path requires KEY=PATH")
        key, path = raw.split("=", 1)
        if key not in allowed or not path:
            raise HistoricalRefinementReadinessError(
                f"invalid stage path override: {raw!r}"
            )
        result[key] = Path(path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build canonical exact-partition-first v7 NG historical readiness"
    )
    parser.add_argument("--artifact-dir", type=Path, default=Path("renders/ng_refine_s95"))
    parser.add_argument("--stage-path", action="append", default=[], metavar="KEY=PATH")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    report = build_readiness_report(
        args.artifact_dir, stage_paths=_parse_stage_paths(args.stage_path)
    )
    if args.out:
        _atomic_json(args.out, report)
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
