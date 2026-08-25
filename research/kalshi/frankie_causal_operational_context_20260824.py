#!/usr/bin/env python3
"""Lossless causal snapshots of Frankie's complete canonical decision-state universe.

The accepted registry minimum is 1,914 leaves across 44 blocks.  The live survey
may grow beyond that boundary; this adapter always takes the union of every live
registry path and every path emitted by the canonical S135 state builder.  Missing
and explicit-null values remain distinct.  No brain-read count is an access list.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

from research.kalshi.frankie_block_availability_matrix_20260824 import matrix_for_blocks


SCHEMA_VERSION = "FRANKIE_CAUSAL_DECISION_STATE_SNAPSHOT_V1_20260824"
ACCEPTED_MINIMUM_PATHS = 1_914
ACCEPTED_MINIMUM_BLOCKS = 44


class OperationalContextError(ValueError):
    """A registry, causal clock, source identity, or snapshot invariant failed."""


def _sha(value: Any, field: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise OperationalContextError(f"{field} must be lowercase SHA-256")
    return text


def _text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise OperationalContextError(f"{field} must be non-empty")
    return text


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise OperationalContextError(f"{field} must be finite")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise OperationalContextError(f"{field} must be finite") from exc
    if not math.isfinite(result):
        raise OperationalContextError(f"{field} must be finite")
    return result


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def _hash(value: Any) -> str:
    raw = json.dumps(
        _jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _block(path: str) -> str:
    # Match data_registry.py exactly.  Top-level list slots are distinct surveyed
    # blocks (for example blocks_emitted[0]..[3]) and must not be collapsed.
    return path.split(".", 1)[0]


def flatten_decision_state(value: Mapping[str, Any]) -> dict[str, Any]:
    """Flatten all scalar/null leaves using the registry's first-four list convention."""
    if not isinstance(value, Mapping):
        raise OperationalContextError("canonical decision state must be an object")
    out: dict[str, Any] = {}

    def walk(item: Any, prefix: str) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                name = str(key)
                if name.startswith("_"):
                    continue
                walk(child, f"{prefix}.{name}" if prefix else name)
            return
        if isinstance(item, (list, tuple)):
            for index, child in enumerate(item[:4]):
                walk(child, f"{prefix}[{index}]")
            return
        if isinstance(item, float) and not math.isfinite(item):
            raise OperationalContextError(f"non-finite decision-state value at {prefix}")
        if item is not None and not isinstance(item, (str, int, float, bool)):
            raise OperationalContextError(f"non-JSON decision-state value at {prefix}")
        if not prefix:
            raise OperationalContextError("decision-state leaf has no path")
        out[prefix] = item

    walk(value, "")
    return out


