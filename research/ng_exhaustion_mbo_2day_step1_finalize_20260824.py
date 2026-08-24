#!/usr/bin/env python3
"""Score the authorized October 4-5 Step-1 diagnostic from the completed seconds child.

This adapter performs no raw-MBO replay and no provider call.  It uses the
frozen Step-1 detector, feature transform, model families, loss, incremental
gain, family classifier, lineage, population, and crosswalk code.  The sole
user-authorized methodological exception is explicit: the two-day sample is
fit and scored on itself instead of using the frozen 52-week out-of-time split.
The results are diagnostic and are never compared with 54-week answer labels.
"""
from __future__ import annotations

import argparse
import gc
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np

import ng_exhaustion_mbo_5y_step1_census_20260822 as base


SCHEMA = "NG_EXHAUSTION_MBO_2DAY_STEP1_RECONCILIATION_V1_20260824"
DIAGNOSTIC_ADAPTER_REVISION = SCHEMA
DIAGNOSTIC_ADAPTER_PATH = "research/ng_exhaustion_mbo_2day_step1_finalize_20260824.py"
STATUS = "STEP1_DUAL_STRUCTURAL_CENSUS_COMPLETE_TWO_DAY_DIAGNOSTIC"
OCTOBER_SEGMENT = "20211001_20211101"
WINDOW_START_ISO = "2021-10-04T00:00:00Z"
WINDOW_END_ISO = "2021-10-06T00:00:00Z"
WINDOW_START_EPOCH = int(datetime(2021, 10, 4, tzinfo=timezone.utc).timestamp())
WINDOW_END_EPOCH = int(datetime(2021, 10, 6, tzinfo=timezone.utc).timestamp())
VALIDATION_STATUS = "USER_AUTHORIZED_SELF_FIT_SELF_SCORE_DIAGNOSTIC_ACCEPTED"
METHOD_EXCEPTION = "REPLACE_52_WEEK_OUT_OF_TIME_SPLIT_WITH_TWO_DAY_SELF_FIT_SELF_SCORE"
EXPECTED_PARENT_MANIFEST_SHA256 = (
    "5739bce85d9bfbbe6c59d000bc411b424d7752b98a309725161d44e6d1d3dc2e"
)


@dataclass(frozen=True)
class ExpectedOctoberIdentity:
    seconds_bytes: int
    seconds_sha256: str
    receipt_file_sha256: str
    receipt_sha256: str


VERIFIED_OCTOBER_IDENTITY = ExpectedOctoberIdentity(
    seconds_bytes=112_852_940,
    seconds_sha256="93654eb5eaf24be6dc6821f422cdd7fc416e12778dcecd6c97150cbc34004f90",
    receipt_file_sha256="80b6cf7199805cf40a0b16b139ee1aa8f705b884acf03856640df4054802f7ab",
    receipt_sha256="4966dac8b25fee7acabf53f880a30155985bd5767ee222381f1188d4eecada3c",
)

# Direct identity aliases prove the adapter does not substitute detector,
# feature, lineage, or crosswalk implementations.
FROZEN_DETECT_EVENTS = base.detect_events_for_week
FROZEN_COMPACT_LINEAGE = base.compact_lineage_input
FROZEN_BEHAVIOR_VECTOR = base.frozen_discovery.behavior_vector
FROZEN_BUILD_CROSSWALK = base.build_crosswalk


def _diagnostic_adapter_binding() -> dict[str, str]:
    path = Path(DIAGNOSTIC_ADAPTER_PATH)
    if not path.is_file():
        raise base.CensusError("diagnostic adapter source is missing")
    return {
        "path": DIAGNOSTIC_ADAPTER_PATH,
        "revision": DIAGNOSTIC_ADAPTER_REVISION,
        "sha256": base.sha256_file(path),
    }


def _relative_output(output: dict[str, Any], out: Path) -> dict[str, Any]:
    result = dict(output)
    result["relative_path"] = Path(str(result["path"])).resolve().relative_to(
        out.resolve()
    ).as_posix()
    return result


def _json_artifact(path: Path, out: Path) -> dict[str, Any]:
    return {
        "relative_path": path.resolve().relative_to(out.resolve()).as_posix(),
        "rows": 1,
        "bytes": path.stat().st_size,
        "sha256": base.sha256_file(path),
    }


