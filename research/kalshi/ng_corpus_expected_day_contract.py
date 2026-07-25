#!/usr/bin/env python3
"""Attest complete expected-session-day coverage before any S3 inventory request.

The upstream resolution specification carries ``expected_days`` supplied by an operator.
Without an independent calendar partition, an accidentally shortened list can make an
incomplete corpus appear complete. This gate requires every calendar date in each
canonical corpus window to be classified exactly once as either an expected NG session
or an explicit no-session exclusion. Saturdays are the only schedule exclusion that
requires no external evidence. Any other exclusion requires reason-coded evidence with
a SHA-256 fingerprint. G15/G16 target dates may never be excluded.

This stage is historical-only and outcome-blind. It cannot mutate blind forecasts,
``knowledge/ng_brain.json``, posterior state, execution state, or the options lane.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

import ng_corpus_coverage_audit as coverage
import ng_corpus_s3_latest_version_resolution as resolution

SCHEMA = "ng_corpus_expected_day_contract_attestation.v1"
READY_STATUS = "CORPUS_EXPECTED_DAY_CONTRACT_READY_FOR_S3_RESOLUTION"
BLOCKED_STATUS = "CORPUS_EXPECTED_DAY_CONTRACT_BLOCKED"
SATURDAY_REASON = "SCHEDULED_SATURDAY_NO_SESSION"
EVIDENCED_REASONS = frozenset({"EXCHANGE_HOLIDAY_NO_SESSION", "EXCHANGE_CLOSURE_NO_SESSION"})


class CorpusExpectedDayContractError(ValueError):
    """Raised when an expected-day contract is malformed or tampered."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusExpectedDayContractError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusExpectedDayContractError(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _authority_fields() -> dict[str, Any]:
    return copy.deepcopy(resolution._authority_fields())


def _authority(value: Mapping[str, Any], *, label: str) -> None:
    try:
        resolution._authority(value, label=label)
    except Exception as error:
        raise CorpusExpectedDayContractError(str(error)) from error


def _parse_day(value: Any, *, label: str) -> date:
    text = str(value or "").strip().replace("-", "")
    if len(text) != 8 or not text.isdigit():
        raise CorpusExpectedDayContractError(f"{label} must be YYYYMMDD or YYYY-MM-DD")
    try:
        return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    except ValueError as error:
        raise CorpusExpectedDayContractError(f"{label} is not a valid date") from error


def _day_text(value: date) -> str:
    return value.strftime("%Y%m%d")


def _window_days(start: str, end_exclusive: str) -> list[date]:
    current = _parse_day(start, label="window start")
    end = _parse_day(end_exclusive, label="window end_exclusive")
    if end <= current:
        raise CorpusExpectedDayContractError("canonical corpus window is empty or backwards")
    values: list[date] = []
    while current < end:
        values.append(current)
        current += timedelta(days=1)
    return values


