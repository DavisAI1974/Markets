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
CONTROL_LANE = "S135_CONTROL"
COMBINED_LANE = "FULL_PROVISIONAL_COMBINED"
REQUIRED_LANES = (CONTROL_LANE, COMBINED_LANE)
REQUIRED_ACTIVE_COMPONENTS = {
    "S137_COGNITIVE_RUNTIME",
    "HIPPORAG_RETRIEVAL",
    "TEMPORAL_GRAPH",
    "LATS_BOUNDED_SEARCH",
    "WORKING_MEMORY",
    "PROGRESS_COMPRESSION",
    "PROVISIONAL_V4_ENGINEERING_CANDIDATE",
}
REQUIRED_EVENTS = {
    "FRANKIE_REPLAY_PROGRESS",
    "FRANKIE_PROVIDER_CALL_STARTED",
    "FRANKIE_PROVIDER_RESPONSE_ACCEPTED",
    "FRANKIE_PERSISTENCE_APPENDED",
    "FRANKIE_OCTOBER_PROGRESS",
    "PAIRED_PREFIX_ACCEPTED",
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
    paired = _child(inp.runtime_metadata, "paired_experiment")
    raw = _map(inp.runtime_metadata).get("helpers")
    helpers = raw if isinstance(raw, list) else []
    by_lane = {
        lane: [row for row in helpers if isinstance(row, Mapping) and row.get("lane_id") == lane]
        for lane in REQUIRED_LANES
    }
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
    exact_helpers = all(
        len(by_lane[lane]) == 4
        and {row.get("role") for row in by_lane[lane]} == REQUIRED_HELPERS
        and all(row.get("active") is True and row.get("model") == EXPECTED_MODEL for row in by_lane[lane])
        for lane in REQUIRED_LANES
    )
    control_prefix = paired.get("control_causal_prefix_hash")
    combined_prefix = paired.get("combined_causal_prefix_hash")
    binding = next(iter(bindings), ()) if len(bindings) == 1 else ()
    passed = (
        paired.get("lanes") == list(REQUIRED_LANES)
        and paired.get("primary_lane") == CONTROL_LANE
        and paired.get("combined_lane") == COMBINED_LANE
        and _is_sha(paired.get("identical_prefix_proof_hash"))
        and _is_sha(control_prefix)
        and control_prefix == combined_prefix
        and len(helpers) == 8
        and exact_helpers
        and len(bindings) == 1
        and valid_hashes
        and bool(binding)
        and binding[0] == control_prefix
    )
    return _result(
        "G09",
        "Four live helpers per paired lane share one identical causal prefix",
        passed,
        (
            _evidence("paired_lanes", list(REQUIRED_LANES), paired.get("lanes", "MISSING")),
            _evidence("helpers_per_lane", 4, {lane: len(by_lane[lane]) for lane in REQUIRED_LANES}),
            _evidence("helper_roles_per_lane", sorted(REQUIRED_HELPERS), {lane: sorted(str(row.get("role")) for row in by_lane[lane]) for lane in REQUIRED_LANES}),
            _evidence("distinct_prefix_bindings", 1, len(bindings)),
            _evidence("identical_prefix_proof", "valid SHA and equal lane prefix", {"proof": _is_sha(paired.get("identical_prefix_proof_hash")), "equal_prefix": _is_sha(control_prefix) and control_prefix == combined_prefix}, paired.get("identical_prefix_proof_hash")),
            _evidence("active_exact_model", True, exact_helpers),
        ),
    )


def _g10(inp: LaunchAuditInput) -> GateResult:
    row = _child(inp.runtime_metadata, "synthesis_authority")
    lanes = _map(row.get("lanes"))
    paired = _child(inp.runtime_metadata, "paired_experiment")
    authorities = {CONTROL_LANE: "S135_PRIMARY", COMBINED_LANE: "SHADOW_ONLY"}
    lane_checks = {}
    for lane in REQUIRED_LANES:
        lane_row = _map(lanes.get(lane))
        lane_checks[lane] = (
            lane_row.get("lane_id") == lane
            and lane_row.get("synthesis_owner") == "FRANKIE"
            and lane_row.get("probability_owner") == "FRANKIE"
            and lane_row.get("primary_lock_owner") == "FRANKIE"
            and lane_row.get("lock_authority") == authorities[lane]
            and lane_row.get("voting") is False
            and lane_row.get("averaging") is False
            and lane_row.get("automatic_consensus") is False
            and lane_row.get("helper_lock_ids") == []
        )
    active = paired.get("active_provisional_components")
    active_set = _set(active)
    active_receipts = _map(paired.get("active_provisional_component_receipt_hashes"))
    meta = _map(paired.get("deferred_meta_loop"))
    component_checks = (
        isinstance(active, list)
        and len(active) == 7
        and active_set == REQUIRED_ACTIVE_COMPONENTS
        and set(active_receipts) == REQUIRED_ACTIVE_COMPONENTS
        and all(_is_sha(value) for value in active_receipts.values())
        and meta.get("component_id") == "META_LOOP"
        and meta.get("status") == "DEFERRED_NOT_YET_LAWFUL"
        and meta.get("lifecycle_stage") == "POST_EVIDENCE_DIAGNOSTIC"
        and meta.get("executed_stage") == "PRE_REVEAL_PREFIX"
        and _is_sha(meta.get("receipt_hash"))
    )
    passed = (
        set(lanes) == set(REQUIRED_LANES)
        and all(lane_checks.values())
        and paired.get("primary_lane") == CONTROL_LANE
        and paired.get("combined_lane") == COMBINED_LANE
        and component_checks
    )
    return _result(
        "G10",
        "Paired Frankie authority and combined provisional lifecycle are exact",
        passed,
        (
            _evidence("lane_authority_checks", "both true", lane_checks),
            _evidence("lock_authorities", authorities, {lane: _map(lanes.get(lane)).get("lock_authority", "MISSING") for lane in REQUIRED_LANES}),
            _evidence("active_combined_components", sorted(REQUIRED_ACTIVE_COMPONENTS), sorted(str(item) for item in active_set)),
            _evidence("deferred_meta_loop", "post-evidence only", {key: meta.get(key, "MISSING") for key in ("status", "lifecycle_stage", "executed_stage")}, meta.get("receipt_hash")),
        ),
    )


def _g11(inp: LaunchAuditInput) -> GateResult:
    raw = _map(inp.runtime_metadata).get("provider_invocations")
    rows = raw if isinstance(raw, list) else []
    tasks = {row.get("task") for row in rows if isinstance(row, Mapping)}
    ids = [row.get("provider_response_id") for row in rows if isinstance(row, Mapping)]
    by_lane = {
        lane: [row for row in rows if isinstance(row, Mapping) and row.get("lane_id") == lane]
        for lane in REQUIRED_LANES
    }
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
    paired_tasks = all(
        len(by_lane[lane]) == 5
        and {row.get("task") for row in by_lane[lane]} == REQUIRED_PROVIDER_TASKS
        for lane in REQUIRED_LANES
    )
    passed = (
        len(rows) == 10
        and tasks == REQUIRED_PROVIDER_TASKS
        and paired_tasks
        and len(set(ids)) == 10
        and valid
    )
    return _result(
        "G11",
        "Ten distinct exact GPT-5.6 Sol paired-lane responses accepted",
        passed,
        (
            _evidence("accepted_invocation_count", 10, len(rows)),
            _evidence("invocations_per_lane", 5, {lane: len(by_lane[lane]) for lane in REQUIRED_LANES}),
            _evidence("provider_tasks_per_lane", sorted(REQUIRED_PROVIDER_TASKS), {lane: sorted(str(row.get("task")) for row in by_lane[lane]) for lane in REQUIRED_LANES}),
            _evidence("distinct_nonempty_provider_ids", 10, len({item for item in ids if _text(item)})),
            _evidence("exact_model_and_receipts", True, valid),
        ),
    )


def _g12(inp: LaunchAuditInput) -> GateResult:
    row = _map(inp.ledger_metadata)
    ledgers = _map(row.get("paired_ledgers"))
    required = {kind.value for kind in LedgerKind}
    present_by_lane = {}
    lane_checks = {}
    for lane in REQUIRED_LANES:
        ledger = _map(ledgers.get(lane))
        counts = _map(ledger.get("record_counts"))
        present_by_lane[lane] = {kind for kind in required if _positive_int(counts.get(kind))}
        lane_checks[lane] = (
            ledger.get("lane_id") == lane
            and ledger.get("chain_validated") is True
            and ledger.get("append_only") is True
            and ledger.get("durable_fsync") is True
            and ledger.get("exclusive_create") is True
            and _text(ledger.get("path"))
            and _is_sha(ledger.get("latest_record_hash"))
            and present_by_lane[lane] == required
        )
    control = _map(ledgers.get(CONTROL_LANE))
    combined = _map(ledgers.get(COMBINED_LANE))
    paired = _child(inp.runtime_metadata, "paired_experiment")
    passed = (
        set(ledgers) == set(REQUIRED_LANES)
        and all(lane_checks.values())
        and control.get("path") != combined.get("path")
        and control.get("latest_record_hash") != combined.get("latest_record_hash")
        and _is_sha(row.get("identical_prefix_proof_hash"))
        and row.get("identical_prefix_proof_hash") == paired.get("identical_prefix_proof_hash")
    )
    return _result(
        "G12",
        "Independent paired immutable ledgers have begun persisting",
        passed,
        (
            _evidence("paired_ledger_checks", "both true", lane_checks, row.get("identical_prefix_proof_hash")),
            _evidence("independent_paths", True, control.get("path") != combined.get("path")),
            _evidence("independent_latest_hashes", True, control.get("latest_record_hash") != combined.get("latest_record_hash")),
            _evidence("ledger_kinds_started_per_lane", sorted(required), {lane: sorted(present_by_lane[lane]) for lane in REQUIRED_LANES}),
        ),
    )


def _g13(inp: LaunchAuditInput) -> GateResult:
    ledgers = _map(_map(inp.ledger_metadata).get("paired_ledgers"))
    counts_by_lane = {
        lane: _map(_map(ledgers.get(lane)).get("retained_case_counts"))
        for lane in REQUIRED_LANES
    }
    retained_by_lane = {
        lane: {kind for kind in REQUIRED_RETENTION if _positive_int(counts_by_lane[lane].get(kind))}
        for lane in REQUIRED_LANES
    }
    passed = set(ledgers) == set(REQUIRED_LANES) and all(
        retained_by_lane[lane] == REQUIRED_RETENTION for lane in REQUIRED_LANES
    )
    return _result(
        "G13",
        "Both lanes retain weak, negative, sparse, ambiguous, contradictory, and inconclusive cases",
        passed,
        (
            _evidence("retained_categories_per_lane", sorted(REQUIRED_RETENTION), {lane: sorted(retained_by_lane[lane]) for lane in REQUIRED_LANES}),
            _evidence("retained_counts_per_lane", "each > 0", {lane: {kind: counts_by_lane[lane].get(kind, 0) for kind in sorted(REQUIRED_RETENTION)} for lane in REQUIRED_LANES}),
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