def validate_october_child(
    parent_manifest_path: str | Path,
    seconds_path: str | Path,
    receipt_path: str | Path,
    *,
    expected_identity: ExpectedOctoberIdentity = VERIFIED_OCTOBER_IDENTITY,
) -> dict[str, Any]:
    """Fail closed unless the exact completed October child is present."""
    parent_manifest_path = Path(parent_manifest_path)
    seconds_path = Path(seconds_path)
    receipt_path = Path(receipt_path)
    if not seconds_path.is_file() or not receipt_path.is_file():
        raise base.CensusError("validated October seconds child or receipt is missing")
    if seconds_path.stat().st_size != expected_identity.seconds_bytes:
        raise base.CensusError("October seconds byte drift")
    if base.sha256_file(seconds_path) != expected_identity.seconds_sha256:
        raise base.CensusError("October seconds SHA-256 drift")
    if base.sha256_file(receipt_path) != expected_identity.receipt_file_sha256:
        raise base.CensusError("October receipt file SHA-256 drift")

    manifest = base.load_manifest(parent_manifest_path)
    if manifest.get("manifest_sha256") != EXPECTED_PARENT_MANIFEST_SHA256:
        raise base.CensusError("parent canonical manifest identity drift")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    claimed = receipt.get("receipt_sha256")
    body = dict(receipt)
    body.pop("receipt_sha256", None)
    if claimed != expected_identity.receipt_sha256 or claimed != base.sha256_json(body):
        raise base.CensusError("October canonical receipt SHA-256 drift")
    expected_scope = base._segment_source_scope(manifest, OCTOBER_SEGMENT, None)
    expected_objects = [
        {key: row[key] for key in ("key", "bytes", "sha256", "native_segment_job_id")}
        for row in base._segment_objects(manifest, OCTOBER_SEGMENT, None)
    ]
    checks = (
        (receipt.get("schema") == "NG_EXHAUSTION_MBO_5Y_STEP1_SEGMENT_RECEIPT_V1", "schema"),
        (receipt.get("status") == "SEGMENT_COMPLETE", "completion status"),
        (receipt.get("segment") == OCTOBER_SEGMENT, "segment"),
        (receipt.get("source_manifest_sha256") == manifest["manifest_sha256"], "manifest"),
        (receipt.get("source_scope") == expected_scope, "source scope"),
        (receipt.get("source_object_count") == len(expected_objects), "object count"),
        (receipt.get("source_objects") == expected_objects, "object roster"),
        (receipt.get("engine_hashes") == base.material_hashes(), "engine hashes"),
        (receipt.get("ruleset_sha256") == base.ruleset_sha256(), "ruleset"),
        (receipt.get("case_retention_policy") == base.RULESET, "retention policy"),
        (receipt.get("release_or_virgin_holdout_consumed") is False, "holdout wall"),
        (receipt.get("predictive_or_trading_experiment_run") is False, "experiment wall"),
        (
            (receipt.get("seconds_output") or {}).get("gzip_sha256")
            == expected_identity.seconds_sha256,
            "seconds output hash",
        ),
    )
    for passed, label in checks:
        if not passed:
            raise base.CensusError(f"October child {label} drift")
    if int((receipt.get("seconds_output") or {}).get("rows", 0)) <= 0:
        raise base.CensusError("October child seconds row count is absent")
    return receipt


def iter_two_day_seconds(seconds_path: str | Path) -> Iterable[dict[str, Any]]:
    """Stream the exact authorized half-open interval from the verified child."""
    prior = None
    for row in base.read_gzip_jsonl(seconds_path):
        second = int(row["epoch_second"])
        if prior is not None and second <= prior:
            raise base.CensusError("October seconds are not strictly increasing")
        prior = second
        if WINDOW_START_EPOCH <= second < WINDOW_END_EPOCH:
            yield row


def _self_fit_model(
    model: str,
    week: str,
    byweek: dict[str, list[dict[str, Any]]],
    arrays: dict[str, np.ndarray],
    valid: dict[str, np.ndarray],
    depth: int,
    history_len: int,
) -> dict[str, Any] | None:
    """Use frozen matrices/scaling/model/loss with train == score sample."""
    engine = base.frozen_structural
    X, Y, meta = engine.matrices(
        [week], byweek, arrays, valid, depth, history_len
    )
    if not len(Y):
        return None
    Xz, Yz, Xscore, Yscore = engine.scale_pair(X, Y, X, Y, history_len)
    if history_len == 0:
        parameter = None
        prediction = np.zeros_like(Yscore)
    else:
        candidates = []
        for candidate in engine.grid(model):
            predicted = engine.fit_predict(
                model, candidate, Xz, Yz, Xscore, inner=True
            )
            loss = np.mean((Yscore - predicted) ** 2, axis=1)
            candidates.append((float(loss.mean()), float(candidate), candidate))
        _, _, parameter = min(candidates)
        prediction = engine.fit_predict(
            model, parameter, Xz, Yz, Xscore, inner=False
        )
    loss = np.mean((Yscore - prediction) ** 2, axis=1)
    return {
        "param": parameter,
        "loss": loss,
        "meta": meta,
        "n": int(len(loss)),
        "mse": float(loss.mean()),
    }