def _sha256(value: Any, *, label: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise CorpusExpectedDayContractError(f"{label} must be 64 lowercase hexadecimal characters")
    return text


def _normalize_exclusions(corpus: Mapping[str, Any], *, corpus_id: str) -> tuple[list[dict[str, Any]], list[str]]:
    blockers: list[str] = []
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(corpus.get("excluded_days") or []):
        if not isinstance(raw, Mapping):
            raise CorpusExpectedDayContractError(f"{corpus_id}: excluded_days[{index}] is not an object")
        item = copy.deepcopy(dict(raw))
        day_value = _day_text(_parse_day(item.get("day"), label=f"{corpus_id}:excluded_days[{index}].day"))
        if day_value in seen:
            raise CorpusExpectedDayContractError(f"{corpus_id}: duplicate excluded day {day_value}")
        seen.add(day_value)
        reason = str(item.get("reason_code") or "").strip()
        parsed = _parse_day(day_value, label=f"{corpus_id}:excluded day")
        normalized: dict[str, Any] = {"day": day_value, "reason_code": reason}
        if parsed.weekday() == 5:
            if reason != SATURDAY_REASON:
                blockers.append(f"{corpus_id}:{day_value}:SATURDAY_REASON_MISMATCH")
        else:
            if reason not in EVIDENCED_REASONS:
                blockers.append(f"{corpus_id}:{day_value}:UNSUPPORTED_NON_SATURDAY_EXCLUSION")
            evidence_source = str(item.get("evidence_source") or "").strip()
            observed_at = str(item.get("evidence_observed_at") or "").strip()
            if not evidence_source:
                blockers.append(f"{corpus_id}:{day_value}:EXCLUSION_EVIDENCE_SOURCE_MISSING")
            if not observed_at:
                blockers.append(f"{corpus_id}:{day_value}:EXCLUSION_EVIDENCE_TIME_MISSING")
            try:
                evidence_sha256 = _sha256(item.get("evidence_sha256"), label=f"{corpus_id}:{day_value}:evidence_sha256")
            except CorpusExpectedDayContractError:
                evidence_sha256 = ""
                blockers.append(f"{corpus_id}:{day_value}:EXCLUSION_EVIDENCE_SHA256_INVALID")
            normalized.update(
                {
                    "evidence_source": evidence_source,
                    "evidence_observed_at": observed_at,
                    "evidence_sha256": evidence_sha256,
                }
            )
        rows.append(normalized)
    return sorted(rows, key=lambda row: row["day"]), blockers


def build_contract(source_spec: Mapping[str, Any]) -> dict[str, Any]:
    spec = copy.deepcopy(dict(source_spec))
    if spec.get("schema") != resolution.SPEC_SCHEMA:
        raise CorpusExpectedDayContractError(f"source spec schema must be {resolution.SPEC_SCHEMA}")
    _authority(spec, label="expected-day source spec")
    corpora = list(spec.get("corpora") or [])
    if len(corpora) != len(coverage.EXPECTED_WINDOWS):
        raise CorpusExpectedDayContractError("source spec must contain both canonical corpora")

    blockers: list[str] = []
    summaries: list[dict[str, Any]] = []
    seen_corpora: set[str] = set()
    target_days = set(coverage.G15_DATES) | set(coverage.G16_DATES)

    for raw_corpus in corpora:
        if not isinstance(raw_corpus, Mapping):
            raise CorpusExpectedDayContractError("source corpus is not an object")
        corpus = copy.deepcopy(dict(raw_corpus))
        corpus_id = str(corpus.get("corpus_id") or "")
        expected = coverage.EXPECTED_WINDOWS.get(corpus_id)
        if expected is None or corpus_id in seen_corpora:
            raise CorpusExpectedDayContractError(f"unexpected or duplicate corpus_id {corpus_id!r}")
        seen_corpora.add(corpus_id)
        if str(corpus.get("lane") or "") != expected["lane"]:
            raise CorpusExpectedDayContractError(f"{corpus_id}: lane mismatch")

        calendar_days = [_day_text(day) for day in _window_days(expected["start"], expected["end_exclusive"])]
        calendar_set = set(calendar_days)
        expected_days = sorted(
            {
                _day_text(_parse_day(raw, label=f"{corpus_id}:expected day"))
                for raw in list(corpus.get("expected_days") or [])
            }
        )
        if len(expected_days) != len(list(corpus.get("expected_days") or [])):
            blockers.append(f"{corpus_id}:EXPECTED_DAYS_DUPLICATE_OR_NONCANONICAL")
        exclusions, exclusion_blockers = _normalize_exclusions(corpus, corpus_id=corpus_id)
        blockers.extend(exclusion_blockers)
        expected_set = set(expected_days)
        explicit_excluded = {row["day"] for row in exclusions}
        implicit_saturdays = [
            {
                "day": day,
                "reason_code": SATURDAY_REASON,
                "classification_source": "canonical_weekday_rule",
            }
            for day in calendar_days
            if _parse_day(day, label="calendar day").weekday() == 5
            and day not in expected_set
            and day not in explicit_excluded
        ]
        exclusions = sorted([*exclusions, *implicit_saturdays], key=lambda row: row["day"])
        excluded_days = [row["day"] for row in exclusions]
        excluded_set = set(excluded_days)

        overlap = sorted(expected_set & excluded_set)
        missing_classifications = sorted(calendar_set - expected_set - excluded_set)
        out_of_window = sorted((expected_set | excluded_set) - calendar_set)
        if overlap:
            blockers.extend(f"{corpus_id}:{day}:EXPECTED_AND_EXCLUDED" for day in overlap)
        if missing_classifications:
            blockers.extend(f"{corpus_id}:{day}:CALENDAR_DAY_UNCLASSIFIED" for day in missing_classifications)
        if out_of_window:
            blockers.extend(f"{corpus_id}:{day}:DAY_OUTSIDE_CANONICAL_WINDOW" for day in out_of_window)

        non_saturday_unexpected = sorted(
            day for day in calendar_days if _parse_day(day, label="calendar day").weekday() != 5 and day not in expected_set and day not in excluded_set
        )
        if non_saturday_unexpected:
            blockers.extend(f"{corpus_id}:{day}:NON_SATURDAY_SESSION_NOT_CLASSIFIED" for day in non_saturday_unexpected)

        applicable_targets = sorted(day for day in target_days if day in calendar_set)
        excluded_targets = sorted(set(applicable_targets) & excluded_set)
        if excluded_targets:
            blockers.extend(f"{corpus_id}:{day}:TARGET_REPLAY_DAY_EXCLUDED" for day in excluded_targets)
        missing_targets = sorted(set(applicable_targets) - expected_set)
        if missing_targets:
            blockers.extend(f"{corpus_id}:{day}:TARGET_REPLAY_DAY_NOT_EXPECTED" for day in missing_targets)

        sources = list(corpus.get("sources") or [])
        source_days: list[str] = []
        for index, raw_source in enumerate(sources):
            if not isinstance(raw_source, Mapping):
                raise CorpusExpectedDayContractError(f"{corpus_id}: source[{index}] is not an object")
            source_days.append(_day_text(_parse_day(raw_source.get("day"), label=f"{corpus_id}:source[{index}].day")))
        source_day_set = set(source_days)
        missing_source_days = sorted(expected_set - source_day_set)
        unexpected_source_days = sorted(source_day_set - expected_set)
        if missing_source_days:
            blockers.extend(f"{corpus_id}:{day}:EXPECTED_DAY_WITHOUT_DECLARED_SOURCE" for day in missing_source_days)
        if unexpected_source_days:
            blockers.extend(f"{corpus_id}:{day}:DECLARED_SOURCE_ON_NONEXPECTED_DAY" for day in unexpected_source_days)
        try:
            object_count = int(corpus.get("expected_object_count"))
        except (TypeError, ValueError, OverflowError):
            object_count = -1
        if object_count != len(sources):
            blockers.append(f"{corpus_id}:EXPECTED_OBJECT_COUNT_MISMATCH")
        if corpus.get("inventory_scope_verified") is not True:
            blockers.append(f"{corpus_id}:INVENTORY_SCOPE_NOT_VERIFIED")
        if corpus.get("inventory_complete_asserted") is not True:
            blockers.append(f"{corpus_id}:INVENTORY_NOT_ASSERTED_COMPLETE")

        summary = {
            "corpus_id": corpus_id,
            "lane": expected["lane"],
            "canonical_window": {"start": expected["start"], "end_exclusive": expected["end_exclusive"]},
            "calendar_day_count": len(calendar_days),
            "expected_session_day_count": len(expected_days),
            "excluded_day_count": len(excluded_days),
            "implicit_saturday_exclusion_count": len(implicit_saturdays),
            "declared_source_count": len(sources),
            "expected_object_count": object_count,
            "expected_days": expected_days,
            "excluded_days": exclusions,
            "source_days": sorted(source_days),
            "target_days_required": applicable_targets,
            "full_calendar_partition_attested": not overlap and not missing_classifications and not out_of_window,
            "all_target_days_expected": not excluded_targets and not missing_targets,
            "every_expected_day_has_declared_source": not missing_source_days,
            "no_source_declared_on_excluded_day": not unexpected_source_days,
        }
        summary["calendar_partition_fingerprint"] = _fp(summary)
        summaries.append(summary)

    if seen_corpora != set(coverage.EXPECTED_WINDOWS):
        raise CorpusExpectedDayContractError("source spec is missing a canonical corpus")

    blockers = sorted(set(blockers))
    summaries = sorted(summaries, key=lambda row: row["corpus_id"])
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "status": READY_STATUS if not blockers else BLOCKED_STATUS,
        "source_spec": spec,
        "source_spec_fingerprint": _fp(spec),
        "corpus_calendar_partitions": summaries,
        "corpus_calendar_partitions_fingerprint": _fp(summaries),
        "canonical_windows_fingerprint": _fp(coverage.EXPECTED_WINDOWS),
        "g15_target_days_fingerprint": _fp(list(coverage.G15_DATES)),
        "g16_target_days_fingerprint": _fp(list(coverage.G16_DATES)),
        "complete_calendar_partition_attested": not blockers,
        "expected_days_operator_truncation_rejected": True,
        "non_saturday_exclusions_require_evidence": True,
        "target_replay_days_may_not_be_excluded": True,
        "scheduled_saturdays_classified_automatically": True,
        "identity_from_s3_keys_inferred": False,
        "blockers": blockers,
        "next_action": "RUN_PAGINATED_S3_LATEST_VERSION_RESOLUTION" if not blockers else "REPAIR_EXPECTED_DAY_CONTRACT",
        **_authority_fields(),
    }
    receipt["receipt_fingerprint"] = _fp(receipt)
    return receipt


