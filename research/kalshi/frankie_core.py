"""Deterministic core for Frankie, the hybrid market-research agent.

This module owns the parts an LLM may never waive: point-in-time event validation,
contract/clock eligibility, source provenance, candidate authority, lane schema validation,
adjudication, evidence hashing, and the immutable origin pin to ``spawn.py``.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from frankie_cognition import (
    COGNITIVE_CONTRACT_VERSION,
    CognitiveContractError,
    ReasoningStep,
    UncertaintyRecord,
    validate_reasoning_contract,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SPAWN_PATH = HERE / "spawn.py"
DEFAULT_PAPER_MANIFEST = HERE / "frankie_paper_manifest.json"
DEFAULT_NOVEL_REGISTRY = ROOT / "dashboard" / "novel_candidates.json"
DEFAULT_EVIDENCE_ROOT = ROOT / "data" / "frankie" / "evidence"

# Git blob identity of the original research/kalshi/spawn.py used as Frankie's
# protected origin. Git object identity is SHA-1 by design; decision/evidence hashes use SHA-256.
EXPECTED_SPAWN_GIT_BLOB = "2eb3ab8570be66bd9568bcd3ca2e6b9f19d6b33e"

SCHEMA_VERSION = "1.1"
AGENT_VERSION = "frankie-s137.0"
EXECUTION_ENABLED = False
MAX_JSON_BYTES = 2_000_000

ALLOWED_STATES = {"WATCH_ONLY", "SHADOW", "REJECT", "HUMAN_REVIEW"}
ALLOWED_BALANCE_MODES = {
    "PAYOFF_NEUTRAL",
    "DELTA_NEUTRAL",
    "INVENTORY_SKEWED",
    "DIRECTIONAL",
    "WATCH_ONLY",
}
ALLOWED_LANE_VERDICTS = {"ADVANCE", "HOLD", "REJECT", "INSUFFICIENT"}


class FrankieError(RuntimeError):
    """Base error. Messages may be persisted, so never include secret values."""


class GateStop(FrankieError):
    """A deterministic prerequisite failed; reasoning must not continue."""


class BackendError(FrankieError):
    """A reasoning backend failed or returned invalid structured output."""


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def git_blob_sha(path: Path) -> str:
    raw = path.read_bytes()
    # Git stores this protected Python source with LF endings.  On Windows the
    # working-tree checkout may use CRLF, which must not look like an origin
    # mutation when the normalized Git blob is unchanged.
    raw = raw.replace(b"\r\n", b"\n")
    payload = b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
    return hashlib.sha1(payload).hexdigest()  # noqa: S324 - Git object identity.


def verify_original_spawn() -> dict[str, Any]:
    if not SPAWN_PATH.is_file():
        raise GateStop(f"canonical spawn missing: {SPAWN_PATH}")
    observed = git_blob_sha(SPAWN_PATH)
    if observed != EXPECTED_SPAWN_GIT_BLOB:
        raise GateStop(
            "canonical spawn.py changed: expected Git blob "
            f"{EXPECTED_SPAWN_GIT_BLOB}, observed {observed}. Frankie refuses to run until "
            "the origin change is reviewed and this pin is intentionally updated."
        )
    return {
        "path": str(SPAWN_PATH.relative_to(ROOT)),
        "expected_git_blob": EXPECTED_SPAWN_GIT_BLOB,
        "observed_git_blob": observed,
        "verified": True,
    }


def load_json(path: Path, *, max_bytes: int = MAX_JSON_BYTES) -> Any:
    if not path.is_file():
        raise GateStop(f"required JSON file missing: {path}")
    size = path.stat().st_size
    if size > max_bytes:
        raise GateStop(f"JSON file too large ({size} > {max_bytes} bytes): {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GateStop(f"invalid JSON in {path}: {exc}") from exc


def parse_iso(value: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise GateStop(f"invalid ISO timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise GateStop(f"timestamp must include a timezone: {value!r}")
    return parsed.astimezone(dt.timezone.utc)


def safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value)).strip("-.")
    return cleaned[:120] or "unnamed"


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


@dataclass(frozen=True)
class FrankieConfig:
    paper_manifest: Path = DEFAULT_PAPER_MANIFEST
    novel_registry: Path = DEFAULT_NOVEL_REGISTRY
    evidence_root: Path = DEFAULT_EVIDENCE_ROOT
    allow_missing_papers: bool = False
    primary_backend: str = "bedrock"
    critic_backend: str = "openai"
    bedrock_region: str = "us-east-1"
    bedrock_model: str | None = None
    openai_model: str = "gpt-5"
    sqs_queue_url: str | None = None
    sqs_region: str = "us-east-2"
    s3_bucket: str | None = None
    s3_prefix: str = "frankie/evidence"
    deterministic_only: bool = False

    @classmethod
    def from_env(cls) -> "FrankieConfig":
        def flag(name: str, default: bool = False) -> bool:
            value = os.environ.get(name)
            if value is None:
                return default
            return value.strip().lower() in {"1", "true", "yes", "on"}

        return cls(
            paper_manifest=Path(os.environ.get("FRANKIE_PAPER_MANIFEST", DEFAULT_PAPER_MANIFEST)),
            novel_registry=Path(os.environ.get("FRANKIE_NOVEL_REGISTRY", DEFAULT_NOVEL_REGISTRY)),
            evidence_root=Path(os.environ.get("FRANKIE_EVIDENCE_ROOT", DEFAULT_EVIDENCE_ROOT)),
            allow_missing_papers=flag("FRANKIE_ALLOW_MISSING_PAPERS", False),
            primary_backend=os.environ.get("FRANKIE_PRIMARY_BACKEND", "bedrock"),
            critic_backend=os.environ.get("FRANKIE_CRITIC_BACKEND", "openai"),
            bedrock_region=os.environ.get("FRANKIE_BEDROCK_REGION", "us-east-1"),
            bedrock_model=os.environ.get("FRANKIE_BEDROCK_MODEL"),
            openai_model=os.environ.get("FRANKIE_OPENAI_MODEL", "gpt-5"),
            sqs_queue_url=os.environ.get("FRANKIE_QUEUE_URL"),
            sqs_region=os.environ.get("FRANKIE_SQS_REGION", "us-east-2"),
            s3_bucket=os.environ.get("FRANKIE_EVIDENCE_BUCKET"),
            s3_prefix=os.environ.get("FRANKIE_EVIDENCE_PREFIX", "frankie/evidence").strip("/"),
            deterministic_only=flag("FRANKIE_DETERMINISTIC_ONLY", False),
        )


@dataclass(frozen=True)
class Paper:
    id: str
    title: str
    url: str
    claims: tuple[str, ...]
    why_it_matters: str
    source_hash: str | None = None


@dataclass(frozen=True)
class PaperManifest:
    status: str
    source_session: str | None
    papers: tuple[Paper, ...]
    repo_grounding: tuple[str, ...]
    manifest_hash: str


def load_paper_manifest(path: Path, *, allow_missing: bool) -> PaperManifest:
    raw = load_json(path)
    if not isinstance(raw, dict):
        raise GateStop("Frankie paper manifest must be a JSON object")
    status = str(raw.get("status") or "UNKNOWN")
    papers_raw = raw.get("papers") or []
    if not isinstance(papers_raw, list):
        raise GateStop("paper manifest papers must be a list")
    papers: list[Paper] = []
    seen: set[str] = set()
    for index, item in enumerate(papers_raw):
        if not isinstance(item, dict):
            raise GateStop(f"paper manifest item {index} is not an object")
        missing = [key for key in ("id", "title", "url", "claims", "why_it_matters") if not item.get(key)]
        if missing:
            raise GateStop(f"paper manifest item {index} missing: {', '.join(missing)}")
        paper_id = safe_id(str(item["id"]))
        if paper_id in seen:
            raise GateStop(f"duplicate paper id: {paper_id}")
        seen.add(paper_id)
        claims = item["claims"]
        if not isinstance(claims, list) or not all(isinstance(v, str) and v.strip() for v in claims):
            raise GateStop(f"paper {paper_id} claims must be a non-empty string list")
        papers.append(
            Paper(
                id=paper_id,
                title=str(item["title"]),
                url=str(item["url"]),
                claims=tuple(str(v) for v in claims),
                why_it_matters=str(item["why_it_matters"]),
                source_hash=str(item["source_hash"]) if item.get("source_hash") else None,
            )
        )
    if (status != "READY" or not papers) and not allow_missing:
        raise GateStop(
            f"PAPER_MANIFEST_INCOMPLETE: status={status!r}, papers={len(papers)}. "
            "A private chat link is not a durable research source."
        )
    grounding = raw.get("repo_grounding") or []
    if not isinstance(grounding, list):
        raise GateStop("repo_grounding must be a list")
    return PaperManifest(
        status=status,
        source_session=str(raw.get("source_session")) if raw.get("source_session") else None,
        papers=tuple(papers),
        repo_grounding=tuple(str(v) for v in grounding),
        manifest_hash=sha256_json(raw),
    )


@dataclass(frozen=True)
class CandidateDefinition:
    id: str
    title: str
    family: str
    authority: str
    balance_mode: str
    verdict: str
    use_when: str
    kill_test: str


def load_candidate_registry(path: Path) -> dict[str, CandidateDefinition]:
    raw = load_json(path)
    candidates_raw = raw.get("candidates") if isinstance(raw, dict) else None
    if not isinstance(candidates_raw, list):
        raise GateStop("Novel candidate registry missing candidates list")
    out: dict[str, CandidateDefinition] = {}
    for item in candidates_raw:
        if not isinstance(item, dict) or not item.get("id"):
            raise GateStop("invalid Novel candidate registry item")
        candidate = CandidateDefinition(
            id=str(item["id"]),
            title=str(item.get("title") or item["id"]),
            family=str(item.get("family") or "unknown"),
            authority=str(item.get("authority") or "WATCH_ONLY"),
            balance_mode=str(item.get("balance_mode") or "WATCH_ONLY"),
            verdict=str(item.get("verdict") or "PREREGISTERED"),
            use_when=str(item.get("use_when") or ""),
            kill_test=str(item.get("kill_test") or ""),
        )
        if candidate.authority not in {"WATCH_ONLY", "SHADOW"}:
            raise GateStop(f"candidate {candidate.id} has forbidden authority: {candidate.authority}")
        if candidate.balance_mode not in ALLOWED_BALANCE_MODES:
            raise GateStop(f"candidate {candidate.id} has invalid balance mode")
        out[candidate.id] = candidate
    return out


@dataclass(frozen=True)
class FrankieEvent:
    event_id: str
    candidate_id: str
    knowable_at: str
    observed_at: str
    trigger: str
    source_provenance: tuple[dict[str, Any], ...]
    contract_identity: dict[str, Any]
    market_state: dict[str, Any]
    causal_state: dict[str, Any]
    cost_state: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "FrankieEvent":
        required = (
            "event_id", "candidate_id", "knowable_at", "observed_at", "trigger",
            "source_provenance", "contract_identity", "market_state", "causal_state", "cost_state",
        )
        missing = [key for key in required if key not in raw]
        if missing:
            raise GateStop(f"event missing required fields: {', '.join(missing)}")
        if raw.get("execution_enabled") is True:
            raise GateStop("event attempted to enable execution; Frankie is non-executable")
        provenance = raw["source_provenance"]
        if not isinstance(provenance, list) or not provenance:
            raise GateStop("source_provenance must be a non-empty list")
        source_clocks: list[tuple[int, dt.datetime]] = []
        for index, source in enumerate(provenance):
            if not isinstance(source, dict):
                raise GateStop(f"source_provenance[{index}] must be an object")
            for key in ("source", "knowable_at", "content_hash"):
                if not source.get(key):
                    raise GateStop(f"source_provenance[{index}] missing {key}")
            source_clocks.append((index, parse_iso(str(source["knowable_at"]))))
        knowable = parse_iso(str(raw["knowable_at"]))
        observed = parse_iso(str(raw["observed_at"]))
        if observed < knowable:
            raise GateStop("observed_at precedes knowable_at")
        future_sources = [index for index, clock in source_clocks if clock > observed]
        if future_sources:
            raise GateStop(
                "source provenance is not knowable by observed_at: "
                + ", ".join(str(index) for index in future_sources)
            )
        for name in ("contract_identity", "market_state", "causal_state", "cost_state"):
            if not isinstance(raw[name], dict):
                raise GateStop(f"{name} must be an object")
        return cls(
            event_id=safe_id(str(raw["event_id"])),
            candidate_id=str(raw["candidate_id"]),
            knowable_at=knowable.isoformat().replace("+00:00", "Z"),
            observed_at=observed.isoformat().replace("+00:00", "Z"),
            trigger=str(raw["trigger"]),
            source_provenance=tuple(dict(v) for v in provenance),
            contract_identity=dict(raw["contract_identity"]),
            market_state=dict(raw["market_state"]),
            causal_state=dict(raw["causal_state"]),
            cost_state=dict(raw["cost_state"]),
            metadata=dict(raw.get("metadata") or {}),
        )

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class Qualification:
    eligible: bool
    state: str
    reasons: tuple[str, ...]
    blockers: tuple[str, ...]
    event_hash: str


def qualify_event(event: FrankieEvent, candidate: CandidateDefinition) -> Qualification:
    reasons: list[str] = []
    blockers: list[str] = []
    identity = str(event.contract_identity.get("status") or "UNKNOWN").upper()
    if identity in {"EXACT", "MAPPED", "NOT_APPLICABLE"}:
        reasons.append(f"contract_identity={identity}")
    else:
        blockers.append(f"contract_identity={identity}")
    clock = str(event.causal_state.get("clock_status") or "UNKNOWN").upper()
    if clock in {"EXACT", "POINT_IN_TIME", "NOT_APPLICABLE"}:
        reasons.append(f"causal_clock={clock}")
    else:
        blockers.append(f"causal_clock={clock}")
    fresh = event.causal_state.get("source_fresh")
    if fresh is True:
        reasons.append("sources_fresh=true")
    else:
        blockers.append("sources_fresh=false_or_unknown")
    if candidate.balance_mode == "PAYOFF_NEUTRAL" and identity != "EXACT":
        blockers.append("PAYOFF_NEUTRAL requires exact payoff identity")
    if event.cost_state.get("costs_known") is True:
        reasons.append("costs_known=true")
    else:
        reasons.append("costs_known=false_or_unknown")
    if not event.trigger.strip():
        blockers.append("empty trigger")
    return Qualification(
        eligible=not blockers,
        state="QUALIFIED" if not blockers else "STOPPED",
        reasons=tuple(reasons),
        blockers=tuple(blockers),
        event_hash=sha256_json(event.as_dict()),
    )


@dataclass(frozen=True)
class LaneResult:
    lane: str
    backend: str
    verdict: str
    recommended_state: str
    balance_mode: str
    causal_chain: tuple[str, ...]
    information_clock: str
    exact_contracts: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    falsifiers: tuple[str, ...]
    paper_citations: tuple[str, ...]
    rationale: str
    reasoning_steps: tuple[ReasoningStep, ...]
    uncertainty: UncertaintyRecord
    trace_hash: str
    raw_hash: str

    @classmethod
    def from_dict(
        cls,
        raw: Mapping[str, Any],
        *,
        lane: str,
        backend: str,
        paper_ids: set[str],
        allowed_evidence_refs: set[str],
    ) -> "LaneResult":
        required = (
            "verdict", "recommended_state", "balance_mode", "causal_chain", "information_clock",
            "exact_contracts", "missing_evidence", "falsifiers", "paper_citations", "rationale",
            "reasoning_steps", "uncertainty",
        )
        missing = [key for key in required if key not in raw]
        if missing:
            raise BackendError(f"{lane}/{backend} result missing: {', '.join(missing)}")
        verdict = str(raw["verdict"]).upper()
        state = str(raw["recommended_state"]).upper()
        balance = str(raw["balance_mode"]).upper()
        if verdict not in ALLOWED_LANE_VERDICTS:
            raise BackendError(f"{lane}/{backend} invalid verdict: {verdict}")
        if state not in ALLOWED_STATES:
            raise BackendError(f"{lane}/{backend} invalid state: {state}")
        if balance not in ALLOWED_BALANCE_MODES:
            raise BackendError(f"{lane}/{backend} invalid balance mode: {balance}")

        def strings(name: str) -> tuple[str, ...]:
            value = raw[name]
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise BackendError(f"{lane}/{backend} {name} must be a string list")
            return tuple(v.strip() for v in value if v.strip())

        citations = strings("paper_citations")
        unknown = sorted(set(citations) - paper_ids)
        if unknown:
            raise BackendError(f"{lane}/{backend} cited unknown paper ids: {', '.join(unknown)}")
        try:
            reasoning_steps, uncertainty, trace_hash = validate_reasoning_contract(
                raw,
                allowed_evidence_refs=allowed_evidence_refs,
            )
        except CognitiveContractError as exc:
            raise BackendError(f"{lane}/{backend} cognitive contract failed: {exc}") from exc
        normalized = {
            "verdict": verdict,
            "recommended_state": state,
            "balance_mode": balance,
            "causal_chain": strings("causal_chain"),
            "information_clock": str(raw["information_clock"]),
            "exact_contracts": strings("exact_contracts"),
            "missing_evidence": strings("missing_evidence"),
            "falsifiers": strings("falsifiers"),
            "paper_citations": citations,
            "rationale": str(raw["rationale"]),
        }
        hash_payload = {
            **normalized,
            "reasoning_steps": [dataclasses.asdict(step) for step in reasoning_steps],
            "uncertainty": dataclasses.asdict(uncertainty),
            "trace_hash": trace_hash,
        }
        return cls(
            lane=lane,
            backend=backend,
            reasoning_steps=reasoning_steps,
            uncertainty=uncertainty,
            trace_hash=trace_hash,
            raw_hash=sha256_json(hash_payload),
            **normalized,
        )


@dataclass(frozen=True)
class FrankieDecision:
    schema_version: str
    agent_version: str
    decision_id: str
    event_id: str
    candidate_id: str
    generated_at_utc: str
    state: str
    authority: str
    execution_enabled: bool
    balance_mode: str
    qualification: dict[str, Any]
    primary_lane: dict[str, Any] | None
    critic_lane: dict[str, Any] | None
    promotion_blockers: tuple[str, ...]
    adjudication_reasons: tuple[str, ...]
    provenance: dict[str, Any]
    decision_hash: str

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def adjudicate(
    *,
    event: FrankieEvent,
    candidate: CandidateDefinition,
    qualification: Qualification,
    primary: LaneResult | None,
    critic: LaneResult | None,
    manifest: PaperManifest,
    spawn_provenance: dict[str, Any],
    cognitive_context: Mapping[str, Any],
) -> FrankieDecision:
    reasons: list[str] = []
    blockers: list[str] = []
    if not qualification.eligible:
        state = "REJECT"
        reasons.append("deterministic qualification failed")
        blockers.extend(qualification.blockers)
    elif primary is None or critic is None:
        state = "WATCH_ONLY"
        reasons.append("deterministic-only observation; hybrid lanes not run")
        blockers.append("hybrid lane results absent")
    elif primary.verdict == "REJECT" or critic.verdict == "REJECT":
        state = "REJECT"
        reasons.append("at least one independent lane rejected the mechanism")
    elif primary.verdict == "INSUFFICIENT" or critic.verdict == "INSUFFICIENT":
        state = "HUMAN_REVIEW"
        reasons.append("at least one lane found evidence insufficient")
    elif primary.balance_mode != critic.balance_mode:
        state = "HUMAN_REVIEW"
        reasons.append("lanes disagree on balance mode; no voting or averaging")
    elif primary.recommended_state != critic.recommended_state:
        state = "HUMAN_REVIEW"
        reasons.append("lanes disagree on state; no voting or averaging")
    elif primary.recommended_state == "SHADOW":
        state = "SHADOW"
        reasons.append("both independent lanes agree on SHADOW")
    else:
        state = primary.recommended_state
        reasons.append("independent lanes agree")
    balance_mode = (
        primary.balance_mode
        if primary and critic and primary.balance_mode == critic.balance_mode
        else candidate.balance_mode
    )
    if event.cost_state.get("costs_known") is not True and state == "SHADOW":
        state = "WATCH_ONLY"
        blockers.append("costs unknown")
        reasons.append("economic gate capped SHADOW to WATCH_ONLY")
    if manifest.status != "READY" or not manifest.papers:
        blockers.append("paper manifest incomplete")
        if state == "SHADOW":
            state = "WATCH_ONLY"
            reasons.append("paper-grounding gate capped SHADOW to WATCH_ONLY")
    blockers.extend(
        [
            "Frankie has no order router",
            "Frankie has no venue execution credentials",
            "live authority requires independent risk-service promotion",
        ]
    )
    if state not in ALLOWED_STATES:
        raise GateStop(f"adjudicator produced invalid state: {state}")
    core = {
        "schema_version": SCHEMA_VERSION,
        "agent_version": AGENT_VERSION,
        "decision_id": str(uuid.uuid4()),
        "event_id": event.event_id,
        "candidate_id": candidate.id,
        "generated_at_utc": utc_now().isoformat(timespec="seconds").replace("+00:00", "Z"),
        "state": state,
        "authority": state,
        "execution_enabled": EXECUTION_ENABLED,
        "balance_mode": balance_mode,
        "qualification": dataclasses.asdict(qualification),
        "primary_lane": dataclasses.asdict(primary) if primary else None,
        "critic_lane": dataclasses.asdict(critic) if critic else None,
        "promotion_blockers": tuple(dict.fromkeys(blockers)),
        "adjudication_reasons": tuple(reasons),
        "provenance": {
            "event_hash": qualification.event_hash,
            "paper_manifest_hash": manifest.manifest_hash,
            "spawn_origin": spawn_provenance,
            "cognitive_contract_version": COGNITIVE_CONTRACT_VERSION,
            "evidence_catalog_hash": str(cognitive_context.get("evidence_catalog_hash") or ""),
            "primary_trace_hash": primary.trace_hash if primary else None,
            "critic_trace_hash": critic.trace_hash if critic else None,
            "candidate_registry": str(DEFAULT_NOVEL_REGISTRY.relative_to(ROOT)),
            "agent_source": "research/kalshi/agent_frankie.py",
        },
    }
    return FrankieDecision(**core, decision_hash=sha256_json(core))


def write_evidence(
    decision: FrankieDecision,
    *,
    event: FrankieEvent,
    config: FrankieConfig,
) -> dict[str, Any]:
    day = decision.generated_at_utc[:10].replace("-", "")
    filename = f"{safe_id(decision.event_id)}_{decision.decision_hash[:16]}.json"
    path = config.evidence_root / day / filename
    envelope = {"decision": decision.as_dict(), "event": event.as_dict()}
    envelope["envelope_hash"] = sha256_json(envelope)
    atomic_write_json(path, envelope)
    result: dict[str, Any] = {
        "local_path": str(path),
        "envelope_hash": envelope["envelope_hash"],
        "s3_uri": None,
    }
    if config.s3_bucket:
        try:
            import creds

            client = creds.aws_client("s3", config.sqs_region)
            key = f"{config.s3_prefix}/{day}/{filename}"
            client.put_object(
                Bucket=config.s3_bucket,
                Key=key,
                Body=canonical_json(envelope),
                ContentType="application/json",
                Metadata={
                    "decision-hash": decision.decision_hash,
                    "event-hash": decision.qualification["event_hash"],
                    "execution-enabled": "false",
                },
            )
            result["s3_uri"] = f"s3://{config.s3_bucket}/{key}"
        except Exception as exc:
            result["s3_error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
    return result