def _load_lineage_view(
    lineage_input_path: str | Path,
    feature_view: str,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, np.ndarray], dict[str, np.ndarray]]:
    if feature_view == "full":
        return base._load_lineage_inputs(lineage_input_path)
    if feature_view != "sparse":
        raise base.CensusError(f"unknown structural feature view: {feature_view}")
    byweek: dict[str, list[dict[str, Any]]] = defaultdict(list)
    vectors: dict[str, list[list[float]]] = defaultdict(list)
    for row in base.read_gzip_jsonl(lineage_input_path):
        week = str(row["week_sunday"])
        full = list(row.pop("behavior_vector_full"))
        if len(full) != 22:
            raise base.CensusError("frozen full behavior vector dimension drift")
        # Frozen sparse behavior_vector is next_same plus the seven signed
        # displacement horizons, exactly the first eight full-path fields.
        vectors[week].append(full[:8])
        byweek[week].append(row)
    arrays: dict[str, np.ndarray] = {}
    valid: dict[str, np.ndarray] = {}
    for week, rows in byweek.items():
        rows.sort(key=lambda row: int(row["sequence_index"]))
        if [int(row["sequence_index"]) for row in rows] != list(range(len(rows))):
            raise base.CensusError(f"non-contiguous sparse event sequence: {week}")
        array = np.asarray(vectors[week], dtype=float)
        ok = np.all(np.isfinite(array), axis=1)
        transformed = array.copy()
        transformed[:, 1:] = np.arcsinh(transformed[:, 1:])
        arrays[week] = transformed
        valid[week] = ok
    return dict(byweek), arrays, valid


