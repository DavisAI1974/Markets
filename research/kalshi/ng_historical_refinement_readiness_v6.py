#!/usr/bin/env python3
"""Canonical v6 readiness with full-window exact L1/MBO overlap before G15 replay.

Readiness v5 verifies the declared one-year L1/dense-trades and spring/summer MBO
scopes, but broad completeness alone does not prove that every shared day joins on the
same dataset, publisher, instrument, raw symbol, observed definition period, and event
time. V6 inserts the deterministic broad-corpus exact-overlap gate after broad-scope
verification and before exact G15 replay. The lock-first G15 scoring wall and the full
counterfactual G16 lineage remain unchanged.
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
import ng_historical_refinement_readiness_v5 as v5

SCHEMA = "ng_historical_refinement_readiness.v6"
StageSpec = legacy.StageSpec
HistoricalRefinementReadinessError = legacy.HistoricalRefinementReadinessError
_V5_OVERALL_STATUS = v5._overall_status

_BROAD_EXACT_OVERLAP = StageSpec(
    "broad_corpus_exact_overlap",
    "ng_broad_corpus_exact_overlap_gate.json",
    "ng_broad_corpus_exact_overlap_gate.v1",
    "fingerprint",
    frozenset({"BROAD_CORPUS_EXACT_OVERLAP_VERIFIED"}),
    "ng_broad_corpus_exact_overlap_gate",
    ("validate_gate",),
    "Align every shared spring/summer day on exact dataset, publisher, instrument, raw symbol, definition period, and event time before G15 replay.",
    required_fields=(
        "broad_scope_gate_fingerprint",
        "inspection_receipt_fingerprint",
        "catalog_fingerprint",
        "coverage_audit_fingerprint",
        "all_shared_days_exactly_aligned",
        "g15_g16_days_included",
        "expected_overlap_day_count",
    ),
    pre_outcome=True,
)

STAGES: tuple[StageSpec, ...] = (
    *v5.STAGES[:4],
    _BROAD_EXACT_OVERLAP,
    *v5.STAGES[4:],
)

LINK_RULES: tuple[tuple[str, str, str, str], ...] = (
    (
        "broad_corpus_scope",
        "fingerprint",
        "broad_corpus_exact_overlap",
        "broad_scope_gate_fingerprint",
    ),
    (
        "broad_corpus_scope",
        "inspection_receipt_fingerprint",
        "broad_corpus_exact_overlap",
        "inspection_receipt_fingerprint",
    ),
    (
        "broad_corpus_scope",
        "catalog_fingerprint",
        "broad_corpus_exact_overlap",
        "catalog_fingerprint",
    ),
    (
        "corpus_coverage",
        "fingerprint",
        "broad_corpus_exact_overlap",
        "coverage_audit_fingerprint",
    ),
    *v5.LINK_RULES,
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
        return "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V6"
    if "broad_corpus_exact_overlap" in ready_keys and "g15_exact_replay" not in ready_keys:
        return "BROAD_CORPUS_EXACT_OVERLAP_VERIFIED_G15_REPLAY_INCOMPLETE"
    if "broad_corpus_scope" in ready_keys and "broad_corpus_exact_overlap" not in ready_keys:
        return "BROAD_CORPUS_SCOPE_VERIFIED_EXACT_OVERLAP_INCOMPLETE"
    return _V5_OVERALL_STATUS(
        [key for key in ready_keys if key != "broad_corpus_exact_overlap"]
    )


@contextmanager
def _v5_contract() -> Iterator[None]:
    saved = (v5.SCHEMA, v5.STAGES, v5.LINK_RULES, v5._overall_status)
    v5.SCHEMA = SCHEMA
    v5.STAGES = STAGES
    v5.LINK_RULES = LINK_RULES
    v5._overall_status = _overall_status
    try:
        yield
    finally:
        v5.SCHEMA, v5.STAGES, v5.LINK_RULES, v5._overall_status = saved


def build_readiness_report(
    artifact_dir: Path,
    *,
    stage_paths: Mapping[str, Path] | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]] | None = None,
) -> dict[str, Any]:
    with _v5_contract():
        report = v5.build_readiness_report(
            artifact_dir,
            stage_paths=stage_paths,
            validator_overrides=validator_overrides,
        )
    ready = list(report.get("ready_stages") or [])
    report["broad_corpus_exact_overlap_verified"] = "broad_corpus_exact_overlap" in ready
    report["note"] = (
        "Readiness v6 requires both broad inventory completeness and exact full-window L1/MBO alignment "
        "before G15 replay. Every expected MBO day must match L1 on dataset, publisher, instrument, raw "
        "symbol, observed definition period, and positive event-time overlap."
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
            "readiness v6 report schema or fingerprint mismatch"
        )
    with _v5_contract():
        v5.validate_readiness_report(value)
    ready = list(value.get("ready_stages") or [])
    expected_overlap = "broad_corpus_exact_overlap" in ready
    if value.get("broad_corpus_exact_overlap_verified") is not expected_overlap:
        raise HistoricalRefinementReadinessError(
            "readiness v6 exact-overlap summary mismatch"
        )
    if "g15_exact_replay" in ready and not expected_overlap:
        raise HistoricalRefinementReadinessError(
            "G15 replay may not be ready before broad-corpus exact-overlap verification"
        )
    rows = {str(row.get("key")): row for row in value.get("stages") or []}
    if expected_overlap:
        overlap = rows.get("broad_corpus_exact_overlap") or {}
        if overlap.get("effective_status") not in {"READY", "READY_WITH_STAND_DOWNS"}:
            raise HistoricalRefinementReadinessError(
                "exact-overlap summary claims readiness while stage is not ready"
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
                f"readiness v6 must keep {field}=false"
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
    with _v5_contract():
        return v5._linked_fixture_chain()


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
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V6"
        assert complete["broad_corpus_exact_overlap_verified"] is True
        (root / _BROAD_EXACT_OVERLAP.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == "broad_corpus_exact_overlap"
        g15_row = next(row for row in blocked["stages"] if row["key"] == "g15_exact_replay")
        assert g15_row["effective_status"] == "BLOCKED_BY_UPSTREAM"
    print("[ng_historical_refinement_readiness_v6] selftest PASS")
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
        description="Build canonical broad-overlap-first v6 NG historical refinement readiness"
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
