#!/usr/bin/env python3
"""Corrected two-day Step-1: unchanged legacy control plus direct full-MBO native vectors."""
from __future__ import annotations

import argparse
import json
import math
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

import ng_exhaustion_mbo_2day_step1_finalize_20260824 as prior
import ng_exhaustion_mbo_5y_step1_census_20260822 as base
from ng_exhaustion_mbo_v4_full_state_replay_20260820 import replay_dbn_files

SCHEMA = "NG_EXHAUSTION_MBO_2DAY_FULL_MBO_STEP1_V1_20260825"
STATUS = "STEP1_DUAL_STRUCTURAL_CENSUS_COMPLETE_TWO_DAY_FULL_MBO"
WINDOW_START = prior.WINDOW_START_EPOCH
WINDOW_END = prior.WINDOW_END_EPOCH
RAW_BOOTSTRAP_DATES = ("20211001", "20211003", "20211004", "20211005")
WRAPPER_PATH = "research/ng_exhaustion_mbo_2day_full_mbo_step1_20260825.py"
EXPECTED_BASELINE_RECEIPT_SHA256 = "140c6234b8e6f4216416290aa50f4070160e200a3e7025cbca3aa08d0ef42e52"
EXPECTED_BASELINE_TAR_SHA256 = "27cacc62681bc482e89eefcc3746f5d71958beab4e25816054e0c388a0346b33"
EXPECTED_NATIVE_COUNTS = {"events": 1603, "families": {"A": 1532, "B": 23, "C": 48}}

MBO_FEATURE_NAMES = (
    *(f"second_action_count_{x}" for x in "ACMTFNR"),
    *(f"second_action_qty_{x}" for x in "ACMT"),
    "second_distinct_order_id_count", "second_order_ids_resting_after_count",
    "second_order_ids_resting_after_share", "second_action_bid_qty", "second_action_ask_qty",
    "spread", "depth_imbalance_full", "bid_depth_full", "ask_depth_full",
    "bid_price_level_count_full", "ask_price_level_count_full",
    "bid_order_count_full", "ask_order_count_full",
    "best_bid_queue_order_count", "best_ask_queue_order_count",
    "best_bid_queue_size", "best_ask_queue_size",
    "best_bid_front_order_share", "best_ask_front_order_share",
    "best_bid_front_order_age_s", "best_ask_front_order_age_s",
    "best_bid_queue_age_p90_s", "best_ask_queue_age_p90_s",
    "best_bid_largest_order_share", "best_ask_largest_order_share",
    "activity20_add_qty", "activity20_cancel_qty",
    "activity20_trade_buy_qty", "activity20_trade_sell_qty",
    "activity20_top_add_qty", "activity20_top_cancel_qty",
    "activity20_priority_lost_modify_count", "activity20_missing_reference_count",
    "second_acm_bid_depth_delta", "second_acm_ask_depth_delta",
    "second_replenishment_qty", "second_depletion_qty", "second_replenishment_minus_depletion_ratio",
    "bid_depth_full_delta_from_prior_group", "ask_depth_full_delta_from_prior_group",
    "bid_order_count_full_delta_from_prior_group", "ask_order_count_full_delta_from_prior_group",
    "bid_price_level_count_full_delta_from_prior_group", "ask_price_level_count_full_delta_from_prior_group",
    "best_bid_fifo_retained_order_share", "best_ask_fifo_retained_order_share",
    "best_bid_fifo_front_order_continues", "best_ask_fifo_front_order_continues",
)
FULL_NATIVE_VECTOR_DIMENSION = 22 + len(MBO_FEATURE_NAMES)


def _num(value: Any) -> float:
    try:
        value = float(value)
        return value if math.isfinite(value) else 0.0
    except (TypeError, ValueError, OverflowError):
        return 0.0