def _parse_availability_clock(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        if text.isdigit() and len(text) == 8:
            parsed = datetime.strptime(text, "%Y%m%d").replace(tzinfo=timezone.utc)
        else:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except ValueError:
        return None


def _field_clocks(value: Mapping[str, Any]) -> dict[str, tuple[float | None, float | None, str]]:
    """Resolve only explicit availability metadata; never infer from an as-of label."""
    clocks: dict[str, tuple[float | None, float | None, str]] = {}
    known_keys = (
        "known_by", "event_known_by", "published_at", "publication_timestamp",
        "publication_ts", "knowable_from", "asof_utc",
        "consensus_pre_print_snapshot_utc", "print_datetime_utc",
    )
    available_keys = (
        "available_at", "availability_ts", "vintage_available_at",
        "publication_ts", "knowable_from", "asof_utc",
        "consensus_pre_print_snapshot_utc", "print_datetime_utc",
    )

    def walk(
        item: Any,
        prefix: str,
        inherited_known: float | None,
        inherited_available: float | None,
        inherited_basis: str,
    ) -> None:
        known, available, basis = inherited_known, inherited_available, inherited_basis
        if isinstance(item, Mapping):
            for key in known_keys:
                if key in item and (parsed := _parse_availability_clock(item[key])) is not None:
                    known, basis = parsed, f"EXPLICIT_METADATA:{prefix or '<root>'}.{key}"
                    break
            for key in available_keys:
                if key in item and (parsed := _parse_availability_clock(item[key])) is not None:
                    available, basis = parsed, f"EXPLICIT_METADATA:{prefix or '<root>'}.{key}"
                    break
            for key, child in item.items():
                name = str(key)
                if not name.startswith("_"):
                    walk(child, f"{prefix}.{name}" if prefix else name, known, available, basis)
            return
        if isinstance(item, (list, tuple)):
            for index, child in enumerate(item[:4]):
                walk(child, f"{prefix}[{index}]", known, available, basis)
            return
        clocks[prefix] = (known, available, basis)

    walk(value, "", None, None, "SNAPSHOT_CUTOFF_CONSERVATIVE")
    return clocks


@dataclass(frozen=True)
class RegistryCoverageOracle:
    paths: tuple[str, ...]
    source_ids: tuple[str, ...]
    source_hashes: tuple[str, ...]
    path_count: int
    block_count: int
    block_sources: Mapping[str, Mapping[str, str]]
    receipt_hash: str

    @classmethod
    def create(
        cls,
        *,
        paths: Sequence[str],
        source_ids: Sequence[str],
        source_hashes: Sequence[str],
        block_sources: Mapping[str, Sequence[str]] | None = None,
    ) -> "RegistryCoverageOracle":
        frozen = tuple(sorted({_text(item, "registry path") for item in paths}))
        ids = tuple(_text(item, "registry source id") for item in source_ids)
        hashes = tuple(_sha(item, "registry source hash") for item in source_hashes)
        if not ids or len(ids) != len(hashes):
            raise OperationalContextError("registry source ids and hashes must be non-empty and aligned")
        blocks = {_block(path) for path in frozen}
        if len(frozen) < ACCEPTED_MINIMUM_PATHS or len(blocks) < ACCEPTED_MINIMUM_BLOCKS:
            raise OperationalContextError(
                "registry parity regressed below 1,914 served paths / 44 blocks: "
                f"observed={len(frozen)}/{len(blocks)}"
            )
        declared = block_sources or {}
        provenance: dict[str, Mapping[str, str]] = {}
        for block in sorted(blocks):
            lookup = block.split("[", 1)[0]
            pair = declared.get(lookup, ("source declared by owning feed", "feed-specific"))
            if not isinstance(pair, Sequence) or isinstance(pair, (str, bytes)) or len(pair) != 2:
                raise OperationalContextError(f"registry block provenance is invalid: {lookup}")
            provenance[block] = MappingProxyType(
                {
                    "upstream_source": _text(pair[0], f"{lookup} upstream source"),
                    "cadence": _text(pair[1], f"{lookup} cadence"),
                }
            )
        frozen_provenance = MappingProxyType(provenance)
        core = {
            "paths": frozen,
            "source_ids": ids,
            "source_hashes": hashes,
            "path_count": len(frozen),
            "block_count": len(blocks),
            "block_sources": frozen_provenance,
            "minimum_paths": ACCEPTED_MINIMUM_PATHS,
            "minimum_blocks": ACCEPTED_MINIMUM_BLOCKS,
        }
        return cls(
            frozen, ids, hashes, len(frozen), len(blocks), frozen_provenance, _hash(core)
        ).validate()

    @classmethod
    def from_repo(cls, repo_root: str | Path) -> "RegistryCoverageOracle":
        root = Path(repo_root).resolve()
        registry_path = root / "research/kalshi/data_registry.py"
        spec = importlib.util.spec_from_file_location("frankie_live_data_registry", registry_path)
        if spec is None or spec.loader is None:
            raise OperationalContextError("cannot load canonical data registry")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        fields = module.survey()
        if not isinstance(fields, Mapping):
            raise OperationalContextError("canonical data registry survey did not return a mapping")
        survey_hash = _hash(sorted(str(path) for path in fields))
        return cls.create(
            paths=tuple(str(path) for path in fields),
            source_ids=(str(registry_path.relative_to(root)), "data_registry.survey()"),
            source_hashes=(_file_sha(registry_path), survey_hash),
            block_sources=getattr(module, "BLOCK_SOURCE", {}),
        )

    def validate(self) -> "RegistryCoverageOracle":
        if self.path_count != len(self.paths) or self.block_count != len({_block(p) for p in self.paths}):
            raise OperationalContextError("registry count mismatch")
        core = {
            "paths": self.paths,
            "source_ids": self.source_ids,
            "source_hashes": self.source_hashes,
            "path_count": self.path_count,
            "block_count": self.block_count,
            "block_sources": self.block_sources,
            "minimum_paths": ACCEPTED_MINIMUM_PATHS,
            "minimum_blocks": ACCEPTED_MINIMUM_BLOCKS,
        }
        if self.receipt_hash != _hash(core):
            raise OperationalContextError("registry receipt hash mismatch")
        return self


class DecisionFieldStatus(str, Enum):
    PRESENT = "PRESENT"
    EXPLICIT_NULL = "EXPLICIT_NULL"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class HourlyWeatherObservationSurface:
    state: Mapping[str, Any]
    field_sources: Mapping[str, tuple[str, str]]
    observation_count: int
    source_file_count: int
    source_tree_sha256: str


def load_hourly_weather_observations(
    repo_root: str | Path, *, decision_day: str, evaluated_at: Any
) -> HourlyWeatherObservationSurface:
    """Load only same-day ASOS rows whose observation receipt clock is at/before prefix.

    Historical raw rows predate collector receipt metadata, so `valid` is the
    observation-known clock when no explicit known_by/received_at/available_at
    is present. No daily aggregation or later hour is computed or admitted.
    """
    root = Path(repo_root).resolve()
    cutoff = _finite(evaluated_at, "evaluated_at")
    compact_day = decision_day.replace("-", "")
    if len(compact_day) != 8 or not compact_day.isdigit():
        raise OperationalContextError("decision_day must be YYYYMMDD")
    month = compact_day[:6]
    store = root / "data/nws_hourly"
    files = tuple(sorted(store.glob(f"*_{month}.jsonl*"))) if store.is_dir() else ()
    file_rows = [
        {"path": str(path.relative_to(root)), "bytes": path.stat().st_size, "sha256": _file_sha(path)}
        for path in files if path.is_file()
    ]
    tree_hash = _hash(file_rows)
    records: dict[str, Any] = {}
    seen = 0
    for path in files:
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                if len(line.encode("utf-8")) > 65_536:
                    raise OperationalContextError("hourly weather record exceeds byte cap")
                try:
                    row = json.loads(line)
                except (TypeError, ValueError) as exc:
                    raise OperationalContextError("hourly weather store contains invalid JSON") from exc
                if not isinstance(row, Mapping):
                    raise OperationalContextError("hourly weather record must be an object")
                station = _text(row.get("station"), "hourly weather station")
                observed_text = _text(row.get("valid"), "hourly weather valid")
                observed_at = _parse_availability_clock(observed_text)
                if observed_at is None:
                    raise OperationalContextError("hourly weather valid clock is invalid")
                observed_day = datetime.fromtimestamp(observed_at, tz=timezone.utc).strftime("%Y%m%d")
                if observed_day != compact_day:
                    continue
                clock_value = next(
                    (row.get(key) for key in ("known_by", "received_at", "available_at") if row.get(key) not in (None, "")),
                    observed_text,
                )
                known_by = _parse_availability_clock(clock_value)
                if known_by is None:
                    raise OperationalContextError("hourly weather availability clock is invalid")
                if known_by > cutoff:
                    continue
                seen += 1
                if seen > 10_000:
                    raise OperationalContextError("hourly weather prefix exceeds record cap")
                timestamp_key = datetime.fromtimestamp(observed_at, tz=timezone.utc).strftime("%Y%m%dT%H_%M_%SZ")
                record_id = f"{station}_{timestamp_key}"
                if record_id in records:
                    raise OperationalContextError(f"duplicate hourly weather observation: {record_id}")
                values = {
                    str(key): value for key, value in row.items()
                    if key not in {"station", "valid", "known_by", "received_at", "available_at"}
                }
                records[record_id] = {
                    "station": station,
                    "observed_at": datetime.fromtimestamp(observed_at, tz=timezone.utc).isoformat(),
                    "known_by": datetime.fromtimestamp(known_by, tz=timezone.utc).isoformat(),
                    "available_at": datetime.fromtimestamp(known_by, tz=timezone.utc).isoformat(),
                    "values": values,
                }
    state: Mapping[str, Any] = MappingProxyType(
        {"weather_observation_hourly": MappingProxyType({"records": MappingProxyType(records)})}
    )
    source_id = f"data/nws_hourly/*_{month}.jsonl*:NWS_IEM_ASOS_RAW"
    field_sources = MappingProxyType(
        {path: (source_id, tree_hash) for path in flatten_decision_state(state)}
    )
    return HourlyWeatherObservationSurface(
        state=state,
        field_sources=field_sources,
        observation_count=len(records),
        source_file_count=len(file_rows),
        source_tree_sha256=tree_hash,
    )


@dataclass(frozen=True)
class DecisionField:
    path: str
    block: str
    value: Any
    status: DecisionFieldStatus
    known_by: float
    available_at: float
    evaluated_at: float
    clock_basis: str
    source_id: str
    source_sha256: str
    missing_reason: str | None
    value_hash: str
    field_hash: str

    def validate(self) -> "DecisionField":
        path = _text(self.path, "field path")
        if self.block != _block(path):
            raise OperationalContextError("field block/path mismatch")
        known = _finite(self.known_by, "known_by")
        available = _finite(self.available_at, "available_at")
        evaluated = _finite(self.evaluated_at, "evaluated_at")
        if not known <= available <= evaluated:
            raise OperationalContextError("decision field violates known_by/availability/no-backfill order")
        _text(self.source_id, "source_id")
        _text(self.clock_basis, "clock_basis")
        _sha(self.source_sha256, "source_sha256")
        if self.status is DecisionFieldStatus.PRESENT and self.value is None:
            raise OperationalContextError("present decision field cannot be null")
        if self.status is not DecisionFieldStatus.PRESENT and self.value is not None:
            raise OperationalContextError("missing/null decision field cannot carry a value")
        if self.status is DecisionFieldStatus.UNAVAILABLE and not self.missing_reason:
            raise OperationalContextError("unavailable field requires a missingness reason")
        if self.value_hash != _hash(self.value):
            raise OperationalContextError("decision field value hash mismatch")
        core = asdict(self)
        core.pop("field_hash")
        if self.field_hash != _hash(core):
            raise OperationalContextError("decision field hash mismatch")
        return self


@dataclass(frozen=True)
class DecisionStateSnapshot:
    schema: str
    run_id: str
    decision_day: str
    evaluated_at: float
    registry_receipt_hash: str
    fields: tuple[DecisionField, ...]
    path_count: int
    block_count: int
    registry_path_count: int
    registry_block_count: int
    additive_path_count: int
    coverage_fraction: float
    schema_registered_count: int
    emitted_leaf_count: int
    emitted_registered_count: int
    emitted_additive_count: int
    present_count: int
    explicit_null_count: int
    unavailable_count: int
    emitted_coverage_fraction: float
    value_coverage_fraction: float
    source_snapshot_leaf_count: int
    source_snapshot_leaf_hash: str
    build_status: str
    build_error_hash: str | None
    family_manifest: Mapping[str, Mapping[str, Any]]
    availability_matrix: Mapping[str, Any]
    snapshot_hash: str

    def core(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "run_id": self.run_id,
            "decision_day": self.decision_day,
            "evaluated_at": self.evaluated_at,
            "registry_receipt_hash": self.registry_receipt_hash,
            "fields": [asdict(item) for item in self.fields],
            "path_count": self.path_count,
            "block_count": self.block_count,
            "registry_path_count": self.registry_path_count,
            "registry_block_count": self.registry_block_count,
            "additive_path_count": self.additive_path_count,
            "coverage_fraction": self.coverage_fraction,
            "schema_registered_count": self.schema_registered_count,
            "emitted_leaf_count": self.emitted_leaf_count,
            "emitted_registered_count": self.emitted_registered_count,
            "emitted_additive_count": self.emitted_additive_count,
            "present_count": self.present_count,
            "explicit_null_count": self.explicit_null_count,
            "unavailable_count": self.unavailable_count,
            "emitted_coverage_fraction": self.emitted_coverage_fraction,
            "value_coverage_fraction": self.value_coverage_fraction,
            "source_snapshot_leaf_count": self.source_snapshot_leaf_count,
            "source_snapshot_leaf_hash": self.source_snapshot_leaf_hash,
            "build_status": self.build_status,
            "build_error_hash": self.build_error_hash,
            "family_manifest": _jsonable(self.family_manifest),
            "availability_matrix": _jsonable(self.availability_matrix),
        }

    def provider_payload(self) -> dict[str, Any]:
        """Lossless JSON projection supplied identically to every helper and Frankie."""
        self.validate()
        return {
            "schema": self.schema,
            "snapshot_hash": self.snapshot_hash,
            "registry_receipt_hash": self.registry_receipt_hash,
            "decision_day": self.decision_day,
            "evaluated_at": self.evaluated_at,
            "path_count": self.path_count,
            "block_count": self.block_count,
            "registry_path_count": self.registry_path_count,
            "registry_block_count": self.registry_block_count,
            "additive_path_count": self.additive_path_count,
            "coverage_fraction": self.coverage_fraction,
            "schema_registered_count": self.schema_registered_count,
            "emitted_leaf_count": self.emitted_leaf_count,
            "emitted_registered_count": self.emitted_registered_count,
            "emitted_additive_count": self.emitted_additive_count,
            "present_count": self.present_count,
            "explicit_null_count": self.explicit_null_count,
            "unavailable_count": self.unavailable_count,
            "emitted_coverage_fraction": self.emitted_coverage_fraction,
            "value_coverage_fraction": self.value_coverage_fraction,
            "source_snapshot_leaf_count": self.source_snapshot_leaf_count,
            "source_snapshot_leaf_hash": self.source_snapshot_leaf_hash,
            "build_status": self.build_status,
            "build_error_hash": self.build_error_hash,
            "family_manifest": {key: dict(value) for key, value in self.family_manifest.items()},
            "availability_matrix": _jsonable(self.availability_matrix),
            "fields": [asdict(item) for item in self.fields],
        }

    def validate(self) -> "DecisionStateSnapshot":
        if self.schema != SCHEMA_VERSION:
            raise OperationalContextError("decision-state snapshot schema mismatch")
        _text(self.run_id, "run_id")
        _finite(self.evaluated_at, "evaluated_at")
        _sha(self.registry_receipt_hash, "registry_receipt_hash")
        for item in self.fields:
            item.validate()
        paths = tuple(item.path for item in self.fields)
        if paths != tuple(sorted(set(paths))):
            raise OperationalContextError("decision-state paths must be unique and sorted")
        if self.path_count != len(paths) or self.block_count != len({_block(path) for path in paths}):
            raise OperationalContextError("decision-state snapshot count mismatch")
        if self.registry_path_count < ACCEPTED_MINIMUM_PATHS:
            raise OperationalContextError("decision-state registry coverage is incomplete")
        if (
            self.registry_block_count < ACCEPTED_MINIMUM_BLOCKS
            or self.registry_block_count > self.block_count
        ):
            raise OperationalContextError("decision-state registry block coverage is incomplete")
        if self.schema_registered_count != self.registry_path_count:
            raise OperationalContextError("schema registered count differs from registry")
        if self.present_count + self.explicit_null_count + self.unavailable_count != self.schema_registered_count:
            raise OperationalContextError("registered field status counts do not sum to schema")
        if (
            self.availability_matrix.get("block_count") != self.block_count
            or set(self.availability_matrix.get("blocks", {}))
            != {_block(path) for path in paths}
        ):
            raise OperationalContextError("decision-state availability matrix coverage mismatch")
        matrix_core = {
            "block_count": self.availability_matrix["block_count"],
            "blocks": self.availability_matrix["blocks"],
        }
        if self.availability_matrix.get("matrix_hash") != _hash(matrix_core):
            raise OperationalContextError("decision-state availability matrix hash mismatch")
        if self.emitted_leaf_count != self.source_snapshot_leaf_count:
            raise OperationalContextError("source snapshot leaf count mismatch")
        _sha(self.source_snapshot_leaf_hash, "source_snapshot_leaf_hash")
        if self.snapshot_hash != _hash(self.core()):
            raise OperationalContextError("decision-state snapshot hash mismatch")
        return self


class CausalDecisionStateSnapshotAdapter:
    def __init__(self, oracle: RegistryCoverageOracle) -> None:
        self.oracle = oracle.validate()

    def snapshot(
        self,
        *,
        run_id: str,
        decision_day: str,
        evaluated_at: Any,
        canonical_state: Mapping[str, Any],
        canonical_source_id: str,
        canonical_source_sha256: str,
        build_status: str = "CANONICAL_S135_ACCEPTED",
        build_error_hash: str | None = None,
        field_sources: Mapping[str, Sequence[str]] | None = None,
    ) -> DecisionStateSnapshot:
        cutoff = _finite(evaluated_at, "evaluated_at")
        flat = flatten_decision_state(canonical_state)
        clocks = _field_clocks(canonical_state)
        all_paths = tuple(sorted(set(self.oracle.paths) | set(flat)))
        source_id = _text(canonical_source_id, "canonical_source_id")
        source_sha = _sha(canonical_source_sha256, "canonical_source_sha256")
        exact_sources = field_sources or {}
        fields: list[DecisionField] = []
        family: dict[str, dict[str, Any]] = {}
        registry_set = set(self.oracle.paths)
        availability_matrix = matrix_for_blocks(_block(path) for path in all_paths)
        present_registered = explicit_null_registered = unavailable_registered = 0
        for path in all_paths:
            present = path in flat
            value = flat.get(path)
            explicit_known, explicit_available, clock_basis = clocks.get(
                path, (None, None, "SNAPSHOT_CUTOFF_CONSERVATIVE")
            )
            known_by = (
                explicit_available if explicit_known is None and explicit_available is not None
                else (cutoff if explicit_known is None else explicit_known)
            )
            available_at = known_by if explicit_available is None else explicit_available
            quarantined_weather = _block(path) == "weather" and present
            policy = availability_matrix["blocks"][_block(path)]
            rule = policy["availability_rule"]
            unverified_clock = False
            if present and explicit_known is None and explicit_available is None and not quarantined_weather:
                block_value = canonical_state.get(_block(path).split("[", 1)[0])
                if rule == "STATIC_OR_PREFIX":
                    clock_basis = f"BLOCK_POLICY:{policy['cadence_class']}:PREFIX"
                elif rule in {
                    "PRIOR_DATE", "REPORT_DATE_PLUS_1D", "REPORT_DATE_PLUS_2D",
                    "PERIOD_PLUS_3D",
                }:
                    keys = (
                        ("vintage_asof", "asof_session", "asof_prior_session", "n0_prev_full_session_date", "date")
                        if rule == "PRIOR_DATE"
                        else (
                            ("period",)
                            if rule in {"PERIOD_PLUS_3D", "REPORT_DATE_PLUS_2D"}
                            else ("as_of", "as_of_report_date", "period")
                        )
                    )
                    raw_clock = next(
                        (block_value.get(key) for key in keys if isinstance(block_value, Mapping) and block_value.get(key)),
                        None,
                    )
                    derived = _parse_availability_clock(raw_clock)
                    if derived is None:
                        unverified_clock = True
                    else:
                        delay_days = (
                            3 if rule == "PERIOD_PLUS_3D"
                            else (2 if rule == "REPORT_DATE_PLUS_2D" else 1)
                        )
                        known_by = available_at = derived + timedelta(days=delay_days).total_seconds()
                        clock_basis = f"BLOCK_POLICY:{rule}:{keys}"
                else:
                    unverified_clock = True
            future_clock = known_by > cutoff or available_at > cutoff
            if quarantined_weather:
                status = DecisionFieldStatus.UNAVAILABLE
                value = None
                reason = "UNAVAILABLE_CAUSAL_QUARANTINE_SAME_DAY_REALIZED_WEATHER"
                clock_basis = "CAUSAL_QUARANTINE_REALIZED_WEATHER_PROXY"
                known_by = available_at = cutoff
            elif unverified_clock:
                status = DecisionFieldStatus.UNAVAILABLE
                value = None
                reason = "UNAVAILABLE_CAUSAL_QUARANTINE_UNVERIFIED_AVAILABILITY"
                clock_basis = f"BLOCK_POLICY:{policy['cadence_class']}:UNVERIFIED"
                known_by = available_at = cutoff
            elif future_clock:
                status = DecisionFieldStatus.UNAVAILABLE
                value = None
                reason = "UNAVAILABLE_CAUSAL_QUARANTINE_FUTURE_AVAILABILITY"
                clock_basis = f"{clock_basis}:AFTER_PREFIX"
                known_by = available_at = cutoff
            elif not present:
                status = DecisionFieldStatus.UNAVAILABLE
                reason = "CANONICAL_STATE_DID_NOT_EMIT_REGISTERED_PATH"
            elif value is None:
                status = DecisionFieldStatus.EXPLICIT_NULL
                reason = "CANONICAL_EXPLICIT_NULL"
            else:
                status = DecisionFieldStatus.PRESENT
                reason = None
            value_hash = _hash(value)
            path_source = exact_sources.get(path, (source_id, source_sha))
            if (
                not isinstance(path_source, Sequence)
                or isinstance(path_source, (str, bytes))
                or len(path_source) != 2
            ):
                raise OperationalContextError(f"field provenance is invalid: {path}")
            field_source_id = _text(path_source[0], f"{path} source_id")
            field_source_sha = _sha(path_source[1], f"{path} source_sha256")
            core = {
                "path": path,
                "block": _block(path),
                "value": value,
                "status": status,
                "known_by": known_by,
                "available_at": available_at,
                "evaluated_at": cutoff,
                "clock_basis": clock_basis,
                "source_id": field_source_id,
                "source_sha256": field_source_sha,
                "missing_reason": reason,
                "value_hash": value_hash,
            }
            field = DecisionField(**core, field_hash=_hash(core)).validate()
            fields.append(field)
            counts = family.setdefault(
                field.block,
                {
                    "registered": 0,
                    "additive": 0,
                    "present": 0,
                    "explicit_null": 0,
                    "unavailable": 0,
                    **dict(
                        self.oracle.block_sources.get(
                            field.block,
                            {
                                "upstream_source": source_id,
                                "cadence": "canonical-state as-of snapshot",
                            },
                        )
                    ),
                    "availability_policy": dict(availability_matrix["blocks"][field.block]),
                },
            )
            counts["registered" if path in registry_set else "additive"] += 1
            counts[status.value.lower()] += 1
            if path in registry_set:
                if status is DecisionFieldStatus.PRESENT:
                    present_registered += 1
                elif status is DecisionFieldStatus.EXPLICIT_NULL:
                    explicit_null_registered += 1
                else:
                    unavailable_registered += 1
        manifest = MappingProxyType(
            {name: MappingProxyType(dict(counts)) for name, counts in sorted(family.items())}
        )
        base = {
            "schema": SCHEMA_VERSION,
            "run_id": _text(run_id, "run_id"),
            "decision_day": _text(decision_day, "decision_day"),
            "evaluated_at": cutoff,
            "registry_receipt_hash": self.oracle.receipt_hash,
            "fields": tuple(fields),
            "path_count": len(fields),
            "block_count": len(manifest),
            "registry_path_count": self.oracle.path_count,
            "registry_block_count": self.oracle.block_count,
            "additive_path_count": len(set(flat) - registry_set),
            "coverage_fraction": (present_registered + explicit_null_registered) / len(registry_set),
            "schema_registered_count": self.oracle.path_count,
            "emitted_leaf_count": len(flat),
            "emitted_registered_count": len(set(flat) & registry_set),
            "emitted_additive_count": len(set(flat) - registry_set),
            "present_count": present_registered,
            "explicit_null_count": explicit_null_registered,
            "unavailable_count": unavailable_registered,
            "emitted_coverage_fraction": (present_registered + explicit_null_registered) / len(registry_set),
            "value_coverage_fraction": present_registered / len(registry_set),
            "source_snapshot_leaf_count": len(flat),
            "source_snapshot_leaf_hash": _hash(flat),
            "build_status": _text(build_status, "build_status"),
            "build_error_hash": None if build_error_hash is None else _sha(build_error_hash, "build_error_hash"),
            "family_manifest": manifest,
            "availability_matrix": MappingProxyType(
                {
                    "block_count": availability_matrix["block_count"],
                    "blocks": MappingProxyType(
                        {key: MappingProxyType(value) for key, value in availability_matrix["blocks"].items()}
                    ),
                    "matrix_hash": availability_matrix["matrix_hash"],
                }
            ),
        }
        snapshot = DecisionStateSnapshot(**base, snapshot_hash=_hash({**base, "fields": [asdict(x) for x in fields]}))
        return snapshot.validate()


def build_canonical_s135_snapshot(
    *,
    repo_root: str | Path,
    run_id: str,
    decision_day: str,
    evaluated_at: Any,
    group: str,
    oracle: RegistryCoverageOracle | None = None,
) -> DecisionStateSnapshot:
    """Call S135 when its stores are staged; otherwise emit full-schema missingness."""
    root = Path(repo_root).resolve()
    source = root / "research/kalshi/frankie_s135_current_runtime.py"
    coverage = oracle or RegistryCoverageOracle.from_repo(root)
    state: Mapping[str, Any] = {}
    status = "CANONICAL_S135_ACCEPTED"
    error_hash = None
    try:
        spec = importlib.util.spec_from_file_location("frankie_causal_s135_runtime", source)
        if spec is None or spec.loader is None:
            raise OperationalContextError("cannot load S135 runtime")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        from datetime import date, timedelta

        day = date.fromisoformat(decision_day.replace("-", ""))
        mask_after = (day - timedelta(days=1)).isoformat().replace("-", "")
        built = module.decision_state(
            [decision_day.replace("-", "")], mask_after=mask_after, group=group
        )
        row = built.get(decision_day.replace("-", "")) if isinstance(built, Mapping) else None
        if not isinstance(row, Mapping):
            raise OperationalContextError("S135 did not emit the requested decision day")
        hourly = load_hourly_weather_observations(
            root, decision_day=decision_day, evaluated_at=evaluated_at
        )
        state = {**row, **hourly.state}
    except Exception as exc:
        status = "EXPLICIT_MISSING_CANONICAL_SUBSTRATE"
        error_hash = _hash({"type": type(exc).__name__, "message": str(exc)[:512]})
    return CausalDecisionStateSnapshotAdapter(coverage).snapshot(
        run_id=run_id,
        decision_day=decision_day,
        evaluated_at=evaluated_at,
        canonical_state=state,
        canonical_source_id=str(source.relative_to(root)),
        canonical_source_sha256=_file_sha(source),
        build_status=status,
        build_error_hash=error_hash,
        field_sources=hourly.field_sources if status == "CANONICAL_S135_ACCEPTED" else None,
    )


def snapshot_availability_audit(snapshot: DecisionStateSnapshot) -> dict[str, Any]:
    """Return exact grouped status/reason evidence for launch and post-run audit."""
    snap = snapshot.validate()
    blocks: dict[str, dict[str, Any]] = {
        block: {
            "registered": int(manifest["registered"]),
            "additive": int(manifest["additive"]),
            "present": 0, "explicit_null": 0, "unavailable": 0,
            "causal_quarantine": 0, "unavailable_reasons": {},
        }
        for block, manifest in snap.family_manifest.items()
    }
    for field in snap.fields:
        row = blocks[field.block]
        row[field.status.value.lower()] += 1
        if field.status is DecisionFieldStatus.UNAVAILABLE:
            reason = str(field.missing_reason)
            row["unavailable_reasons"][reason] = row["unavailable_reasons"].get(reason, 0) + 1
            if reason.startswith("UNAVAILABLE_CAUSAL_QUARANTINE_"):
                row["causal_quarantine"] += 1
    core = {
        "snapshot_hash": snap.snapshot_hash,
        "registered_counts": {
            "present": snap.present_count,
            "explicit_null": snap.explicit_null_count,
            "unavailable": snap.unavailable_count,
            "total": snap.registry_path_count,
        },
        "all_field_counts": {
            "present": sum(row["present"] for row in blocks.values()),
            "explicit_null": sum(row["explicit_null"] for row in blocks.values()),
            "unavailable": sum(row["unavailable"] for row in blocks.values()),
            "total": snap.path_count,
        },
        "causal_quarantine_count": sum(row["causal_quarantine"] for row in blocks.values()),
        "blocks": {key: value for key, value in sorted(blocks.items())},
    }
    return {**core, "audit_hash": _hash(core)}


__all__ = [
    "ACCEPTED_MINIMUM_BLOCKS",
    "ACCEPTED_MINIMUM_PATHS",
    "CausalDecisionStateSnapshotAdapter",
    "DecisionField",
    "DecisionFieldStatus",
    "DecisionStateSnapshot",
    "HourlyWeatherObservationSurface",
    "OperationalContextError",
    "RegistryCoverageOracle",
    "build_canonical_s135_snapshot",
    "flatten_decision_state",
    "load_hourly_weather_observations",
    "snapshot_availability_audit",
]
