"""DRAFT, UNVERIFIED, SALVAGED 2026-09-02 - read the note before trusting anything below.

This file was written by the output-ledgers persona and left UNCOMMITTED in its worktree when
Greg's interrupt stopped it. It has NO tests, was never run, and predates two of Greg's
corrections that reached the persona too late: (1) there is NO floor of ten - the FULL derived
set (registry outputs + one per contract section + 9a + knowledge verification) is required;
(2) no hardcoded windows or horizons - timings are derived on the causal clocks, and the state
movie must carry the book and FIFO state per cutoff. Treat as raw material for the rebuild
(FRANKIE_WIRING_TODO_S120.md item 8), not as a module.
"""
"""The principal's OUTPUT ledgers: the registry's output layers plus one per contract section.

Frankie receives every record of every field for the day as a causal stream in `ts_recv_ns`
order and computes every calculation-contract section himself. What he writes is produced
SEQUENTIALLY as the stream advances and is never rewritten - the feed inventory, section 15
(l.191-204): *"These outputs are part of the experimental data and must remain append-only"*,
and the registry group `append_only_outputs` (registry JSON l.289-306, `proof_mode:
APPEND_ONLY_HASH_CHAIN`, `activation_stage: SEQUENTIAL_AS_PRODUCED`). This module is the
schema and the validator for that output surface. Staging and the report call it; it edits
nothing they own.

THE SET IS "THE REGISTRY'S OUTPUT LAYERS PLUS ONE PER CONTRACT SECTION", never a number. The
registry's ten output ids are a FLOOR read from the committed registry at validation time,
and the per-section ledgers are enumerated by READING the calculation contract's `### 4.x`
headings at validation time. No count in any document is a spec: the sixteen of mission
section 5 was already eighteen headings by the time 4.0 and 4.0b landed, and a validator
built to a count would have passed a run that never wrote them.

Every ledger is APPEND-ONLY: entries stamped with `cutoff_recv_ns` (the F_LAST `ts_recv_ns`
after which the entry was written - contract section 2 l.40-41, *"the first lawful knowledge
time for a completed group is its F_LAST receive time"*), a monotone `sequence`, nondecreasing
cutoffs, and a hash chain `entry_hash = sha256(prev_hash + canonical(entry))` from a genesis
of `sha256(b"")` - the same convention `native_causal_stream` uses for delivery receipts. An
edited entry breaks its own hash; a reordered entry breaks the cutoff monotonicity; a
replaced first lock is a second FIRST_LOCK on the same candidate and is refused (V4 section
10 l.246-248: *"A later cleaner call cannot replace an earlier exact signal"*).

The ledgers and where each comes from:

- `output_state_and_state_delta_movie` - inventory 15 l.193; V4 section 3 l.75-91: per
  channel one of OBSERVED / PAST_CARRY / STALE / MISSING / STRUCTURALLY_NOT_YET_KNOWN /
  NOT_APPLICABLE / TRUE_ZERO, carried values keep source timestamp and age, and the MISSING
  channels are NAMED on every frame.
- `output_frankie_reasoning_movie` - inventory 15 l.194. An entry may record a HELPER
  INVOCATION (persona, question, answer hash) because a helper is a tool invocation inside a
  role with a selectable persona, never a parallel lane (inventory 10 l.128-137; D63; D64) -
  so a helper record carrying a lane or CPU affinity is refused - and knowledge retrievals by
  receipt id into `output_knowledge_retrieval_receipts`.
- `output_probability_movie` - inventory 15 l.195; V4 section 1 l.33-41 names the primary
  heads (persistence vs collapse, runway / remaining-lifespan distribution, P/O/S/X
  distribution, continuation / termination, chain-depth distribution); V4 section 10
  l.234-248 binds each entry to instance and snapshot identity, model/head/view identity,
  probabilities, lawful evaluation timestamp, lock-rule revision and lock state. Immutable.
- `output_candidate_discoveries` - inventory 15 l.196; contract section 2 l.40-46 (PRIOR /
  T0 / H+N, lawful availability); mission section 5 point 5 l.196-197 (the exact member sits
  beneath every summary) - each discovery names its member groups and a falsifier.
- `output_first_locks_and_no_locks` - inventory 15 l.197; V4 section 10 l.246-248. FIRST_LOCK
  is stamped at the cutoff it was written at, references the probability entry it locks, and
  is never moved earlier; NO_LOCK / NO_RELIABLE_LOCK carry a reason.
- `output_negative_sparse_inconclusive_ledger` - inventory 15 l.198; mission section 5 point 2
  l.187-188 (absence is a result); contract section 3 l.59-70 (every average declares its
  population and denominator). Each entry carries numerator and denominator.
- `output_knowledge_retrieval_receipts` - inventory 15 l.199; mission l.53-57 (retained
  knowledge loads only through the hash-bound manifest); layer id, file sha256, cutoff, and
  the INSPECTED / UNINSPECTED disposition `native_frankie_knowledge_registry` already uses.
- `output_provider_invocation_response_receipts` - inventory 15 l.200; mission section 10
  l.438-450 and D70: the principal runs as an AGENT SESSION over committed files, so the
  receipt is session id, model identity as reported by the session, and a per-cutoff turn
  receipt whose request and response hashes differ. An API-shaped entry (`provider`,
  `requested_model`, `served_model`, `principal_invocation_id`, token `usage`) is REFUSED,
  because a gate that demanded those would reject a correct session run.
- `output_answer_wall_access_receipts` - inventory 15 l.201; registry l.305 (*"no-access
  receipts for current A scope"*); mission section 2 (the blind wall). Must be EMPTY with a
  stated reason; any entry is an access and invalidates the run.
- `output_source_state_manifest_code_model_run_hashes` - inventory 15 l.202; mission section
  10 l.429-436; contract section 5 l.357-358 (identity receipt). Written exactly twice, START
  and END; mission, contract, manifest, source, code and model hashes must not change between
  the two - only the state hash may.
- `contract_section_<4.x>` - one per `### 4.x` heading of the calculation contract (mission
  section 5 l.146-152: *"You compute the sixteen calculation-contract sections yourself ...
  at every lawful cutoff"*), each entry carrying the section's exact rows lawful at that
  cutoff (contract section 2 l.40-41), the strata declared with the nine items of contract
  section 3 l.59-70, and a falsifier. An empty row set is allowed with an absence reason
  (mission section 5 point 2).
- `raw_mbo_classification` - mission section 9a l.385-419: per retained raw-MBO field or field
  group, LOAD_BEARING / RETAINED_UNREAD / DEGENERATE_ON_THIS_SLICE / REDUNDANT / CANNOT_JUDGE
  with evidence. Keep-everything is a first-class answer (l.397-399); an entry that removes
  anything is refused (l.401-402, *"YOU ADVISE; YOU NEVER DROP"*).
- `knowledge_verification` - mission l.47 (A-memory receives *"only the verified prior
  lessons/insights/notes package"*) and l.421 (the Forecaster plane holds only validated
  output): per delivered lesson, VERIFIED / UNVERIFIED / REFUTED with evidence, so "verified"
  is a record and not a claim.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (
    REGISTRY_PATH,
    SHA256_RE,
    canonical_bytes,
    load_registry,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_staging import ALLOWED_ARMS, ALLOWED_ROLES

OUTPUT_BUNDLE_SCHEMA = "FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_OUTPUTS_V1"
OUTPUT_RECEIPT_SCHEMA = "FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_OUTPUTS_RECEIPT_V1"
OUTPUT_LEDGER_POLICY = "APPEND_ONLY_OUTPUT"
CAUSAL_CLOCK = "ts_recv_ns"
APPEND_ONLY_OUTPUTS_GROUP = "append_only_outputs"

GENESIS_PREV_HASH = hashlib.sha256(b"").hexdigest()
"""The first entry of every ledger chains from the hash of nothing."""

RAW_MBO_CLASSIFICATION_LEDGER = "raw_mbo_classification"
KNOWLEDGE_VERIFICATION_LEDGER = "knowledge_verification"
SECTION_LEDGER_PREFIX = "contract_section_"

STATE_MOVIE = "output_state_and_state_delta_movie"
REASONING_MOVIE = "output_frankie_reasoning_movie"
PROBABILITY_MOVIE = "output_probability_movie"
CANDIDATE_DISCOVERIES = "output_candidate_discoveries"
FIRST_LOCKS = "output_first_locks_and_no_locks"
NEGATIVE_LEDGER = "output_negative_sparse_inconclusive_ledger"
KNOWLEDGE_RECEIPTS = "output_knowledge_retrieval_receipts"
INVOCATION_RECEIPTS = "output_provider_invocation_response_receipts"
ANSWER_WALL_RECEIPTS = "output_answer_wall_access_receipts"
RUN_HASHES = "output_source_state_manifest_code_model_run_hashes"

#: Ledgers that may be EMPTY when they say why. The answer wall MUST be empty; the negative
#: ledger may be, on a run that produced no abstention, but only with its reason stated.
EMPTY_PERMITTED = frozenset({ANSWER_WALL_RECEIPTS, NEGATIVE_LEDGER})

CONTRACT_SECTION_HEADING_RE = re.compile(r"^### (4\.[0-9]+[a-z]?)\b", re.MULTILINE)

# V4 section 3 l.79-87 - the missingness a channel must distinguish at minimum.
CHANNEL_STATUSES = (
    "OBSERVED",
    "PAST_CARRY",
    "STALE",
    "MISSING",
    "STRUCTURALLY_NOT_YET_KNOWN",
    "NOT_APPLICABLE",
    "TRUE_ZERO",
)
_STATUSES_WITHOUT_VALUE = frozenset({"MISSING", "STRUCTURALLY_NOT_YET_KNOWN", "NOT_APPLICABLE"})
_CARRIED_STATUSES = frozenset({"PAST_CARRY", "STALE"})

# V4 section 1 l.35-39 - the primary heads, in the proposal's order.
PRIMARY_HEADS = (
    "exhaustion_persistence_vs_collapse",
    "runway_remaining_lifespan_distribution",
    "p_o_s_x_structural_state_distribution",
    "continuation_termination_probability",
    "chain_depth_distribution",
)
# V4 section 10 l.244 - first-lock, no-reliable-lock, no-lock, wrong-lock, late and censored.
LOCK_STATES = ("FIRST_LOCK", "NO_RELIABLE_LOCK", "NO_LOCK", "WRONG_LOCK", "LATE", "CENSORED")
LOCK_LEDGER_STATES = ("FIRST_LOCK", "NO_LOCK", "NO_RELIABLE_LOCK")
# Contract section 2 l.42-44.
RECOGNITION_LABELS = ("PRIOR", "T0", "H+N")
# Inventory 15 l.198.
NEGATIVE_KINDS = ("ABSTENTION", "WEAK", "NEGATIVE", "SPARSE", "INCONCLUSIVE")
# Mission section 9a l.408-414.
RAW_MBO_CLASSES = (
    "LOAD_BEARING",
    "RETAINED_UNREAD",
    "DEGENERATE_ON_THIS_SLICE",
    "REDUNDANT",
    "CANNOT_JUDGE",
)
RETAINED_UNREAD_CAUSES = ("WIRING_DEFECT", "GENUINE_SPARE")
KNOWLEDGE_VERDICTS = ("VERIFIED", "UNVERIFIED", "REFUTED")
RETRIEVAL_DISPOSITIONS = ("INSPECTED", "UNINSPECTED")
# Contract section 3 l.66 - resolved, censored, or still-open.
STRATUM_STATUSES = ("RESOLVED", "CENSORED", "OPEN")
#: Contract section 3 l.59-70, the nine things every average must declare, as keys.
STRATUM_REQUIRED_KEYS = (
    "numerator",
    "formula",
    "population",
    "denominator",
    "source_day",
    "source_role",
    "family",
    "subfamily",
    "cluster_version",
    "side",
    "session",
    "phase",
    "continuity_segment",
    "causal_clock",
    "cutoff_recv_ns",
    "status",
    "missingness_rule",
    "inclusion_rule",
)
INVOCATION_MECHANISM = "AGENT_SESSION"
#: Mission section 10 l.445-448: the fields an API gate demanded and a session run cannot
#: supply. Their presence on a receipt means the receipt describes an architecture this
#: mission does not use.
API_SHAPED_KEYS = frozenset(
    {
        "provider",
        "requested_model",
        "served_model",
        "principal_invocation_id",
        "usage",
        "input_tokens",
        "output_tokens",
        "api_key",
        "endpoint",
        "http_status",
    }
)
#: Inventory 10 l.133-137: a helper has no lane, no CPU affinity, no output artifact of its own.
HELPER_LANE_KEYS = frozenset({"lane", "cpu", "cpu_affinity", "parallel", "output_artifact"})
HASH_PHASES = ("START", "END")
#: Mission section 10 l.429-436 and contract section 5 l.357-358: what the identity receipt binds.
RUN_HASH_KEYS = (
    "mission_sha256",
    "calculation_contract_sha256",
    "knowledge_manifest_sha256",
    "source_manifest_sha256",
    "code_sha256",
    "state_sha256",
)
#: Of those, the ones that may not change between START and END. Only the state moves.
RUN_HASH_INVARIANT_KEYS = tuple(k for k in RUN_HASH_KEYS if k != "state_sha256")


class PrincipalOutputError(ValueError):
    """An output ledger could not be written lawfully, or a bundle could not be trusted."""


# --------------------------------------------------------------------------------------
# What is required: the registry's output layers plus one per contract section
# --------------------------------------------------------------------------------------


def registry_output_layer_ids(registry_path: Path = REGISTRY_PATH) -> tuple[str, ...]:
    """The FLOOR, read from the committed registry's `append_only_outputs` group - never typed."""
    registry = load_registry(registry_path)
    for group in registry.get("groups", ()):
        if group.get("group_id") == APPEND_ONLY_OUTPUTS_GROUP:
            ids = tuple(str(e["layer_id"]) for e in group.get("entries", ()))
            if not ids:
                raise PrincipalOutputError("registry group append_only_outputs has no entries")
            if len(set(ids)) != len(ids):
                raise PrincipalOutputError("registry group append_only_outputs repeats a layer id")
            return ids
    raise PrincipalOutputError(
        f"registry at {registry_path} has no {APPEND_ONLY_OUTPUTS_GROUP!r} group"
    )


