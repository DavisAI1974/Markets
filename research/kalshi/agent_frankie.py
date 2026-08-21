#!/usr/bin/env python3
"""Frankie hybrid agent entry point.

Derived from the original ``spawn.py`` operating philosophy: every premise is a lookup,
missing inputs stop the line, and no prompt may loosen a deterministic gate. The original
file remains untouched; ``legacy`` delegates to it after verifying its pinned Git blob.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from frankie_backends import ScriptedBackend, backend_from_name  # noqa: E402
from frankie_cognition import COGNITIVE_CONTRACT_VERSION  # noqa: E402
from frankie_core import (  # noqa: E402
    EXECUTION_ENABLED,
    SPAWN_PATH,
    FrankieConfig,
    FrankieEvent,
    GateStop,
    load_candidate_registry,
    load_paper_manifest,
    qualify_event,
    verify_original_spawn,
)
from frankie_engine import consume_once, evaluate_event, serve  # noqa: E402
from frankie_improve import propose_improvement, record_outcome  # noqa: E402
from frankie_meta_loop_coordinator_s138 import (  # noqa: E402
    VERSION as META_COORDINATOR_VERSION,
    MetaLoopError,
    build_frankie_meta_contract,
    reconcile_frankie_meta_system,
    validate_frankie_meta_audit,
)


def print_json(value) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def read_json_object(path: str, label: str) -> dict:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateStop(f"cannot read {label} JSON {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise GateStop(f"{label} JSON must contain one object")
    return raw


def read_event(path: str) -> FrankieEvent:
    return FrankieEvent.from_dict(read_json_object(path, "event"))


def cmd_health(args: argparse.Namespace) -> int:
    del args
    config = FrankieConfig.from_env()
    origin = verify_original_spawn()
    manifest = load_paper_manifest(config.paper_manifest, allow_missing=True)
    registry = load_candidate_registry(config.novel_registry)
    print_json(
        {
            "agent": "Frankie",
            "execution_enabled": EXECUTION_ENABLED,
            "origin": origin,
            "paper_manifest": {
                "path": str(config.paper_manifest),
                "status": manifest.status,
                "papers": len(manifest.papers),
                "hybrid_ready": manifest.status == "READY" and bool(manifest.papers),
                "source_session": manifest.source_session,
            },
            "candidate_registry": {"path": str(config.novel_registry), "candidates": len(registry)},
            "backends": {
                "primary": config.primary_backend,
                "critic": config.critic_backend,
                "bedrock_region": config.bedrock_region,
                "bedrock_model_configured": bool(config.bedrock_model),
                "openai_model": config.openai_model,
            },
            "aws": {
                "queue_configured": bool(config.sqs_queue_url),
                "evidence_bucket_configured": bool(config.s3_bucket),
                "sqs_region": config.sqs_region,
            },
            "self_improvement": {
                "immutable_outcome_sidecars": True,
                "proposal_generation": True,
                "independent_critic": True,
                "automatic_apply": False,
                "production_promotion": "human-reviewed Git PR only",
            },
            "metacognition": {
                "coordinator_version": META_COORDINATOR_VERSION,
                "activation": "POST_EVIDENCE_ONLY",
                "frankie_self_audit": True,
                "cross_specialist_reconciliation": True,
                "first_lock_rewrite_allowed": False,
                "case_or_chain_drop_allowed": False,
                "majority_vote_truth_allowed": False,
                "automatic_apply": False,
                "automatic_brain_promotion": False,
                "revision_scope": "NEXT_RUN_ONLY",
            },
            "cognition": {
                "contract_version": COGNITIVE_CONTRACT_VERSION,
                "typed_evidence_refs": True,
                "explicit_memory_classes": True,
                "reasoning_trace_authority": "NONE",
                "memory_write_authority": "NONE in evaluation lanes",
            },
            "s115": {
                "status_command": "python research/kalshi/frankie_s115_status.py",
                "forecaster_harness": "research/kalshi/frankie_forecaster_s115.py",
                "retrieval_band": "DEFERRED until A-5 library index, per S115",
            },
        }
    )
    return 0


def cmd_verify_origin(args: argparse.Namespace) -> int:
    del args
    print_json(verify_original_spawn())
    return 0


def cmd_observe(args: argparse.Namespace) -> int:
    config = dataclasses.replace(FrankieConfig.from_env(), allow_missing_papers=True)
    decision, evidence = evaluate_event(
        read_event(args.event),
        config=config,
        deterministic_only=True,
    )
    print_json({"decision": decision.as_dict(), "evidence": evidence})
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    config = FrankieConfig.from_env()
    if args.primary:
        config = dataclasses.replace(config, primary_backend=args.primary)
    if args.critic:
        config = dataclasses.replace(config, critic_backend=args.critic)
    decision, evidence = evaluate_event(read_event(args.event), config=config, deterministic_only=False)
    print_json({"decision": decision.as_dict(), "evidence": evidence})
    return 0


def cmd_legacy(args: argparse.Namespace) -> int:
    verify_original_spawn()
    if not args.spawn_args:
        raise GateStop("legacy requires spawn.py arguments, e.g. legacy emit BLD-1 g23 --day 20260715")
    completed = subprocess.run(
        [sys.executable, str(SPAWN_PATH), *args.spawn_args],
        cwd=str(HERE),
        check=False,
    )
    return int(completed.returncode)


def cmd_consume_once(args: argparse.Namespace) -> int:
    only = True if args.deterministic_only else None
    print_json(consume_once(config=FrankieConfig.from_env(), deterministic_only=only))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    only = True if args.deterministic_only else None
    return serve(config=FrankieConfig.from_env(), deterministic_only=only)


def cmd_record_outcome(args: argparse.Namespace) -> int:
    result = record_outcome(
        evidence_path=Path(args.evidence),
        outcome=read_json_object(args.outcome, "outcome"),
        config=FrankieConfig.from_env(),
    )
    print_json(result)
    return 0


def cmd_improve(args: argparse.Namespace) -> int:
    config = FrankieConfig.from_env()
    proposer = backend_from_name(args.proposer or config.primary_backend, config)
    critic = backend_from_name(args.critic or config.critic_backend, config)
    result = propose_improvement(
        evidence_paths=[Path(path) for path in args.evidence],
        proposer=proposer,
        critic=critic,
        config=config,
    )
    print_json(result)
    return 0


def cmd_meta_contract(args: argparse.Namespace) -> int:
    contract = build_frankie_meta_contract(
        subject=args.subject,
        hypothesis=read_json_object(args.hypothesis, "hypothesis"),
        first_lock=read_json_object(args.first_lock, "first-lock"),
        evidence=read_json_object(args.evidence, "evidence"),
        result=read_json_object(args.result, "result"),
        path_trace=read_json_object(args.path_trace, "path-trace"),
    )
    print_json(contract)
    return 0


def cmd_meta_audit(args: argparse.Namespace) -> int:
    result = validate_frankie_meta_audit(
        read_json_object(args.contract, "meta-contract"),
        read_json_object(args.audit, "meta-audit"),
    )
    print_json(result)
    return 0


def cmd_meta_reconcile(args: argparse.Namespace) -> int:
    specialist_audits = [read_json_object(path, "specialist-meta-audit") for path in args.specialist_audit]
    result = reconcile_frankie_meta_system(
        frankie_audit=read_json_object(args.frankie_audit, "Frankie-meta-audit"),
        specialist_audits=specialist_audits,
    )
    print_json(result)
    return 0


def sample_event() -> FrankieEvent:
    return FrankieEvent.from_dict(
        {
            "event_id": "selftest-event",
            "candidate_id": "CME_KALSHI_DIGITAL_PARITY",
            "knowable_at": "2026-08-06T14:30:00Z",
            "observed_at": "2026-08-06T14:30:01Z",
            "trigger": "selftest qualified structural comparison",
            "source_provenance": [
                {
                    "source": "selftest",
                    "knowable_at": "2026-08-06T14:30:00Z",
                    "content_hash": "selftest-source-hash",
                }
            ],
            "contract_identity": {"status": "MAPPED"},
            "market_state": {"mode": "test"},
            "causal_state": {"clock_status": "POINT_IN_TIME", "source_fresh": True},
            "cost_state": {"costs_known": True},
            "execution_enabled": False,
        }
    )


def lane_result(balance_mode: str = "DELTA_NEUTRAL", state: str = "SHADOW") -> dict:
    return {
        "verdict": "ADVANCE",
        "recommended_state": state,
        "balance_mode": balance_mode,
        "causal_chain": ["upstream state", "contractual transmission", "downstream observation"],
        "information_clock": "point-in-time selftest clock",
        "exact_contracts": ["selftest instrument A", "selftest instrument B"],
        "missing_evidence": [],
        "falsifiers": ["no repeatable convergence on untouched events"],
        "paper_citations": [],
        "rationale": "synthetic selftest only",
        "reasoning_steps": [
            {
                "step_id": "S1",
                "action": "OBSERVE",
                "claim": "the synthetic contract and causal clock are explicit",
                "evidence_refs": ["event:contract_identity", "event:causal_state"],
                "depends_on": [],
                "status": "SUPPORTED",
            },
            {
                "step_id": "S2",
                "action": "VERIFY",
                "claim": "deterministic qualification permits at most shadow evaluation",
                "evidence_refs": ["derived:qualification"],
                "depends_on": ["S1"],
                "status": "SUPPORTED",
            },
        ],
        "uncertainty": {
            "level": "HIGH",
            "drivers": ["synthetic selftest evidence only"],
            "calibrated_probability": None,
        },
    }


def _after_decision(generated_at_utc: str) -> str:
    parsed = dt.datetime.fromisoformat(generated_at_utc.replace("Z", "+00:00"))
    return (parsed + dt.timedelta(seconds=1)).isoformat().replace("+00:00", "Z")


def cmd_selftest(args: argparse.Namespace) -> int:
    del args
    checks: list[tuple[str, bool]] = []

    def check(name: str, value: bool) -> None:
        checks.append((name, bool(value)))
        print(f"  {'PASS' if value else 'FAIL':<4} | {name}")

    origin = verify_original_spawn()
    check("original spawn.py Git blob is unchanged", origin["verified"])
    base = FrankieConfig.from_env()
    registry = load_candidate_registry(base.novel_registry)
    check("Novel candidate registry is readable", "CME_KALSHI_DIGITAL_PARITY" in registry)
    manifest = load_paper_manifest(base.paper_manifest, allow_missing=True)
    check("reviewed paper manifest is READY", manifest.status == "READY" and bool(manifest.papers))
    event = sample_event()
    qualification = qualify_event(event, registry[event.candidate_id])
    check("qualified synthetic event clears deterministic gates", qualification.eligible)

    with tempfile.TemporaryDirectory() as tmp:
        config = dataclasses.replace(
            base,
            allow_missing_papers=True,
            evidence_root=Path(tmp) / "evidence",
            s3_bucket=None,
        )
        primary = ScriptedBackend("scripted-primary", lane_result())
        critic = ScriptedBackend("scripted-critic", lane_result())
        decision, evidence = evaluate_event(
            event,
            config=config,
            primary_backend=primary,
            critic_backend=critic,
            deterministic_only=False,
        )
        evidence_path = Path(evidence["local_path"])
        check("READY manifest permits agreed SHADOW", decision.state == "SHADOW")
        check(
            "typed cognitive contract is recorded",
            decision.provenance.get("cognitive_contract_version") == COGNITIVE_CONTRACT_VERSION,
        )
        check("Frankie can never enable execution", decision.execution_enabled is False)
        check("evidence is written after adjudication", evidence_path.is_file())

        outcome = record_outcome(
            evidence_path=evidence_path,
            outcome={
                "resolved_at": _after_decision(decision.generated_at_utc),
                "result": "NO_EDGE_AFTER_COSTS",
                "metrics": {"net_edge": 0.0},
                "source_provenance": [
                    {
                        "source": "selftest-outcome",
                        "knowable_at": _after_decision(decision.generated_at_utc),
                        "content_hash": "selftest-outcome-hash",
                    }
                ],
                "execution_enabled": False,
            },
            config=config,
        )
        check("resolved outcomes are immutable sidecars", Path(outcome["outcome_path"]).is_file())
        evidence_hash = json.loads(evidence_path.read_text(encoding="utf-8"))["envelope_hash"]

        proposal = ScriptedBackend(
            "scripted-proposer",
            {
                "target_component": "test_harness",
                "hypothesis": "a missing null test allowed a false positive",
                "change_summary": "add one session-preserving null regression",
                "evidence_refs": [evidence_hash],
                "requested_files": ["research/kalshi/tests/test_harness_candidate.py"],
                "expected_benefit": "reject false positives before shadow",
                "falsifiers": ["new test does not separate the failed case"],
                "test_plan": ["replay", "session-preserving null", "untouched shadow"],
                "untouched_forward_gate": "five independent forward events",
                "rollback_plan": "revert the reviewed proposal commit",
                "execution_enabled": False,
                "apply_allowed": False,
            },
        )
        review = ScriptedBackend(
            "scripted-reviewer",
            {
                "verdict": "SANDBOX_ELIGIBLE",
                "reasons": ["bounded and falsifiable"],
                "required_tests": ["run the new regression"],
                "leakage_risks": [],
                "execution_risks": [],
            },
        )
        improvement = propose_improvement(
            evidence_paths=[evidence_path],
            proposer=proposal,
            critic=review,
            config=config,
        )
        check("self-improvement produces a sandbox proposal", improvement["state"] == "SANDBOX_ELIGIBLE")
        check("self-improvement cannot apply itself", improvement["apply_allowed"] is False)

        forbidden = ScriptedBackend(
            "scripted-forbidden",
            {**proposal.result, "requested_files": ["research/kalshi/spawn.py"]},
        )
        stopped = False
        try:
            propose_improvement(
                evidence_paths=[evidence_path],
                proposer=forbidden,
                critic=review,
                config=config,
            )
        except GateStop:
            stopped = True
        check("self-improvement cannot touch spawn.py", stopped)

    meta_contract = build_frankie_meta_contract(
        subject="selftest-metacognition",
        hypothesis={"claim": "candidate mechanism"},
        first_lock={"status": "FROZEN", "decision_hash": "selftest"},
        evidence={"observed": "mixed"},
        result={"outcome": "inconclusive"},
        path_trace={"steps": ["hypothesis", "first_lock", "reveal"]},
    )
    meta_audit = validate_frankie_meta_audit(
        meta_contract,
        {
            "produced_vs_found": "mixed",
            "path_soundness": "bounded",
            "contradictions": ["counterexample"],
            "measurement_vs_market": "measurement may explain part of the difference",
            "alternative_mechanisms": ["liquidity refill"],
            "missing_evidence": ["predecessor lifecycle"],
            "assumptions": ["coverage representative"],
            "claim_stances": {"candidate mechanism": "UNRESOLVED"},
            "case_disposition": "UNRESOLVED",
            "confidence_delta": -0.1,
            "next_discriminating_test": "replay with explicit lifecycle",
            "revision_proposal": {"scope": "NEXT_RUN_ONLY", "actions": ["add_control"]},
        },
    )
    meta_system = reconcile_frankie_meta_system(
        frankie_audit=meta_audit,
        specialist_audits=[],
    )
    check("Frankie coordinator meta-loop is post-evidence only", meta_contract["activation"] == "POST_EVIDENCE_ONLY")
    check("Frankie meta-loop preserves first lock and every case/chain", not meta_audit["first_lock_rewritten"] and not meta_audit["case_or_chain_dropped"])
    check("Frankie meta-loop cannot auto-apply or promote", meta_system["scientific_boundaries"]["automatic_apply_allowed"] is False and meta_system["scientific_boundaries"]["automatic_brain_promotion_allowed"] is False)

    print(f"\n  {sum(ok for _, ok in checks)}/{len(checks)} passed")
    return 0 if all(ok for _, ok in checks) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("health")
    sub.add_parser("verify-origin")
    p = sub.add_parser("observe", help="deterministic WATCH/REJECT observation; no LLM")
    p.add_argument("event")
    p = sub.add_parser("evaluate", help="run independent causal and trading-mechanics lanes")
    p.add_argument("event")
    p.add_argument("--primary", choices=("bedrock", "openai"))
    p.add_argument("--critic", choices=("bedrock", "openai"))
    p = sub.add_parser("legacy", help="delegate to untouched spawn.py after origin verification")
    p.add_argument("spawn_args", nargs=argparse.REMAINDER)
    p = sub.add_parser("consume-once")
    p.add_argument("--deterministic-only", action="store_true")
    p = sub.add_parser("serve")
    p.add_argument("--deterministic-only", action="store_true")
    p = sub.add_parser("record-outcome", help="append an immutable resolved-outcome sidecar")
    p.add_argument("evidence")
    p.add_argument("outcome")
    p = sub.add_parser("improve", help="propose and independently critique one bounded improvement")
    p.add_argument("evidence", nargs="+")
    p.add_argument("--proposer", choices=("bedrock", "openai"))
    p.add_argument("--critic", choices=("bedrock", "openai"))
    p = sub.add_parser("meta-contract", help="bind Frankie's immutable post-evidence metacognitive contract")
    p.add_argument("subject")
    p.add_argument("hypothesis")
    p.add_argument("first_lock")
    p.add_argument("evidence")
    p.add_argument("result")
    p.add_argument("path_trace")
    p = sub.add_parser("meta-audit", help="validate Frankie's next-run-only self-audit")
    p.add_argument("contract")
    p.add_argument("audit")
    p = sub.add_parser("meta-reconcile", help="reconcile Frankie's audit with validated specialist audits")
    p.add_argument("frankie_audit")
    p.add_argument("specialist_audit", nargs="*")
    sub.add_parser("selftest")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    commands = {
        "health": cmd_health,
        "verify-origin": cmd_verify_origin,
        "observe": cmd_observe,
        "evaluate": cmd_evaluate,
        "legacy": cmd_legacy,
        "consume-once": cmd_consume_once,
        "serve": cmd_serve,
        "record-outcome": cmd_record_outcome,
        "improve": cmd_improve,
        "meta-contract": cmd_meta_contract,
        "meta-audit": cmd_meta_audit,
        "meta-reconcile": cmd_meta_reconcile,
        "selftest": cmd_selftest,
    }
    try:
        return commands[args.command](args)
    except (GateStop, MetaLoopError) as exc:
        print(f"STOP - {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR - {type(exc).__name__}: {str(exc)[:2000]}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
