#!/usr/bin/env python3
"""Capture paginated S3 inventory while binding declared finalization to runtime time.

The pre-S3 finalization contract proves that an operator-declared inventory observation
falls after each product-specific finalization lag. This stage closes the remaining gap:
the actual checksum-enabled paginated S3 capture must start after those same deadlines,
and the declared observation timestamp must be close to the runtime capture interval.

The stage embeds and validates the upstream finalization receipt and the complete
paginated inventory receipt. It remains historical-only, outcome-blind, non-executing,
and may not mutate blind forecasts, posterior state, or ``ng_brain.json``.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import ng_corpus_inventory_finalization_contract as finalization
import ng_corpus_s3_paginated_inventory_capture as paginated

SCHEMA = "ng_corpus_s3_runtime_observed_inventory_capture_attestation.v1"
READY_STATUS = "S3_RUNTIME_OBSERVED_INVENTORY_CAPTURED_READY_FOR_MATERIALIZATION"
BLOCKED_STATUS = "S3_RUNTIME_OBSERVED_INVENTORY_CAPTURE_BLOCKED"
DEFAULT_MAX_DECLARED_CLOCK_SKEW_SECONDS = 300


class RuntimeObservedInventoryCaptureError(ValueError):
    """Raised when runtime observation evidence is malformed or tampered."""


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


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeObservedInventoryCaptureError(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise RuntimeObservedInventoryCaptureError(
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


def _authority_fields() -> dict[str, Any]:
    return copy.deepcopy(paginated._authority_fields())


def _authority(value: Mapping[str, Any], *, label: str) -> None:
    try:
        paginated._authority(value, label=label)
    except Exception as error:
        raise RuntimeObservedInventoryCaptureError(str(error)) from error


def _timestamp(value: Any, *, label: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise RuntimeObservedInventoryCaptureError(f"{label} is required")
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise RuntimeObservedInventoryCaptureError(
            f"{label} must be RFC3339/ISO-8601"
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RuntimeObservedInventoryCaptureError(
            f"{label} must include a timezone offset"
        )
    return parsed.astimezone(timezone.utc)


def _timestamp_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _nonnegative_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise RuntimeObservedInventoryCaptureError(
            f"{label} must be a non-negative integer"
        )
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise RuntimeObservedInventoryCaptureError(
            f"{label} must be a non-negative integer"
        ) from error
    if number < 0:
        raise RuntimeObservedInventoryCaptureError(
            f"{label} must be a non-negative integer"
        )
    return number


def _declared_observation_times(source_spec: Mapping[str, Any]) -> list[tuple[str, datetime]]:
    values: list[tuple[str, datetime]] = [
        (
            "global",
            _timestamp(
                source_spec.get("inventory_observed_at"),
                label="source_spec.inventory_observed_at",
            ),
        )
    ]
    for raw_corpus in source_spec.get("corpora") or []:
        if not isinstance(raw_corpus, Mapping):
            raise RuntimeObservedInventoryCaptureError(
                "source_spec corpus is not an object"
            )
        corpus_id = str(raw_corpus.get("corpus_id") or "")
        values.append(
            (
                f"corpus:{corpus_id}",
                _timestamp(
                    raw_corpus.get("inventory_observed_at")
                    or source_spec.get("inventory_observed_at"),
                    label=f"{corpus_id}:inventory_observed_at",
                ),
            )
        )
        for index, raw_source in enumerate(raw_corpus.get("sources") or []):
            if not isinstance(raw_source, Mapping):
                raise RuntimeObservedInventoryCaptureError(
                    f"{corpus_id}:sources[{index}] is not an object"
                )
            source_value = raw_source.get("inventory_observed_at")
            if source_value in (None, ""):
                continue
            source_id = str(raw_source.get("source_id") or index)
            values.append(
                (
                    f"source:{corpus_id}:{source_id}",
                    _timestamp(
                        source_value,
                        label=f"{corpus_id}:{source_id}:inventory_observed_at",
                    ),
                )
            )
    return values


def _finalization_deadlines(
    finalization_receipt: Mapping[str, Any],
) -> list[tuple[str, datetime]]:
    summaries = list(finalization_receipt.get("corpus_finalization_summaries") or [])
    deadlines: list[tuple[str, datetime]] = []
    for raw in summaries:
        if not isinstance(raw, Mapping):
            raise RuntimeObservedInventoryCaptureError(
                "finalization summary is not an object"
            )
        corpus_id = str(raw.get("corpus_id") or "")
        deadlines.append(
            (
                corpus_id,
                _timestamp(
                    raw.get("required_inventory_observation_at_or_after"),
                    label=f"{corpus_id}:required_inventory_observation_at_or_after",
                ),
            )
        )
    if not deadlines:
        raise RuntimeObservedInventoryCaptureError(
            "finalization receipt has no corpus deadlines"
        )
    return deadlines


def build_from_captured_inventory(
    source_spec: Mapping[str, Any],
    *,
    finalization_receipt: Mapping[str, Any],
    materialization_spec: Mapping[str, Any],
    paginated_inventory_receipt: Mapping[str, Any],
    capture_started_at: Any,
    capture_completed_at: Any,
    max_declared_clock_skew_seconds: int = DEFAULT_MAX_DECLARED_CLOCK_SKEW_SECONDS,
) -> dict[str, Any]:
    """Build a runtime-observation receipt from already captured evidence."""

    spec = copy.deepcopy(dict(source_spec))
    _authority(spec, label="runtime-observed source spec")
    final_value = finalization.validate_receipt(finalization_receipt)
    inventory_value = paginated.validate_receipt(paginated_inventory_receipt)
    materialization = copy.deepcopy(dict(materialization_spec))

    if final_value.get("status") != finalization.READY_STATUS:
        raise RuntimeObservedInventoryCaptureError(
            "finalization contract must be ready before runtime capture"
        )
    if final_value.get("source_spec_fingerprint") != _fp(spec):
        raise RuntimeObservedInventoryCaptureError(
            "finalization contract source-spec fingerprint mismatch"
        )
    if inventory_value.get("source_spec_fingerprint") != _fp(spec):
        raise RuntimeObservedInventoryCaptureError(
            "paginated inventory source-spec fingerprint mismatch"
        )
    if inventory_value.get("materialization_spec_fingerprint") != _fp(materialization):
        raise RuntimeObservedInventoryCaptureError(
            "materialization specification fingerprint mismatch"
        )

    started = _timestamp(capture_started_at, label="capture_started_at")
    completed = _timestamp(capture_completed_at, label="capture_completed_at")
    if completed < started:
        raise RuntimeObservedInventoryCaptureError(
            "capture_completed_at may not precede capture_started_at"
        )
    skew_seconds = _nonnegative_int(
        max_declared_clock_skew_seconds,
        label="max_declared_clock_skew_seconds",
    )
    lower = started - timedelta(seconds=skew_seconds)
    upper = completed + timedelta(seconds=skew_seconds)

    blockers: list[str] = list(inventory_value.get("blockers") or [])
    deadline_rows: list[dict[str, Any]] = []
    for corpus_id, deadline in _finalization_deadlines(final_value):
        passed = started >= deadline
        if not passed:
            blockers.append(f"{corpus_id}:RUNTIME_CAPTURE_BEFORE_FINALIZATION_DEADLINE")
        deadline_rows.append(
            {
                "corpus_id": corpus_id,
                "required_at_or_after_utc": _timestamp_text(deadline),
                "capture_started_at_utc": _timestamp_text(started),
                "runtime_capture_after_finalization_deadline": passed,
            }
        )

    declared_rows: list[dict[str, Any]] = []
    for label, observed in _declared_observation_times(spec):
        within = lower <= observed <= upper
        if not within:
            blockers.append(f"{label}:DECLARED_OBSERVATION_OUTSIDE_RUNTIME_CAPTURE_SKEW")
        declared_rows.append(
            {
                "label": label,
                "declared_observed_at_utc": _timestamp_text(observed),
                "allowed_not_before_utc": _timestamp_text(lower),
                "allowed_not_after_utc": _timestamp_text(upper),
                "within_runtime_capture_skew": within,
            }
        )

    blockers = sorted(set(blockers))
    deadline_rows = sorted(deadline_rows, key=lambda row: row["corpus_id"])
    declared_rows = sorted(declared_rows, key=lambda row: row["label"])
    status = (
        READY_STATUS
        if inventory_value.get("status") == paginated.READY_STATUS and not blockers
        else BLOCKED_STATUS
    )
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "status": status,
        "source_spec": spec,
        "source_spec_fingerprint": _fp(spec),
        "finalization_contract": copy.deepcopy(dict(final_value)),
        "finalization_contract_fingerprint": final_value.get("receipt_fingerprint"),
        "paginated_inventory_receipt": copy.deepcopy(dict(inventory_value)),
        "paginated_inventory_receipt_fingerprint": inventory_value.get(
            "receipt_fingerprint"
        ),
        "materialization_spec": materialization,
        "materialization_spec_fingerprint": _fp(materialization),
        "capture_started_at_utc": _timestamp_text(started),
        "capture_completed_at_utc": _timestamp_text(completed),
        "capture_duration_seconds": (completed - started).total_seconds(),
        "max_declared_clock_skew_seconds": skew_seconds,
        "runtime_finalization_checks": deadline_rows,
        "runtime_finalization_checks_fingerprint": _fp(deadline_rows),
        "declared_observation_checks": declared_rows,
        "declared_observation_checks_fingerprint": _fp(declared_rows),
        "actual_runtime_capture_bound_to_product_lags": all(
            row["runtime_capture_after_finalization_deadline"]
            for row in deadline_rows
        ),
        "declared_observations_bound_to_runtime_interval": all(
            row["within_runtime_capture_skew"] for row in declared_rows
        ),
        "complete_pagination_attested": inventory_value.get(
            "complete_pagination_attested"
        )
        is True,
        "checksum_enabled_heads_attested": inventory_value.get(
            "checksum_enabled_heads_attested"
        )
        is True,
        "identity_from_s3_keys_inferred": False,
        "blockers": blockers,
        "next_action": (
            "RUN_S3_MATERIALIZATION_ATTESTATION"
            if not blockers
            else "REPAIR_RUNTIME_OBSERVED_INVENTORY_CAPTURE_BLOCKERS"
        ),
        **_authority_fields(),
    }
    receipt["receipt_fingerprint"] = _fp(receipt)
    return receipt


def validate_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("receipt_fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise RuntimeObservedInventoryCaptureError(
            "runtime-observed receipt schema or fingerprint mismatch"
        )
    checked["receipt_fingerprint"] = observed
    _authority(checked, label="runtime-observed inventory receipt")

    source_spec = checked.get("source_spec")
    final_receipt = checked.get("finalization_contract")
    inventory_receipt = checked.get("paginated_inventory_receipt")
    materialization_spec = checked.get("materialization_spec")
    if not all(
        isinstance(item, Mapping)
        for item in (
            source_spec,
            final_receipt,
            inventory_receipt,
            materialization_spec,
        )
    ):
        raise RuntimeObservedInventoryCaptureError(
            "runtime-observed receipt lacks embedded evidence"
        )

    rebuilt = build_from_captured_inventory(
        source_spec,
        finalization_receipt=final_receipt,
        materialization_spec=materialization_spec,
        paginated_inventory_receipt=inventory_receipt,
        capture_started_at=checked.get("capture_started_at_utc"),
        capture_completed_at=checked.get("capture_completed_at_utc"),
        max_declared_clock_skew_seconds=checked.get(
            "max_declared_clock_skew_seconds"
        ),
    )
    if rebuilt != dict(value):
        raise RuntimeObservedInventoryCaptureError(
            "runtime-observed receipt differs from deterministic rebuild"
        )
    return copy.deepcopy(dict(value))


def capture_live(
    source_spec: Mapping[str, Any],
    *,
    finalization_receipt: Mapping[str, Any],
    aws_executable: str = "aws",
    runner: Callable[[Sequence[str]], dict[str, Any]] = paginated._run_json,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    max_declared_clock_skew_seconds: int = DEFAULT_MAX_DECLARED_CLOCK_SKEW_SECONDS,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run paginated checksum capture and bind it to actual runtime timestamps."""

    started = clock()
    if started.tzinfo is None or started.utcoffset() is None:
        raise RuntimeObservedInventoryCaptureError(
            "runtime clock must return timezone-aware datetimes"
        )
    final_value = finalization.validate_receipt(finalization_receipt)
    for corpus_id, deadline in _finalization_deadlines(final_value):
        if started.astimezone(timezone.utc) < deadline:
            raise RuntimeObservedInventoryCaptureError(
                f"{corpus_id}: runtime capture attempted before finalization deadline"
            )

    materialization_spec, inventory_receipt = paginated.capture_live(
        source_spec,
        aws_executable=aws_executable,
        runner=runner,
    )
    completed = clock()
    receipt = build_from_captured_inventory(
        source_spec,
        finalization_receipt=final_value,
        materialization_spec=materialization_spec,
        paginated_inventory_receipt=inventory_receipt,
        capture_started_at=started,
        capture_completed_at=completed,
        max_declared_clock_skew_seconds=max_declared_clock_skew_seconds,
    )
    return materialization_spec, receipt