def contract_section_ids(contract_text: str) -> tuple[str, ...]:
    """Every `### 4.x` heading of the calculation contract, in document order.

    Read at validation time so that adding a section to the contract adds a required ledger
    with no edit here. A contract with no such heading is not a calculation contract.
    """
    ids = tuple(CONTRACT_SECTION_HEADING_RE.findall(contract_text))
    if not ids:
        raise PrincipalOutputError("contract text carries no `### 4.x` section headings")
    if len(set(ids)) != len(ids):
        raise PrincipalOutputError("contract text repeats a `### 4.x` section heading")
    return ids


def section_ledger_id(section: str) -> str:
    return f"{SECTION_LEDGER_PREFIX}{section}"


def required_ledger_ids(
    contract_text: str, registry_path: Path = REGISTRY_PATH
) -> tuple[str, ...]:
    """The registry's output layers plus one per contract section, plus the two the mission
    requires by name (9a's raw-MBO classification and the knowledge-verification record)."""
    return (
        registry_output_layer_ids(registry_path)
        + tuple(section_ledger_id(s) for s in contract_section_ids(contract_text))
        + (RAW_MBO_CLASSIFICATION_LEDGER, KNOWLEDGE_VERIFICATION_LEDGER)
    )


# --------------------------------------------------------------------------------------
# The append-only ledger
# --------------------------------------------------------------------------------------


