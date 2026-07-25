#!/usr/bin/env python3
"""Attest product-specific corpus finalization lag before S3 resolution.

A complete object inventory is not evidence of a complete historical period when the
inventory snapshot was taken before the period ended or before the publisher's declared
finalization lag elapsed. This gate binds the canonical L1/dense-trades and MBO windows
to explicit, evidence-fingerprinted product-specific lags and timezone-aware inventory
observation timestamps. It remains historical-only and outcome-blind.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import ng_corpus_coverage_audit as coverage
import ng_corpus_s3_latest_version_resolution as resolution

SCHEMA = "ng_corpus_inventory_finalization_contract.v1"
READY_STATUS = "CORPUS_INVENTORY_FINALIZATION_READY_FOR_S3_RESOLUTION"
BLOCKED_STATUS = "CORPUS_INVENTORY_FINALIZATION_BLOCKED"


class CorpusInventoryFinalizationError(ValueError):
    """Raised when the finalization contract is malformed or tampered."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusInventoryFinalizationError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusInventoryFinalizationError(f"JSON artifact must be an object: {path}")
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
        raise CorpusInventoryFinalizationError(str(error)) from error


def _timestamp(value: Any, *, label: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise CorpusInventoryFinalizationError(f"{label} is required")
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise CorpusInventoryFinalizationError(f"{label} must be RFC3339/ISO-8601") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CorpusInventoryFinalizationError(f"{label} must include a timezone offset")
    return parsed.astimezone(timezone.utc)


def _timestamp_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _nonnegative_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise CorpusInventoryFinalizationError(f"{label} must be a non-negative integer")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CorpusInventoryFinalizationError(f"{label} must be a non-negative integer") from error
    if number < 0:
        raise CorpusInventoryFinalizationError(f"{label} must be a non-negative integer")
    return number


def _sha256(value: Any, *, label: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise CorpusInventoryFinalizationError(f"{label} must be 64 lowercase hexadecimal characters")
    return text


def _policy(corpus: Mapping[str, Any], *, corpus_id: str) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    raw = corpus.get("finalization_policy")
    if not isinstance(raw, Mapping):
        return {
            "policy_id": "",
            "evidence_source": "",
            "evidence_observed_at": "",
            "evidence_sha256": "",
        }, [f"{corpus_id}:FINALIZATION_POLICY_MISSING"]
    value = copy.deepcopy(dict(raw))
    policy_id = str(value.get("policy_id") or "").strip()
    evidence_source = str(value.get("evidence_source") or "").strip()
    if not policy_id:
        blockers.append(f"{corpus_id}:FINALIZATION_POLICY_ID_MISSING")
    if not evidence_source:
        blockers.append(f"{corpus_id}:FINALIZATION_POLICY_EVIDENCE_SOURCE_MISSING")
    try:
        evidence_observed = _timestamp(
            value.get("evidence_observed_at"),
            label=f"{corpus_id}:finalization_policy.evidence_observed_at",
        )
        evidence_observed_at = _timestamp_text(evidence_observed)
    except CorpusInventoryFinalizationError:
        evidence_observed_at = ""
        blockers.append(f"{corpus_id}:FINALIZATION_POLICY_EVIDENCE_TIME_INVALID")
    try:
        evidence_sha256 = _sha256(
            value.get("evidence_sha256"),
            label=f"{corpus_id}:finalization_policy.evidence_sha256",
        )
    except CorpusInventoryFinalizationError:
        evidence_sha256 = ""
        blockers.append(f"{corpus_id}:FINALIZATION_POLICY_EVIDENCE_SHA256_INVALID")
    return {
        "policy_id": policy_id,
        "evidence_source": evidence_source,
        "evidence_observed_at": evidence_observed_at,
        "evidence_sha256": evidence_sha256,
    }, blockers


def build_contract(source_spec: Mapping[str, Any]) -> dict[str, Any]:
    spec = copy.deepcopy(dict(source_spec))
    if spec.get("schema") != resolution.SPEC_SCHEMA:
        raise CorpusInventoryFinalizationError(
            f"source spec schema must be {resolution.SPEC_SCHEMA}"
        )
    _authority(spec, label="inventory-finalization source spec")
    global_observed = _timestamp(
        spec.get("inventory_observed_at"), label="inventory_observed_at"
    )
    corpora = list(spec.get("corpora") or [])
    if len(corpora) != len(coverage.EXPECTED_WINDOWS):
        raise CorpusInventoryFinalizationError("source spec must contain both canonical corpora")

    blockers: list[str] = []
    summaries: list[dict[str, Any]] = []
    all_policy_evidence_valid = True
    seen: set[str] = set()
    for raw in corpora:
        if not isinstance(raw, Mapping):
            raise CorpusInventoryFinalizationError("source corpus is not an object")
        corpus = copy.deepcopy(dict(raw))
        corpus_id = str(corpus.get("corpus_id") or "")
        expected = coverage.EXPECTED_WINDOWS.get(corpus_id)
        if expected is None or corpus_id in seen:
            raise CorpusInventoryFinalizationError(f"unexpected or duplicate corpus_id {corpus_id!r}")
        seen.add(corpus_id)
        if str(corpus.get("lane") or "") != expected["lane"]:
            raise CorpusInventoryFinalizationError(f"{corpus_id}: lane mismatch")

        try:
            lag_seconds = _nonnegative_int(
                corpus.get("finalization_lag_seconds"),
                label=f"{corpus_id}:finalization_lag_seconds",
            )
        except CorpusInventoryFinalizationError:
            lag_seconds = -1
            blockers.append(f"{corpus_id}:FINALIZATION_LAG_INVALID")
        policy, policy_blockers = _policy(corpus, corpus_id=corpus_id)
        blockers.extend(policy_blockers)
        if policy_blockers:
            all_policy_evidence_valid = False

        observed = _timestamp(
            corpus.get("inventory_observed_at") or spec.get("inventory_observed_at"),
            label=f"{corpus_id}:inventory_observed_at",
        )
        end_exclusive = _timestamp(
            f"{expected['end_exclusive']}T00:00:00Z",
            label=f"{corpus_id}:canonical end_exclusive",
        )
        required_after = end_exclusive + timedelta(seconds=max(lag_seconds, 0))
        if observed < end_exclusive:
            blockers.append(f"{corpus_id}:INVENTORY_OBSERVED_BEFORE_CORPUS_END")
        if lag_seconds >= 0 and observed < required_after:
            blockers.append(f"{corpus_id}:INVENTORY_OBSERVED_BEFORE_FINALIZATION_LAG")
        if observed > global_observed:
            blockers.append(f"{corpus_id}:CORPUS_OBSERVATION_AFTER_GLOBAL_OBSERVATION")

        source_observations: list[str] = []
        for index, raw_source in enumerate(corpus.get("sources") or []):
            if not isinstance(raw_source, Mapping):
                raise CorpusInventoryFinalizationError(
                    f"{corpus_id}:sources[{index}] is not an object"
                )
            source_value = raw_source.get("inventory_observed_at")
            if source_value in (None, ""):
                continue
            source_observed = _timestamp(
                source_value,
                label=f"{corpus_id}:sources[{index}].inventory_observed_at",
            )
            source_observations.append(_timestamp_text(source_observed))
            if source_observed < required_after:
                source_id = str(raw_source.get("source_id") or index)
                blockers.append(f"{corpus_id}:{source_id}:SOURCE_OBSERVED_BEFORE_FINALIZATION_LAG")
            if source_observed > observed:
                source_id = str(raw_source.get("source_id") or index)
                blockers.append(f"{corpus_id}:{source_id}:SOURCE_OBSERVATION_AFTER_CORPUS_OBSERVATION")

        summary = {
            "corpus_id": corpus_id,
            "lane": expected["lane"],
            "canonical_end_exclusive_utc": _timestamp_text(end_exclusive),
            "finalization_lag_seconds": lag_seconds,
            "required_inventory_observation_at_or_after": _timestamp_text(required_after),
            "inventory_observed_at_utc": _timestamp_text(observed),
            "inventory_observed_after_corpus_end": observed >= end_exclusive,
            "inventory_observed_after_product_lag": lag_seconds >= 0 and observed >= required_after,
            "finalization_policy": policy,
            "source_observation_count": len(source_observations),
            "source_observations_fingerprint": _fp(sorted(source_observations)),
        }
        summary["finalization_summary_fingerprint"] = _fp(summary)
        summaries.append(summary)

    if seen != set(coverage.EXPECTED_WINDOWS):
        raise CorpusInventoryFinalizationError("source spec is missing a canonical corpus")

    blockers = sorted(set(blockers))
    summaries = sorted(summaries, key=lambda row: row["corpus_id"])
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "status": READY_STATUS if not blockers else BLOCKED_STATUS,
        "source_spec": spec,
        "source_spec_fingerprint": _fp(spec),
        "global_inventory_observed_at_utc": _timestamp_text(global_observed),
        "corpus_finalization_summaries": summaries,
        "corpus_finalization_summaries_fingerprint": _fp(summaries),
        "canonical_windows_fingerprint": _fp(coverage.EXPECTED_WINDOWS),
        "product_specific_lags_required": True,
        "lag_policies_evidence_fingerprinted": all_policy_evidence_valid and bool(summaries),
        "inventory_must_follow_corpus_end_and_product_lag": True,
        "blockers": blockers,
        "next_action": (
            "RUN_PAGINATED_S3_LATEST_VERSION_RESOLUTION"
            if not blockers
            else "REPAIR_CORPUS_INVENTORY_FINALIZATION_BLOCKERS"
        ),
        **_authority_fields(),
    }
    receipt["receipt_fingerprint"] = _fp(receipt)
    return receipt


def validate_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("receipt_fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise CorpusInventoryFinalizationError("finalization receipt schema or fingerprint mismatch")
    checked["receipt_fingerprint"] = observed
    _authority(checked, label="inventory-finalization receipt")
    spec = checked.get("source_spec")
    if not isinstance(spec, Mapping):
        raise CorpusInventoryFinalizationError("finalization receipt is missing source_spec")
    rebuilt = build_contract(spec)
    if rebuilt != dict(value):
        raise CorpusInventoryFinalizationError("finalization receipt differs from deterministic rebuild")
    return copy.deepcopy(dict(value))


def _fixture() -> dict[str, Any]:
    spec: dict[str, Any] = {
        "schema": resolution.SPEC_SCHEMA,
        "allowed_roots": ["data"],
        "inventory_observed_at": "2026-07-25T00:00:00Z",
        "corpora": [],
        **_authority_fields(),
    }
    for corpus_id, expected in coverage.EXPECTED_WINDOWS.items():
        spec["corpora"].append(
            {
                "corpus_id": corpus_id,
                "lane": expected["lane"],
                "publisher_id": 1,
                "bucket": "fixture-bucket",
                "prefix": f"ng/{corpus_id}/",
                "expected_days": ["20260315"],
                "expected_object_count": 1,
                "inventory_scope_verified": True,
                "inventory_complete_asserted": True,
                "inventory_observed_at": "2026-07-25T00:00:00Z",
                "finalization_lag_seconds": 86400 if expected["lane"] == "l1_trades" else 172800,
                "finalization_policy": {
                    "policy_id": f"{expected['lane']}-historical-finalization-v1",
                    "evidence_source": "publisher-history-policy.json",
                    "evidence_observed_at": "2026-07-24T00:00:00Z",
                    "evidence_sha256": "1" * 64,
                },
                "sources": [
                    {
                        "source_id": f"{corpus_id}-source",
                        "day": "20260315",
                        "lane": expected["lane"],
                        "key": f"ng/{corpus_id}/source.dbn",
                        "materialized_path": f"data/{corpus_id}.dbn",
                        "definition": {"placeholder": True},
                    }
                ],
            }
        )
    return spec


def selftest() -> int:
    receipt = build_contract(_fixture())
    assert receipt["status"] == READY_STATUS
    validate_receipt(receipt)
    early = _fixture()
    early["inventory_observed_at"] = "2026-07-01T00:00:00Z"
    for corpus in early["corpora"]:
        corpus["inventory_observed_at"] = "2026-07-01T00:00:00Z"
    blocked = build_contract(early)
    assert blocked["status"] == BLOCKED_STATUS
    assert any("BEFORE_FINALIZATION_LAG" in blocker for blocker in blocked["blockers"])
    print("[ng_corpus_inventory_finalization_contract] selftest PASS")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build")
    build_parser.add_argument(
        "--spec",
        type=Path,
        default=Path("renders/ng_refine_s95/ng_corpus_s3_latest_version_resolution_spec.json"),
    )
    build_parser.add_argument(
        "--out",
        type=Path,
        default=Path("renders/ng_refine_s95/ng_corpus_inventory_finalization_contract.json"),
    )
    subparsers.add_parser("selftest")
    args = parser.parse_args(argv)
    if args.command == "selftest":
        return selftest()
    receipt = build_contract(_load(args.spec))
    validate_receipt(receipt)
    _write(args.out, receipt)
    print(json.dumps({"out": str(args.out), "status": receipt["status"]}, sort_keys=True))
    return 0 if receipt["status"] == READY_STATUS else 2


if __name__ == "__main__":
    raise SystemExit(main())
