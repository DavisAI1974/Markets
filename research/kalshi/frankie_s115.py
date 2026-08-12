"""S115 Frankie contract layer.

Implements the registered A-61/A-50/A-66/A-68/A-62/A-65 acceptance rules from
FRANKIE_BUILD_BRIEF_S115.md. This module is deliberately deterministic. It does not call an LLM,
fit a threshold, write doctrine, or grant execution authority.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence


class S115Stop(RuntimeError):
    pass


OWNERSHIP = {
    "D8_merge": {
        "layer": "memory",
        "part": "content_store",
        "owns": "play content: claims, calls, falsifiers, instances",
        "writes": "adjudicated canonical store only",
    },
    "A62_specialist_priors": {
        "layer": "memory",
        "part": "derived_track_record_index",
        "owns": "specialist track record derived from posteriors and actuals",
        "writes": "generated index only; never authored doctrine",
    },
    "A65_compaction": {
        "layer": "memory",
        "part": "serving_policy",
        "owns": "what reaches the reader",
        "writes": "no canonical memory content",
    },
    "A59_NOOA": {
        "layer": "scaffold",
        "part": "render_and_typed_contract",
        "owns": "render target, typed I/O, deterministic-vs-model-completed boundary",
        "writes": "rendered working artifacts only",
    },
    "A68_lens_book": {
        "layer": "memory",
        "part": "within_run_lens_journal",
        "owns": "this lens's own carried state and prior decisions",
        "writes": "append-only journal; never doctrine",
    },
    "A64_branching": {
        "layer": "control_logic",
        "part": "candidate_branching",
        "owns": "multiple refinement candidates and their evaluation routing",
        "writes": "sandbox candidates only",
    },
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ownership_collisions(entries: Mapping[str, Mapping[str, str]] = OWNERSHIP) -> list[dict[str, str]]:
    """Return true same-PART collisions. Sharing a layer is explicitly allowed."""
    seen: dict[tuple[str, str], str] = {}
    collisions: list[dict[str, str]] = []
    for owner, spec in entries.items():
        key = (str(spec["layer"]), str(spec["part"]))
        if key in seen:
            collisions.append({"first": seen[key], "second": owner, "layer": key[0], "part": key[1]})
        else:
            seen[key] = owner
    return collisions


def assert_ownership_clean(entries: Mapping[str, Mapping[str, str]] = OWNERSHIP) -> None:
    collisions = ownership_collisions(entries)
    if collisions:
        raise S115Stop(f"A-66 ownership collision at same part: {collisions}")


def pin_snapshot(paths: Sequence[Path], output: Path) -> dict[str, Any]:
    """A-61: pin exactly what verification read, before verification starts."""
    records: list[dict[str, Any]] = []
    for path in paths:
        if not path.is_file():
            raise S115Stop(f"A-61 snapshot input missing: {path}")
        data = path.read_bytes()
        records.append({"path": str(path), "sha256": _sha256_bytes(data), "bytes": len(data)})
    payload = {
        "schema_version": "1.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "files": sorted(records, key=lambda r: r["path"]),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        existing = json.loads(output.read_text(encoding="utf-8"))
        if existing != payload:
            raise S115Stop(f"A-61 snapshot is immutable once written: {output}")
        return existing
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def verify_snapshot(snapshot: Path) -> None:
    raw = json.loads(snapshot.read_text(encoding="utf-8"))
    for rec in raw.get("files", []):
        path = Path(rec["path"])
        if not path.is_file():
            raise S115Stop(f"A-61 pinned file disappeared: {path}")
        if _sha256_bytes(path.read_bytes()) != rec["sha256"]:
            raise S115Stop(f"A-61 pinned file moved under verifier: {path}")


LEAK_TOKENS = (
    "actual curve",
    "actuals:",
    "blind result",
    "refine result",
    "held-out head result",
    "answer key",
)


def assert_no_narrative_leak(paths: Sequence[Path], extra_tokens: Sequence[str] = ()) -> None:
    """A-50 conservative narrative gate for blind/head runs.

    This is intentionally a deny-list adjunct, not the sole leakage defense. It exists to make the
    automatically loaded CLAUDE.md/handoff channel fail loudly when known outcome language appears.
    """
    tokens = tuple(t.lower() for t in (*LEAK_TOKENS, *extra_tokens))
    for path in paths:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        hits = [token for token in tokens if token and token in text]
        if hits:
            raise S115Stop(f"A-50 leak gate: {path} contains forbidden outcome token(s): {hits}")


@dataclass(frozen=True)
class LensBookEntry:
    lens: str
    day: str
    decision_at: str
    event_id: str
    carried_state: Mapping[str, Any]
    action: Mapping[str, Any]
    source_hashes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def _parse_day(day: str) -> datetime:
    return datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def append_lens_book(path: Path, entry: LensBookEntry) -> str:
    """A-68 append-only journal. Existing bytes are never rewritten."""
    _parse_day(entry.day)
    if not entry.lens or not entry.event_id or not entry.decision_at:
        raise S115Stop("A-68 entry missing lens/event_id/decision_at")
    if not entry.source_hashes:
        raise S115Stop("A-68 entry requires source hashes")
    path.parent.mkdir(parents=True, exist_ok=True)
    row = json.dumps(entry.as_dict(), sort_keys=True, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as handle:
        handle.write(row + "\n")
    return _sha256_bytes(row.encode("utf-8"))


def causal_lens_view(path: Path, *, lens: str, current_day: str) -> list[dict[str, Any]]:
    """A-68/D3: only STRICTLY earlier days are readable. Future rows are absent."""
    cutoff = _parse_day(current_day)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("lens") != lens:
            continue
        if _parse_day(str(rec["day"])) < cutoff:
            rows.append(rec)
    return sorted(rows, key=lambda r: (r["day"], r["decision_at"], r["event_id"]))


def assert_future_absent(view: Sequence[Mapping[str, Any]], current_day: str) -> None:
    cutoff = _parse_day(current_day)
    bad = [r for r in view if _parse_day(str(r["day"])) >= cutoff]
    if bad:
        raise S115Stop(f"A-68 causal violation: future/current entries visible: {bad[:3]}")


@dataclass(frozen=True)
class SpecialistOutcome:
    lens: str
    event_id: str
    day: str
    posterior: Mapping[str, Any]
    actual: Mapping[str, Any]
    failure_mode: str
    correction_mechanism: str
    emitted: bool


def build_specialist_track_records(rows: Iterable[SpecialistOutcome]) -> dict[str, Any]:
    """A-62: generated index only, with mechanism not merely score."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        _parse_day(row.day)
        grouped.setdefault(row.lens, []).append(
            {
                "event_id": row.event_id,
                "day": row.day,
                "failure_mode": row.failure_mode,
                "correction_mechanism": row.correction_mechanism,
                "emitted": bool(row.emitted),
                "posterior_hash": _sha256_bytes(json.dumps(row.posterior, sort_keys=True).encode()),
                "actual_hash": _sha256_bytes(json.dumps(row.actual, sort_keys=True).encode()),
            }
        )
    return {
        "schema_version": "1.0",
        "generated": True,
        "authored": False,
        "lenses": {k: sorted(v, key=lambda r: (r["day"], r["event_id"])) for k, v in sorted(grouped.items())},
    }