def self_fit_structural_scores(
    lineage_input_path: str | Path,
    view: str,
    gain_output_path: str | Path | None,
    *,
    feature_view: str = "full",
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Score D1-D5 with the frozen models under the authorized self-score exception."""
    byweek, arrays, valid = _load_lineage_view(lineage_input_path, feature_view)
    weeks = sorted(byweek)
    if len(weeks) != 1:
        raise base.CensusError(f"two-day diagnostic must contain exactly one week: {weeks}")
    week = weeks[0]
    models = tuple(base.frozen_structural.MODELS)
    model_index = {model: index for index, model in enumerate(models)}
    gains = {
        week: np.full(
            (len(byweek[week]), base.MAX_DEPTH, len(models)),
            np.nan,
            dtype=np.float64,
        )
    }
    depth_results: dict[str, Any] = {}
    writer = (
        None
        if gain_output_path is None
        else base.DeterministicGzipJsonlWriter(Path(gain_output_path))
    )
    try:
        for depth in range(1, base.MAX_DEPTH + 1):
            depth_results[str(depth)] = {}
            for model in models:
                short = _self_fit_model(
                    model, week, byweek, arrays, valid, depth, depth - 1
                )
                long = _self_fit_model(
                    model, week, byweek, arrays, valid, depth, depth
                )
                if short is None or long is None:
                    depth_results[str(depth)][model] = {"n": 0, "gain_mean": None}
                    continue
                if short["meta"] != long["meta"]:
                    raise base.CensusError(
                        f"self-fit paired-sample invariant failed model={model} depth={depth}"
                    )
                incremental_gain = short["loss"] - long["loss"]
                per_week = []
                for gain, (target_week, target_index, event_id) in zip(
                    incremental_gain, short["meta"]
                ):
                    gains[target_week][
                        int(target_index), depth - 1, model_index[model]
                    ] = float(gain)
                    per_week.append(float(gain))
                    if writer is not None:
                        writer.write(
                            {
                                "fold": "user_authorized_two_day_self_fit_self_score",
                                "week_sunday": target_week,
                                "sequence_index": int(target_index),
                                "target_event_id": event_id,
                                "model": model,
                                "depth": depth,
                                "incremental_gain": float(gain),
                                "view": view,
                            }
                        )
                depth_results[str(depth)][model] = {
                    "short_param": short["param"],
                    "long_param": long["param"],
                    "n": int(len(incremental_gain)),
                    "gain_mean": float(incremental_gain.mean()),
                    "gain_median": float(np.median(incremental_gain)),
                    "gain_positive_rate": float(np.mean(incremental_gain > 0)),
                    "short_mse": short["mse"],
                    "long_mse": long["mse"],
                    "per_week_gain_mean": {week: float(np.mean(per_week))},
                }
        gain_output = None if writer is None else writer.close()
    except Exception:
        if writer is not None:
            writer.abort()
        raise
    fold = {
        "train_weeks": [week],
        "test_weeks": [week],
        "depth": depth_results,
        "validation_exception": METHOD_EXCEPTION,
    }
    summary = {
        "dimension": int(next(iter(arrays.values())).shape[1]),
        "valid_events_by_week": {week: int(valid[week].sum())},
        "folds": {"user_authorized_two_day_self_fit_self_score": fold},
        "depth": depth_results,
        "gain_output": gain_output,
        "out_of_time_validation_claimed": False,
        "diagnostic_validation_status": VALIDATION_STATUS,
        "feature_view": feature_view,
    }
    return gains, summary


def _diagnostic_aggregate(primary: dict[str, Any]) -> dict[str, Any]:
    """Retain the 54w aggregate fields without inventing OOT eras."""
    aggregate: dict[str, Any] = {}
    for depth in range(1, base.MAX_DEPTH + 1):
        by_model = {}
        for model in base.frozen_structural.MODELS:
            score = primary["depth"][str(depth)][model]
            by_model[model] = {
                "discovery_era_gains": [],
                "discovery_eras_positive": 0,
                "discovery_era_count": 0,
                "discovery_week_positive_rate": None,
                "confirmation_gain_mean": None,
                "confirmation_per_week_gain_mean": {},
                "diagnostic_self_fit_gain_mean": score.get("gain_mean"),
                "diagnostic_self_fit_gain_positive_rate": score.get(
                    "gain_positive_rate"
                ),
                "diagnostic_self_fit_n": score.get("n", 0),
            }
        aggregate[str(depth)] = by_model
    return aggregate


def self_fit_lineage_population(
    lineage_input_path: str | Path,
    view: str,
    hashes: dict[str, str],
    gains: dict[str, np.ndarray],
    structural_depth: dict[str, Any],
    population_path: str | Path,
    index_path: str | Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Apply the frozen consecutive all-three-positive D0-D5 population rule."""
    byweek, _arrays, _valid = base._load_lineage_inputs(lineage_input_path)
    models = tuple(base.frozen_structural.MODELS)
    adapter_binding = _diagnostic_adapter_binding()
    model_index = {model: index for index, model in enumerate(models)}
    population_writer = base.DeterministicGzipJsonlWriter(Path(population_path))
    index_writer = base.DeterministicGzipJsonlWriter(Path(index_path))
    retained = Counter()
    family_counts = Counter()
    try:
        for week in sorted(byweek):
            rows = byweek[week]
            week_gains = gains[week]
            for origin in rows:
                index = int(origin["sequence_index"])
                evidence: dict[str, Any] = {}
                depth = 0
                unavailable_reasons = []
                for candidate_depth in range(1, base.MAX_DEPTH + 1):
                    values = {}
                    for model in models:
                        value = (
                            float(
                                week_gains[
                                    index + candidate_depth,
                                    candidate_depth - 1,
                                    model_index[model],
                                ]
                            )
                            if index + candidate_depth < len(rows)
                            else float("nan")
                        )
                        values[model] = value if math.isfinite(value) else None
                    evidence[str(candidate_depth)] = values
                    if all(value is not None and value > 0 for value in values.values()):
                        depth = candidate_depth
                        continue
                    if all(value is None for value in values.values()):
                        unavailable_reasons.append(
                            f"D{candidate_depth}_NO_SCORED_DESCENDANT_IN_TWO_DAY_WINDOW"
                        )
                    elif any(value is None for value in values.values()):
                        unavailable_reasons.append(
                            f"D{candidate_depth}_INCOMPLETE_SELF_FIT_MODEL_EVIDENCE"
                        )
                    break
                members = rows[index : min(len(rows), index + depth + 1)]
                reset = rows[index + depth + 1] if index + depth + 1 < len(rows) else None
                causal_links = []
                for left, right in zip(members, members[1:]):
                    confirmation = left.get("causal_confirmation_idx")
                    causal_links.append(
                        {
                            "predecessor_event_id": left["event_id"],
                            "successor_event_id": right["event_id"],
                            "predecessor_confirmation_idx": confirmation,
                            "successor_t0_idx": right["t0_idx"],
                            "predecessor_information_known_before_successor": (
                                None
                                if confirmation is None
                                else int(confirmation) < int(right["t0_idx"])
                            ),
                        }
                    )
                elapsed = (
                    None
                    if len(members) < 2
                    else int(members[-1]["t0_idx"]) - int(members[0]["t0_idx"])
                )
                chain_seed = f"{view}|{week}|{origin['event_id']}"
                chain_id = base.hashlib.sha256(chain_seed.encode()).hexdigest()
                provenance = origin.get("source_provenance") or {}
                integrity_reasons = list(unavailable_reasons)
                if not provenance.get("source_dbn_key") or not provenance.get("source_dbn_sha256"):
                    integrity_reasons.append("SOURCE_OBJECT_PROVENANCE_UNRESOLVED")
                if provenance.get("contract_resolution_status") != "RESOLVED_FROM_DBN_METADATA":
                    integrity_reasons.append("RAW_CONTRACT_UNRESOLVED_RETAINED")
                native_integrity = (
                    (origin.get("native_structure") or {}).get("integrity_at_t0") or {}
                )
                if native_integrity:
                    integrity_reasons.append("NATIVE_REPLAY_INTEGRITY_COUNTER_PRESENT")
                row = {
                    "schema": "NG_EXHAUSTION_STEP1_POPULATION_CASE_V1_20260822",
                    "census_view": view,
                    "chain_id": chain_id,
                    "chain_origin_event_id": origin["event_id"],
                    "week_sunday": week,
                    "origin_sequence_index": index,
                    "ordered_member_event_ids": [item["event_id"] for item in members],
                    "ordered_ancestry": [item["event_id"] for item in members[:-1]],
                    "predecessor_event_id": origin.get("previous_event_id"),
                    "successor_event_id": origin.get("next_event_id"),
                    "realized_structural_depth": depth,
                    "legacy_d_label": f"D{depth}" if view == "LEGACY_CONTROL" else None,
                    "native_taxonomy_labels": (
                        [
                            (item.get("native_structure") or {}).get("label")
                            for item in members
                        ]
                        if view == "V4_NATIVE_FULL"
                        else None
                    ),
                    "reset_event_id": None if reset is None else reset["event_id"],
                    "reset_boundary_status": (
                        "CENSORED_TWO_DAY_END" if reset is None else "REALIZED_NEXT_EVENT"
                    ),
                    "elapsed_time_seconds": elapsed,
                    "inherited_information_evidence": evidence,
                    "inherited_information_uncertainty": unavailable_reasons,
                    "causal_executable_availability": causal_links,
                    "censored": bool(reset is None or origin.get("source_boundary_censored")),
                    "unresolved": bool(integrity_reasons),
                    "short_long_state": "UNDECLARED_STRUCTURAL_CENSUS_ONLY",
                    "source_provenance": provenance,
                    "adapter_revision": base.ADAPTER_REVISION,
                    "diagnostic_adapter": adapter_binding,
                    "engine_hashes": hashes,
                    "ruleset_sha256": base.ruleset_sha256(),
                    "integrity_reasons": integrity_reasons,
                    "retention_policy": base.RULESET,
                    "diagnostic_validation_status": VALIDATION_STATUS,
                }
                population_writer.write(row)
                index_writer.write(
                    {
                        "event_id": origin["event_id"],
                        "week_sunday": week,
                        "t0_idx": int(origin["t0_idx"]),
                        "polarity": int(origin["polarity"]),
                        "family": origin.get("family"),
                        "chain_id": chain_id,
                        "realized_structural_depth": depth,
                        "reset_event_id": None if reset is None else reset["event_id"],
                        "unresolved": bool(integrity_reasons),
                    }
                )
                retained["all_cases"] += 1
                retained["unresolved" if integrity_reasons else "resolved"] += 1
                retained["censored" if row["censored"] else "uncensored"] += 1
                family_counts[str(origin.get("family"))] += 1
        population_output = population_writer.close()
        index_output = index_writer.close()
    except Exception:
        population_writer.abort()
        index_writer.abort()
        raise
    histogram = Counter()
    for row in base.read_gzip_jsonl(index_path):
        histogram[int(row["realized_structural_depth"])] += 1
    summary = {
        "view": view,
        "event_count": retained["all_cases"],
        "population_count": retained["all_cases"],
        "case_retention_exact": True,
        "depth_histogram": {depth: histogram[depth] for depth in range(0, base.MAX_DEPTH + 1)},
        "family_histogram": dict(sorted(family_counts.items())),
        "retention_counts": dict(retained),
        "folds": [
            {
                "fold": "user_authorized_two_day_self_fit_self_score",
                "train_week_count": 1,
                "test_weeks": sorted(byweek),
                "depth": structural_depth,
            }
        ],
        "frozen_lineage_binding": {
            "discovery_module": "research/ng_exhaustion_chain_phase1_discovery_20260817.py",
            "structural_module": "research/ng_exhaustion_chain_phase1_structural_54w_20260817.py",
            "models": list(models),
            "maximum_depth": base.MAX_DEPTH,
        },
        "diagnostic_validation_status": VALIDATION_STATUS,
        "out_of_time_validation_claimed": False,
        "diagnostic_adapter": adapter_binding,
    }
    return population_output, summary, index_output


def _prepare_output(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise base.CensusError("two-day output directory must be new or empty")
    path.mkdir(parents=True, exist_ok=True)


def _family_counts(path: Path) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get("family")) for row in base.read_gzip_jsonl(path)).items()))


