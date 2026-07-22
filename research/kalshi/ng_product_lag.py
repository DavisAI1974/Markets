#!/usr/bin/env python3
"""Exact-key, chronological product-lag measurement contract for NG vehicles.

This module measures how long a follower product takes to react after a validated
leader event. Lag is never universal: every lookup is keyed by venue, product,
series, contract, strike, liquidity bucket, move-size bucket, time-of-day bucket,
and regime. Missing or insufficient exact-key history returns
``NO_MEASURED_WINDOW``; the code never falls back to a pooled market-wide number.

Observations and lookups are research/SHADOW artifacts only. They cannot grant
execution authority and historical lookups use only observations strictly before
the supplied decision timestamp.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

OBSERVATION_SCHEMA = "ng_product_lag_observation.v1"
REGISTRY_SCHEMA = "ng_product_lag_registry.v1"
LOOKUP_SCHEMA = "ng_product_lag_lookup.v1"
AUTHORITY = "PRODUCT_SPECIFIC_LAG_RESEARCH_ONLY"
MEASURED = "MEASURED_WINDOW"
NO_WINDOW = "NO_MEASURED_WINDOW"

KEY_FIELDS = (
    "venue",
    "product",
    "series",
    "contract",
    "strike",
    "liquidity_bucket",
    "move_size_bucket",
    "time_of_day_bucket",
    "regime",
)


class ProductLagError(ValueError):
    """Raised for malformed, contradictory, or tampered lag artifacts."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _finite(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ProductLagError(f"{name} must be finite") from error
    if not math.isfinite(result):
        raise ProductLagError(f"{name} must be finite")
    return result


def _clean_text(value: Any, name: str, *, allow_none: bool = False) -> str | None:
    if value is None and allow_none:
        return None
    text = str(value or "").strip()
    if not text:
        raise ProductLagError(f"{name} is required")
    return text


