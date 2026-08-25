#!/usr/bin/env python3
"""Fail-closed audit for the 15 minimum Frankie full-stack October launch gates.

This module audits supplied metadata only.  It does not launch, mutate, predict, score,
or reconcile.  A passing report means the handoff's minimum launch evidence is present;
it is explicitly not evidence of predictive success.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Any, Callable, Mapping

from research.kalshi.frankie_full_stack_runtime_contracts_20260824 import (
    EXPECTED_MODEL,
    OCTOBER_END,
    OCTOBER_START,
    LedgerKind,
)


SCHEMA = "FRANKIE_FULL_STACK_LAUNCH_GATE_AUDIT_V1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
SCIENTIFIC_DISCLAIMER = (
    "Launch-gate readiness is not evidence of predictive success; recognition, prior prediction, "
    "early locking, failures, abstentions, late locks, and no-locks remain empirical October results."
)

REQUIRED_AUTHORITY_CLASSES = {
    "BINDING_CURRENT",
    "CURRENT_BRAIN",
    "FROZEN_LEARNED_KNOWLEDGE",
    "EXTRA_AGENT_CARRYFORWARD",
    "PROVISIONAL_SHADOW",
    "ARCHIVE_NOT_SERVABLE",
    "SEALED_TARGET_ANSWER",
}
REQUIRED_CORPUS_FAMILIES = {
    "D_STRUCTURES",
    "DIPOLES",
    "CHAINS_AND_EXTENSIONS",
    "PHASE_1",
    "PHASE_2",
    "STOPPED_AND_NEGATIVE_CASES",
}
REQUIRED_V3_DENIALS = {
    "V3_TARGET_POINT_ESTIMATES",
    "D1_EXTRATREES",
    "EXACT_HISTORICAL_CLOCKS",
    "FIXED_HORIZON_TRADE_FINDINGS",
}
REQUIRED_CROSSWALK = {
    "LEGACY_PRICE",
    "LEGACY_NATIVE_SIGNED_FLOW",
    "ROLL20",
    "LEGACY_BOOK_IMBALANCE",
    "PREDECESSOR_FAMILY_CHAIN",
}
REQUIRED_MESSAGE_TYPES = set("ACMRTFN")
REQUIRED_HELPERS = {"recurrence", "extension", "timing", "context"}
REQUIRED_PROVIDER_TASKS = {f"helper:{role}" for role in REQUIRED_HELPERS} | {"frankie:synthesis"}
REQUIRED_RETENTION = {"weak", "negative", "sparse", "ambiguous", "contradictory", "inconclusive"}
REQUIRED_EVENTS = {
    "FRANKIE_REPLAY_PROGRESS",
    "FRANKIE_PROVIDER_CALL_STARTED",
    "FRANKIE_PROVIDER_RESPONSE_ACCEPTED",
    "FRANKIE_PERSISTENCE_APPENDED",
    "FRANKIE_OCTOBER_PROGRESS",
}


class LaunchGateError(ValueError):
    """The report is incomplete or one or more minimum launch gates failed."""


@dataclass(frozen=True)
class LaunchAuditInput:
    knowledge_catalog: Mapping[str, Any]
    ledger_metadata: Mapping[str, Any]
    runtime_metadata: Mapping[str, Any]


@dataclass(frozen=True)
class GateEvidence:
    field: str
    expected: str
    observed: str
    reference_hash: str | None = None


@dataclass(frozen=True)
class GateResult:
    gate_id: str
    title: str
    passed: bool
    evidence: tuple[GateEvidence, ...]
    failure_code: str | None


@dataclass(frozen=True)
class LaunchGateReport:
    schema: str
    status: str
    gates: tuple[GateResult, ...]
    passed_count: int
    failed_gate_ids: tuple[str, ...]
    predictive_success_claimed: bool
    scientific_disclaimer: str
    report_hash: str


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _map(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _child(parent: Any, key: str) -> Mapping[str, Any]:
    return _map(_map(parent).get(key))


def _set(value: Any) -> set[Any]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        return set()
    try:
        return set(value)
    except TypeError:
        return set()


def _is_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA256_RE.fullmatch(value))


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _evidence(field: str, expected: Any, observed: Any, reference_hash: Any = None) -> GateEvidence:
    ref = reference_hash if _is_sha(reference_hash) else None
    if isinstance(observed, (list, tuple, set, frozenset)):
        observed = sorted(str(item) for item in observed)
    return GateEvidence(field, str(expected), _canonical(observed), ref)


def _result(
    gate_id: str,
    title: str,
    passed: bool,
    evidence: tuple[GateEvidence, ...],
) -> GateResult:
    return GateResult(
        gate_id=gate_id,
        title=title,
        passed=bool(passed),
        evidence=evidence,
        failure_code=None if passed else f"{gate_id}_EVIDENCE_INSUFFICIENT",
    )


def _g01(inp: LaunchAuditInput) -> GateResult:
    row = _child(inp.runtime_metadata, "repository_safety_inventory")
    checks = {
        "completed": row.get("completed") is True,
        "branch": _text(row.get("branch")),
        "commit": isinstance(row.get("commit"), str) and bool(COMMIT_RE.fullmatch(row["commit"])),
        "worktrees_checked": row.get("worktrees_checked") is True,
        "uncommitted_artifacts_preserved": row.get("uncommitted_artifacts_preserved") is True,
        "receipt_hash": _is_sha(row.get("receipt_hash")),
    }
    return _result(
        "G01",
        "Repository/worktree safety inventory completed",
        all(checks.values()),
        (
            _evidence("safety_checks", "all true", checks, row.get("receipt_hash")),
            _evidence("branch", "non-empty", row.get("branch", "MISSING")),
        ),
    )


def _g02(inp: LaunchAuditInput) -> GateResult:
    catalog = _map(inp.knowledge_catalog)
    classes = _set(catalog.get("authority_classes"))
    sources = catalog.get("sources") if isinstance(catalog.get("sources"), list) else []
    valid_sources = all(
        isinstance(source, Mapping)
        and _text(source.get("path"))
        and _is_sha(source.get("sha256"))
        and _positive_int(source.get("bytes"))
        and source.get("authority_class") in REQUIRED_AUTHORITY_CLASSES
        and _text(source.get("access_policy"))
        for source in sources
    )
    passed = (
        _is_sha(catalog.get("manifest_hash"))
        and catalog.get("coverage_percent") == 100
        and REQUIRED_AUTHORITY_CLASSES <= classes
        and bool(sources)
        and valid_sources
        and REQUIRED_AUTHORITY_CLASSES <= {source.get("authority_class") for source in sources}
    )
    return _result(
        "G02",
        "Full knowledge-manifest hashes and authority classes recorded",
        passed,
        (
            _evidence("manifest_hash", "lowercase SHA-256", _is_sha(catalog.get("manifest_hash")), catalog.get("manifest_hash")),
            _evidence("coverage_percent", 100, catalog.get("coverage_percent", "MISSING")),
            _evidence("authority_classes", sorted(REQUIRED_AUTHORITY_CLASSES), sorted(classes)),
            _evidence("valid_source_count", "> 0 and fully typed", len(sources) if valid_sources else 0),
        ),
    )


def _g03(inp: LaunchAuditInput) -> GateResult:
    row = _child(inp.knowledge_catalog, "s135")
    bodies = _map(row.get("play_body_hashes"))
    passed = (
        str(row.get("stack_version", "")).startswith("s135.")
        and row.get("brain_version") == "s105.9"
        and row.get("canonical_plays_total") == 90
        and row.get("full_plays_served") == 90
        and len(bodies) == 90
        and all(_text(play_id) and _is_sha(digest) for play_id, digest in bodies.items())
    )
    return _result(
        "G03",
        "Full S135 brain and all 90 plays retrievable",
        passed,
        (
            _evidence("stack_version", "s135.*", row.get("stack_version", "MISSING")),
            _evidence("brain_version", "s105.9", row.get("brain_version", "MISSING")),
            _evidence("served_play_bodies", 90, len(bodies)),
            _evidence("full_plays_served", 90, row.get("full_plays_served", "MISSING")),
        ),
    )


def _g04(inp: LaunchAuditInput) -> GateResult:
    row = _child(inp.knowledge_catalog, "frozen_corpus")
    families = _set(row.get("families"))
    passed = (
        _is_sha(row.get("manifest_hash"))
        and row.get("status") == "FROZEN"
        and isinstance(row.get("week_count"), int)
        and row.get("week_count", 0) >= 54
        and row.get("retrievable") is True
        and REQUIRED_CORPUS_FAMILIES <= families
    )
    return _result(
        "G04",
        "Frozen 54/55-week D corpus retrievable",
        passed,
        (
            _evidence("week_count", ">=54", row.get("week_count", "MISSING"), row.get("manifest_hash")),
            _evidence("status", "FROZEN and retrievable", {"status": row.get("status"), "retrievable": row.get("retrievable")}),
            _evidence("families", sorted(REQUIRED_CORPUS_FAMILIES), sorted(families)),
        ),
    )


def _g05(inp: LaunchAuditInput) -> GateResult:
    row = _child(_child(inp.knowledge_catalog, "access_controls"), "forbidden_v3")
    denied = _set(row.get("denied_categories"))
    passed = (
        row.get("mechanically_denied") is True
        and _is_sha(row.get("denial_receipt_hash"))
        and REQUIRED_V3_DENIALS <= denied
    )
    return _result(
        "G05",
        "Forbidden V3 outputs mechanically denied",
        passed,
        (
            _evidence("mechanically_denied", True, row.get("mechanically_denied", "MISSING"), row.get("denial_receipt_hash")),
            _evidence("denied_categories", sorted(REQUIRED_V3_DENIALS), sorted(denied)),
        ),
    )


def _g06(inp: LaunchAuditInput) -> GateResult:
    row = _child(_child(inp.knowledge_catalog, "access_controls"), "answer_wall")
    passed = (
        row.get("state") == "SEALED"
        and row.get("pre_freeze_access") == "DENIED"
        and row.get("step1_served") is False
        and _is_sha(row.get("denial_receipt_hash"))
    )
    return _result(
        "G06",
        "October Step-1 answer wall denied before freeze",
        passed,
        (
            _evidence("answer_wall_state", "SEALED", row.get("state", "MISSING"), row.get("denial_receipt_hash")),
            _evidence("pre_freeze_access", "DENIED", row.get("pre_freeze_access", "MISSING")),
            _evidence("step1_served", False, row.get("step1_served", "MISSING")),
        ),
    )


def _g07(inp: LaunchAuditInput) -> GateResult:
    row = _child(inp.runtime_metadata, "crosswalk")
    mappings = _set(row.get("mapped_observables"))
    passed = (
        row.get("coverage_percent") == 100
        and _is_sha(row.get("coverage_receipt_hash"))
        and row.get("target_identities_injected") is False
        and REQUIRED_CROSSWALK <= mappings
    )
    return _result(
        "G07",
        "Legacy/V4 semantic crosswalk complete",
        passed,
        (
            _evidence("coverage_percent", 100, row.get("coverage_percent", "MISSING"), row.get("coverage_receipt_hash")),
            _evidence("mapped_observables", sorted(REQUIRED_CROSSWALK), sorted(mappings)),
            _evidence("target_identities_injected", False, row.get("target_identities_injected", "MISSING")),
        ),
    )


def _g08(inp: LaunchAuditInput) -> GateResult:
    row = _child(inp.runtime_metadata, "stream")
    messages = _set(row.get("message_types"))
    passed = (
        row.get("mode") == "CONTINUOUS"
        and row.get("started") is True
        and row.get("predecessor_bootstrap_verified") is True
        and row.get("complete_order_lifecycle") is True
        and row.get("artificial_resets") is False
        and REQUIRED_MESSAGE_TYPES <= messages
        and _is_sha(row.get("receipt_hash"))
    )
    return _result(
        "G08",
        "Continuous MBO replay and predecessor bootstrap verified",
        passed,
        (
            _evidence("stream_mode", "CONTINUOUS and started", {"mode": row.get("mode"), "started": row.get("started")}, row.get("receipt_hash")),
            _evidence("predecessor_bootstrap_verified", True, row.get("predecessor_bootstrap_verified", "MISSING")),
            _evidence("artificial_resets", False, row.get("artificial_resets", "MISSING")),
            _evidence("message_types", sorted(REQUIRED_MESSAGE_TYPES), sorted(messages)),
        ),
    )


def _g09(inp: LaunchAuditInput) -> GateResult:
    raw = _map(inp.runtime_metadata).get("helpers")
    helpers = raw if isinstance(raw, list) else []
    roles = {row.get("role") for row in helpers if isinstance(row, Mapping)}
    bindings = {
        (
            row.get("causal_prefix_hash"),
            row.get("state_prefix_hash"),
            row.get("knowledge_manifest_hash"),
        )
        for row in helpers
        if isinstance(row, Mapping)
    }
    valid_hashes = all(all(_is_sha(value) for value in identity) for identity in bindings)
    passed = (
        len(helpers) == 4
        and roles == REQUIRED_HELPERS
        and all(row.get("active") is True and row.get("model") == EXPECTED_MODEL for row in helpers if isinstance(row, Mapping))
        and len(bindings) == 1
        and valid_hashes
    )
    return _result(
        "G09",
        "Four live helpers share identical causal-prefix binding",
        passed,
        (
            _evidence("helper_roles", sorted(REQUIRED_HELPERS), sorted(str(role) for role in roles)),
            _evidence("helper_count", 4, len(helpers)),
            _evidence("distinct_prefix_bindings", 1, len(bindings)),
            _evidence("active_exact_model", True, all(row.get("active") is True and row.get("model") == EXPECTED_MODEL for row in helpers if isinstance(row, Mapping))),
        ),
    )


def _g10(inp: LaunchAuditInput) -> GateResult:
    row = _child(inp.runtime_metadata, "synthesis_authority")
    passed = (
        row.get("synthesis_owner") == "FRANKIE"
        and row.get("probability_owner") == "FRANKIE"
        and row.get("primary_lock_owner") == "FRANKIE"
        and row.get("voting") is False
        and row.get("averaging") is False
        and row.get("automatic_consensus") is False
        and row.get("helper_lock_ids") == []
    )
    return _result(
        "G10",
        "Frankie is sole synthesizer, probability, and primary-lock owner",
        passed,
        (
            _evidence("owners", "all FRANKIE", {key: row.get(key, "MISSING") for key in ("synthesis_owner", "probability_owner", "primary_lock_owner")}),
            _evidence("aggregation_disabled", True, {key: row.get(key, "MISSING") for key in ("voting", "averaging", "automatic_consensus")}),
            _evidence("helper_lock_count", 0, len(row.get("helper_lock_ids")) if isinstance(row.get("helper_lock_ids"), list) else "MISSING"),
        ),
    )


def _g11(inp: LaunchAuditInput) -> GateResult:
    raw = _map(inp.runtime_metadata).get("provider_invocations")
    rows = raw if isinstance(raw, list) else []
    tasks = {row.get("task") for row in rows if isinstance(row, Mapping)}
    ids = [row.get("provider_response_id") for row in rows if isinstance(row, Mapping)]
    valid = all(
        isinstance(row, Mapping)
        and row.get("transport") == "OPENAI_RESPONSES_API"
        and row.get("accepted") is True
        and row.get("requested_model") == EXPECTED_MODEL
        and row.get("resolved_model") == EXPECTED_MODEL
        and _text(row.get("provider_response_id"))
        and _is_sha(row.get("request_hash"))
        and _is_sha(row.get("response_hash"))
        for row in rows
    )
    passed = len(rows) == 5 and tasks == REQUIRED_PROVIDER_TASKS and len(set(ids)) == 5 and valid
    return _result(
        "G11",
        "Exact GPT-5.6 Sol responses accepted with provider IDs",
        passed,
        (
            _evidence("accepted_invocation_count", 5, len(rows)),
            _evidence("provider_tasks", sorted(REQUIRED_PROVIDER_TASKS), sorted(str(task) for task in tasks)),
            _evidence("distinct_nonempty_provider_ids", 5, len({item for item in ids if _text(item)})),
            _evidence("exact_model_and_receipts", True, valid),
        ),
    )


def _g12(inp: LaunchAuditInput) -> GateResult:
    row = _map(inp.ledger_metadata)
    counts = _map(row.get("record_counts"))
    required = {kind.value for kind in LedgerKind}
    present = {kind for kind in required if _positive_int(counts.get(kind))}
    passed = (
        row.get("chain_validated") is True
        and row.get("append_only") is True
        and row.get("durable_fsync") is True
        and row.get("exclusive_create") is True
        and _is_sha(row.get("latest_record_hash"))
        and present == required
    )
    return _result(
        "G12",
        "Required immutable ledgers have begun persisting",
        passed,
        (
            _evidence("durability", "hash-chain, append-only, fsync, exclusive-create", {key: row.get(key, "MISSING") for key in ("chain_validated", "append_only", "durable_fsync", "exclusive_create")}, row.get("latest_record_hash")),
            _evidence("ledger_kinds_started", sorted(required), sorted(present)),
        ),
    )


def _g13(inp: LaunchAuditInput) -> GateResult:
    counts = _map(_map(inp.ledger_metadata).get("retained_case_counts"))
    retained = {kind for kind in REQUIRED_RETENTION if _positive_int(counts.get(kind))}
    passed = retained == REQUIRED_RETENTION
    return _result(
        "G13",
        "Weak, negative, sparse, ambiguous, contradictory, and inconclusive cases retained",
        passed,
        (
            _evidence("retained_categories", sorted(REQUIRED_RETENTION), sorted(retained)),
            _evidence("retained_counts", "each > 0", {kind: counts.get(kind, 0) for kind in sorted(REQUIRED_RETENTION)}),
        ),
    )


def _g14(inp: LaunchAuditInput) -> GateResult:
    row = _child(inp.runtime_metadata, "service_isolation")
    passed = (
        row.get("isolated") is True
        and _text(row.get("service_id"))
        and row.get("target_start") == OCTOBER_START
        and row.get("target_end") == OCTOBER_END
        and row.get("permanent_services_untouched") is True
        and _text(row.get("stop_command"))
        and _text(row.get("rollback_command"))
    )
    return _result(
        "G14",
        "Service isolation and rollback/stop procedure documented",
        passed,
        (
            _evidence("isolated_service", True, {"isolated": row.get("isolated"), "service_id_present": _text(row.get("service_id"))}),
            _evidence("bounded_target", [OCTOBER_START, OCTOBER_END], [row.get("target_start"), row.get("target_end")]),
            _evidence("stop_and_rollback_documented", True, {"stop": _text(row.get("stop_command")), "rollback": _text(row.get("rollback_command"))}),
            _evidence("permanent_services_untouched", True, row.get("permanent_services_untouched", "MISSING")),
        ),
    )


def _g15(inp: LaunchAuditInput) -> GateResult:
    row = _child(inp.runtime_metadata, "observability")
    events = _set(row.get("progress_event_names"))
    url = row.get("run_url")
    passed = (
        row.get("live_logs") is True
        and isinstance(url, str)
        and url.startswith("https://")
        and REQUIRED_EVENTS <= events
    )
    return _result(
        "G15",
        "Live logs and run URL make bounded progress observable",
        passed,
        (
            _evidence("live_logs", True, row.get("live_logs", "MISSING")),
            _evidence("https_run_url_present", True, isinstance(url, str) and url.startswith("https://")),
            _evidence("progress_events", sorted(REQUIRED_EVENTS), sorted(events)),
        ),
    )


_GATES: tuple[Callable[[LaunchAuditInput], GateResult], ...] = (
    _g01,
    _g02,
    _g03,
    _g04,
    _g05,
    _g06,
    _g07,
    _g08,
    _g09,
    _g10,
    _g11,
    _g12,
    _g13,
    _g14,
    _g15,
)


def audit_launch_gates(inp: LaunchAuditInput) -> LaunchGateReport:
    if not isinstance(inp, LaunchAuditInput):
        raise LaunchGateError("launch audit input must use LaunchAuditInput")
    gates: list[GateResult] = []
    for index, gate in enumerate(_GATES, start=1):
        try:
            result = gate(inp)
        except Exception:
            gate_id = f"G{index:02d}"
            result = _result(
                gate_id,
                "Malformed gate metadata",
                False,
                (_evidence("metadata_validation", "well-formed", "MALFORMED"),),
            )
        if result.gate_id != f"G{index:02d}" or not result.evidence:
            raise LaunchGateError("internal launch-gate ordering/evidence invariant failed")
        gates.append(result)
    failed = tuple(result.gate_id for result in gates if not result.passed)
    core = {
        "schema": SCHEMA,
        "status": "LAUNCH_GATES_PASSED" if not failed else "LAUNCH_GATES_FAILED",
        "gates": [asdict(result) for result in gates],
        "passed_count": len(gates) - len(failed),
        "failed_gate_ids": list(failed),
        "predictive_success_claimed": False,
        "scientific_disclaimer": SCIENTIFIC_DISCLAIMER,
    }
    return LaunchGateReport(
        schema=SCHEMA,
        status=core["status"],
        gates=tuple(gates),
        passed_count=core["passed_count"],
        failed_gate_ids=failed,
        predictive_success_claimed=False,
        scientific_disclaimer=SCIENTIFIC_DISCLAIMER,
        report_hash=_hash(core),
    )


def require_launch_ready(report: LaunchGateReport) -> None:
    if not isinstance(report, LaunchGateReport):
        raise LaunchGateError("launch readiness requires a LaunchGateReport")
    core = {
        "schema": report.schema,
        "status": report.status,
        "gates": [asdict(result) for result in report.gates],
        "passed_count": report.passed_count,
        "failed_gate_ids": list(report.failed_gate_ids),
        "predictive_success_claimed": report.predictive_success_claimed,
        "scientific_disclaimer": report.scientific_disclaimer,
    }
    if report.report_hash != _hash(core):
        raise LaunchGateError("launch gates not ready: REPORT_HASH_MISMATCH")
    if (
        report.schema != SCHEMA
        or len(report.gates) != 15
        or report.status != "LAUNCH_GATES_PASSED"
        or report.passed_count != 15
        or report.failed_gate_ids
        or report.predictive_success_claimed
        or report.scientific_disclaimer != SCIENTIFIC_DISCLAIMER
    ):
        failed = ",".join(report.failed_gate_ids) or "REPORT_INVARIANT"
        raise LaunchGateError(f"launch gates not ready: {failed}")