def entry_hash(prev_hash: str, entry_without_hash: Mapping[str, Any]) -> str:
    """`sha256(prev_hash + canonical(entry))`, the entry canonicalised WITHOUT `entry_hash`."""
    body = {k: v for k, v in entry_without_hash.items() if k != "entry_hash"}
    return hashlib.sha256(prev_hash.encode("ascii") + canonical_bytes(body)).hexdigest()


def _require_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PrincipalOutputError(f"{label} must be an int, got {type(value).__name__}")
    return value


class AppendOnlyLedger:
    """One output ledger. `append` is the only write; nothing edits, reorders or removes."""

    def __init__(self, ledger_id: str, *, empty_reason: str | None = None) -> None:
        if not isinstance(ledger_id, str) or not ledger_id.strip():
            raise PrincipalOutputError("ledger_id must be a non-empty string")
        self.ledger_id = ledger_id
        self.empty_reason = empty_reason
        self._entries: list[dict[str, Any]] = []

    @property
    def entries(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(self._entries)

    @property
    def head_hash(self) -> str:
        return self._entries[-1]["entry_hash"] if self._entries else GENESIS_PREV_HASH

    def append(self, cutoff_recv_ns: int, body: Mapping[str, Any]) -> dict[str, Any]:
        cutoff = _require_int(cutoff_recv_ns, f"{self.ledger_id} cutoff_recv_ns")
        if cutoff < 0:
            raise PrincipalOutputError(f"{self.ledger_id} cutoff_recv_ns must be non-negative")
        if self._entries and cutoff < self._entries[-1]["cutoff_recv_ns"]:
            raise PrincipalOutputError(
                f"{self.ledger_id}: cutoff {cutoff} is earlier than the previous entry's "
                f"{self._entries[-1]['cutoff_recv_ns']}; an output is written after the stream "
                "reaches its cutoff and never before"
            )
        if not isinstance(body, Mapping):
            raise PrincipalOutputError(f"{self.ledger_id} entry body must be a mapping")
        entry: dict[str, Any] = {
            "ledger_id": self.ledger_id,
            "sequence": len(self._entries),
            "cutoff_recv_ns": cutoff,
            "prev_hash": self.head_hash,
            "body": dict(body),
        }
        entry["entry_hash"] = entry_hash(entry["prev_hash"], entry)
        self._entries.append(entry)
        return dict(entry)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ledger_id": self.ledger_id,
            "policy": OUTPUT_LEDGER_POLICY,
            "causal_clock": CAUSAL_CLOCK,
            "genesis_prev_hash": GENESIS_PREV_HASH,
            "empty_reason": self.empty_reason,
            "entries": [dict(e) for e in self._entries],
        }


class OutputBundle:
    """Every ledger a run writes, under one run identity, bound to the contract it was run
    against by the sha256 of the contract text."""

    def __init__(
        self,
        *,
        run_id: str,
        arm: str,
        role: str,
        source_day: str,
        contract_text: str,
    ) -> None:
        if arm not in ALLOWED_ARMS or role not in ALLOWED_ROLES:
            raise PrincipalOutputError("bundle names an unknown arm or role")
        for label, value in (("run_id", run_id), ("source_day", source_day)):
            if not isinstance(value, str) or not value.strip():
                raise PrincipalOutputError(f"bundle {label} must be a non-empty string")
        self.run_id = run_id
        self.arm = arm
        self.role = role
        self.source_day = source_day
        self.contract_sha256 = hashlib.sha256(contract_text.encode("utf-8")).hexdigest()
        self.contract_sections = contract_section_ids(contract_text)
        self._ledgers: dict[str, AppendOnlyLedger] = {}

    def ledger(self, ledger_id: str, *, empty_reason: str | None = None) -> AppendOnlyLedger:
        if ledger_id not in self._ledgers:
            self._ledgers[ledger_id] = AppendOnlyLedger(ledger_id, empty_reason=empty_reason)
        elif empty_reason is not None:
            self._ledgers[ledger_id].empty_reason = empty_reason
        return self._ledgers[ledger_id]

    @property
    def ledgers(self) -> Mapping[str, AppendOnlyLedger]:
        return dict(self._ledgers)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": OUTPUT_BUNDLE_SCHEMA,
            "run_id": self.run_id,
            "arm": self.arm,
            "role": self.role,
            "source_day": self.source_day,
            "causal_clock": CAUSAL_CLOCK,
            "calculation_contract_sha256": self.contract_sha256,
            "ledgers": {k: v.to_dict() for k, v in self._ledgers.items()},
        }


# --------------------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------------------


def _fail(ledger_id: str, sequence: Any, message: str) -> None:
    raise PrincipalOutputError(f"{ledger_id}[{sequence}]: {message}")


def _text(body: Mapping[str, Any], key: str, ledger_id: str, seq: Any) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value.strip():
        _fail(ledger_id, seq, f"`{key}` must be a non-empty string")
    return value  # type: ignore[return-value]


def _sha(body: Mapping[str, Any], key: str, ledger_id: str, seq: Any) -> str:
    value = body.get(key)
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        _fail(ledger_id, seq, f"`{key}` must be a lowercase SHA-256")
    return value  # type: ignore[return-value]


def _int(body: Mapping[str, Any], key: str, ledger_id: str, seq: Any) -> int:
    value = body.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(ledger_id, seq, f"`{key}` must be an int")
    return value  # type: ignore[return-value]


def _choice(body: Mapping[str, Any], key: str, allowed: Sequence[str], ledger_id: str, seq: Any) -> str:
    value = body.get(key)
    if value not in allowed:
        _fail(ledger_id, seq, f"`{key}` must be one of {list(allowed)}, got {value!r}")
    return value  # type: ignore[return-value]


def _list(body: Mapping[str, Any], key: str, ledger_id: str, seq: Any) -> list[Any]:
    value = body.get(key)
    if not isinstance(value, list):
        _fail(ledger_id, seq, f"`{key}` must be a list")
    return value  # type: ignore[return-value]


def _mapping(body: Mapping[str, Any], key: str, ledger_id: str, seq: Any) -> Mapping[str, Any]:
    value = body.get(key)
    if not isinstance(value, Mapping):
        _fail(ledger_id, seq, f"`{key}` must be a mapping")
    return value  # type: ignore[return-value]


