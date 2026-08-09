"""S115 architecture validation for Frankie (A-67, A-69, A-42/FJ-1 adapter).

No fitted thresholds, coefficients, pooled scores, or free-form self-grading live here.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import failure_localization as fj1


class ValidationStop(RuntimeError):
    pass


BENCHMARKS = ("zero_change", "seasonal_naive", "persistence")
FIXED_METRICS = (
    "absolute_error",
    "emission_ratio",
    "band_covered",
    "stand_down_honest",
    "quantity_provenance",
)


@dataclass(frozen=True)
class EventScore:
    event_id: str
    lens: str
    day_class: str
    guess: float
    actual: float
    zero_change: float
    seasonal_naive: float
    persistence: float
    emitted: bool
    band_low: float | None
    band_high: float | None
    stood_down: bool
    stand_down_honest: bool
    quantity_provenance: str  # DERIVED | FITTED | NONE

    def as_dict(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d["absolute_error"] = abs(self.guess - self.actual)
        d["benchmark_errors"] = {
            "zero_change": abs(self.zero_change - self.actual),
            "seasonal_naive": abs(self.seasonal_naive - self.actual),
            "persistence": abs(self.persistence - self.actual),
        }
        d["emission_ratio"] = (abs(self.guess) / abs(self.actual)) if self.actual != 0 else None
        d["band_covered"] = (
            self.band_low <= self.actual <= self.band_high
            if self.band_low is not None and self.band_high is not None
            else None
        )
        return d


def per_event_report(rows: Iterable[EventScore]) -> dict[str, Any]:
    """D4/D37: returns rows, never a pooled scalar."""
    items = [row.as_dict() for row in rows]
    return {
        "schema_version": "1.0",
        "metrics_fixed_before_run": list(FIXED_METRICS),
        "benchmarks": list(BENCHMARKS),
        "pooled_scalar": None,
        "events": items,
    }


def compare_arms(blind: Sequence[EventScore], frankie: Sequence[EventScore]) -> dict[str, Any]:
    """A-67 arm 1: same events, per-event comparison only."""
    b = {row.event_id: row for row in blind}
    f = {row.event_id: row for row in frankie}
    if set(b) != set(f):
        raise ValidationStop("A-67 arms do not contain the identical event IDs")
    pairs = []
    for event_id in sorted(b):
        br = b[event_id].as_dict()
        fr = f[event_id].as_dict()
        if br["lens"] != fr["lens"] or br["day_class"] != fr["day_class"]:
            raise ValidationStop(f"A-67 cell mismatch for {event_id}")
        pairs.append(
            {
                "event_id": event_id,
                "lens": br["lens"],
                "day_class": br["day_class"],
                "blind": br,
                "frankie": fr,
                "error_delta_frankie_minus_blind": fr["absolute_error"] - br["absolute_error"],
            }
        )
    return {
        "schema_version": "1.0",
        "pooled_scalar": None,
        "interpretation": "per-event only; no average above/below",
        "pairs": pairs,
    }


def create_ab_seal(
    *,
    staged_state_paths: Sequence[Path],
    output: Path,
    blind_namespace: str,
    frankie_namespace: str,
) -> dict[str, Any]:
    """Freeze the common substrate before either arm runs."""
    if blind_namespace == frankie_namespace:
        raise ValidationStop("A-67 arms require separate namespaces")
    if "canonical" in blind_namespace.lower() or "canonical" in frankie_namespace.lower():
        raise ValidationStop("A-67 may not use a canonical output namespace")
    files = []
    for path in staged_state_paths:
        if not path.is_file():
            raise ValidationStop(f"A-67 staged input missing: {path}")
        raw = path.read_bytes()
        files.append({"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
    payload = {
        "schema_version": "1.0",
        "blind_namespace": blind_namespace,
        "frankie_namespace": frankie_namespace,
        "metrics": list(FIXED_METRICS),
        "benchmarks": list(BENCHMARKS),
        "files": sorted(files, key=lambda x: x["path"]),
        "narrative_locked_until_both_complete": True,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


@dataclass(frozen=True)
class TrainingSplit:
    walked_event_ids: tuple[str, ...]
    heldout_event_ids: tuple[str, ...]
    blind_wall_up: bool

    def validate(self) -> None:
        walked = set(self.walked_event_ids)
        held = set(self.heldout_event_ids)
        if not self.blind_wall_up:
            raise ValidationStop("A-69 requires blind wall UP during walked-corpus forecasts")
        if not walked:
            raise ValidationStop("A-69 walked corpus is empty")
        if not held:
            raise ValidationStop("A-69 held-out head is empty")
        overlap = walked & held
        if overlap:
            raise ValidationStop(f"A-69 train/held-out overlap: {sorted(overlap)[:5]}")


def grade_fj1(*, edge: str, fault_side: str, mode: str) -> dict[str, str]:
    """A-42/FJ-1: validate one proposed label against the frozen paper+extension table.

    This intentionally does not let Frankie invent a new flattering category.
    """
    table = fj1._mode_table()  # frozen table is the validator's actual source of truth
    key = (mode, edge)
    if key not in table:
        raise ValidationStop(f"FJ-1 off-table mode/edge: {mode!r} on {edge!r}")
    want_side, origin = table[key]
    if want_side != fault_side:
        raise ValidationStop(
            f"FJ-1 wrong fault side for {mode!r} on {edge!r}: got {fault_side!r}, want {want_side!r}"
        )
    return {"edge": edge, "fault_side": fault_side, "mode": mode, "origin": origin}


def training_release_gate(
    *,
    split: TrainingSplit,
    corpus_improved: bool,
    heldout_improved: bool,
    fj1_labels: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    """A-69: corpus gain alone is never enough; held-out must travel with it."""
    split.validate()
    validated = [grade_fj1(edge=x["edge"], fault_side=x["fault_side"], mode=x["mode"]) for x in fj1_labels]
    if corpus_improved and not heldout_improved:
        verdict = "SCRAP_RECALL_OR_OVERFIT"
    elif heldout_improved:
        verdict = "FORWARD_EVIDENCE_PRESENT"
    else:
        verdict = "NO_FORWARD_IMPROVEMENT"
    return {
        "verdict": verdict,
        "corpus_improved": bool(corpus_improved),
        "heldout_improved": bool(heldout_improved),
        "walked_n": len(split.walked_event_ids),
        "heldout_n": len(split.heldout_event_ids),
        "fj1": validated,
        "root_cause_rule": fj1.ROOT_CAUSE_RULE,
    }