def _fixture() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    spec = paginated._selftest_spec()
    spec["inventory_observed_at"] = "2026-07-25T00:00:00Z"
    for corpus in spec["corpora"]:
        corpus["inventory_observed_at"] = "2026-07-25T00:00:00Z"
        corpus["finalization_lag_seconds"] = 0
        corpus["finalization_policy"] = {
            "policy_id": f"{corpus['lane']}-runtime-selftest",
            "evidence_source": "fixture-policy",
            "evidence_observed_at": "2026-07-24T00:00:00Z",
            "evidence_sha256": "a" * 64,
        }
    final_receipt = finalization.build_contract(spec)

    import base64

    checksum = base64.b64encode(hashlib.sha256(b"selftest").digest()).decode("ascii")
    pages: dict[str, list[dict[str, Any]]] = {}
    heads: dict[str, dict[str, Any]] = {}
    for corpus in spec["corpora"]:
        source = corpus["sources"][0]
        response = {
            "Versions": [
                {
                    "Key": source["key"],
                    "VersionId": "v1",
                    "IsLatest": True,
                    "LastModified": "2026-07-25T00:00:00Z",
                    "Size": 8,
                    "ETag": "v1",
                }
            ],
            "IsTruncated": False,
        }
        pages[corpus["corpus_id"]] = [
            {
                "request": {
                    "page_index": 1,
                    "key_marker": None,
                    "version_id_marker": None,
                    "argv": ["aws", "s3api", "list-object-versions"],
                },
                "response": response,
            }
        ]
        heads[source["source_id"]] = {
            "ContentLength": 8,
            "LastModified": "2026-07-25T00:00:00Z",
            "VersionId": "v1",
            "ETag": "v1",
            "ChecksumSHA256": checksum,
            "Metadata": {},
        }
    materialization, inventory = paginated.build_from_paginated_evidence(
        spec,
        captured_pages=pages,
        head_responses=heads,
    )
    receipt = build_from_captured_inventory(
        spec,
        finalization_receipt=final_receipt,
        materialization_spec=materialization,
        paginated_inventory_receipt=inventory,
        capture_started_at="2026-07-25T00:00:00Z",
        capture_completed_at="2026-07-25T00:00:02Z",
    )
    return spec, final_receipt, materialization, receipt


