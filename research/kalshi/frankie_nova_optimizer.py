#!/usr/bin/env python3
"""Frankie-specific NOVA token optimizer and external-state harness.

This module is a Frankie adaptation of ideas from the existing
DavisAI1974/Nova-Optimizer project.  The original NOVA repository is intentionally
left untouched.

The adaptation is deliberately conservative:

* Frankie already owns the authoritative market/causal state, lens book,
  specialist track records, play index, and canonical brain.  This module does
  not create competing stores.
* The EvoHarness-RL Belief/Progress/Experience (BPE) split is used as an access
  taxonomy over those existing stores, not as a replacement architecture.
* NOVA-style compaction is SAFE by default: JSON keys and values are preserved
  exactly and only representation whitespace is removed.  Any lossy view must
  be explicitly marked and validated before it can become decision-bearing.
* Every state access can be written to an append-only ledger with byte/token
  cost, action class, source, and explicit withheld-content metadata.
* The existing Markets Terminal MCP surface remains unchanged.  This module
  does not add command execution, writes through MCP, or trading authority.

Paper-derived additions implemented here:

1. BPE state classification without duplicating Frankie's stores.
2. Explicit track / commit / recall / note action classes.
3. Cost-aware access telemetry so retrieval frequency and token cost can be
   measured before any adaptive policy is trained.
4. Selective-access planning (locate -> ranged read -> full read/refusal) as a
   deterministic plan, not a new MCP capability.
5. Explicit declaration of withheld content; silent truncation is forbidden.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


class HarnessStop(RuntimeError):
    """Raised when a Frankie harness invariant would be violated."""


class BPEState(str, Enum):
    BELIEF = "belief"
    PROGRESS = "progress"
    EXPERIENCE = "experience"


class HarnessAction(str, Enum):
    TRACK = "track"
    COMMIT = "commit"
    RECALL = "recall"
    NOTE = "note"


# BPE is a view over EXISTING Frankie ownership.  Do not turn this map into new
# canonical stores without a separate reviewed ownership decision.
BPE_CONTRACT: dict[str, dict[str, Any]] = {
    "belief": {
        "owner": "existing causal decision state / rendered point-in-time evidence",
        "meaning": "what is currently known at the decision clock",
        "write_rule": "not owned here; future information must be physically absent",
    },
    "progress": {
        "owner": "A-68 causal lens book",
        "meaning": "what this lens is carrying and what it has already done",
        "write_rule": "append-only; only strictly earlier entries may be served",
    },
    "experience": {
        "owner": "A-62 generated specialist track records + play index + reviewed brain lessons",
        "meaning": "reusable prior failures, corrections, mechanisms, and plays",
        "write_rule": (
            "generated track records may update from outcomes; general doctrine still requires "
            "proposal -> adjudication -> merge"
        ),
    },
}

HARNESS_ACTION_CONTRACT: dict[str, str] = {
    "track": "inspect or retrieve current causal state; never manufacture missing evidence",
    "commit": "append task/lens progress to the existing causal book",
    "recall": "retrieve prior plays, track records, analogs, or reviewed lessons on demand",
    "note": "emit a candidate lesson/proposal; never directly rewrite canonical doctrine",
}


# Fields NOVA commonly removes from verbose schemas.  Frankie SAFE mode uses
# this only for non-binding display/tool-description views.  Required schema
# semantics, names, enums, and types are always preserved.
REMOVABLE_NONBINDING_FIELDS = {
    "examples",
    "example",
    "x-examples",
    "externalDocs",
    "deprecated",
}


def estimate_tokens(text: str) -> int:
    """Deterministic dependency-free estimate used for relative access cost.

    The canonical billing count still comes from the model/provider.  This
    estimator is intentionally simple so tests never need tokenizer downloads.
    """
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def compact_json_lossless(value: Any) -> str:
    """Return a byte-compact JSON representation with exact JSON semantics."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _json_roundtrip(value: Any) -> Any:
    return json.loads(compact_json_lossless(value))


def assert_lossless_json(value: Any, compacted: str) -> None:
    """Hard gate: compacted JSON must decode to the exact same JSON value."""
    decoded = json.loads(compacted)
    expected = _json_roundtrip(value)
    if decoded != expected:
        raise HarnessStop("lossless compaction changed JSON semantics")


@dataclass(frozen=True)
class OptimizationResult:
    text: str
    original_bytes: int
    optimized_bytes: int
    estimated_tokens_before: int
    estimated_tokens_after: int
    strategies: tuple[str, ...]
    withheld: tuple[str, ...]
    decision_safe: bool
    requires_a65_validation: bool

    @property
    def tokens_saved_estimate(self) -> int:
        return max(0, self.estimated_tokens_before - self.estimated_tokens_after)

    @property
    def reduction_percent(self) -> float:
        if self.estimated_tokens_before <= 0:
            return 0.0
        return round(100.0 * self.tokens_saved_estimate / self.estimated_tokens_before, 2)