def finalize_two_day_step1(
    parent_manifest_path: str | Path,
    seconds_path: str | Path,
    receipt_path: str | Path,
    out_dir: str | Path,
    *,
    expected_identity: ExpectedOctoberIdentity = VERIFIED_OCTOBER_IDENTITY,
) -> dict[str, Any]:
    """Finalize and score the exact two-day diagnostic from the verified child."""
    parent_manifest_path = Path(parent_manifest_path)
    seconds_path = Path(seconds_path)
    receipt_path = Path(receipt_path)
    out = Path(out_dir)
    child = validate_october_child(
        parent_manifest_path,
        seconds_path,
        receipt_path,
        expected_identity=expected_identity,
    )
    _prepare_output(out)
    hashes = base.material_hashes()
    adapter_binding = _diagnostic_adapter_binding()
    selected_rows = list(iter_two_day_seconds(seconds_path))
    if not selected_rows:
        raise base.CensusError("authorized two-day interval contains no Step-1 seconds")
    selected_output = base.deterministic_gzip_jsonl(
        out / "TWO_DAY_SECONDS.jsonl.gz", selected_rows
    )
    selected_output = _relative_output(selected_output, out)

    pre_classifier = base.frozen_detector.FrozenPreFamilyClassifier.load(
        "research/FRANKIE_NG_PRE_FAMILY_CLASSIFIER_FROZEN_OPERATIONAL_20260817.json"
    )
    a_classifier = base.frozen_detector.FrozenAClassifier.load(
        "research/FRANKIE_NG_A_POSTSTATE_CLASSIFIER_FROZEN_PREBLIND_20260816.json"
    )
    event_writers = {
        "legacy": base.DeterministicGzipJsonlWriter(out / "LEGACY_CONTROL_EVENTS.jsonl.gz"),
        "native": base.DeterministicGzipJsonlWriter(out / "V4_NATIVE_FULL_EVENTS.jsonl.gz"),
    }
    lineage_writers = {
        "legacy": base.DeterministicGzipJsonlWriter(
            out / "LEGACY_CONTROL_LINEAGE_INPUTS.jsonl.gz"
        ),
        "native": base.DeterministicGzipJsonlWriter(
            out / "V4_NATIVE_FULL_LINEAGE_INPUTS.jsonl.gz"
        ),
    }
    try:
        for key, view in (("legacy", "LEGACY_CONTROL"), ("native", "V4_NATIVE_FULL")):
            events = FROZEN_DETECT_EVENTS(
                selected_rows, view, pre_classifier, a_classifier
            )
            for event in events:
                event_writers[key].write(event)
                lineage_writers[key].write(FROZEN_COMPACT_LINEAGE(event))
        event_outputs = {
            key: _relative_output(writer.close(), out)
            for key, writer in event_writers.items()
        }
        lineage_outputs = {
            key: _relative_output(writer.close(), out)
            for key, writer in lineage_writers.items()
        }
    except Exception:
        for writer in [*event_writers.values(), *lineage_writers.values()]:
            writer.abort()
        raise
    if not event_outputs["legacy"]["rows"] or not event_outputs["native"]["rows"]:
        raise base.CensusError("two-day detector produced an empty dual-view event population")

    structural_outputs = {}
    gain_arrays = {}
    for key, view, prefix in (
        ("legacy", "LEGACY_CONTROL", "LEGACY_CONTROL"),
        ("native", "V4_NATIVE_FULL", "V4_NATIVE_FULL"),
    ):
        gains, structural = self_fit_structural_scores(
            out / lineage_outputs[key]["relative_path"],
            view,
            out / f"{prefix}_SELF_FIT_GAINS.jsonl.gz",
            feature_view="full",
        )
        _sparse_gains, sparse = self_fit_structural_scores(
            out / lineage_outputs[key]["relative_path"],
            view,
            None,
            feature_view="sparse",
        )
        structural["gain_output"] = _relative_output(structural["gain_output"], out)
        aggregate = _diagnostic_aggregate(structural)
        summary_path = out / f"{prefix}_STRUCTURAL_SELF_FIT_SUMMARY.json"
        base.atomic_json(
            summary_path,
            {
                "status": "PHASE1_STRUCTURAL_TWO_DAY_DIAGNOSTIC_COMPLETE",
                "source_engine": "research/ng_exhaustion_chain_phase1_discovery_20260817.py",
                "week_count": 1,
                "weeks": ["20211003"],
                "characteristics_accessed": False,
                "primary_full_path": structural,
                "sparse_sensitivity": sparse,
                "aggregate": aggregate,
                "out_of_time_gain_table": None,
                "self_fit_gain_table": structural["gain_output"]["relative_path"],
                "historical_phase1_complete": False,
                "phase2_allowed": False,
                "runway_clock_mutated": False,
                "permanent_frankie_mutated": False,
                "diagnostic_validation_status": VALIDATION_STATUS,
                "only_methodological_exception": METHOD_EXCEPTION,
                "comparison_to_54w_answers_performed": False,
                "frozen_science_revision": base.REVISION,
                "diagnostic_adapter": adapter_binding,
            },
        )
        structural = {
            **structural,
            "sparse_sensitivity": sparse,
            "aggregate": aggregate,
            "summary_output": _json_artifact(summary_path, out),
        }
        gain_arrays[key] = gains
        structural_outputs[key] = structural

    population_outputs = {}
    population_summaries = {}
    crosswalk_indices = {}
    for key, view, prefix in (
        ("legacy", "LEGACY_CONTROL", "LEGACY_CONTROL"),
        ("native", "V4_NATIVE_FULL", "V4_NATIVE_FULL"),
    ):
        population, summary, index = self_fit_lineage_population(
            out / lineage_outputs[key]["relative_path"],
            view,
            hashes,
            gain_arrays[key],
            structural_outputs[key]["depth"],
            out / f"{prefix}_POPULATION.jsonl.gz",
            out / f"{prefix}_CROSSWALK_INDEX.jsonl.gz",
        )
        population_outputs[key] = _relative_output(population, out)
        population_summaries[key] = summary
        crosswalk_indices[key] = _relative_output(index, out)
        gc.collect()
    crosswalk_output, crosswalk_summary = FROZEN_BUILD_CROSSWALK(
        out / crosswalk_indices["legacy"]["relative_path"],
        out / crosswalk_indices["native"]["relative_path"],
        out / "DUAL_CENSUS_CROSSWALK.jsonl.gz",
    )
    crosswalk_output = _relative_output(crosswalk_output, out)

    bypass = {
        "schema": "NG_EXHAUSTION_TWO_DAY_SELF_FIT_VALIDATION_BYPASS_V1_20260824",
        "status": VALIDATION_STATUS,
        "source_window": {
            "start": WINDOW_START_ISO,
            "end_exclusive": WINDOW_END_ISO,
            "interval_semantics": "HALF_OPEN_START_INCLUSIVE_END_EXCLUSIVE",
        },
        "only_methodological_exception": METHOD_EXCEPTION,
        "unchanged_science": [
            "frozen_detector",
            "22_dimension_behavior_vector",
            "ridge_extra_trees_knn",
            "short_vs_long_squared_loss",
            "incremental_gain_short_minus_long",
            "all_three_positive_consecutive_depth_rule_D0_D5",
            "A_B_C_family_annotation",
            "dynamic_endpoints",
            "lineage_ancestry_reset",
            "legacy_native_crosswalk",
        ],
        "out_of_time_validation_claimed": False,
        "self_fit_self_score_results_accepted_for_this_diagnostic": True,
        "comparison_to_54w_answers_performed": False,
        "old_output_labels_used_as_expected_answers": False,
        "artifact_namespace_difference": (
            "SELF_FIT replaces OOT in two gain/summary filenames so the normal "
            "scientific row fields are retained without falsely claiming out-of-time validation"
        ),
        "frozen_science_revision": base.REVISION,
        "diagnostic_adapter": adapter_binding,
    }
    bypass["receipt_sha256"] = base.sha256_json(bypass)
    bypass_path = out / "TWO_DAY_VALIDATION_BYPASS_RECEIPT.json"
    base.atomic_json(bypass_path, bypass)

    source_manifest = {
        "schema": "NG_EXHAUSTION_MBO_2DAY_STEP1_SOURCE_MANIFEST_V1_20260824",
        "source_window": bypass["source_window"],
        "parent_manifest_sha256": EXPECTED_PARENT_MANIFEST_SHA256,
        "parent_manifest_file_sha256": base.sha256_file(parent_manifest_path),
        "october_segment": OCTOBER_SEGMENT,
        "october_seconds_bytes": expected_identity.seconds_bytes,
        "october_seconds_sha256": expected_identity.seconds_sha256,
        "october_receipt_file_sha256": expected_identity.receipt_file_sha256,
        "october_receipt_sha256": expected_identity.receipt_sha256,
        "october_source_objects": child["source_objects"],
        "october_source_object_count": child["source_object_count"],
        "october_source_scope": child["source_scope"],
        "selected_seconds": selected_output,
        "raw_mbo_replayed": False,
        "diagnostic_adapter": adapter_binding,
    }
    source_manifest["manifest_sha256"] = base.sha256_json(source_manifest)
    source_manifest_path = out / "TWO_DAY_SOURCE_MANIFEST.json"
    base.atomic_json(source_manifest_path, source_manifest)

    receipt = {
        "schema": SCHEMA,
        "status": STATUS,
        "revision": base.REVISION,
        "frozen_science_revision": base.REVISION,
        "diagnostic_adapter_revision": DIAGNOSTIC_ADAPTER_REVISION,
        "diagnostic_adapter": adapter_binding,
        "source_window": bypass["source_window"],
        "source_manifest": _json_artifact(source_manifest_path, out),
        "selected_seconds": selected_output,
        "event_counts": {
            "legacy": event_outputs["legacy"]["rows"],
            "native": event_outputs["native"]["rows"],
        },
        "family_counts": {
            "legacy": _family_counts(out / event_outputs["legacy"]["relative_path"]),
            "native": _family_counts(out / event_outputs["native"]["relative_path"]),
        },
        "event_outputs": event_outputs,
        "lineage_input_outputs": lineage_outputs,
        "structural_outputs": structural_outputs,
        "population_outputs": population_outputs,
        "crosswalk_index_outputs": crosswalk_indices,
        "legacy_population_summary": population_summaries["legacy"],
        "native_population_summary": population_summaries["native"],
        "crosswalk_output": crosswalk_output,
        "crosswalk_summary": crosswalk_summary,
        "diagnostic_validation": {
            "status": VALIDATION_STATUS,
            "observed_week_count": 1,
            "d0_d5_population_claimable": True,
            "d1_d5_scores_accepted": True,
            "out_of_time_validation_claimed": False,
            "only_methodological_exception": METHOD_EXCEPTION,
            "receipt": _json_artifact(bypass_path, out),
        },
        "comparison_to_54w_answers_performed": False,
        "engine_hashes": hashes,
        "ruleset_sha256": base.ruleset_sha256(),
        "adapter_revision": base.ADAPTER_REVISION,
        "native_taxonomy": base.NATIVE_TAXONOMY,
        "retention_policy": base.RULESET,
        "child_output_reuse": {
            "reused_validated_october_seconds_child": True,
            "raw_mbo_replayed": False,
        },
        "release_or_virgin_holdout_consumed": False,
        "predictive_or_trading_experiment_run": False,
        "provider_llm_called": False,
        "external_provider_model_called": False,
        "local_structural_models_fitted": True,
        "local_structural_model_families": ["ridge", "extra_trees", "knn"],
        "frankie_launched": False,
        "permanent_frankie_mutated": False,
        "frozen_detector_mutated": False,
    }
    receipt["receipt_sha256"] = base.sha256_json(receipt)
    base.atomic_json(out / "STEP1_DUAL_CENSUS_RECEIPT.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--parent-manifest",
        default="research/kalshi/NG_EXHAUSTION_MBO_5Y_CANONICAL_OBJECT_MANIFEST_20260822.json",
    )
    parser.add_argument("--october-seconds", required=True)
    parser.add_argument("--october-receipt", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    receipt = finalize_two_day_step1(
        args.parent_manifest,
        args.october_seconds,
        args.october_receipt,
        args.out_dir,
    )
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "source_window": receipt["source_window"],
                "event_counts": receipt["event_counts"],
                "family_counts": receipt["family_counts"],
                "legacy_depth_histogram": receipt["legacy_population_summary"][
                    "depth_histogram"
                ],
                "native_depth_histogram": receipt["native_population_summary"][
                    "depth_histogram"
                ],
                "diagnostic_validation": receipt["diagnostic_validation"]["status"],
                "raw_mbo_replayed": False,
                "provider_llm_called": False,
                "local_structural_models_fitted": True,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