def write_generated_track_records(path: Path, payload: Mapping[str, Any]) -> None:
    if payload.get("generated") is not True or payload.get("authored") is not False:
        raise S115Stop("A-62 refuses authored specialist priors")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


LOAD_BEARING_KEYS = ("direction", "magnitude", "fired", "stood_down")


def posterior_diff(full: Mapping[str, Any], changed: Mapping[str, Any]) -> dict[str, Any]:
    """A-65 same-day view regression. Per-cell caller controls event/day identity."""
    diffs: dict[str, Any] = {}
    for key in LOAD_BEARING_KEYS:
        a = full.get(key)
        b = changed.get(key)
        if a != b:
            diffs[key] = {"full": a, "changed": b}
    return {"load_bearing_changed": bool(diffs), "diffs": diffs}


def validate_compaction(
    *,
    full: Mapping[str, Any],
    changed: Mapping[str, Any],
    independently_believed_lossy: bool = False,
) -> dict[str, Any]:
    result = posterior_diff(full, changed)
    if result["load_bearing_changed"]:
        result["verdict"] = "REJECT_VIEW_CHANGE"
    elif independently_believed_lossy:
        result["verdict"] = "TEST_INSENSITIVE"
    else:
        result["verdict"] = "VALIDATED_FOR_THIS_CELL_ONLY"
    return result


def validate_repository_relative(path: str) -> None:
    pure = PurePosixPath(path.replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts:
        raise S115Stop(f"path must be repository-relative: {path}")


assert_ownership_clean()