class FrankieNovaOptimizer:
    """NOVA-style compaction under Frankie-specific safety rules."""

    def compact_payload(self, payload: Any) -> OptimizationResult:
        """Losslessly compact a JSON-compatible payload.

        This is the default path for decision-bearing state.  It removes only
        formatting overhead and therefore needs no semantic reconstruction.
        """
        original = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        compacted = compact_json_lossless(payload)
        assert_lossless_json(payload, compacted)
        return OptimizationResult(
            text=compacted,
            original_bytes=len(original.encode("utf-8")),
            optimized_bytes=len(compacted.encode("utf-8")),
            estimated_tokens_before=estimate_tokens(original),
            estimated_tokens_after=estimate_tokens(compacted),
            strategies=("lossless_json_minification",),
            withheld=(),
            decision_safe=True,
            requires_a65_validation=False,
        )

    def compact_tool_view(self, tools: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], OptimizationResult]:
        """Compact non-binding tool descriptions without changing tool semantics.

        Markets Terminal currently exposes exactly two tools.  Unlike NOVA's
        generic super-tool consolidation, Frankie MUST NOT merge or rename them:
        the small surface is already the safer representation.
        """
        before_obj = [dict(t) for t in tools]
        after_obj = [self._compact_tool(dict(t)) for t in before_obj]

        before_names = [str(t.get("name")) for t in before_obj]
        after_names = [str(t.get("name")) for t in after_obj]
        if before_names != after_names:
            raise HarnessStop("tool compaction changed tool identity")
        for before, after in zip(before_obj, after_obj):
            self._assert_schema_contract_preserved(before, after)

        original = json.dumps(before_obj, ensure_ascii=False, indent=2, sort_keys=True)
        compacted = compact_json_lossless(after_obj)
        withheld = tuple(sorted(self._collect_removed_paths(before_obj, after_obj)))
        result = OptimizationResult(
            text=compacted,
            original_bytes=len(original.encode("utf-8")),
            optimized_bytes=len(compacted.encode("utf-8")),
            estimated_tokens_before=estimate_tokens(original),
            estimated_tokens_after=estimate_tokens(compacted),
            strategies=("schema_metadata_trim", "lossless_json_minification"),
            withheld=withheld,
            # Removing examples/deprecation/external-doc metadata changes the
            # representation, so it is NOT decision-safe until validated.
            decision_safe=not withheld,
            requires_a65_validation=bool(withheld),
        )
        return after_obj, result

    def _compact_tool(self, tool: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in tool.items():
            if key in REMOVABLE_NONBINDING_FIELDS:
                continue
            if isinstance(value, dict):
                out[key] = self._compact_schema(value)
            elif isinstance(value, list):
                out[key] = [self._compact_schema(v) if isinstance(v, dict) else v for v in value]
            else:
                out[key] = value
        return out

    def _compact_schema(self, schema: Mapping[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in schema.items():
            if key in REMOVABLE_NONBINDING_FIELDS:
                continue
            if isinstance(value, Mapping):
                out[key] = self._compact_schema(value)
            elif isinstance(value, list):
                out[key] = [self._compact_schema(v) if isinstance(v, Mapping) else v for v in value]
            else:
                out[key] = value
        return out

    @staticmethod
    def _assert_schema_contract_preserved(before: Mapping[str, Any], after: Mapping[str, Any]) -> None:
        """Refuse changes to fields that can change invocation semantics."""
        protected = ("name", "type", "required", "enum", "properties", "input_schema", "parameters")

        def walk(b: Any, a: Any, path: str = "$") -> None:
            if isinstance(b, Mapping):
                if not isinstance(a, Mapping):
                    raise HarnessStop(f"schema shape changed at {path}")
                for key, bval in b.items():
                    if key in REMOVABLE_NONBINDING_FIELDS:
                        continue
                    if key not in a:
                        raise HarnessStop(f"required schema field removed at {path}.{key}")
                    if key in protected and key not in ("properties", "input_schema", "parameters"):
                        if a[key] != bval:
                            raise HarnessStop(f"protected schema field changed at {path}.{key}")
                    walk(bval, a[key], f"{path}.{key}")
            elif isinstance(b, list):
                if not isinstance(a, list) or len(a) != len(b):
                    raise HarnessStop(f"schema list changed at {path}")
                for i, (bv, av) in enumerate(zip(b, a)):
                    walk(bv, av, f"{path}[{i}]")
            elif a != b:
                raise HarnessStop(f"schema value changed at {path}")

        walk(before, after)

    @staticmethod
    def _collect_removed_paths(before: Any, after: Any, path: str = "$") -> set[str]:
        removed: set[str] = set()
        if isinstance(before, Mapping) and isinstance(after, Mapping):
            for key, value in before.items():
                child = f"{path}.{key}"
                if key not in after:
                    removed.add(child)
                else:
                    removed.update(FrankieNovaOptimizer._collect_removed_paths(value, after[key], child))
        elif isinstance(before, list) and isinstance(after, list):
            for i, (bv, av) in enumerate(zip(before, after)):
                removed.update(FrankieNovaOptimizer._collect_removed_paths(bv, av, f"{path}[{i}]"))
        return removed


@dataclass(frozen=True)
class HarnessAccessEvent:
    seq: int
    day: str
    action: str
    state_class: str
    source: str
    request: str
    bytes_returned: int
    estimated_tokens: int
    withheld: tuple[str, ...] = ()
    expanded_after: bool = False
    decision_relevant: bool | None = None
    source_hash: str | None = None

    def validate(self) -> None:
        if self.seq < 1:
            raise HarnessStop("access event seq must be >= 1")
        if self.action not in {x.value for x in HarnessAction}:
            raise HarnessStop(f"invalid harness action: {self.action}")
        if self.state_class not in {x.value for x in BPEState}:
            raise HarnessStop(f"invalid BPE state class: {self.state_class}")
        if not self.day or not self.source or not self.request:
            raise HarnessStop("day/source/request are required")
        if self.bytes_returned < 0 or self.estimated_tokens < 0:
            raise HarnessStop("negative access cost")


class HarnessAccessLedger:
    """Append-only, causal telemetry for Frankie external-state access."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def append(self, event: HarnessAccessEvent) -> str:
        event.validate()
        prior = self.read_all()
        expected_seq = (prior[-1]["seq"] + 1) if prior else 1
        if event.seq != expected_seq:
            raise HarnessStop(f"append-only seq violation: expected {expected_seq}, got {event.seq}")
        row = asdict(event)
        encoded = compact_json_lossless(row)
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(encoded + "\n")
        return digest

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for line_no, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise HarnessStop(f"malformed access ledger line {line_no}: {exc}") from exc
            rows.append(row)
        return rows

    def causal_view(self, current_day: str) -> list[dict[str, Any]]:
        """Serve only strictly earlier access events."""
        return [row for row in self.read_all() if str(row.get("day", "")) < current_day]

    def summary(self) -> dict[str, Any]:
        rows = self.read_all()
        by_action: dict[str, int] = {}
        by_state: dict[str, int] = {}
        for row in rows:
            by_action[row["action"]] = by_action.get(row["action"], 0) + 1
            by_state[row["state_class"]] = by_state.get(row["state_class"], 0) + 1
        return {
            "events": len(rows),
            "bytes_returned": sum(int(r.get("bytes_returned", 0)) for r in rows),
            "estimated_tokens": sum(int(r.get("estimated_tokens", 0)) for r in rows),
            "by_action": by_action,
            "by_state": by_state,
            "expanded_after": sum(bool(r.get("expanded_after")) for r in rows),
            "decision_relevant_true": sum(r.get("decision_relevant") is True for r in rows),
            "decision_relevant_false": sum(r.get("decision_relevant") is False for r in rows),
            "decision_relevant_unknown": sum(r.get("decision_relevant") is None for r in rows),
        }


@dataclass(frozen=True)
class RetrievalPlan:
    step: str
    reason: str
    withheld: tuple[str, ...] = ()


def plan_retrieval(*, file_bytes: int | None, has_query: bool, has_range: bool, full_read_cap: int = 262_144) -> RetrievalPlan:
    """Plan selective access without changing the MCP tool surface.

    This encodes the EvoHarness lesson that retrieval itself has a cost.  It is
    intentionally deterministic and conservative.  It does NOT execute a read.
    """
    if has_query:
        return RetrievalPlan("locate", "query available; locate before broader retrieval")
    if has_range:
        return RetrievalPlan("ranged_read", "known relevant range; avoid unrelated context")
    if file_bytes is None:
        return RetrievalPlan("metadata_first", "size/relevance unknown; inspect metadata before full read")
    if file_bytes <= full_read_cap:
        return RetrievalPlan("full_read", "file is within the explicit full-read cap")
    return RetrievalPlan(
        "refuse_full_read",
        f"file is {file_bytes} bytes, over the {full_read_cap}-byte cap",
        withheld=(f"content beyond full-read cap; {file_bytes} total bytes",),
    )


def next_access_event(
    *,
    ledger: HarnessAccessLedger,
    day: str,
    action: HarnessAction,
    state_class: BPEState,
    source: str,
    request: str,
    returned_text: str,
    withheld: Iterable[str] = (),
    expanded_after: bool = False,
    decision_relevant: bool | None = None,
) -> HarnessAccessEvent:
    """Construct the next append-only event without mutating the ledger."""
    rows = ledger.read_all()
    seq = (rows[-1]["seq"] + 1) if rows else 1
    encoded = returned_text.encode("utf-8")
    return HarnessAccessEvent(
        seq=seq,
        day=day,
        action=action.value,
        state_class=state_class.value,
        source=source,
        request=request,
        bytes_returned=len(encoded),
        estimated_tokens=estimate_tokens(returned_text),
        withheld=tuple(withheld),
        expanded_after=expanded_after,
        decision_relevant=decision_relevant,
        source_hash=hashlib.sha256(encoded).hexdigest(),
    )
