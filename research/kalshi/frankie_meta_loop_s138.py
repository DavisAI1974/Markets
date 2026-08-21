#!/usr/bin/env python3
"""Bounded post-evidence metacognitive sidecar for Frankie and specialists A-E.

This module never rewrites a frozen blind/first-lock artifact, never drops a
case/chain, never changes specialist roles, and never promotes or applies a
brain lesson. It only binds immutable artifacts, validates a reflective audit,
and produces next-run-only revision proposals.
"""
from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

VERSION = "s138.frankie-meta-loop.1"
SPECIALISTS = tuple("ABCDE")
CASE_DISPOSITIONS = {"RETAIN", "STRENGTHEN", "WEAKEN", "SPLIT", "UNRESOLVED"}
REVISION_SCOPE = "NEXT_RUN_ONLY"

META_QUESTIONS = (
    "What did I believe or predict before reveal?",
    "What evidence did I expect if that explanation was right?",
    "What did the evidence actually show?",
    "Did the execution test the hypothesis I thought it tested?",
    "Which observations contradict my preferred interpretation?",
    "What did I learn about the market versus my measurement apparatus?",
    "Could another mechanism explain the same evidence?",
    "What missingness, timing, provenance, or observability limits the conclusion?",
    "Should the working hypothesis strengthen, weaken, split, or remain unresolved?",
    "What is the smallest next experiment that separates the live explanations?",
)


class MetaLoopError(ValueError):
    pass


def _canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def artifact_hash(value: Any) -> str:
    return hashlib.sha256(_canon(value)).hexdigest()