class CausalMboCollector:
    """Bind callback-scoped full state to each event's instrument and receive cutoff."""

    def __init__(self, targets: list[dict[str, Any]]) -> None:
        self.targets: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
        for target in targets:
            self.targets[(int(target["instrument_id"]), int(target["cutoff_ts_recv_ns"]) // 1_000_000_000)].append(target)
        self.rows: dict[tuple[int, int], dict[str, Any]] = {}
        self.prior: dict[int, dict[str, Any]] = {}
        self.matches: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _queue(book: Any, side: str, now_ns: int) -> dict[str, Any]:
        best = book.best_price_raw(side)
        ids = [] if best is None else [oid for oid in book.levels[side][best] if oid in book.orders]
        orders = [book.orders[oid] for oid in ids]
        size = sum(int(order.size) for order in orders)
        ages = sorted(max(0.0, (now_ns - int(order.priority_recv_ns)) / 1e9) for order in orders)
        p90 = 0.0 if not ages else ages[min(len(ages) - 1, int(math.ceil(0.9 * len(ages))) - 1)]
        return {"ids": tuple(ids), "count": len(ids), "size": size,
                "front_size": 0 if not orders else int(orders[0].size),
                "front_age": 0.0 if not orders else max(0.0, (now_ns - int(orders[0].priority_recv_ns)) / 1e9),
                "p90_age": p90,
                "largest_share": max((int(order.size) for order in orders), default=0) / size if size else 0.0}

    @classmethod
    def _state(cls, envelope: dict[str, Any]) -> dict[str, Any]:
        ref = envelope["full_state"]
        book = ref.book
        now_ns = int(envelope["ts_recv_ns"])
        return {"bid_depth": int(book._side_depth["B"]), "ask_depth": int(book._side_depth["A"]),
                "bid_orders": int(book._side_order_count["B"]), "ask_orders": int(book._side_order_count["A"]),
                "bid_levels": len(book.levels["B"]), "ask_levels": len(book.levels["A"]),
                "bid": cls._queue(book, "B", now_ns), "ask": cls._queue(book, "A", now_ns),
                "orders": book.orders}

    def consume(self, envelope: dict[str, Any], _legacy: list[dict[str, Any]]) -> None:
        frame = envelope["compact_event_frame"]
        recv_ns = int(frame["ts_recv_ns"])
        iid = int(frame["instrument_id"])
        recv_sec = recv_ns // 1_000_000_000
        state = self._state(envelope)
        prior = self.prior.get(iid, state)
        target_rows = self.targets.get((iid, recv_sec), ())
        if not target_rows:
            self.prior[iid] = state
            return
        row = self.rows.setdefault((iid, recv_sec), {"action_count": Counter(), "action_qty": Counter(),
                                         "side_qty": Counter(), "order_ids": set()})
        actions = frame.get("raw_actions") or []
        for action in actions:
            kind = str(action.get("action") or "N")
            qty = max(0.0, _num(action.get("size")))
            row["action_count"][kind] += 1
            row["action_qty"][kind] += qty
            row["side_qty"][str(action.get("side") or "N")] += qty
            oid = int(action.get("order_id") or 0)
            if oid > 0:
                row["order_ids"].add(oid)

        has_acm = any(str(action.get("action")) in {"A", "C", "M"} for action in actions)
        bid_delta = state["bid_depth"] - prior["bid_depth"] if has_acm else 0
        ask_delta = state["ask_depth"] - prior["ask_depth"] if has_acm else 0
        row["acm_bid_delta"] = row.get("acm_bid_delta", 0) + bid_delta
        row["acm_ask_delta"] = row.get("acm_ask_delta", 0) + ask_delta
        self.prior[iid] = state
        activity = (frame.get("activity") or {}).get("20") or {}
        live_orders = state["orders"]
        ids = row["order_ids"]
        resting = sum(oid in live_orders for oid in ids)
        replenishment = max(0, row["acm_bid_delta"]) + max(0, row["acm_ask_delta"])
        depletion = max(0, -row["acm_bid_delta"]) + max(0, -row["acm_ask_delta"])
        def retained(side: str) -> float:
            old, new = set(prior[side]["ids"]), set(state[side]["ids"])
            return len(old & new) / len(old) if old else 0.0
        def front_same(side: str) -> float:
            old, new = prior[side]["ids"], state[side]["ids"]
            return float(bool(old and new and old[0] == new[0]))
        top = frame.get("book") or {}
        row["features"] = {
            **{f"second_action_count_{x}": row["action_count"].get(x, 0) for x in "ACMTFNR"},
            **{f"second_action_qty_{x}": row["action_qty"].get(x, 0) for x in "ACMT"},
            "second_distinct_order_id_count": len(ids),
            "second_order_ids_resting_after_count": resting,
            "second_order_ids_resting_after_share": resting / len(ids) if ids else 0.0,
            "second_action_bid_qty": row["side_qty"].get("B", 0),
            "second_action_ask_qty": row["side_qty"].get("A", 0),
            "spread": top.get("spread"),
            "depth_imbalance_full": (state["bid_depth"] - state["ask_depth"]) / (state["bid_depth"] + state["ask_depth"]) if state["bid_depth"] + state["ask_depth"] else 0.0,
            "bid_depth_full": state["bid_depth"], "ask_depth_full": state["ask_depth"],
            "bid_price_level_count_full": state["bid_levels"], "ask_price_level_count_full": state["ask_levels"],
            "bid_order_count_full": state["bid_orders"], "ask_order_count_full": state["ask_orders"],
            "best_bid_queue_order_count": state["bid"]["count"], "best_ask_queue_order_count": state["ask"]["count"],
            "best_bid_queue_size": state["bid"]["size"], "best_ask_queue_size": state["ask"]["size"],
            "best_bid_front_order_share": state["bid"]["front_size"] / state["bid"]["size"] if state["bid"]["size"] else 0.0,
            "best_ask_front_order_share": state["ask"]["front_size"] / state["ask"]["size"] if state["ask"]["size"] else 0.0,
            "best_bid_front_order_age_s": state["bid"]["front_age"], "best_ask_front_order_age_s": state["ask"]["front_age"],
            "best_bid_queue_age_p90_s": state["bid"]["p90_age"], "best_ask_queue_age_p90_s": state["ask"]["p90_age"],
            "best_bid_largest_order_share": state["bid"]["largest_share"], "best_ask_largest_order_share": state["ask"]["largest_share"],
            "activity20_add_qty": (activity.get("action_qty") or {}).get("A"),
            "activity20_cancel_qty": (activity.get("action_qty") or {}).get("C"),
            "activity20_trade_buy_qty": activity.get("trade_buy_aggressor_qty"),
            "activity20_trade_sell_qty": activity.get("trade_sell_aggressor_qty"),
            "activity20_top_add_qty": activity.get("top_level_add_qty_derived"),
            "activity20_top_cancel_qty": activity.get("top_level_cancel_qty_derived"),
            "activity20_priority_lost_modify_count": activity.get("priority_lost_modify_count"),
            "activity20_missing_reference_count": activity.get("missing_reference_count"),
            "second_acm_bid_depth_delta": row["acm_bid_delta"], "second_acm_ask_depth_delta": row["acm_ask_delta"],
            "second_replenishment_qty": replenishment, "second_depletion_qty": depletion,
            "second_replenishment_minus_depletion_ratio": (replenishment - depletion) / (replenishment + depletion) if replenishment + depletion else 0.0,
            "bid_depth_full_delta_from_prior_group": state["bid_depth"] - prior["bid_depth"],
            "ask_depth_full_delta_from_prior_group": state["ask_depth"] - prior["ask_depth"],
            "bid_order_count_full_delta_from_prior_group": state["bid_orders"] - prior["bid_orders"],
            "ask_order_count_full_delta_from_prior_group": state["ask_orders"] - prior["ask_orders"],
            "bid_price_level_count_full_delta_from_prior_group": state["bid_levels"] - prior["bid_levels"],
            "ask_price_level_count_full_delta_from_prior_group": state["ask_levels"] - prior["ask_levels"],
            "best_bid_fifo_retained_order_share": retained("bid"), "best_ask_fifo_retained_order_share": retained("ask"),
            "best_bid_fifo_front_order_continues": front_same("bid"), "best_ask_fifo_front_order_continues": front_same("ask"),
        }
        for target in target_rows:
            cutoff = int(target["cutoff_ts_recv_ns"])
            if recv_ns <= cutoff:
                self.matches[target["event_id"]] = {"features": {name: _num(row["features"].get(name)) for name in MBO_FEATURE_NAMES},
                    "matched_ts_recv_ns": recv_ns, "instrument_id": iid, "cutoff_ts_recv_ns": cutoff,
                    "source_dbn_object": (actions[-1] if actions else {}).get("source_dbn_object"),
                    "source_dbn_sha256": (actions[-1] if actions else {}).get("source_dbn_sha256")}

    def feature_row(self, event_id: str) -> dict[str, Any]:
        if event_id not in self.matches:
            raise base.CensusError(f"full-MBO causal cutoff unmatched for native event {event_id}")
        return self.matches[event_id]


def _binding() -> dict[str, Any]:
    return {"path": WRAPPER_PATH, "schema": SCHEMA, "sha256": base.sha256_file(Path(WRAPPER_PATH)),
            "native_vector_dimension": FULL_NATIVE_VECTOR_DIMENSION,
            "native_mbo_feature_names": list(MBO_FEATURE_NAMES)}


def _artifact(path: Path, root: Path) -> dict[str, Any]:
    return {"relative_path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size,
            "sha256": base.sha256_file(path)}


def _copy_legacy(baseline: Path, out: Path, receipt: dict[str, Any]) -> dict[str, dict[str, Any]]:
    names = (
        "LEGACY_CONTROL_EVENTS.jsonl.gz", "LEGACY_CONTROL_LINEAGE_INPUTS.jsonl.gz",
        "LEGACY_CONTROL_SELF_FIT_GAINS.jsonl.gz", "LEGACY_CONTROL_STRUCTURAL_SELF_FIT_SUMMARY.json",
        "LEGACY_CONTROL_POPULATION.jsonl.gz", "LEGACY_CONTROL_CROSSWALK_INDEX.jsonl.gz",
    )
    expected: dict[str, dict[str, Any]] = {}
    def collect(value: Any) -> None:
        if isinstance(value, dict):
            if {"relative_path", "bytes", "sha256"} <= set(value):
                expected[str(value["relative_path"])] = value
            for child in value.values(): collect(child)
        elif isinstance(value, list):
            for child in value: collect(child)
    collect(receipt)
    copied = {}
    for name in names:
        src, dst = baseline / name, out / name
        if not src.is_file():
            raise base.CensusError(f"baseline legacy artifact missing: {name}")
        identity = expected.get(name)
        if identity is None or src.stat().st_size != int(identity["bytes"]) or base.sha256_file(src) != identity["sha256"]:
            raise base.CensusError(f"baseline legacy artifact identity drift: {name}")
        shutil.copyfile(src, dst)
        copied[name] = _artifact(dst, out)
    return copied


def _verify_baseline_artifacts(baseline: Path, receipt: dict[str, Any]) -> dict[str, str]:
    verified: dict[str, str] = {}
    def verify(value: Any) -> None:
        if isinstance(value, dict):
            if {"relative_path", "bytes", "sha256"} <= set(value):
                rel = Path(str(value["relative_path"])); path = (baseline / rel).resolve()
                if rel.is_absolute() or ".." in rel.parts or not path.is_relative_to(baseline.resolve()) or not path.is_file():
                    raise base.CensusError(f"baseline receipt artifact missing: {rel}")
                digest = base.sha256_file(path)
                if path.stat().st_size != int(value["bytes"]) or digest != value["sha256"]:
                    raise base.CensusError(f"baseline receipt artifact identity drift: {rel}")
                verified[rel.as_posix()] = digest
            for child in value.values(): verify(child)
        elif isinstance(value, list):
            for child in value: verify(child)
    verify(receipt)
    if len(verified) < 16:
        raise base.CensusError("baseline receipt artifact inventory is unexpectedly thin")
    return verified


def _load_asymmetric(path: Path) -> tuple[list[dict[str, Any]], np.ndarray, np.ndarray]:
    items = []
    for row in base.read_gzip_jsonl(path):
        predictor = list(row["behavior_vector_full"])
        target = list(row["behavior_vector_frozen22"])
        if len(predictor) != FULL_NATIVE_VECTOR_DIMENSION or len(target) != 22:
            raise base.CensusError("asymmetric full-MBO predictor/target dimension drift")
        items.append((row, predictor, target))
    items.sort(key=lambda item: int(item[0]["sequence_index"]))
    rows = [item[0] for item in items]
    predictors = [item[1] for item in items]
    targets = [item[2] for item in items]
    if [int(x["sequence_index"]) for x in rows] != list(range(len(rows))):
        raise base.CensusError("non-contiguous full-MBO native event sequence")
    x = np.asarray(predictors, dtype=float); y = np.asarray(targets, dtype=float)
    x[:, 1:] = np.arcsinh(x[:, 1:]); y[:, 1:] = np.arcsinh(y[:, 1:])
    return rows, x, y


def _asymmetric_model(model: str, rows: list[dict[str, Any]], predictors: np.ndarray,
                      targets: np.ndarray, depth: int, history_len: int) -> dict[str, Any] | None:
    xs, ys, meta = [], [], []
    valid = np.all(np.isfinite(predictors), axis=1) & np.all(np.isfinite(targets), axis=1)
    for index in range(depth, len(rows)):
        if not valid[index] or not valid[index-depth:index].all():
            continue
        ys.append(targets[index])
        xs.append(predictors[index-history_len:index].reshape(-1) if history_len else np.empty(0, float))
        meta.append((str(rows[index]["week_sunday"]), index, rows[index]["event_id"]))
    if not ys:
        return None
    X = np.asarray(xs, float) if history_len else np.empty((len(ys), 0), float)
    Y = np.asarray(ys, float)
    ymu, ysd = Y.mean(axis=0), Y.std(axis=0); ysd[ysd < 1e-12] = 1.0
    Yz = (Y - ymu) / ysd
    if history_len:
        xmu, xsd = X.mean(axis=0), X.std(axis=0); xsd[xsd < 1e-12] = 1.0
        Xz = (X - xmu) / xsd
    else:
        Xz = X
    engine = base.frozen_structural
    if history_len == 0:
        parameter, prediction = None, np.zeros_like(Yz)
    else:
        candidates = []
        for candidate in engine.grid(model):
            predicted = engine.fit_predict(model, candidate, Xz, Yz, Xz, inner=True)
            candidates.append((float(np.mean((Yz - predicted) ** 2)), float(candidate), candidate))
        parameter = min(candidates)[2]
        prediction = engine.fit_predict(model, parameter, Xz, Yz, Xz, inner=False)
    loss = np.mean((Yz - prediction) ** 2, axis=1)
    return {"param": parameter, "loss": loss, "meta": meta, "n": len(loss), "mse": float(loss.mean()),
            "x_standardization": "PREDICTOR_COLUMNS_INDEPENDENT", "y_standardization": "TARGET_22_COLUMNS_INDEPENDENT"}


def asymmetric_self_fit_scores(path: Path, gain_path: Path) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    rows, predictors, targets = _load_asymmetric(path)
    week = str(rows[0]["week_sunday"])
    models = tuple(base.frozen_structural.MODELS); model_index = {name: i for i, name in enumerate(models)}
    gains = {week: np.full((len(rows), base.MAX_DEPTH, len(models)), np.nan, dtype=np.float64)}
    depth_results: dict[str, Any] = {}; writer = base.DeterministicGzipJsonlWriter(gain_path)
    try:
        for depth in range(1, base.MAX_DEPTH + 1):
            depth_results[str(depth)] = {}
            for model in models:
                short = _asymmetric_model(model, rows, predictors, targets, depth, depth - 1)
                long = _asymmetric_model(model, rows, predictors, targets, depth, depth)
                if short is None or long is None:
                    depth_results[str(depth)][model] = {"n": 0, "gain_mean": None}; continue
                if short["meta"] != long["meta"]:
                    raise base.CensusError("asymmetric paired-sample invariant failed")
                gain = short["loss"] - long["loss"]
                for value, (_, index, event_id) in zip(gain, short["meta"]):
                    gains[week][int(index), depth - 1, model_index[model]] = float(value)
                    writer.write({"fold": "user_authorized_two_day_self_fit_self_score", "week_sunday": week,
                        "sequence_index": int(index), "target_event_id": event_id, "model": model,
                        "depth": depth, "incremental_gain": float(value), "view": "V4_NATIVE_FULL_MBO_ASYMMETRIC"})
                depth_results[str(depth)][model] = {"short_param": short["param"], "long_param": long["param"],
                    "n": len(gain), "gain_mean": float(gain.mean()), "gain_median": float(np.median(gain)),
                    "gain_positive_rate": float(np.mean(gain > 0)), "short_mse": short["mse"], "long_mse": long["mse"],
                    "per_week_gain_mean": {week: float(gain.mean())}}
        gain_output = writer.close()
    except Exception:
        writer.abort(); raise
    summary = {"dimension": FULL_NATIVE_VECTOR_DIMENSION, "predictor_dimension": FULL_NATIVE_VECTOR_DIMENSION,
        "target_dimension": 22, "predictor_semantics": "HISTORY_FROZEN22_PLUS_CAUSAL_FULL_MBO",
        "target_semantics": "CURRENT_FROZEN22_OUTCOME_ONLY", "separate_predictor_target_standardization": True,
        "valid_events_by_week": {week: len(rows)}, "depth": depth_results, "gain_output": gain_output,
        "folds": {"user_authorized_two_day_self_fit_self_score": {"train_weeks": [week], "test_weeks": [week],
            "depth": depth_results, "validation_exception": prior.METHOD_EXCEPTION}},
        "out_of_time_validation_claimed": False, "diagnostic_validation_status": prior.VALIDATION_STATUS,
        "feature_view": "full_mbo_asymmetric"}
    return gains, summary


def run(manifest_path: Path, baseline: Path, baseline_tar_sha256: str,
        raw_paths: list[Path], out: Path) -> dict[str, Any]:
    if out.exists() and any(out.iterdir()):
        raise base.CensusError("corrected full-MBO output directory must be new or empty")
    out.mkdir(parents=True, exist_ok=True)
    manifest = base.load_manifest(manifest_path)
    expected = [x for x in base._segment_objects(manifest, prior.OCTOBER_SEGMENT, set(RAW_BOOTSTRAP_DATES))]
    by_name = {Path(x["key"]).name: x for x in expected}
    if len(raw_paths) != len(expected) or {p.name for p in raw_paths} != set(by_name):
        raise base.CensusError("raw-MBO roster is not the exact October 1/3/4/5 bootstrap+target set")
    provenance = {}
    for path in raw_paths:
        obj = by_name[path.name]
        if path.stat().st_size != int(obj["bytes"]) or base.sha256_file(path) != obj["sha256"]:
            raise base.CensusError(f"raw-MBO identity drift: {path.name}")
        provenance[str(path)] = {k: obj.get(k) for k in (
            "key", "interval", "native_segment_job_id", "canonical_interval_job_id",
            "requested_symbol", "selection_reason", "raw_contract_resolution")}

    baseline_receipt = json.loads((baseline / "STEP1_DUAL_CENSUS_RECEIPT.json").read_text())
    claimed = baseline_receipt.get("receipt_sha256")
    body = dict(baseline_receipt); body.pop("receipt_sha256", None)
    if baseline_tar_sha256 != EXPECTED_BASELINE_TAR_SHA256:
        raise base.CensusError("baseline two-day archive identity drift")
    if claimed != EXPECTED_BASELINE_RECEIPT_SHA256 or claimed != base.sha256_json(body):
        raise base.CensusError("baseline two-day receipt self-hash drift")
    baseline_verified = _verify_baseline_artifacts(baseline, baseline_receipt)
    copied = _copy_legacy(baseline, out, baseline_receipt)

    native_rows: list[dict[str, Any]] = []
    aggregator = base.SecondAggregator(emit=native_rows.append, source_provenance=provenance)
    replay_seconds = replay_dbn_files([str(p) for p in raw_paths], aggregator.consume, materialize_full_state=False)
    aggregator.finish()
    selected = [x for x in native_rows if WINDOW_START <= int(x["epoch_second"]) < WINDOW_END]
    seconds_output = base.deterministic_gzip_jsonl(out / "V4_NATIVE_FULL_MBO_SECONDS.jsonl.gz", selected)

    pre = base.frozen_detector.FrozenPreFamilyClassifier.load(
        "research/FRANKIE_NG_PRE_FAMILY_CLASSIFIER_FROZEN_OPERATIONAL_20260817.json")
    acl = base.frozen_detector.FrozenAClassifier.load(
        "research/FRANKIE_NG_A_POSTSTATE_CLASSIFIER_FROZEN_PREBLIND_20260816.json")
    events = base.detect_events_for_week(selected, "V4_NATIVE_FULL", pre, acl)
    families = dict(sorted(Counter(str(x.get("family")) for x in events).items()))
    if len(events) != EXPECTED_NATIVE_COUNTS["events"] or families != EXPECTED_NATIVE_COUNTS["families"]:
        raise base.CensusError(f"native raw-MBO detector parity drift: events={len(events)} families={families}")
    targets = []
    for event in events:
        source = event.get("source_provenance") or {}
        iid, cutoff = source.get("instrument_id"), source.get("event_known_by_ts_recv_ns")
        if not iid or not cutoff:
            raise base.CensusError(f"native event lacks receive-cutoff instrument binding: {event['event_id']}")
        targets.append({"event_id": event["event_id"], "instrument_id": int(iid), "cutoff_ts_recv_ns": int(cutoff)})
    collector = CausalMboCollector(targets)
    replay_features = replay_dbn_files([str(p) for p in raw_paths], collector.consume, materialize_full_state=False)
    cutoff_writer = base.DeterministicGzipJsonlWriter(out / "V4_NATIVE_FULL_MBO_CAUSAL_CUTOFF_BINDINGS.jsonl.gz")
    event_writer = base.DeterministicGzipJsonlWriter(out / "V4_NATIVE_FULL_MBO_EVENTS.jsonl.gz")
    lineage_writer = base.DeterministicGzipJsonlWriter(out / "V4_NATIVE_FULL_MBO_LINEAGE_INPUTS.jsonl.gz")
    for event in events:
        binding = collector.feature_row(event["event_id"])
        if binding["matched_ts_recv_ns"] > binding["cutoff_ts_recv_ns"]:
            raise base.CensusError("full-MBO receive cutoff violated")
        features = binding["features"]
        feature_hash = base.sha256_json({"names": list(MBO_FEATURE_NAMES), "values": [features[x] for x in MBO_FEATURE_NAMES]})
        cutoff_writer.write({"event_id": event["event_id"], "instrument_id": binding["instrument_id"],
            "cutoff_ts_recv_ns": binding["cutoff_ts_recv_ns"], "matched_ts_recv_ns": binding["matched_ts_recv_ns"],
            "matched_not_after_cutoff": True, "source_dbn_object": binding["source_dbn_object"],
            "source_dbn_sha256": binding["source_dbn_sha256"], "full_mbo_feature_vector_sha256": feature_hash})
        event["full_mbo_at_t0"] = {"causal_resolution": "INSTRUMENT_SPECIFIC_LATEST_GROUP_NOT_AFTER_TS_RECV_CUTOFF",
            "cutoff_ts_recv_ns": binding["cutoff_ts_recv_ns"], "matched_ts_recv_ns": binding["matched_ts_recv_ns"],
            "instrument_id": binding["instrument_id"], "feature_vector_sha256": feature_hash, **features}
        row = base.compact_lineage_input(event)
        frozen22 = list(row["behavior_vector_full"])
        if len(frozen22) != 22:
            raise base.CensusError("frozen behavior-vector dimension drift")
        row["behavior_vector_frozen22"] = frozen22
        row["full_mbo_feature_names"] = list(MBO_FEATURE_NAMES)
        row["behavior_vector_full"] = frozen22 + [features[x] for x in MBO_FEATURE_NAMES]
        event_writer.write(event); lineage_writer.write(row)
    event_output, lineage_output, cutoff_output = event_writer.close(), lineage_writer.close(), cutoff_writer.close()

    # Primary X is prior-event frozen22+causal-MBO history; Y is current frozen22 only.
    # Sparse sensitivity remains the accepted frozen first-eight path via a 22-D sidecar.
    sparse_writer = base.DeterministicGzipJsonlWriter(out / "V4_NATIVE_FULL_MBO_SPARSE_LINEAGE_INPUTS.jsonl.gz")
    for row in base.read_gzip_jsonl(out / "V4_NATIVE_FULL_MBO_LINEAGE_INPUTS.jsonl.gz"):
        row["behavior_vector_full"] = row.pop("behavior_vector_frozen22")
        sparse_writer.write(row)
    sparse_lineage = sparse_writer.close()
    prior._diagnostic_adapter_binding = _binding
    gains, structural = asymmetric_self_fit_scores(
        out / "V4_NATIVE_FULL_MBO_LINEAGE_INPUTS.jsonl.gz",
        out / "V4_NATIVE_FULL_MBO_SELF_FIT_GAINS.jsonl.gz")
    _unused, sparse = prior.self_fit_structural_scores(
        out / "V4_NATIVE_FULL_MBO_SPARSE_LINEAGE_INPUTS.jsonl.gz", "V4_NATIVE_FULL",
        None, feature_view="sparse")
    structural["sparse_sensitivity"] = sparse
    structural["aggregate"] = prior._diagnostic_aggregate(structural)
    summary_path = out / "V4_NATIVE_FULL_MBO_STRUCTURAL_SELF_FIT_SUMMARY.json"
    base.atomic_json(summary_path, {"status": "PHASE1_STRUCTURAL_TWO_DAY_FULL_MBO_COMPLETE",
        "primary_full_path": structural, "sparse_sensitivity": sparse,
        "aggregate": structural["aggregate"], "native_vector_dimension": FULL_NATIVE_VECTOR_DIMENSION,
        "native_mbo_feature_names": list(MBO_FEATURE_NAMES), "wrapper": _binding(),
        "comparison_to_54w_answers_performed": False, "provider_llm_called": False})
    population, population_summary, index = prior.self_fit_lineage_population(
        out / "V4_NATIVE_FULL_MBO_LINEAGE_INPUTS.jsonl.gz", "V4_NATIVE_FULL",
        {**base.material_hashes(), "full_mbo_wrapper": _binding()["sha256"]}, gains,
        structural["depth"], out / "V4_NATIVE_FULL_MBO_POPULATION.jsonl.gz",
        out / "V4_NATIVE_FULL_MBO_CROSSWALK_INDEX.jsonl.gz")
    crosswalk, crosswalk_summary = base.build_crosswalk(
        out / "LEGACY_CONTROL_CROSSWALK_INDEX.jsonl.gz",
        out / "V4_NATIVE_FULL_MBO_CROSSWALK_INDEX.jsonl.gz",
        out / "DUAL_CENSUS_FULL_MBO_CROSSWALK.jsonl.gz")

    raw_manifest = [{k: obj[k] for k in ("key", "bytes", "sha256")} for obj in expected]
    receipt = {"schema": SCHEMA, "status": STATUS,
        "source_window": {"start": prior.WINDOW_START_ISO, "end_exclusive": prior.WINDOW_END_ISO},
        "legacy_control": {"unchanged_from_receipt_sha256": claimed,
            "baseline_results_tar_sha256": baseline_tar_sha256,
            "baseline_receipt_file_sha256": base.sha256_file(baseline / "STEP1_DUAL_CENSUS_RECEIPT.json"),
            "all_baseline_receipt_artifacts_verified": True,
            "baseline_verified_artifact_count": len(baseline_verified),
            "baseline_verified_artifact_set_sha256": base.sha256_json(baseline_verified),
            "all_copied_artifacts_verified_against_baseline_receipt": True, "copied_artifacts": copied,
            "event_count": baseline_receipt["event_counts"]["legacy"],
            "population_summary": baseline_receipt["legacy_population_summary"]},
        "native_full_mbo": {"raw_mbo_replayed": True, "raw_bootstrap_dates": list(RAW_BOOTSTRAP_DATES),
            "raw_source_objects": raw_manifest, "seconds_replay_summary": replay_seconds,
            "causal_feature_replay_summary": replay_features,
            "vector_dimension": FULL_NATIVE_VECTOR_DIMENSION, "frozen_component_dimension": 22,
            "mbo_component_dimension": len(MBO_FEATURE_NAMES), "mbo_feature_names": list(MBO_FEATURE_NAMES),
            "seconds_output": prior._relative_output(seconds_output, out),
            "event_output": prior._relative_output(event_output, out),
            "lineage_output": prior._relative_output(lineage_output, out),
            "causal_cutoff_binding_output": prior._relative_output(cutoff_output, out),
            "causal_binding_semantics": "INSTRUMENT_SPECIFIC_LATEST_GROUP_NOT_AFTER_TS_RECV_CUTOFF",
            "sparse_lineage_output": prior._relative_output(sparse_lineage, out),
            "gain_output": prior._relative_output(structural["gain_output"], out),
            "structural_summary": _artifact(summary_path, out),
            "population_output": prior._relative_output(population, out),
            "crosswalk_index_output": prior._relative_output(index, out),
            "event_count": len(events), "family_counts": families,
            "expected_native_parity": EXPECTED_NATIVE_COUNTS, "native_parity_passed": True,
            "population_summary": population_summary},
        "crosswalk_output": prior._relative_output(crosswalk, out), "crosswalk_summary": crosswalk_summary,
        "wrapper": _binding(), "legacy_science_changed": False, "prior_outputs_overwritten": False,
        "comparison_to_54w_answers_performed": False, "provider_llm_called": False,
        "frankie_launched": False, "predictive_or_trading_experiment_run": False}
    receipt["receipt_sha256"] = base.sha256_json(receipt)
    base.atomic_json(out / "STEP1_DUAL_FULL_MBO_RECEIPT.json", receipt)
    return receipt


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parent-manifest", required=True, type=Path)
    ap.add_argument("--baseline-results", required=True, type=Path)
    ap.add_argument("--baseline-results-tar-sha256", required=True)
    ap.add_argument("--raw-mbo", required=True, nargs="+", type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    args = ap.parse_args()
    receipt = run(args.parent_manifest, args.baseline_results, args.baseline_results_tar_sha256,
                  args.raw_mbo, args.out_dir)
    print("TWO_DAY_FULL_MBO_STEP1=PASS")
    print("TWO_DAY_FULL_MBO_RECEIPT_SHA256=" + receipt["receipt_sha256"])
    print("TWO_DAY_FULL_MBO_NATIVE_VECTOR_DIMENSION=" + str(FULL_NATIVE_VECTOR_DIMENSION))
    print("TWO_DAY_FULL_MBO_NATIVE_EVENTS=" + str(receipt["native_full_mbo"]["event_count"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