def normalize_key(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Return the canonical exact product-lag key without inferring any field."""
    missing = [name for name in KEY_FIELDS if name not in raw]
    if missing:
        raise ProductLagError("lag key missing: " + ", ".join(missing))
    return {
        "venue": _clean_text(raw.get("venue"), "venue").lower(),
        "product": _clean_text(raw.get("product"), "product"),
        "series": _clean_text(raw.get("series"), "series"),
        "contract": _clean_text(raw.get("contract"), "contract"),
        "strike": _clean_text(raw.get("strike"), "strike", allow_none=True),
        "liquidity_bucket": _clean_text(raw.get("liquidity_bucket"), "liquidity_bucket"),
        "move_size_bucket": _clean_text(raw.get("move_size_bucket"), "move_size_bucket"),
        "time_of_day_bucket": _clean_text(raw.get("time_of_day_bucket"), "time_of_day_bucket"),
        "regime": _clean_text(raw.get("regime"), "regime"),
    }


def key_fingerprint(key: Mapping[str, Any]) -> str:
    return _fingerprint(normalize_key(key))


def _quality(raw: Mapping[str, Any] | None) -> dict[str, bool]:
    source = raw or {}
    return {
        "leader_event_valid": bool(source.get("leader_event_valid", False)),
        "follower_event_valid": bool(source.get("follower_event_valid", False)),
        "exact_definition_match": bool(source.get("exact_definition_match", False)),
        "sequence_complete": bool(source.get("sequence_complete", False)),
        "executable_book_observed": bool(source.get("executable_book_observed", False)),
    }


def make_observation(
    *,
    observation_id: str,
    key: Mapping[str, Any],
    leader_event_s: float,
    follower_first_reprice_s: float,
    follower_completion_s: float | None = None,
    quality: Mapping[str, Any] | None = None,
    source_mode: str = "historical_replay",
    source_fingerprints: Sequence[str] = (),
) -> dict[str, Any]:
    """Create one immutable lag observation with derived millisecond delays."""
    leader = _finite(leader_event_s, "leader_event_s")
    first = _finite(follower_first_reprice_s, "follower_first_reprice_s")
    if first < leader:
        raise ProductLagError("follower first reprice precedes leader event")
    completion = None
    if follower_completion_s is not None:
        completion = _finite(follower_completion_s, "follower_completion_s")
        if completion < first:
            raise ProductLagError("follower completion precedes first reprice")
    payload: dict[str, Any] = {
        "schema": OBSERVATION_SCHEMA,
        "authority": AUTHORITY,
        "observation_id": _clean_text(observation_id, "observation_id"),
        "key": normalize_key(key),
        "key_fingerprint": key_fingerprint(key),
        "leader_event_s": leader,
        "follower_first_reprice_s": first,
        "follower_completion_s": completion,
        "first_reprice_lag_ms": round((first - leader) * 1000.0, 6),
        "completion_lag_ms": None if completion is None else round((completion - leader) * 1000.0, 6),
        "quality": _quality(quality),
        "source_mode": _clean_text(source_mode, "source_mode"),
        "source_fingerprints": sorted({_clean_text(item, "source_fingerprint") for item in source_fingerprints}),
        "execution_authority": False,
        "actual_order_sent": False,
        "may_update_ng_brain": False,
    }
    payload["fingerprint"] = _fingerprint(payload)
    return payload


def validate_observation(raw: Mapping[str, Any]) -> dict[str, Any]:
    observation = copy.deepcopy(dict(raw))
    supplied = observation.pop("fingerprint", None)
    if observation.get("schema") != OBSERVATION_SCHEMA:
        raise ProductLagError("unexpected observation schema")
    if observation.get("authority") != AUTHORITY:
        raise ProductLagError("unexpected observation authority")
    if observation.get("execution_authority") is not False or observation.get("actual_order_sent") is not False:
        raise ProductLagError("lag observation cannot grant or record execution")
    if observation.get("may_update_ng_brain") is not False:
        raise ProductLagError("lag observation cannot update ng_brain")
    observation_id = _clean_text(observation.get("observation_id"), "observation_id")
    key = normalize_key(observation.get("key") or {})
    if observation.get("key_fingerprint") != key_fingerprint(key):
        raise ProductLagError(f"{observation_id}: key fingerprint mismatch")
    leader = _finite(observation.get("leader_event_s"), "leader_event_s")
    first = _finite(observation.get("follower_first_reprice_s"), "follower_first_reprice_s")
    if first < leader:
        raise ProductLagError(f"{observation_id}: follower first reprice precedes leader")
    completion_raw = observation.get("follower_completion_s")
    completion = None if completion_raw is None else _finite(completion_raw, "follower_completion_s")
    if completion is not None and completion < first:
        raise ProductLagError(f"{observation_id}: completion precedes first reprice")
    expected_first = round((first - leader) * 1000.0, 6)
    if abs(_finite(observation.get("first_reprice_lag_ms"), "first_reprice_lag_ms") - expected_first) > 1e-6:
        raise ProductLagError(f"{observation_id}: first-reprice lag mismatch")
    expected_completion = None if completion is None else round((completion - leader) * 1000.0, 6)
    if expected_completion is None:
        if observation.get("completion_lag_ms") is not None:
            raise ProductLagError(f"{observation_id}: unexpected completion lag")
    elif abs(_finite(observation.get("completion_lag_ms"), "completion_lag_ms") - expected_completion) > 1e-6:
        raise ProductLagError(f"{observation_id}: completion lag mismatch")
    observation["quality"] = _quality(observation.get("quality"))
    observation["source_mode"] = _clean_text(observation.get("source_mode"), "source_mode")
    observation["source_fingerprints"] = sorted(
        {_clean_text(item, "source_fingerprint") for item in observation.get("source_fingerprints") or []}
    )
    expected = _fingerprint(observation)
    if supplied != expected:
        raise ProductLagError(f"{observation_id}: observation fingerprint mismatch")
    observation["fingerprint"] = expected
    return observation


def observation_is_usable(observation: Mapping[str, Any]) -> bool:
    quality = _quality(observation.get("quality"))
    return all(
        quality[name]
        for name in (
            "leader_event_valid",
            "follower_event_valid",
            "exact_definition_match",
            "sequence_complete",
            "executable_book_observed",
        )
    )


def _quantile(values: Sequence[float], fraction: float) -> float:
    if not values:
        raise ProductLagError("cannot calculate a quantile from zero values")
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _distribution(values: Sequence[float]) -> dict[str, float] | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    return {
        "min_ms": round(ordered[0], 6),
        "p25_ms": round(_quantile(ordered, 0.25), 6),
        "p50_ms": round(_quantile(ordered, 0.50), 6),
        "p75_ms": round(_quantile(ordered, 0.75), 6),
        "p90_ms": round(_quantile(ordered, 0.90), 6),
        "max_ms": round(ordered[-1], 6),
    }


def build_registry(observations: Iterable[Mapping[str, Any]], *, min_samples: int = 5) -> dict[str, Any]:
    """Build an exact-key registry; observations are never pooled across key fields."""
    if int(min_samples) < 1:
        raise ProductLagError("min_samples must be positive")
    validated: list[dict[str, Any]] = []
    ids: set[str] = set()
    for raw in observations:
        observation = validate_observation(raw)
        observation_id = str(observation["observation_id"])
        if observation_id in ids:
            raise ProductLagError(f"duplicate observation_id: {observation_id}")
        ids.add(observation_id)
        validated.append(observation)
    validated.sort(key=lambda row: (float(row["leader_event_s"]), str(row["observation_id"])))

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in validated:
        grouped[str(observation["key_fingerprint"])].append(observation)

    groups: list[dict[str, Any]] = []
    for fingerprint in sorted(grouped):
        rows = grouped[fingerprint]
        key = rows[0]["key"]
        if any(row["key"] != key for row in rows):
            raise ProductLagError("key fingerprint collision or contradictory key")
        summaries = [
            {
                "observation_id": row["observation_id"],
                "leader_event_s": row["leader_event_s"],
                "first_reprice_lag_ms": row["first_reprice_lag_ms"],
                "completion_lag_ms": row["completion_lag_ms"],
                "usable": observation_is_usable(row),
                "quality": row["quality"],
                "source_mode": row["source_mode"],
                "observation_fingerprint": row["fingerprint"],
            }
            for row in rows
        ]
        usable = [row for row in summaries if row["usable"]]
        first_values = [float(row["first_reprice_lag_ms"]) for row in usable]
        completion_values = [float(row["completion_lag_ms"]) for row in usable if row["completion_lag_ms"] is not None]
        group = {
            "key": key,
            "key_fingerprint": fingerprint,
            "status": MEASURED if len(usable) >= int(min_samples) else NO_WINDOW,
            "minimum_samples": int(min_samples),
            "total_observations": len(summaries),
            "usable_observations": len(usable),
            "rejected_observations": len(summaries) - len(usable),
            "coverage_start_s": None if not summaries else summaries[0]["leader_event_s"],
            "coverage_end_s": None if not summaries else summaries[-1]["leader_event_s"],
            "first_reprice_distribution": _distribution(first_values),
            "completion_distribution": _distribution(completion_values),
            "observations": summaries,
        }
        group["fingerprint"] = _fingerprint(group)
        groups.append(group)

    registry: dict[str, Any] = {
        "schema": REGISTRY_SCHEMA,
        "authority": AUTHORITY,
        "no_universal_lag": True,
        "exact_key_fields": list(KEY_FIELDS),
        "minimum_samples_per_exact_key": int(min_samples),
        "observation_count": len(validated),
        "group_count": len(groups),
        "groups": groups,
        "source_observation_fingerprints": [row["fingerprint"] for row in validated],
        "execution_authority": False,
        "may_update_ng_brain": False,
    }
    registry["fingerprint"] = _fingerprint(registry)
    return registry


def validate_registry(raw: Mapping[str, Any]) -> dict[str, Any]:
    registry = copy.deepcopy(dict(raw))
    supplied = registry.pop("fingerprint", None)
    if registry.get("schema") != REGISTRY_SCHEMA or registry.get("authority") != AUTHORITY:
        raise ProductLagError("unexpected registry schema or authority")
    if registry.get("no_universal_lag") is not True:
        raise ProductLagError("registry must prohibit universal lag")
    if registry.get("exact_key_fields") != list(KEY_FIELDS):
        raise ProductLagError("registry exact-key fields changed")
    if registry.get("execution_authority") is not False or registry.get("may_update_ng_brain") is not False:
        raise ProductLagError("registry cannot grant authority")
    minimum = int(registry.get("minimum_samples_per_exact_key") or 0)
    if minimum < 1:
        raise ProductLagError("invalid registry minimum sample count")
    groups = registry.get("groups") or []
    if int(registry.get("group_count") or 0) != len(groups):
        raise ProductLagError("registry group count mismatch")
    seen: set[str] = set()
    observations_total = 0
    source_fingerprints: list[str] = []
    prior_key = ""
    for group in groups:
        group_copy = copy.deepcopy(group)
        group_supplied = group_copy.pop("fingerprint", None)
        if group_supplied != _fingerprint(group_copy):
            raise ProductLagError("group fingerprint mismatch")
        key = normalize_key(group.get("key") or {})
        fingerprint = key_fingerprint(key)
        if group.get("key_fingerprint") != fingerprint:
            raise ProductLagError("group key fingerprint mismatch")
        if fingerprint in seen:
            raise ProductLagError("duplicate registry group")
        if prior_key and fingerprint < prior_key:
            raise ProductLagError("registry groups are not deterministic")
        prior_key = fingerprint
        seen.add(fingerprint)
        summaries = group.get("observations") or []
        if int(group.get("total_observations") or 0) != len(summaries):
            raise ProductLagError("group observation count mismatch")
        usable = [row for row in summaries if row.get("usable") is True]
        if int(group.get("usable_observations") or 0) != len(usable):
            raise ProductLagError("group usable count mismatch")
        expected_status = MEASURED if len(usable) >= minimum else NO_WINDOW
        if group.get("status") != expected_status:
            raise ProductLagError("group status contradicts sample count")
        previous_time = -math.inf
        for summary in summaries:
            event_time = _finite(summary.get("leader_event_s"), "leader_event_s")
            if event_time < previous_time:
                raise ProductLagError("group observations are not chronological")
            previous_time = event_time
            source_fingerprints.append(_clean_text(summary.get("observation_fingerprint"), "observation_fingerprint"))
        observations_total += len(summaries)
    if int(registry.get("observation_count") or 0) != observations_total:
        raise ProductLagError("registry observation count mismatch")
    if registry.get("source_observation_fingerprints") != source_fingerprints:
        raise ProductLagError("registry observation fingerprint order mismatch")
    expected = _fingerprint(registry)
    if supplied != expected:
        raise ProductLagError("registry fingerprint mismatch")
    registry["fingerprint"] = expected
    return registry


def lookup_lag(
    registry_raw: Mapping[str, Any],
    *,
    key: Mapping[str, Any],
    as_of_s: float,
    minimum_samples: int | None = None,
) -> dict[str, Any]:
    """Return an exact-key pre-cutoff lag window or ``NO_MEASURED_WINDOW``."""
    registry = validate_registry(registry_raw)
    cutoff = _finite(as_of_s, "as_of_s")
    clean_key = normalize_key(key)
    fingerprint = key_fingerprint(clean_key)
    required = int(minimum_samples or registry["minimum_samples_per_exact_key"])
    if required < 1:
        raise ProductLagError("minimum_samples must be positive")
    matched = next((group for group in registry["groups"] if group["key_fingerprint"] == fingerprint), None)
    reasons: list[str] = []
    eligible: list[dict[str, Any]] = []
    total_exact = 0
    if matched is None:
        reasons.append("NO_EXACT_KEY_HISTORY")
    else:
        total_exact = len(matched.get("observations") or [])
        eligible = [
            row
            for row in matched.get("observations") or []
            if row.get("usable") is True and float(row["leader_event_s"]) < cutoff
        ]
        if len(eligible) < required:
            reasons.append("INSUFFICIENT_PRE_CUTOFF_SAMPLES")
    status = MEASURED if matched is not None and len(eligible) >= required else NO_WINDOW
    first_values = [float(row["first_reprice_lag_ms"]) for row in eligible]
    completion_values = [float(row["completion_lag_ms"]) for row in eligible if row.get("completion_lag_ms") is not None]
    output: dict[str, Any] = {
        "schema": LOOKUP_SCHEMA,
        "authority": AUTHORITY,
        "status": status,
        "key": clean_key,
        "key_fingerprint": fingerprint,
        "as_of_s": cutoff,
        "strictly_pre_cutoff": True,
        "minimum_samples": required,
        "exact_key_observations": total_exact,
        "eligible_pre_cutoff_observations": len(eligible),
        "first_reprice_window": _distribution(first_values) if status == MEASURED else None,
        "completion_window": _distribution(completion_values) if status == MEASURED else None,
        "reasons": reasons,
        "observation_fingerprints": [row["observation_fingerprint"] for row in eligible],
        "registry_fingerprint": registry["fingerprint"],
        "fallback_used": False,
        "execution_authority": False,
        "may_update_ng_brain": False,
    }
    output["fingerprint"] = _fingerprint(output)
    return output


def validate_lookup(raw: Mapping[str, Any]) -> dict[str, Any]:
    output = copy.deepcopy(dict(raw))
    supplied = output.pop("fingerprint", None)
    if output.get("schema") != LOOKUP_SCHEMA or output.get("authority") != AUTHORITY:
        raise ProductLagError("unexpected lookup schema or authority")
    if output.get("status") not in {MEASURED, NO_WINDOW}:
        raise ProductLagError("invalid lookup status")
    if output.get("strictly_pre_cutoff") is not True or output.get("fallback_used") is not False:
        raise ProductLagError("lookup must remain exact-key and pre-cutoff")
    if output.get("execution_authority") is not False or output.get("may_update_ng_brain") is not False:
        raise ProductLagError("lookup cannot grant authority")
    key = normalize_key(output.get("key") or {})
    if output.get("key_fingerprint") != key_fingerprint(key):
        raise ProductLagError("lookup key fingerprint mismatch")
    _finite(output.get("as_of_s"), "as_of_s")
    eligible = int(output.get("eligible_pre_cutoff_observations") or 0)
    minimum = int(output.get("minimum_samples") or 0)
    if output.get("status") == MEASURED:
        if eligible < minimum or output.get("first_reprice_window") is None:
            raise ProductLagError("measured lookup lacks sufficient window")
        if output.get("reasons"):
            raise ProductLagError("measured lookup cannot carry failure reasons")
    else:
        if output.get("first_reprice_window") is not None or output.get("completion_window") is not None:
            raise ProductLagError("NO_MEASURED_WINDOW cannot expose a lag window")
        if not output.get("reasons"):
            raise ProductLagError("NO_MEASURED_WINDOW requires a reason")
    expected = _fingerprint(output)
    if supplied != expected:
        raise ProductLagError("lookup fingerprint mismatch")
    output["fingerprint"] = expected
    return output


def atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _load_observations(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() in {".jsonl", ".ndjson"}:
        rows = []
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as error:
                    raise ProductLagError(f"{path}:{line_number}: {error}") from error
        return rows
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    return list(payload.get("observations") or [])


def selftest() -> int:
    key = {
        "venue": "kalshi",
        "product": "NG event contract",
        "series": "KXNG",
        "contract": "KXNG-26MAR18",
        "strike": "3.25",
        "liquidity_bucket": "medium",
        "move_size_bucket": "small",
        "time_of_day_bucket": "us_morning",
        "regime": "shoulder_contango",
    }
    quality = {
        "leader_event_valid": True,
        "follower_event_valid": True,
        "exact_definition_match": True,
        "sequence_complete": True,
        "executable_book_observed": True,
    }
    observations = [
        make_observation(
            observation_id=f"o{index}",
            key=key,
            leader_event_s=float(index * 10),
            follower_first_reprice_s=float(index * 10) + 0.1 + index * 0.01,
            follower_completion_s=float(index * 10) + 0.4 + index * 0.01,
            quality=quality,
        )
        for index in range(1, 7)
    ]
    registry = build_registry(observations, min_samples=5)
    measured = lookup_lag(registry, key=key, as_of_s=100.0)
    assert measured["status"] == MEASURED
    missing = dict(key)
    missing["liquidity_bucket"] = "thin"
    no_window = lookup_lag(registry, key=missing, as_of_s=100.0)
    assert no_window["status"] == NO_WINDOW
    assert no_window["fallback_used"] is False
    validate_lookup(measured)
    print("[ng_product_lag] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and query exact-key NG product lag windows")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--observations", type=Path, required=True)
    build_parser.add_argument("--minimum-samples", type=int, default=5)
    build_parser.add_argument("--out", type=Path, required=True)

    lookup_parser = subparsers.add_parser("lookup")
    lookup_parser.add_argument("--registry", type=Path, required=True)
    lookup_parser.add_argument("--key", type=Path, required=True)
    lookup_parser.add_argument("--as-of-s", type=float, required=True)
    lookup_parser.add_argument("--minimum-samples", type=int)
    lookup_parser.add_argument("--out", type=Path, required=True)

    subparsers.add_parser("selftest")
    args = parser.parse_args()
    if args.command == "selftest":
        return selftest()
    if args.command == "build":
        registry = build_registry(_load_observations(args.observations), min_samples=args.minimum_samples)
        atomic_json(args.out, registry)
        print(json.dumps({"status": "ok", "groups": registry["group_count"], "out": str(args.out)}, indent=2))
        return 0
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    key = json.loads(args.key.read_text(encoding="utf-8"))
    output = lookup_lag(
        registry,
        key=key,
        as_of_s=args.as_of_s,
        minimum_samples=args.minimum_samples,
    )
    atomic_json(args.out, output)
    print(json.dumps({"status": output["status"], "out": str(args.out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