def _mapping(name: str, value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MetaLoopError(f"{name} must be a mapping")
    return value


def _text(name: str, value: Any) -> str:
    text = str(value).strip()
    if not text:
        raise MetaLoopError(f"{name} must be non-empty")
    return text


def build_meta_contract(
    *,
    subject: str,
    hypothesis: Mapping[str, Any],
    first_lock: Mapping[str, Any],
    evidence: Mapping[str, Any],
    result: Mapping[str, Any],
    path_trace: Mapping[str, Any],
    specialist: str | None = None,
) -> dict[str, Any]:
    """Bind the pre/post evidence artifacts without granting mutation authority."""
    hypothesis = _mapping("hypothesis", hypothesis)
    first_lock = _mapping("first_lock", first_lock)
    evidence = _mapping("evidence", evidence)
    result = _mapping("result", result)
    path_trace = _mapping("path_trace", path_trace)
    spec = None
    if specialist is not None:
        spec = str(specialist).upper()
        if spec not in SPECIALISTS:
            raise MetaLoopError(f"specialist must be one of {SPECIALISTS}")

    contract = {
        "version": VERSION,
        "subject": _text("subject", subject),
        "specialist": spec,
        "activation": "POST_EVIDENCE_ONLY",
        "bindings": {
            "hypothesis_sha256": artifact_hash(hypothesis),
            "first_lock_sha256": artifact_hash(first_lock),
            "evidence_sha256": artifact_hash(evidence),
            "result_sha256": artifact_hash(result),
            "path_trace_sha256": artifact_hash(path_trace),
        },
        "questions": list(META_QUESTIONS),
        "required_output_fields": [
            "produced_vs_found", "path_soundness", "contradictions",
            "measurement_vs_market", "alternative_mechanisms", "missing_evidence",
            "assumptions", "claim_stances", "case_disposition", "confidence_delta",
            "next_discriminating_test", "revision_proposal",
        ],
        "scientific_boundaries": {
            "first_lock_rewrite_allowed": False,
            "blind_artifact_mutation_allowed": False,
            "evidence_mutation_allowed": False,
            "case_or_chain_drop_allowed": False,
            "specialist_role_rewrite_allowed": False,
            "automatic_brain_promotion_allowed": False,
            "automatic_apply_allowed": False,
            "next_run_revision_only": True,
            "negative_inconclusive_sparse_cases_are_evidence": True,
            "consensus_is_truth": False,
        },
    }
    contract["contract_sha256"] = artifact_hash(contract)
    return contract


def validate_meta_audit(contract: Mapping[str, Any], audit: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed on hindsight rewrite, dropping, promotion, or unbound audits."""
    contract = _mapping("contract", contract)
    audit = _mapping("audit", audit)
    if contract.get("version") != VERSION:
        raise MetaLoopError("unsupported meta-loop contract version")
    required = set(contract.get("required_output_fields", ()))
    missing = sorted(required - set(audit))
    if missing:
        raise MetaLoopError(f"meta audit missing required fields: {missing}")

    disposition = str(audit.get("case_disposition", "")).upper()
    if disposition not in CASE_DISPOSITIONS:
        raise MetaLoopError("case_disposition must preserve the case; DROP is never valid")

    proposal = _mapping("revision_proposal", audit.get("revision_proposal"))
    if str(proposal.get("scope", "")).upper() != REVISION_SCOPE:
        raise MetaLoopError("revision_proposal.scope must be NEXT_RUN_ONLY")
    forbidden = {
        "rewrite_first_lock", "mutate_blind_artifact", "mutate_evidence",
        "drop_case", "drop_chain", "promote_to_brain", "automatic_apply",
    }
    actions = {str(x) for x in proposal.get("actions", ())}
    bad = sorted(forbidden & actions)
    if bad:
        raise MetaLoopError(f"forbidden revision actions requested: {bad}")

    if not isinstance(audit.get("claim_stances"), Mapping):
        raise MetaLoopError("claim_stances must be a mapping")
    for field in ("assumptions", "missing_evidence"):
        value = audit.get(field)
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            raise MetaLoopError(f"{field} must be a sequence")

    if audit.get("artifact_bindings") is not None and dict(audit["artifact_bindings"]) != dict(contract["bindings"]):
        raise MetaLoopError("artifact bindings do not match the immutable contract")

    out = copy.deepcopy(dict(audit))
    out["specialist"] = contract.get("specialist")
    out["artifact_bindings"] = dict(contract["bindings"])
    out["case_disposition"] = disposition
    out["status"] = "VALIDATED_META_AUDIT"
    out["first_lock_rewritten"] = False
    out["case_or_chain_dropped"] = False
    out["promotion_performed"] = False
    out["automatic_apply_performed"] = False
    out["meta_audit_sha256"] = artifact_hash(out)
    return out


def attach_specialist_meta_sidecar(payload: Mapping[str, Any], *, specialist: str) -> dict[str, Any]:
    """Attach a sidecar to an already-served A-E packet without rewriting roles/data."""
    payload = _mapping("payload", payload)
    spec = str(specialist).upper()
    if spec not in SPECIALISTS:
        raise MetaLoopError(f"specialist must be one of {SPECIALISTS}")
    frozen_hash = artifact_hash(payload)
    out = copy.deepcopy(dict(payload))
    out["specialist_meta_loop_contract"] = {
        "version": VERSION,
        "specialist": spec,
        "coordinator": "Frankie",
        "blind_packet_sha256": frozen_hash,
        "activation": "POST_REVEAL_ONLY",
        "local_self_audit_required": True,
        "cross_specialist_reconciliation_required": True,
        "specialist_role_rewritten": False,
        "blind_packet_mutation_allowed": False,
        "case_or_chain_drop_allowed": False,
        "automatic_consensus_resolution_allowed": False,
        "automatic_brain_promotion_allowed": False,
    }
    return out


def reconcile_specialist_meta_audits(audits: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Surface shared assumptions/disagreement; never majority-vote scientific truth."""
    if not audits:
        raise MetaLoopError("at least one specialist meta audit is required")
    seen: set[str] = set()
    assumptions: Counter[str] = Counter()
    missing_union: set[str] = set()
    stances: dict[str, dict[str, str]] = defaultdict(dict)
    next_tests: list[dict[str, str]] = []

    for raw in audits:
        audit = _mapping("specialist audit", raw)
        if audit.get("status") != "VALIDATED_META_AUDIT":
            raise MetaLoopError("specialist reconciliation requires validated meta audits")
        spec = str(audit.get("specialist", "")).upper()
        if spec not in SPECIALISTS or spec in seen:
            raise MetaLoopError(f"invalid or duplicate specialist audit: {spec!r}")
        seen.add(spec)
        for item in audit.get("assumptions", ()):
            assumptions[_text("assumption", item)] += 1
        for item in audit.get("missing_evidence", ()):
            missing_union.add(_text("missing evidence", item))
        for claim, stance in dict(audit.get("claim_stances", {})).items():
            stances[_text("claim", claim)][spec] = _text("stance", stance)
        next_tests.append({"specialist": spec, "test": _text("next test", audit.get("next_discriminating_test"))})

    disagreements = {
        claim: dict(sorted(by_spec.items()))
        for claim, by_spec in sorted(stances.items())
        if len(set(by_spec.values())) > 1
    }
    out = {
        "version": VERSION,
        "status": "SPECIALIST_META_RECONCILIATION_COMPLETE",
        "specialists": sorted(seen),
        "shared_assumptions": [
            {"assumption": text, "specialist_count": count}
            for text, count in sorted(assumptions.items()) if count >= 2
        ],
        "claim_disagreements": disagreements,
        "missing_evidence_union": sorted(missing_union),
        "next_discriminating_tests": sorted(next_tests, key=lambda x: x["specialist"]),
        "consensus_is_truth": False,
        "majority_vote_resolution_allowed": False,
        "coordinator_review_required": True,
        "case_or_chain_drop_allowed": False,
        "automatic_brain_promotion_allowed": False,
        "automatic_apply_allowed": False,
    }
    out["reconciliation_sha256"] = artifact_hash(out)
    return out


def selftest() -> None:
    contract = build_meta_contract(
        subject="demo",
        hypothesis={"claim": "exhaustion continuation"},
        first_lock={"p": 0.62, "locked_at": "t0"},
        evidence={"observed": "mixed"},
        result={"score": 0.0},
        path_trace={"steps": ["hypothesis", "forecast", "reveal"]},
    )
    audit = {
        "produced_vs_found": "mixed", "path_soundness": "adequate",
        "contradictions": ["counterexample"], "measurement_vs_market": "ambiguous",
        "alternative_mechanisms": ["liquidity refill"], "missing_evidence": ["predecessor lifecycle"],
        "assumptions": ["clock is causal"], "claim_stances": {"continuation": "uncertain"},
        "case_disposition": "UNRESOLVED", "confidence_delta": -0.1,
        "next_discriminating_test": "condition on predecessor lifecycle",
        "revision_proposal": {"scope": "NEXT_RUN_ONLY", "actions": ["split_hypothesis"]},
    }
    assert validate_meta_audit(contract, audit)["status"] == "VALIDATED_META_AUDIT"
    print("FRANKIE_META_LOOP_SELFTEST_PASS")


if __name__ == "__main__":
    selftest()