def _verify_chain(ledger_id: str, ledger: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Recompute every hash from genesis; check sequence and cutoff monotonicity."""
    if ledger.get("ledger_id") != ledger_id:
        raise PrincipalOutputError(
            f"ledger keyed {ledger_id!r} declares ledger_id {ledger.get('ledger_id')!r}"
        )
    if ledger.get("policy") != OUTPUT_LEDGER_POLICY:
        raise PrincipalOutputError(f"{ledger_id}: policy must be {OUTPUT_LEDGER_POLICY}")
    if ledger.get("causal_clock") != CAUSAL_CLOCK:
        raise PrincipalOutputError(f"{ledger_id}: causal_clock must be {CAUSAL_CLOCK}")
    entries = ledger.get("entries")
    if not isinstance(entries, list):
        raise PrincipalOutputError(f"{ledger_id}: entries must be a list")
    prev = GENESIS_PREV_HASH
    last_cutoff: int | None = None
    for i, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            _fail(ledger_id, i, "entry is not a mapping")
        if entry.get("ledger_id") != ledger_id:
            _fail(ledger_id, i, "entry names a different ledger")
        if entry.get("sequence") != i:
            _fail(ledger_id, i, f"sequence is {entry.get('sequence')!r}, expected {i}")
        cutoff = entry.get("cutoff_recv_ns")
        if isinstance(cutoff, bool) or not isinstance(cutoff, int):
            _fail(ledger_id, i, "cutoff_recv_ns must be an int")
        if last_cutoff is not None and cutoff < last_cutoff:
            _fail(
                ledger_id,
                i,
                f"cutoff {cutoff} is earlier than the previous entry's {last_cutoff}; the "
                "ledger is out of causal order",
            )
        last_cutoff = cutoff
        if entry.get("prev_hash") != prev:
            _fail(ledger_id, i, "prev_hash does not chain to the previous entry")
        if not isinstance(entry.get("body"), Mapping):
            _fail(ledger_id, i, "body must be a mapping")
        expected = entry_hash(prev, entry)
        if entry.get("entry_hash") != expected:
            _fail(
                ledger_id,
                i,
                "entry_hash does not match its content; the entry was edited after it was "
                "written, and an output is never rewritten",
            )
        prev = expected
    return entries


class _Context:
    """What the per-ledger validators may look at across ledgers."""

    def __init__(self, bundle: Mapping[str, Any], sections: Sequence[str]) -> None:
        self.bundle = bundle
        self.sections = tuple(sections)
        self.entries: dict[str, list[Mapping[str, Any]]] = {}
        self.receipt_ids: dict[str, int] = {}  # knowledge receipt id -> cutoff
        self.probability_hashes: set[str] = set()
        self.first_locks: dict[str, int] = {}  # candidate_id -> lock_recv_ns
        self.locks = 0
        self.no_locks = 0
        self.all_cutoffs: set[int] = set()


# -- per-ledger body validators ----------------------------------------------------------


def _v_state_movie(entries: list[Mapping[str, Any]], ctx: _Context) -> None:
    for e in entries:
        seq, body, cutoff = e["sequence"], e["body"], e["cutoff_recv_ns"]
        channels = _mapping(body, "channels", STATE_MOVIE, seq)
        if not channels:
            _fail(STATE_MOVIE, seq, "a frame with no channels is not a state")
        missing: list[str] = []
        for name, chan in channels.items():
            if not isinstance(chan, Mapping):
                _fail(STATE_MOVIE, seq, f"channel {name!r} must be a mapping")
            status = _choice(chan, "status", CHANNEL_STATUSES, STATE_MOVIE, seq)
            if status == "MISSING":
                missing.append(name)
            if status not in _STATUSES_WITHOUT_VALUE and "value" not in chan:
                _fail(STATE_MOVIE, seq, f"channel {name!r} is {status} and carries no value")
            if status in _CARRIED_STATUSES:
                src = _int(chan, "source_recv_ns", STATE_MOVIE, seq)
                age = _int(chan, "age_ns", STATE_MOVIE, seq)
                if src > cutoff or age != cutoff - src:
                    _fail(
                        STATE_MOVIE,
                        seq,
                        f"carried channel {name!r} must keep its source timestamp and its age "
                        "against this cutoff (V4 section 3)",
                    )
        declared = _list(body, "missing_channels", STATE_MOVIE, seq)
        if sorted(declared) != sorted(missing):
            _fail(
                STATE_MOVIE,
                seq,
                f"missing_channels {sorted(declared)} does not name the MISSING channels "
                f"{sorted(missing)}",
            )
        _mapping(body, "state_delta", STATE_MOVIE, seq)


def _v_reasoning_movie(entries: list[Mapping[str, Any]], ctx: _Context) -> None:
    role = ctx.bundle.get("role")
    for e in entries:
        seq, body, cutoff = e["sequence"], e["body"], e["cutoff_recv_ns"]
        if body.get("role") != role:
            _fail(REASONING_MOVIE, seq, f"role must be the bundle's role {role!r}")
        _text(body, "reasoning", REASONING_MOVIE, seq)
        for h in _list(body, "helper_invocations", REASONING_MOVIE, seq):
            if not isinstance(h, Mapping):
                _fail(REASONING_MOVIE, seq, "helper invocation must be a mapping")
            lane_keys = sorted(HELPER_LANE_KEYS & set(h))
            if lane_keys:
                _fail(
                    REASONING_MOVIE,
                    seq,
                    f"helper invocation carries {lane_keys}; a helper is a tool invocation "
                    "inside a role with a selectable persona, never a parallel lane (D63/D64)",
                )
            _text(h, "persona", REASONING_MOVIE, seq)
            _text(h, "question", REASONING_MOVIE, seq)
            _sha(h, "answer_sha256", REASONING_MOVIE, seq)
            if h.get("invoked_by_role") != role:
                _fail(REASONING_MOVIE, seq, "helper invocation must name the invoking role")
        for rid in _list(body, "knowledge_retrievals", REASONING_MOVIE, seq):
            if rid not in ctx.receipt_ids:
                _fail(
                    REASONING_MOVIE,
                    seq,
                    f"knowledge retrieval {rid!r} has no receipt in {KNOWLEDGE_RECEIPTS}",
                )
            if ctx.receipt_ids[rid] > cutoff:
                _fail(REASONING_MOVIE, seq, f"knowledge retrieval {rid!r} is receipted after this cutoff")


def _v_probability_movie(entries: list[Mapping[str, Any]], ctx: _Context) -> None:
    last_eval: dict[tuple[str, str], int] = {}
    for e in entries:
        seq, body, cutoff = e["sequence"], e["body"], e["cutoff_recv_ns"]
        instance = _text(body, "instance_id", PROBABILITY_MOVIE, seq)
        _text(body, "snapshot_id", PROBABILITY_MOVIE, seq)
        head = _choice(body, "head", PRIMARY_HEADS, PROBABILITY_MOVIE, seq)
        _text(body, "model_head_view_identity", PROBABILITY_MOVIE, seq)
        _text(body, "lock_rule_revision", PROBABILITY_MOVIE, seq)
        _choice(body, "lock_state", LOCK_STATES, PROBABILITY_MOVIE, seq)
        evaluated = _int(body, "evaluation_recv_ns", PROBABILITY_MOVIE, seq)
        if evaluated > cutoff:
            _fail(PROBABILITY_MOVIE, seq, "evaluation_recv_ns is after the cutoff it was written at")
        key = (instance, head)
        if key in last_eval and evaluated < last_eval[key]:
            _fail(PROBABILITY_MOVIE, seq, "a later entry evaluates earlier than a prior one for the same instance and head")
        last_eval[key] = evaluated
        probs = _mapping(body, "probabilities", PROBABILITY_MOVIE, seq)
        if not probs:
            _fail(PROBABILITY_MOVIE, seq, "probabilities must not be empty")
        total = 0.0
        for label, p in probs.items():
            if isinstance(p, bool) or not isinstance(p, (int, float)) or not 0.0 <= p <= 1.0:
                _fail(PROBABILITY_MOVIE, seq, f"probability {label!r} = {p!r} is not in [0, 1]")
            total += float(p)
        if abs(total - 1.0) > 1e-6:
            _fail(PROBABILITY_MOVIE, seq, f"probabilities sum to {total}, not 1")
        ctx.probability_hashes.add(e["entry_hash"])


def _v_candidates(entries: list[Mapping[str, Any]], ctx: _Context) -> None:
    for e in entries:
        seq, body, cutoff = e["sequence"], e["body"], e["cutoff_recv_ns"]
        _text(body, "candidate_id", CANDIDATE_DISCOVERIES, seq)
        _text(body, "family_id", CANDIDATE_DISCOVERIES, seq)
        _choice(body, "recognition", RECOGNITION_LABELS, CANDIDATE_DISCOVERIES, seq)
        avail = _int(body, "first_lawful_availability_ns", CANDIDATE_DISCOVERIES, seq)
        lawful = _int(body, "lawful_cutoff_recv_ns", CANDIDATE_DISCOVERIES, seq)
        if not avail <= lawful <= cutoff:
            _fail(
                CANDIDATE_DISCOVERIES,
                seq,
                "a discovery is lawful only at or after its first availability and at or before "
                "the cutoff it was written at (contract section 2)",
            )
        members = _list(body, "member_group_indices", CANDIDATE_DISCOVERIES, seq)
        if not members or any(isinstance(m, bool) or not isinstance(m, int) for m in members):
            _fail(CANDIDATE_DISCOVERIES, seq, "a discovery names the exact member groups beneath it")
        _text(body, "falsifier", CANDIDATE_DISCOVERIES, seq)


def _v_locks(entries: list[Mapping[str, Any]], ctx: _Context) -> None:
    for e in entries:
        seq, body, cutoff = e["sequence"], e["body"], e["cutoff_recv_ns"]
        cand = _text(body, "candidate_id", FIRST_LOCKS, seq)
        state = _choice(body, "lock_state", LOCK_LEDGER_STATES, FIRST_LOCKS, seq)
        _text(body, "lock_rule_revision", FIRST_LOCKS, seq)
        if state == "FIRST_LOCK":
            lock_ns = _int(body, "lock_recv_ns", FIRST_LOCKS, seq)
            if lock_ns != cutoff:
                _fail(
                    FIRST_LOCKS,
                    seq,
                    f"lock_recv_ns {lock_ns} is not the cutoff {cutoff} it was written at; a "
                    "lock is stamped when it is called and is never moved",
                )
            if cand in ctx.first_locks:
                _fail(
                    FIRST_LOCKS,
                    seq,
                    f"candidate {cand!r} already holds a FIRST_LOCK at {ctx.first_locks[cand]}; a "
                    "later call cannot replace an earlier exact signal (V4 section 10)",
                )
            ph = _sha(body, "probability_entry_hash", FIRST_LOCKS, seq)
            if ph not in ctx.probability_hashes:
                _fail(FIRST_LOCKS, seq, "probability_entry_hash names no entry of the probability movie")
            ctx.first_locks[cand] = lock_ns
            ctx.locks += 1
        else:
            _text(body, "reason", FIRST_LOCKS, seq)
            if cand in ctx.first_locks:
                _fail(FIRST_LOCKS, seq, f"candidate {cand!r} is already first-locked; a lock is never withdrawn")
            ctx.no_locks += 1


def _v_negative(entries: list[Mapping[str, Any]], ctx: _Context) -> None:
    for e in entries:
        seq, body = e["sequence"], e["body"]
        _choice(body, "kind", NEGATIVE_KINDS, NEGATIVE_LEDGER, seq)
        _text(body, "section", NEGATIVE_LEDGER, seq)
        _mapping(body, "stratum", NEGATIVE_LEDGER, seq)
        num = _int(body, "numerator", NEGATIVE_LEDGER, seq)
        den = _int(body, "denominator", NEGATIVE_LEDGER, seq)
        if num < 0 or den < 0 or num > den:
            _fail(NEGATIVE_LEDGER, seq, f"numerator {num} / denominator {den} is not a population count")
        _text(body, "statement", NEGATIVE_LEDGER, seq)


def _v_knowledge_receipts(entries: list[Mapping[str, Any]], ctx: _Context) -> None:
    for e in entries:
        seq, body, cutoff = e["sequence"], e["body"], e["cutoff_recv_ns"]
        rid = _text(body, "receipt_id", KNOWLEDGE_RECEIPTS, seq)
        if rid in ctx.receipt_ids:
            _fail(KNOWLEDGE_RECEIPTS, seq, f"receipt_id {rid!r} repeats")
        _text(body, "layer_id", KNOWLEDGE_RECEIPTS, seq)
        _text(body, "path", KNOWLEDGE_RECEIPTS, seq)
        _sha(body, "sha256", KNOWLEDGE_RECEIPTS, seq)
        _choice(body, "disposition", RETRIEVAL_DISPOSITIONS, KNOWLEDGE_RECEIPTS, seq)
        retrieved = _int(body, "retrieved_at_recv_ns", KNOWLEDGE_RECEIPTS, seq)
        if retrieved > cutoff:
            _fail(KNOWLEDGE_RECEIPTS, seq, "retrieved after the cutoff it was receipted at")
        ctx.receipt_ids[rid] = cutoff


def _v_invocations(entries: list[Mapping[str, Any]], ctx: _Context) -> None:
    last_turn = -1
    for e in entries:
        seq, body = e["sequence"], e["body"]
        api = sorted(API_SHAPED_KEYS & set(body))
        if api:
            _fail(
                INVOCATION_RECEIPTS,
                seq,
                f"receipt carries API-shaped fields {api}; the principal runs as an AGENT "
                "SESSION over committed files and no provider API is called (mission section "
                "10, D70), so a provider-shaped receipt describes a run that did not happen",
            )
        if body.get("mechanism") != INVOCATION_MECHANISM:
            _fail(INVOCATION_RECEIPTS, seq, f"mechanism must be {INVOCATION_MECHANISM!r}")
        _text(body, "session_id", INVOCATION_RECEIPTS, seq)
        _text(body, "model_identity_as_reported_by_session", INVOCATION_RECEIPTS, seq)
        turn = _int(body, "turn_index", INVOCATION_RECEIPTS, seq)
        if turn <= last_turn:
            _fail(INVOCATION_RECEIPTS, seq, "turn_index must increase")
        last_turn = turn
        req = _sha(body, "request_sha256", INVOCATION_RECEIPTS, seq)
        resp = _sha(body, "response_sha256", INVOCATION_RECEIPTS, seq)
        if req == resp:
            _fail(
                INVOCATION_RECEIPTS,
                seq,
                "request and response hash identically; a run that returned its own input "
                "produced no findings",
            )


def _v_answer_wall(entries: list[Mapping[str, Any]], ctx: _Context) -> None:
    if entries:
        _fail(
            ANSWER_WALL_RECEIPTS,
            0,
            f"{len(entries)} answer-wall access receipt(s) present; any access to the answer "
            "wall invalidates the run - a valid run's ledger is EMPTY with its reason stated",
        )


def _v_run_hashes(entries: list[Mapping[str, Any]], ctx: _Context) -> None:
    if len(entries) != 2 or [e["body"].get("phase") for e in entries] != list(HASH_PHASES):
        raise PrincipalOutputError(
            f"{RUN_HASHES}: written exactly twice, START then END, got "
            f"{[e['body'].get('phase') for e in entries]}"
        )
    for e in entries:
        seq, body = e["sequence"], e["body"]
        for key in RUN_HASH_KEYS:
            _sha(body, key, RUN_HASHES, seq)
        _text(body, "model_identity", RUN_HASHES, seq)
        if body.get("run_id") != ctx.bundle.get("run_id"):
            _fail(RUN_HASHES, seq, "run_id must be the bundle's run_id")
        if body["calculation_contract_sha256"] != ctx.bundle.get("calculation_contract_sha256"):
            _fail(RUN_HASHES, seq, "calculation_contract_sha256 is not the contract this bundle was validated against")
    start, end = entries[0]["body"], entries[1]["body"]
    for key in RUN_HASH_INVARIANT_KEYS + ("model_identity",):
        if start[key] != end[key]:
            _fail(RUN_HASHES, 1, f"{key} changed between START and END; only the state may move during a run")


def _v_section(section: str):
    ledger_id = section_ledger_id(section)

    def validate(entries: list[Mapping[str, Any]], ctx: _Context) -> None:
        for e in entries:
            seq, body, cutoff = e["sequence"], e["body"], e["cutoff_recv_ns"]
            if body.get("section") != section:
                _fail(ledger_id, seq, f"section must be {section!r}")
            rows = _list(body, "exact_rows", ledger_id, seq)
            if not rows:
                _text(body, "absence_reason", ledger_id, seq)
            for row in rows:
                if not isinstance(row, Mapping):
                    _fail(ledger_id, seq, "exact row must be a mapping")
                _int(row, "group_index", ledger_id, seq)
                f_last = _int(row, "f_last_recv_ns", ledger_id, seq)
                if f_last > cutoff:
                    _fail(
                        ledger_id,
                        seq,
                        f"exact row group {row['group_index']} has F_LAST {f_last} after the "
                        f"cutoff {cutoff}; it was not lawfully known when this entry was written",
                    )
            for stratum in _list(body, "strata", ledger_id, seq):
                if not isinstance(stratum, Mapping):
                    _fail(ledger_id, seq, "stratum must be a mapping")
                missing = [k for k in STRATUM_REQUIRED_KEYS if k not in stratum]
                if missing:
                    _fail(ledger_id, seq, f"stratum omits {missing} (contract section 3)")
                _choice(stratum, "status", STRATUM_STATUSES, ledger_id, seq)
                if stratum["causal_clock"] != CAUSAL_CLOCK or stratum["cutoff_recv_ns"] != cutoff:
                    _fail(ledger_id, seq, "stratum must declare this ledger's clock and this entry's cutoff")
                den = _int(stratum, "denominator", ledger_id, seq)
                if den < 0:
                    _fail(ledger_id, seq, "denominator must be non-negative")
            _text(body, "falsifier", ledger_id, seq)

    return validate


def _v_raw_mbo(entries: list[Mapping[str, Any]], ctx: _Context) -> None:
    L = RAW_MBO_CLASSIFICATION_LEDGER
    for e in entries:
        seq, body = e["sequence"], e["body"]
        _text(body, "field_or_group", L, seq)
        cls = _choice(body, "classification", RAW_MBO_CLASSES, L, seq)
        _text(body, "evidence", L, seq)
        if str(body.get("action", "")).upper() in {"DROP", "REMOVE", "DROPPED", "REMOVED"}:
            _fail(L, seq, "an output advises and never drops; removal is Greg's decision after discussion (mission 9a)")
        if cls == "LOAD_BEARING":
            secs = _list(body, "read_by_sections", L, seq)
            if not secs:
                _fail(L, seq, "LOAD_BEARING names the section(s) whose reading changes conclusions")
        elif cls == "RETAINED_UNREAD":
            _choice(body, "cause", RETAINED_UNREAD_CAUSES, L, seq)
        elif cls == "DEGENERATE_ON_THIS_SLICE":
            if "single_value" not in body or not isinstance(body.get("expected_on_other_days"), bool):
                _fail(L, seq, "DEGENERATE_ON_THIS_SLICE states the single value and whether it is expected on other days")
        elif cls == "REDUNDANT":
            _text(body, "derivation", L, seq)
        else:
            _text(body, "reason", L, seq)


def _v_knowledge_verification(entries: list[Mapping[str, Any]], ctx: _Context) -> None:
    L = KNOWLEDGE_VERIFICATION_LEDGER
    for e in entries:
        seq, body = e["sequence"], e["body"]
        _text(body, "lesson_id", L, seq)
        _text(body, "source_layer_id", L, seq)
        _sha(body, "source_sha256", L, seq)
        verdict = _choice(body, "verdict", KNOWLEDGE_VERDICTS, L, seq)
        if verdict == "UNVERIFIED":
            _text(body, "reason", L, seq)
        else:
            _text(body, "evidence", L, seq)


_REGISTRY_VALIDATORS = {
    STATE_MOVIE: _v_state_movie,
    REASONING_MOVIE: _v_reasoning_movie,
    PROBABILITY_MOVIE: _v_probability_movie,
    CANDIDATE_DISCOVERIES: _v_candidates,
    FIRST_LOCKS: _v_locks,
    NEGATIVE_LEDGER: _v_negative,
    KNOWLEDGE_RECEIPTS: _v_knowledge_receipts,
    INVOCATION_RECEIPTS: _v_invocations,
    ANSWER_WALL_RECEIPTS: _v_answer_wall,
    RUN_HASHES: _v_run_hashes,
    RAW_MBO_CLASSIFICATION_LEDGER: _v_raw_mbo,
    KNOWLEDGE_VERIFICATION_LEDGER: _v_knowledge_verification,
}
#: Cross-ledger references force this order: receipts before the movie that cites them,
#: probabilities before the locks that bind them, everything before the run hashes and the
#: invocation receipts that must cover every cutoff.
_VALIDATION_ORDER = (
    KNOWLEDGE_RECEIPTS,
    PROBABILITY_MOVIE,
    STATE_MOVIE,
    REASONING_MOVIE,
    CANDIDATE_DISCOVERIES,
    FIRST_LOCKS,
    NEGATIVE_LEDGER,
    ANSWER_WALL_RECEIPTS,
    RAW_MBO_CLASSIFICATION_LEDGER,
    KNOWLEDGE_VERIFICATION_LEDGER,
    INVOCATION_RECEIPTS,
    RUN_HASHES,
)


def _as_mapping(bundle: OutputBundle | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(bundle, OutputBundle):
        return bundle.to_dict()
    if not isinstance(bundle, Mapping):
        raise PrincipalOutputError("bundle must be an OutputBundle or a mapping")
    return bundle


def validate_principal_outputs(
    bundle: OutputBundle | Mapping[str, Any],
    contract_text: str,
    *,
    registry_path: Path = REGISTRY_PATH,
) -> dict[str, Any]:
    """Every required ledger present, every chain intact, every entry lawful - or refuse.

    Absent ledger = failed spawn. An explicitly EMPTY ledger with a stated reason is allowed
    only for the answer-wall receipts (which MUST be empty) and the negative ledger.
    """
    body = _as_mapping(bundle)
    if body.get("schema") != OUTPUT_BUNDLE_SCHEMA:
        raise PrincipalOutputError(f"bundle schema is {body.get('schema')!r}, expected {OUTPUT_BUNDLE_SCHEMA!r}")
    if body.get("arm") not in ALLOWED_ARMS or body.get("role") not in ALLOWED_ROLES:
        raise PrincipalOutputError("bundle names an unknown arm or role")
    for label in ("run_id", "source_day"):
        if not isinstance(body.get(label), str) or not body[label].strip():
            raise PrincipalOutputError(f"bundle {label} must be a non-empty string")
    if body.get("causal_clock") != CAUSAL_CLOCK:
        raise PrincipalOutputError(f"bundle causal_clock must be {CAUSAL_CLOCK}")
    contract_sha = hashlib.sha256(contract_text.encode("utf-8")).hexdigest()
    if body.get("calculation_contract_sha256") != contract_sha:
        raise PrincipalOutputError(
            "bundle was written against a different calculation contract than the one it is "
            "validated against"
        )
    sections = contract_section_ids(contract_text)
    required = required_ledger_ids(contract_text, registry_path)
    ledgers = body.get("ledgers")
    if not isinstance(ledgers, Mapping):
        raise PrincipalOutputError("bundle carries no ledgers")
    missing = [lid for lid in required if lid not in ledgers]
    if missing:
        raise PrincipalOutputError(
            f"{len(missing)} required output ledger(s) absent: {missing}; an absent ledger is a "
            "failed spawn, never an empty success"
        )

    ctx = _Context(body, sections)
    # Chains first, for every ledger including any additional one the principal chose to write.
    for lid, ledger in ledgers.items():
        if not isinstance(ledger, Mapping):
            raise PrincipalOutputError(f"ledger {lid!r} is not a mapping")
        entries = _verify_chain(lid, ledger)
        reason = ledger.get("empty_reason")
        if not entries:
            if lid not in EMPTY_PERMITTED:
                raise PrincipalOutputError(
                    f"{lid}: no entries; only {sorted(EMPTY_PERMITTED)} may be empty, and only "
                    "with a stated reason"
                )
            if not isinstance(reason, str) or not reason.strip():
                raise PrincipalOutputError(f"{lid}: empty without a stated empty_reason")
        elif reason is not None:
            raise PrincipalOutputError(f"{lid}: carries {len(entries)} entries and an empty_reason")
        ctx.entries[lid] = entries
        ctx.all_cutoffs.update(e["cutoff_recv_ns"] for e in entries)

    # Bodies, registry ledgers in dependency order, then every section ledger.
    for lid in _VALIDATION_ORDER:
        if lid in ctx.entries:
            _REGISTRY_VALIDATORS[lid](ctx.entries[lid], ctx)
    for section in sections:
        _v_section(section)(ctx.entries[section_ledger_id(section)], ctx)

    # Cross-ledger: the session turned at every cutoff anything was written at, and the
    # identity receipt brackets the run.
    turn_cutoffs = {e["cutoff_recv_ns"] for e in ctx.entries[INVOCATION_RECEIPTS]}
    uncovered = sorted(ctx.all_cutoffs - turn_cutoffs)
    if uncovered:
        raise PrincipalOutputError(
            f"{INVOCATION_RECEIPTS}: no turn receipt at cutoff(s) {uncovered}, yet outputs were "
            "written there; every cutoff that produced an output was a session turn"
        )
    hashes = ctx.entries[RUN_HASHES]
    if hashes[0]["cutoff_recv_ns"] > min(ctx.all_cutoffs) or hashes[1]["cutoff_recv_ns"] < max(ctx.all_cutoffs):
        raise PrincipalOutputError(
            f"{RUN_HASHES}: START must be at or before the first output cutoff and END at or "
            "after the last"
        )

    per_ledger: dict[str, Any] = {}
    for lid in list(required) + sorted(set(ledgers) - set(required)):
        entries = ctx.entries[lid]
        per_ledger[lid] = {
            "required": lid in required,
            "entries": len(entries),
            "first_cutoff_recv_ns": entries[0]["cutoff_recv_ns"] if entries else None,
            "last_cutoff_recv_ns": entries[-1]["cutoff_recv_ns"] if entries else None,
            "head_hash": entries[-1]["entry_hash"] if entries else GENESIS_PREV_HASH,
            "empty_reason": ledgers[lid].get("empty_reason"),
        }
    receipt = {
        "schema": OUTPUT_RECEIPT_SCHEMA,
        "status": "ACCEPTED",
        "run_id": body["run_id"],
        "arm": body["arm"],
        "role": body["role"],
        "source_day": body["source_day"],
        "calculation_contract_sha256": contract_sha,
        "contract_sections": list(sections),
        "required_ledger_set": "the registry's output layers plus one per contract section",
        "required_ledgers": list(required),
        "additional_ledgers": sorted(set(ledgers) - set(required)),
        "cutoffs": sorted(ctx.all_cutoffs),
        "first_locks": ctx.locks,
        "no_locks": ctx.no_locks,
        "ledgers": per_ledger,
        "bundle_sha256": hashlib.sha256(canonical_bytes(body)).hexdigest(),
    }
    return receipt


# --------------------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------------------


def render_outputs_summary(bundle: OutputBundle | Mapping[str, Any]) -> str:
    """Markdown: counts, first/last cutoff per ledger, locks, no-locks, per-section counts.

    Renders WITHOUT validating, so a refused bundle can still be looked at; the receipt from
    `validate_principal_outputs` is the acceptance, this is the view.
    """
    body = _as_mapping(bundle)
    ledgers = body.get("ledgers") or {}
    lines = [
        f"# Principal output ledgers - run {body.get('run_id')} ({body.get('arm')} / {body.get('role')}, day {body.get('source_day')})",
        "",
        f"Required set: the registry's output layers plus one per contract section. Ledgers written: {len(ledgers)}.",
        "",
        "| ledger | entries | first cutoff (recv_ns) | last cutoff (recv_ns) | empty reason |",
        "|---|---:|---:|---:|---|",
    ]
    locks = no_locks = 0
    section_rows: list[tuple[str, int]] = []
    for lid, ledger in ledgers.items():
        entries = ledger.get("entries") or []
        first = entries[0]["cutoff_recv_ns"] if entries else "-"
        last = entries[-1]["cutoff_recv_ns"] if entries else "-"
        lines.append(f"| {lid} | {len(entries)} | {first} | {last} | {ledger.get('empty_reason') or ''} |")
        if lid == FIRST_LOCKS:
            for e in entries:
                if e.get("body", {}).get("lock_state") == "FIRST_LOCK":
                    locks += 1
                else:
                    no_locks += 1
        if lid.startswith(SECTION_LEDGER_PREFIX):
            section_rows.append((lid[len(SECTION_LEDGER_PREFIX):], len(entries)))
    lines += ["", f"First locks: {locks}. No-locks: {no_locks}.", ""]
    if section_rows:
        lines += ["| contract section | entries |", "|---|---:|"]
        lines += [f"| {s} | {n} |" for s, n in section_rows]
        lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------------------
# Fixture: a small valid bundle over a three-section contract and a three-cutoff stream
# --------------------------------------------------------------------------------------

FIXTURE_CONTRACT = """# Fixture calculation contract

## 4. Calculation matrix

### 4.1 Identity, integrity, and exact member surface

**Exact calculation.** Every F_LAST-closed group exactly once.

### 4.5 Formation, serialization, and observation clocks

**Exact calculation.** Event-to-receive latency per group.

### 4.10 Exhaustion state, birth, persistence, and completion

**Exact calculation.** A complete causal runway for each candidate.
"""

FIXTURE_CUTOFFS = (
    1_633_298_413_318_097_271,
    1_633_298_414_318_097_271,
    1_633_298_415_318_097_271,
)
FIXTURE_RUN_ID = "frankie-a-clean-rt-fixture-1"
FIXTURE_SOURCE_DAY = "20211003"


def _h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fixture_stratum(cutoff: int, numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "formula": "count(groups with condition) / count(groups)",
        "population": "F_LAST-closed groups at or before cutoff",
        "denominator": denominator,
        "source_day": FIXTURE_SOURCE_DAY,
        "source_role": "REAL_TIME_FRANKIE",
        "family": "fam-000001",
        "subfamily": "NONE",
        "cluster_version": "open-world-v1",
        "side": "BID",
        "session": "SUNDAY",
        "phase": "PRE_SETTLEMENT",
        "continuity_segment": 18904,
        "causal_clock": CAUSAL_CLOCK,
        "cutoff_recv_ns": cutoff,
        "status": "OPEN",
        "missingness_rule": "rows lacking f_last_recv_ns are withheld and counted",
        "inclusion_rule": "every group closed at or before cutoff",
    }


def build_fixture_bundle(contract_text: str = FIXTURE_CONTRACT) -> OutputBundle:
    """A valid bundle: three cutoffs, every registry ledger, one ledger per fixture section,
    the 9a classification and the knowledge-verification record."""
    c1, c2, c3 = FIXTURE_CUTOFFS
    b = OutputBundle(
        run_id=FIXTURE_RUN_ID,
        arm="A_CLEAN",
        role="REAL_TIME_FRANKIE",
        source_day=FIXTURE_SOURCE_DAY,
        contract_text=contract_text,
    )
    invariants = {
        "mission_sha256": _h("mission"),
        "calculation_contract_sha256": b.contract_sha256,
        "knowledge_manifest_sha256": _h("manifest"),
        "source_manifest_sha256": _h("source"),
        "code_sha256": _h("code"),
        "model_identity": "claude-opus-5",
        "run_id": FIXTURE_RUN_ID,
    }
    hashes = b.ledger(RUN_HASHES)
    hashes.append(c1, {"phase": "START", "state_sha256": _h("state-0"), **invariants})

    receipts = b.ledger(KNOWLEDGE_RECEIPTS)
    receipts.append(
        c1,
        {
            "receipt_id": "kr-0001",
            "layer_id": "mission_realtime_20260828",
            "path": "research/kalshi/agents/frankie_native_raw_mbo_oct45_realtime_mission_20260828.md",
            "sha256": _h("mission"),
            "disposition": "INSPECTED",
            "retrieved_at_recv_ns": c1,
        },
    )

    invocations = b.ledger(INVOCATION_RECEIPTS)
    state = b.ledger(STATE_MOVIE)
    reasoning = b.ledger(REASONING_MOVIE)
    probability = b.ledger(PROBABILITY_MOVIE)
    candidates = b.ledger(CANDIDATE_DISCOVERIES)
    locks = b.ledger(FIRST_LOCKS)
    negative = b.ledger(NEGATIVE_LEDGER)
    b.ledger(ANSWER_WALL_RECEIPTS, empty_reason="no answer-wall access was made on this run; A scope is blind by construction")
    prob_hashes: list[str] = []

    for turn, cutoff in enumerate(FIXTURE_CUTOFFS):
        invocations.append(
            cutoff,
            {
                "mechanism": INVOCATION_MECHANISM,
                "session_id": "session_fixture_0001",
                "model_identity_as_reported_by_session": "claude-opus-5",
                "turn_index": turn,
                "request_sha256": _h(f"request-{turn}"),
                "response_sha256": _h(f"response-{turn}"),
                "staged_request_path": f"principal_runs/fixture/turn_{turn}_request.json",
            },
        )
        state.append(
            cutoff,
            {
                "channels": {
                    "spread_ticks": {"status": "OBSERVED", "value": 1},
                    "imbalance": {"status": "OBSERVED", "value": 0.12 * (turn + 1)},
                    "roll20": {"status": "STRUCTURALLY_NOT_YET_KNOWN"} if turn == 0 else {"status": "PAST_CARRY", "value": 3, "source_recv_ns": c1, "age_ns": cutoff - c1},
                    "dipole": {"status": "MISSING"},
                },
                "missing_channels": ["dipole"],
                "state_delta": {"imbalance": 0.12} if turn else {"first_frame": True},
            },
        )
        prob = probability.append(
            cutoff,
            {
                "instance_id": "cand-0001",
                "snapshot_id": f"snap-{turn}",
                "head": "exhaustion_persistence_vs_collapse",
                "model_head_view_identity": "rt-frankie/persistence/v1",
                "probabilities": {"PERSIST": 0.4 + 0.1 * turn, "COLLAPSE": 0.6 - 0.1 * turn},
                "evaluation_recv_ns": cutoff,
                "lock_rule_revision": "lock-rule-r1",
                "lock_state": "NO_LOCK" if turn < 2 else "FIRST_LOCK",
            },
        )
        prob_hashes.append(prob["entry_hash"])
        reasoning.append(
            cutoff,
            {
                "role": "REAL_TIME_FRANKIE",
                "reasoning": f"turn {turn}: persistence read off the bid ladder at cutoff {cutoff}",
                "helper_invocations": (
                    [
                        {
                            "persona": "queue-survival-reviewer",
                            "question": "does the at-risk count support the persistence read?",
                            "answer_sha256": _h(f"answer-{turn}"),
                            "invoked_by_role": "REAL_TIME_FRANKIE",
                        }
                    ]
                    if turn == 1
                    else []
                ),
                "knowledge_retrievals": ["kr-0001"] if turn == 0 else [],
            },
        )
        for section in b.contract_sections:
            b.ledger(section_ledger_id(section)).append(
                cutoff,
                {
                    "section": section,
                    "exact_rows": [
                        {"group_index": 2281 * (turn + 1) + i, "f_last_recv_ns": cutoff - 1_000 * (i + 1)}
                        for i in range(2)
                    ],
                    "strata": [_fixture_stratum(cutoff, numerator=turn + 1, denominator=2281 * (turn + 1))],
                    "falsifier": f"any exact row of {section} whose F_LAST is after {cutoff}",
                },
            )

    candidates.append(
        c2,
        {
            "candidate_id": "cand-0001",
            "family_id": "fam-000001",
            "recognition": "T0",
            "first_lawful_availability_ns": c2 - 500,
            "lawful_cutoff_recv_ns": c2,
            "member_group_indices": [4562, 4563],
            "falsifier": "a second instrument in the member groups, or a member F_LAST after the lawful cutoff",
        },
    )
    locks.append(
        c2,
        {
            "candidate_id": "cand-0001",
            "lock_state": "NO_LOCK",
            "lock_rule_revision": "lock-rule-r1",
            "reason": "persistence 0.5 does not clear the r1 bar",
        },
    )
    locks.append(
        c3,
        {
            "candidate_id": "cand-0001",
            "lock_state": "FIRST_LOCK",
            "lock_rule_revision": "lock-rule-r1",
            "lock_recv_ns": c3,
            "probability_entry_hash": prob_hashes[2],
        },
    )
    negative.append(
        c3,
        {
            "kind": "SPARSE",
            "section": "4.5",
            "stratum": {"family": "fam-000001", "side": "ASK", "phase": "PRE_SETTLEMENT"},
            "numerator": 0,
            "denominator": 3,
            "statement": "no ASK-side group in fam-000001 closed before the cutoff; absence recorded, not inferred",
        },
    )
    raw = b.ledger(RAW_MBO_CLASSIFICATION_LEDGER)
    raw.append(c3, {"field_or_group": "book_full", "classification": "LOAD_BEARING", "read_by_sections": ["4.1", "4.10"], "evidence": "4.10's runway state changes when the full book is withheld"})
    raw.append(c3, {"field_or_group": "flags", "classification": "CANNOT_JUDGE", "reason": "the exact member rows carrying flags were not in what was received", "evidence": "only averaged rows read"})
    raw.append(c3, {"field_or_group": "publisher_id", "classification": "DEGENERATE_ON_THIS_SLICE", "single_value": 1, "expected_on_other_days": True, "evidence": "one value on all groups"})
    kv = b.ledger(KNOWLEDGE_VERIFICATION_LEDGER)
    kv.append(c3, {"lesson_id": "lesson-0001", "source_layer_id": "mission_realtime_20260828", "source_sha256": _h("mission"), "verdict": "UNVERIFIED", "reason": "no member of the lesson's stratum closed on this slice"})
    hashes.append(c3, {"phase": "END", "state_sha256": _h("state-3"), **invariants})
    return b