def validate_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("receipt_fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise CorpusExpectedDayContractError("expected-day receipt schema or fingerprint mismatch")
    checked["receipt_fingerprint"] = observed
    _authority(checked, label="expected-day receipt")
    if checked.get("identity_from_s3_keys_inferred") is not False:
        raise CorpusExpectedDayContractError("trading identity may not be inferred from S3 keys")
    spec = checked.get("source_spec")
    if not isinstance(spec, Mapping):
        raise CorpusExpectedDayContractError("expected-day receipt lacks embedded source specification")
    if checked.get("source_spec_fingerprint") != _fp(spec):
        raise CorpusExpectedDayContractError("expected-day source-spec fingerprint mismatch")
    rebuilt = build_contract(spec)
    if rebuilt != dict(value):
        raise CorpusExpectedDayContractError("expected-day receipt differs from deterministic rebuild")
    return copy.deepcopy(dict(value))


def _selftest_spec() -> dict[str, Any]:
    spec: dict[str, Any] = {
        "schema": resolution.SPEC_SCHEMA,
        "allowed_roots": ["data"],
        "inventory_observed_at": "2026-07-25T00:00:00Z",
        "corpora": [],
        **_authority_fields(),
    }
    for corpus_id, expected in coverage.EXPECTED_WINDOWS.items():
        days = _window_days(expected["start"], expected["end_exclusive"])
        expected_days = [_day_text(day) for day in days if day.weekday() != 5]
        exclusions: list[dict[str, Any]] = []
        sources = [
            {
                "source_id": f"{corpus_id}-{day}",
                "day": day,
                "lane": expected["lane"],
                "key": f"ng/{corpus_id}/{day}.dbn",
                "materialized_path": f"data/{corpus_id}/{day}.dbn",
                "definition": {"placeholder": True},
            }
            for day in expected_days
        ]
        spec["corpora"].append(
            {
                "corpus_id": corpus_id,
                "lane": expected["lane"],
                "publisher_id": 1,
                "bucket": "selftest-bucket",
                "prefix": f"ng/{corpus_id}/",
                "expected_days": expected_days,
                "excluded_days": exclusions,
                "expected_object_count": len(sources),
                "inventory_scope_verified": True,
                "inventory_complete_asserted": True,
                "sources": sources,
            }
        )
    return spec


def selftest() -> int:
    spec = _selftest_spec()
    receipt = build_contract(spec)
    assert receipt["status"] == READY_STATUS
    validate_receipt(receipt)
    tampered = copy.deepcopy(receipt)
    tampered["options_lane_started"] = True
    payload = copy.deepcopy(tampered)
    payload.pop("receipt_fingerprint", None)
    tampered["receipt_fingerprint"] = _fp(payload)
    try:
        validate_receipt(tampered)
    except CorpusExpectedDayContractError:
        print("[ng_corpus_expected_day_contract] selftest PASS")
        return 0
    raise AssertionError("authority escalation was accepted")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--spec", type=Path, required=True)
    build_parser.add_argument("--out", type=Path, required=True)
    subparsers.add_parser("selftest")
    args = parser.parse_args(argv)
    if args.command == "selftest":
        return selftest()
    receipt = build_contract(_load(args.spec))
    _write(args.out, receipt)
    print(json.dumps({"out": str(args.out), "status": receipt["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