def selftest() -> int:
    _, _, _, receipt = _fixture()
    assert receipt["status"] == READY_STATUS
    assert receipt["actual_runtime_capture_bound_to_product_lags"] is True
    assert receipt["declared_observations_bound_to_runtime_interval"] is True
    validate_receipt(receipt)
    print("[ng_corpus_s3_runtime_observed_inventory_capture] selftest PASS")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    capture = subparsers.add_parser("capture")
    capture.add_argument("--spec", type=Path, required=True)
    capture.add_argument("--finalization", type=Path, required=True)
    capture.add_argument("--materialization-spec-out", type=Path, required=True)
    capture.add_argument("--receipt-out", type=Path, required=True)
    capture.add_argument(
        "--max-declared-clock-skew-seconds",
        type=int,
        default=DEFAULT_MAX_DECLARED_CLOCK_SKEW_SECONDS,
    )
    subparsers.add_parser("selftest")
    args = parser.parse_args(argv)

    if args.command == "selftest":
        return selftest()

    materialization_spec, receipt = capture_live(
        _load(args.spec),
        finalization_receipt=_load(args.finalization),
        max_declared_clock_skew_seconds=args.max_declared_clock_skew_seconds,
    )
    _write(args.materialization_spec_out, materialization_spec)
    _write(args.receipt_out, receipt)
    print(
        json.dumps(
            {
                "materialization_spec_out": str(args.materialization_spec_out),
                "receipt_out": str(args.receipt_out),
                "status": receipt["status"],
            },
            sort_keys=True,
        )
    )
    return 0 if receipt["status"] == READY_STATUS else 2


if __name__ == "__main__":
    raise SystemExit(main())
