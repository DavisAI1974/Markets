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
from sklearn.cluster import OPTICS

import ng_exhaustion_mbo_2day_step1_finalize_20260824 as prior
import ng_exhaustion_mbo_5y_step1_census_20260822 as base
from ng_exhaustion_mbo_v4_full_state_replay_20260820 import replay_dbn_files
from ng_exhaustion_mbo_v4_state_adapter_20260820 import V4MboAdapter, InstrumentBook, _int, _resolve_symbol, sha256_file

SCHEMA = "NG_EXHAUSTION_MBO_2DAY_FULL_MBO_STEP1_V1_20260825"
STATUS = "STEP1_DUAL_STRUCTURAL_CENSUS_COMPLETE_TWO_DAY_FULL_MBO"
WINDOW_START = prior.WINDOW_START_EPOCH
WINDOW_END = prior.WINDOW_END_EPOCH
RAW_BOOTSTRAP_DATES = ("20211001", "20211003", "20211004", "20211005")
WRAPPER_PATH = "research/ng_exhaustion_mbo_2day_full_mbo_step1_20260825.py"
EXPECTED_BASELINE_RECEIPT_SHA256 = "140c6234b8e6f4216416290aa50f4070160e200a3e7025cbca3aa08d0ef42e52"
EXPECTED_BASELINE_TAR_SHA256 = "27cacc62681bc482e89eefcc3746f5d71958beab4e25816054e0c388a0346b33"
PROPOSAL_SURFACES = ("FLOW", "DEPLETION", "ABSORPTION", "FIFO_FAILURE", "FULL_DEPTH_SHIFT")
PROPOSAL_WARMUP_SECONDS = 3600
PROPOSAL_PRIOR_ABS_QUANTILE = 0.95
PROPOSAL_REARM_SECONDS = 2

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
    def _state_book(cls, book: InstrumentBook, now_ns: int) -> dict[str, Any]:
        return {"bid_depth": int(book._side_depth["B"]), "ask_depth": int(book._side_depth["A"]),
                "bid_orders": int(book._side_order_count["B"]), "ask_orders": int(book._side_order_count["A"]),
                "bid_levels": len(book.levels["B"]), "ask_levels": len(book.levels["A"]),
                "bid": cls._queue(book, "B", now_ns), "ask": cls._queue(book, "A", now_ns),
                "orders": book.orders}

    @classmethod
    def _state(cls, envelope: dict[str, Any]) -> dict[str, Any]:
        return cls._state_book(envelope["full_state"].book, int(envelope["ts_recv_ns"]))

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
                                         "side_qty": Counter(), "order_ids": set(), "raw_actions": []})
        actions = frame.get("raw_actions") or []
        row["raw_actions"].extend(dict(action) for action in actions)
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
            if recv_ns == cutoff:
                checkpoint = envelope["full_state"].checkpoint()
                self.matches[target["event_id"]] = {"features": {name: _num(row["features"].get(name)) for name in MBO_FEATURE_NAMES},
                    "matched_ts_recv_ns": recv_ns, "instrument_id": iid, "cutoff_ts_recv_ns": cutoff,
                    "source_dbn_key": target["source_dbn_key"],
                    "source_dbn_object": (actions[-1] if actions else {}).get("source_dbn_object"),
                    "source_dbn_sha256": (actions[-1] if actions else {}).get("source_dbn_sha256"),
                    "raw_actions_through_cutoff": list(row["raw_actions"]),
                    "full_depth_fifo_checkpoint": checkpoint}

    def feature_row(self, event_id: str) -> dict[str, Any]:
        if event_id not in self.matches:
            raise base.CensusError(f"full-MBO causal cutoff unmatched for native event {event_id}")
        return self.matches[event_id]


class MboSurfaceCollector:
    """Build independent signed causal proposal surfaces from complete MBO callbacks."""

    def __init__(self, source_provenance: dict[str, dict[str, Any]]) -> None:
        self.source_provenance = source_provenance
        self.prior: dict[int, dict[str, Any]] = {}
        self.current: dict[int, tuple[int, dict[str, Any]]] = {}
        self.surface_rows: list[dict[str, Any]] = []

    @staticmethod
    def _new_row(iid: int, sec: int) -> dict[str, Any]:
        return {"instrument_id": iid, "recv_second": sec, "cutoff_ts_recv_ns": 0,
                "max_ts_event_ns": 0, "f_last_group_completion_ts_recv_ns": 0,
                "trade_buy": 0.0, "trade_sell": 0.0,
                "cancel_bid": 0.0, "cancel_ask": 0.0,
                "neg_modify_bid": 0.0, "neg_modify_ask": 0.0,
                "add_bid": 0.0, "add_ask": 0.0,
                "pos_modify_bid": 0.0, "pos_modify_ask": 0.0,
                "bid_depth_delta": 0.0, "ask_depth_delta": 0.0,
                "bid_fifo_failure_sum": 0.0, "ask_fifo_failure_sum": 0.0,
                "fifo_observations": 0, "source_dbn_key": None,
                "source_dbn_object": None, "source_dbn_sha256": None}

    def _finalize(self, row: dict[str, Any], event_known_by_ts_recv_ns: int) -> None:
        cutoff = int(row["cutoff_ts_recv_ns"])
        group_complete = int(row["f_last_group_completion_ts_recv_ns"])
        known_by = int(event_known_by_ts_recv_ns)
        if cutoff <= 0 or group_complete != cutoff or known_by < cutoff:
            raise base.CensusError("MBO surface is not bound to a completed causal receive-clock group")
        if int(row["max_ts_event_ns"]) > cutoff:
            raise base.CensusError("MBO surface event clock is later than its receive cutoff")
        trades = row["trade_buy"] + row["trade_sell"]
        flow = (row["trade_buy"] - row["trade_sell"]) / trades if trades else 0.0
        bid_dep = row["cancel_bid"] + row["neg_modify_bid"]
        ask_dep = row["cancel_ask"] + row["neg_modify_ask"]
        dep_total = bid_dep + ask_dep
        depletion = (ask_dep - bid_dep) / dep_total if dep_total else 0.0
        bid_repl = row["add_bid"] + row["pos_modify_bid"]
        ask_repl = row["add_ask"] + row["pos_modify_ask"]
        repl_total = bid_repl + ask_repl
        buy_share = row["trade_buy"] / trades if trades else 0.0
        sell_share = row["trade_sell"] / trades if trades else 0.0
        absorption = (bid_repl * sell_share - ask_repl * buy_share) / repl_total if repl_total else 0.0
        fifo_n = int(row["fifo_observations"])
        fifo = ((row["ask_fifo_failure_sum"] - row["bid_fifo_failure_sum"]) / fifo_n) if fifo_n else 0.0
        depth_total = abs(row["bid_depth_delta"]) + abs(row["ask_depth_delta"])
        depth_shift = (row["bid_depth_delta"] - row["ask_depth_delta"]) / depth_total if depth_total else 0.0
        self.surface_rows.append({"instrument_id": int(row["instrument_id"]),
            "recv_second": int(row["recv_second"]), "cutoff_ts_recv_ns": int(row["cutoff_ts_recv_ns"]),
            "ts_event_ns": int(row["max_ts_event_ns"]),
            "ts_recv_ns": int(row["cutoff_ts_recv_ns"]),
            "event_known_by_ts_recv_ns": int(event_known_by_ts_recv_ns),
            "f_last_group_completion_ts_recv_ns": int(row["f_last_group_completion_ts_recv_ns"]),
            "surfaces": {"FLOW": flow, "DEPLETION": depletion, "ABSORPTION": absorption,
                         "FIFO_FAILURE": fifo, "FULL_DEPTH_SHIFT": depth_shift},
            "surface_inputs": {key: row[key] for key in (
                "trade_buy", "trade_sell", "cancel_bid", "cancel_ask", "neg_modify_bid", "neg_modify_ask",
                "add_bid", "add_ask", "pos_modify_bid", "pos_modify_ask", "bid_depth_delta", "ask_depth_delta",
                "bid_fifo_failure_sum", "ask_fifo_failure_sum", "fifo_observations")},
            "source_dbn_key": row["source_dbn_key"],
            "source_dbn_object": row["source_dbn_object"], "source_dbn_sha256": row["source_dbn_sha256"]})

    def consume_effect(self, msg: Any, effect: Any, book: InstrumentBook, frame: dict[str, Any] | None) -> None:
        iid = int(msg.instrument_id); recv_ns = int(msg.ts_recv_ns); sec = recv_ns // 1_000_000_000
        state = CausalMboCollector._state_book(book, recv_ns); prior = self.prior.get(iid, state)
        active = self.current.get(iid)
        if active is None or active[0] != sec:
            if active is not None: self._finalize(active[1], recv_ns)
            row = self._new_row(iid, sec); self.current[iid] = (sec, row)
        else:
            row = active[1]
        row["cutoff_ts_recv_ns"] = recv_ns
        if msg.is_last: row["f_last_group_completion_ts_recv_ns"] = recv_ns
        row["max_ts_event_ns"] = max(int(row["max_ts_event_ns"]), int(msg.ts_event_ns))
        row["source_dbn_object"] = msg.source_dbn_object; row["source_dbn_sha256"] = msg.source_dbn_sha256
        row["source_dbn_key"] = (self.source_provenance.get(str(msg.source_dbn_object)) or {}).get("key")
        if not row["source_dbn_key"]:
            raise base.CensusError("MBO action cannot be bound to its manifest source key")
        if msg.action == "T":
            if msg.side == "B": row["trade_buy"] += max(0.0, float(msg.size))
            elif msg.side == "A": row["trade_sell"] += max(0.0, float(msg.size))
        side = str(effect.side)
        delta = effect.size_delta
        if side in {"B", "A"} and delta is not None and msg.action in {"A", "C", "M"}:
            side_key = "bid" if side == "B" else "ask"; value = float(delta)
            row[f"{side_key}_depth_delta"] += value
            if msg.action == "C": row[f"cancel_{side_key}"] += max(0.0, -value)
            elif msg.action == "A": row[f"add_{side_key}"] += max(0.0, value)
            elif value < 0: row[f"neg_modify_{side_key}"] += -value
            elif value > 0: row[f"pos_modify_{side_key}"] += value
        for side in ("bid", "ask"):
            old, new = set(prior[side]["ids"]), set(state[side]["ids"])
            failure = 0.0 if not old else 1.0 - len(old & new) / len(old)
            row[f"{side}_fifo_failure_sum"] += failure
        row["fifo_observations"] += 1
        self.prior[iid] = state

    def finish(self) -> None:
        for _, row in self.current.values(): self._finalize(row, int(row["cutoff_ts_recv_ns"]))
        self.current.clear()


def replay_surface_effects(paths: list[Path], collector: MboSurfaceCollector) -> dict[str, Any]:
    """Replay through the accepted adapter while retaining each exact ApplyEffect."""
    try:
        import databento as db
    except ImportError as exc:
        raise base.CensusError("databento is required for exact MBO effect replay") from exc
    adapter = V4MboAdapter(); sources = []
    for path in paths:
        digest = sha256_file(path); store = db.DBNStore.from_file(str(path)); instrument_map = None
        try:
            instrument_map = db.common.symbology.InstrumentMap(); instrument_map.insert_metadata(store.metadata)
        except Exception:
            instrument_map = None
        records = 0
        for record in store:
            if type(record).__name__ not in {"MboMsg", "MBOMsg"}: continue
            iid, recv = _int(record, "instrument_id"), _int(record, "ts_recv")
            msg = adapter.normalize(record, _resolve_symbol(instrument_map, iid, recv), str(path), digest)
            book = adapter.books.setdefault(iid, InstrumentBook(iid))
            effect, frame, _legacy = book.apply(msg)
            adapter.record_count += 1; records += 1
            if frame is not None: adapter.completed_event_group_count += 1
            collector.consume_effect(msg, effect, book, frame)
        adapter.assert_groups_closed()
        sources.append({"path": str(path), "sha256": digest, "mbo_records": records})
    collector.finish()
    return {"status": "EXACT_APPLY_EFFECT_REPLAY_COMPLETE", "sources": sources,
            "record_count": adapter.record_count, "completed_event_group_count": adapter.completed_event_group_count,
            "exact_A_C_M_size_delta_retained": True, "trades_used_as_flow_only": True}


def _prior_quantile(values: list[float]) -> float:
    return float(np.quantile(np.asarray(values, dtype=float), PROPOSAL_PRIOR_ABS_QUANTILE, method="linear"))


def discover_uncapped_proposals(surface_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    histories: dict[tuple[int, str], list[float]] = defaultdict(list)
    above: dict[tuple[int, str, int], bool] = defaultdict(bool)
    last_onset: dict[tuple[int, str, int], int] = defaultdict(lambda: -10**18)
    merged: dict[tuple[int, int, int], dict[str, Any]] = {}
    for row in sorted(surface_rows, key=lambda x: (int(x["recv_second"]), int(x["cutoff_ts_recv_ns"]), int(x["instrument_id"]))):
        iid, sec = int(row["instrument_id"]), int(row["recv_second"])
        for surface in PROPOSAL_SURFACES:
            value = float(row["surfaces"][surface]); history = histories[(iid, surface)]
            eligible = len(history) >= PROPOSAL_WARMUP_SECONDS
            threshold = _prior_quantile(history) if eligible else None
            polarity = 1 if value > 0 else (-1 if value < 0 else 0)
            is_above = bool(eligible and polarity and threshold is not None and threshold > 0 and abs(value) >= threshold)
            state_key = (iid, surface, polarity)
            crossing = is_above and not above[state_key]
            in_target_window = WINDOW_START <= sec < WINDOW_END
            if in_target_window and crossing and sec - last_onset[state_key] >= PROPOSAL_REARM_SECONDS:
                key = (iid, sec, polarity)
                proposal = merged.setdefault(key, {"instrument_id": iid, "recv_second": sec,
                    "cutoff_ts_recv_ns": int(row["cutoff_ts_recv_ns"]), "polarity": polarity,
                    "ts_event_ns": int(row["ts_event_ns"]), "ts_recv_ns": int(row["event_known_by_ts_recv_ns"]),
                    "f_last_group_completion_ts_recv_ns": int(row["f_last_group_completion_ts_recv_ns"]),
                    "threshold_crossing_ts_recv_ns": int(row["event_known_by_ts_recv_ns"]),
                    "event_known_by_ts_recv_ns": int(row["event_known_by_ts_recv_ns"]),
                    "max_contributing_ts_recv_ns": int(row["ts_recv_ns"]),
                    "feature_cutoff_ts_recv_ns": int(row["ts_recv_ns"]),
                    "outcome_availability_cutoff_ts_event_ns": None,
                    "outcome_availability_cutoff_ts_recv_ns": None,
                    "outcome_availability_status": "WITHHELD_UNTIL_POST_LOCK",
                    "surfaces": {},
                    "causal_t0_surfaces": {name: float(row["surfaces"][name]) for name in PROPOSAL_SURFACES},
                    "causal_t0_surface_inputs": dict(row["surface_inputs"]),
                    "source_dbn_key": row["source_dbn_key"],
                    "source_dbn_object": row["source_dbn_object"],
                    "source_dbn_sha256": row["source_dbn_sha256"], "warmup_minimum": PROPOSAL_WARMUP_SECONDS})
                proposal["cutoff_ts_recv_ns"] = max(proposal["cutoff_ts_recv_ns"], int(row["cutoff_ts_recv_ns"]))
                proposal["surfaces"][surface] = {"value": value, "prior_abs_q95": threshold,
                    "prior_valid_seconds": len(history), "causal_threshold_excludes_current": True}
                last_onset[state_key] = sec
            for signed_polarity in (-1, 1):
                above[(iid, surface, signed_polarity)] = bool(is_above and polarity == signed_polarity)
            history.append(abs(value))
    proposals = []
    for proposal in sorted(merged.values(), key=lambda x: (x["recv_second"], x["instrument_id"], x["polarity"])):
        body = {**proposal, "surface_names": sorted(proposal["surfaces"]),
                "merge_semantics": "SAME_INSTRUMENT_POLARITY_RECEIVE_SECOND",
                "event_recv_latency_ns": int(proposal["ts_recv_ns"]) - int(proposal["ts_event_ns"]),
                "event_not_after_receive": int(proposal["ts_event_ns"]) <= int(proposal["ts_recv_ns"])}
        if not body["event_not_after_receive"] or body["max_contributing_ts_recv_ns"] > body["feature_cutoff_ts_recv_ns"]:
            raise base.CensusError("uncapped proposal causal-clock ordering failure")
        canonical_body = {key: value for key, value in body.items() if key != "source_dbn_object"}
        proposal_id = "MBOU1|" + base.sha256_json(canonical_body)
        proposals.append({"event_id": proposal_id, **body})
    check = [{k: v for k, v in row.items()} for row in proposals]
    receipt = {"schema": "NG_EXHAUSTION_UNCAPPED_MBO_PROPOSAL_LOCK_V1_20260825",
        "status": "CAUSAL_PROPOSALS_LOCKED_BEFORE_OUTCOMES", "proposal_count": len(proposals),
        "surfaces": list(PROPOSAL_SURFACES), "warmup_prior_valid_seconds": PROPOSAL_WARMUP_SECONDS,
        "threshold": "PER_INSTRUMENT_EXPANDING_PRIOR_ABS_Q95_EXCLUDING_CURRENT",
        "scored_window": {"start": prior.WINDOW_START_ISO, "end_exclusive": prior.WINDOW_END_ISO},
        "warmup_only_dates": ["20211001", "20211003"],
        "onset": "BELOW_TO_AT_OR_ABOVE_THRESHOLD_CROSSING", "rearm_seconds": PROPOSAL_REARM_SECONDS,
        "merge": "ONE_COMPOSITE_EVENT_FOR_ALL_SAME_INSTRUMENT_POLARITY_RECEIVE_SECOND_SURFACE_CROSSINGS",
        "merge_is_not_a_count_or_family_cap": True,
        "rearm_semantics": "PER_MECHANISM_POLARITY_DUPLICATE_ONSET_SUPPRESSION_ONLY",
        "rearm_is_not_a_count_or_family_cap": True,
        "count_cap": None, "family_cap": None,
        "proposal_set_sha256": base.sha256_json(check), "outcomes_accessed": False}
    receipt["receipt_sha256"] = base.sha256_json(receipt)
    return proposals, receipt


def discover_mbo_families(proposals: list[dict[str, Any]]) -> dict[str, Any]:
    if any(len(row.get("mbo59_feature_vector") or ()) != len(MBO_FEATURE_NAMES) for row in proposals):
        raise base.CensusError("retrospective family discovery requires complete causal MBO59 vectors")
    all_x = np.asarray([row["mbo59_feature_vector"] for row in proposals], dtype=float)
    if len(proposals):
        center = all_x.mean(axis=0); scale = all_x.std(axis=0)
        zero_variance = scale < 1e-12; scale[zero_variance] = 1.0
        all_z = (all_x - center) / scale
    else:
        center = np.zeros(len(MBO_FEATURE_NAMES)); scale = np.ones(len(MBO_FEATURE_NAMES))
        zero_variance = np.ones(len(MBO_FEATURE_NAMES), dtype=bool); all_z = all_x
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for proposal, vector in zip(proposals, all_z):
        day = datetime.fromtimestamp(int(proposal["event_known_by_ts_recv_ns"]) / 1e9,
                                     tz=timezone.utc).date().isoformat()
        proposal["family_feature_vector"] = [float(value) for value in vector]
        by_day[day].append(proposal)
    full_set_recv_cutoff = max((int(row["event_known_by_ts_recv_ns"]) for row in proposals), default=0) or None
    full_set_event_cutoff = max((int(row["ts_event_ns"]) for row in proposals), default=0) or None
    known: dict[str, np.ndarray] = {}; day_receipts = []
    for day in sorted(by_day):
        rows = sorted(by_day[day], key=lambda x: (x["recv_second"], x["instrument_id"], x["event_id"]))
        X = np.asarray([row["family_feature_vector"] for row in rows], dtype=float)
        if len(rows) < 5:
            labels = np.full(len(rows), -1, dtype=int)
        else:
            labels = OPTICS(min_samples=min(20, max(5, int(math.sqrt(len(rows))))), xi=0.05,
                            min_cluster_size=max(5, int(math.ceil(0.02 * len(rows))))).fit_predict(X)
        local_centroids = {int(label): X[labels == label].mean(axis=0) for label in sorted(set(labels)) if label >= 0}
        local_family = {}
        for label, centroid in local_centroids.items():
            candidates = sorted((float(np.linalg.norm(centroid - prior)), family) for family, prior in known.items())
            if candidates and candidates[0][0] <= 0.35:
                family = candidates[0][1]
            else:
                family = "MBOF|" + base.sha256_json([round(float(x), 8) for x in centroid])[:16]
                known[family] = centroid
            local_family[label] = family
        for row, label in zip(rows, labels):
            row["mbo_family"] = "MBO_NOISE" if int(label) < 0 else local_family[int(label)]
            row["mbo_family_day_cluster"] = int(label)
            row["family_availability_cutoff_ts_event_ns"] = full_set_event_cutoff
            row["family_availability_cutoff_ts_recv_ns"] = full_set_recv_cutoff
        day_receipts.append({"utc_day": day, "proposal_count": len(rows),
            "cluster_count": len(local_centroids), "noise_count": int(np.sum(labels < 0)),
            "family_ids": sorted(set(row["mbo_family"] for row in rows)),
            "causal_clock_set_sha256": base.sha256_json([{key: row[key] for key in (
                "event_id", "ts_event_ns", "ts_recv_ns", "f_last_group_completion_ts_recv_ns",
                "threshold_crossing_ts_recv_ns", "event_known_by_ts_recv_ns",
                "max_contributing_ts_recv_ns", "feature_cutoff_ts_recv_ns",
                "outcome_availability_cutoff_ts_event_ns", "outcome_availability_cutoff_ts_recv_ns")}
                for row in rows]),
            "earliest_event_known_by_ts_recv_ns": min(int(row["event_known_by_ts_recv_ns"]) for row in rows),
            "latest_event_known_by_ts_recv_ns": max(int(row["event_known_by_ts_recv_ns"]) for row in rows)})
    return {"method": "DETERMINISTIC_PER_DAY_OPTICS_FULL_CAUSAL_MBO59_CROSS_DAY_CENTROID_MATCH",
            "feature_names": list(MBO_FEATURE_NAMES), "feature_dimension": len(MBO_FEATURE_NAMES),
            "standardization": "FULL_PROPOSAL_SET_COLUMN_STANDARDIZATION_ZERO_VARIANCE_SCALE_ONE",
            "standardization_center": [float(value) for value in center],
            "standardization_scale": [float(value) for value in scale],
            "zero_variance_feature_names": [name for name, flag in zip(MBO_FEATURE_NAMES, zero_variance) if flag],
            "cross_day_centroid_tolerance_l2": 0.35,
            "noise_retained": True, "days": day_receipts,
            "classification_availability": "RETROSPECTIVE_AFTER_COMPLETE_PROPOSAL_SET",
            "family_availability_cutoff_ts_event_ns": full_set_event_cutoff,
            "family_availability_cutoff_ts_recv_ns": full_set_recv_cutoff,
            "family_not_knowable_at_t0": True, "family_used_in_proposal_generation": False,
            "family_used_in_outcome_construction": False, "family_used_in_structural_scorer": False,
            "family_count_excluding_noise": len({row["mbo_family"] for row in proposals if row["mbo_family"] != "MBO_NOISE"})}


def _outcome_availability(stream: dict[str, Any], seconds_by_epoch: dict[int, dict[str, Any]],
                          confirmation_idx: int | None) -> dict[str, Any]:
    sunday_epoch = int(datetime.combine(stream["week_sunday"], datetime.min.time(), tzinfo=timezone.utc).timestamp())
    if confirmation_idx is None:
        return {"status": "ENDPOINT_CONFIRMATION_CENSORED", "outcome_availability_cutoff_ts_event_ns": None,
                "outcome_availability_cutoff_ts_recv_ns": None, "horizons": {}}
    horizons = {}; maximum_recv = 0; maximum_event = 0
    for horizon in base.frozen_detector.HORIZONS:
        idx = int(confirmation_idx) + int(horizon); epoch = sunday_epoch + idx
        row = seconds_by_epoch.get(epoch)
        recv = None if row is None else int(row.get("last_ts_recv_ns") or 0) or None
        horizons[str(horizon)] = {"outcome_ts_event_ns": epoch * 1_000_000_000,
                                  "outcome_known_by_ts_recv_ns": recv,
                                  "censored_or_no_exact_receive_binding": recv is None}
        if recv is not None:
            maximum_recv = max(maximum_recv, recv); maximum_event = max(maximum_event, epoch * 1_000_000_000)
    return {"status": "POST_LOCK_FROZEN_OUTCOME_CLOCK_BOUND",
            "outcome_availability_cutoff_ts_event_ns": maximum_event or None,
            "outcome_availability_cutoff_ts_recv_ns": maximum_recv or None, "horizons": horizons}


def build_locked_proposal_events(proposals: list[dict[str, Any]], selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stream = base.build_week_stream(selected, "native")
    seconds_by_epoch = {int(row["epoch_second"]): row for row in selected}
    sunday_epoch = int(datetime.combine(stream["week_sunday"], datetime.min.time(), tzinfo=timezone.utc).timestamp())
    events = []
    for proposal in proposals:
        known_by_second = int(proposal["event_known_by_ts_recv_ns"]) // 1_000_000_000
        t0 = known_by_second - sunday_epoch; polarity = int(proposal["polarity"])
        onset, confirmation = base.frozen_detector.endpoint(stream, t0, polarity)
        now = datetime.fromtimestamp(known_by_second, tz=timezone.utc)
        outcome_clock = _outcome_availability(stream, seconds_by_epoch, confirmation)
        source = {"source_dbn_key": proposal["source_dbn_key"], "staged_source_dbn_object": proposal["source_dbn_object"],
                  "source_dbn_sha256": proposal["source_dbn_sha256"], "instrument_id": proposal["instrument_id"],
                  "event_ts_event_ns": proposal["ts_event_ns"], "event_known_by_ts_recv_ns": proposal["event_known_by_ts_recv_ns"],
                  "contract_resolution_status": "RESOLVED_FROM_DBN_METADATA_OR_RETAINED_INSTRUMENT_ID"}
        event = {"event_id": proposal["event_id"], "week_sunday": base.frozen_detector.ymds(stream["week_sunday"]),
            "t0_idx": t0, "source_utc_day": now.date().isoformat().replace("-", ""),
            "t0_second_utc_day": now.hour * 3600 + now.minute * 60 + now.second,
            "polarity": polarity, "family": proposal["mbo_family"], "pre_family_distances": None,
            "a_frozen_post_state": None, "seed_state": "UNCAPPED_FULL_MBO_CAUSAL_ONSET",
            "feature": {"uncapped_mbo_surfaces": proposal["surfaces"],
                        "causal_t0_all_signed_surfaces": proposal["causal_t0_surfaces"],
                        "causal_t0_complete_surface_inputs": proposal["causal_t0_surface_inputs"],
                        "family_feature_vector": proposal["family_feature_vector"]},
            "dynamic_endpoint": {"structural_onset_idx": onset, "causal_confirmation_idx": confirmation,
                "structural_onset_offset_s": None if onset is None else onset - t0,
                "causal_confirmation_offset_s": None if confirmation is None else confirmation - t0,
                "censored": confirmation is None},
            "time_context": {"utc": now.isoformat(), "clock_basis": "TS_RECV_CAUSAL_ONSET"},
            "outcome": {"post_endpoint_price": base.frozen_detector.price_aftermath(stream, confirmation, polarity),
                        "availability_clock": outcome_clock, "applied_after_proposal_and_family_lock": True},
            "source_boundary_censored": True, "source_provenance": source,
            "native_structure": {"taxonomy": "UNCAPPED_FULL_MBO_OPTICS_V1", "label": proposal["mbo_family"],
                "classification_timing": "RETROSPECTIVE_AFTER_COMPLETE_PROPOSAL_SET",
                "family_availability_cutoff_ts_event_ns": proposal["family_availability_cutoff_ts_event_ns"],
                "family_availability_cutoff_ts_recv_ns": proposal["family_availability_cutoff_ts_recv_ns"],
                "family_not_knowable_at_t0": True, "family_used_in_proposal_generation": False,
                "family_used_in_outcome_construction": False, "family_used_in_structural_scorer": False},
            "causal_clocks": {key: proposal[key] for key in (
                "ts_event_ns", "ts_recv_ns", "f_last_group_completion_ts_recv_ns",
                "threshold_crossing_ts_recv_ns", "event_known_by_ts_recv_ns", "max_contributing_ts_recv_ns",
                "feature_cutoff_ts_recv_ns", "event_recv_latency_ns", "event_not_after_receive")},
            "outcome_availability": outcome_clock}
        events.append(event)
    base.frozen_detector.attach_links(events)
    return events


def write_comparator_match_graph(events: list[dict[str, Any]], baseline: Path, out_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    comparators = {"legacy": list(base.read_gzip_jsonl(baseline / "LEGACY_CONTROL_EVENTS.jsonl.gz")),
                   "native": list(base.read_gzip_jsonl(baseline / "V4_NATIVE_FULL_EVENTS.jsonl.gz"))}
    writer = base.DeterministicGzipJsonlWriter(out_path); counts = Counter()
    for event in events:
        event_ns = int(event["causal_clocks"]["ts_event_ns"]); recv_ns = int(event["causal_clocks"]["ts_recv_ns"])
        for view, rows in comparators.items():
            for old in rows:
                if int(old["polarity"]) != int(event["polarity"]): continue
                sunday = datetime.strptime(str(old["week_sunday"]), "%Y%m%d").replace(tzinfo=timezone.utc)
                old_event_ns = (int(sunday.timestamp()) + int(old["t0_idx"])) * 1_000_000_000
                old_recv_ns = int((old.get("source_provenance") or {}).get("event_known_by_ts_recv_ns") or old_event_ns)
                de, dr = event_ns - old_event_ns, recv_ns - old_recv_ns
                if abs(de) > 2_000_000_000 and abs(dr) > 2_000_000_000: continue
                def relation(delta: int) -> str: return "COINCIDE" if abs(delta) <= 1_000_000_000 else ("LEAD" if delta < 0 else "FOLLOW")
                writer.write({"mbo_event_id": event["event_id"], "comparator_view": view,
                    "comparator_event_id": old["event_id"], "comparator_abc_family_annotation": old.get("family"),
                    "mbo_causal_clocks": event["causal_clocks"],
                    "mbo_outcome_availability": event["outcome_availability"],
                    "event_clock_delta_ns": de, "receive_clock_delta_ns": dr,
                    "event_clock_relation": relation(de), "receive_clock_relation": relation(dr),
                    "tolerance_ns": 2_000_000_000, "match_is_annotation_only": True})
                counts[f"{view}_{relation(de).lower()}_event_clock"] += 1
                counts[f"{view}_{relation(dr).lower()}_receive_clock"] += 1
    output = writer.close()
    observed = {
        view: {
            "event_count": len(rows),
            "family_counts": dict(sorted(Counter(str(row.get("family")) for row in rows).items())),
        }
        for view, rows in comparators.items()
    }
    return output, {"old_comparison_counts_observed_not_enforced": observed,
        "edge_relation_counts": dict(sorted(counts.items())), "abc_is_annotation_only": True,
        "count_or_family_cap_applied": False}


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
    copied = {}
    for name in names:
        src, dst = baseline / name, out / name
        if not src.is_file():
            raise base.CensusError(f"baseline legacy artifact missing: {name}")
        source_bytes, source_sha = src.stat().st_size, base.sha256_file(src)
        shutil.copyfile(src, dst)
        if dst.stat().st_size != source_bytes or base.sha256_file(dst) != source_sha:
            raise base.CensusError(f"baseline legacy artifact copy identity drift: {name}")
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

    surface_collector = MboSurfaceCollector(provenance)
    replay_surfaces = replay_surface_effects(raw_paths, surface_collector)
    proposals, proposal_lock = discover_uncapped_proposals(surface_collector.surface_rows)
    proposals_check, proposal_lock_check = discover_uncapped_proposals(surface_collector.surface_rows)
    if base.sha256_json(proposals) != base.sha256_json(proposals_check) or base.sha256_json(proposal_lock) != base.sha256_json(proposal_lock_check):
        raise base.CensusError("uncapped MBO proposal determinism failure")

    targets = [{"event_id": row["event_id"], "instrument_id": int(row["instrument_id"]),
                "source_dbn_key": row["source_dbn_key"],
                "cutoff_ts_recv_ns": int(row["feature_cutoff_ts_recv_ns"])} for row in proposals]
    collector = CausalMboCollector(targets)
    replay_features = replay_dbn_files([str(p) for p in raw_paths], collector.consume, materialize_full_state=False)
    for rows in (proposals, proposals_check):
        for proposal in rows:
            features = collector.feature_row(proposal["event_id"])["features"]
            proposal["mbo59_feature_names"] = list(MBO_FEATURE_NAMES)
            proposal["mbo59_feature_vector"] = [features[name] for name in MBO_FEATURE_NAMES]

    proposal_writer = base.DeterministicGzipJsonlWriter(out / "UNCAPPED_MBO_PROPOSALS.jsonl.gz")
    for proposal in proposals: proposal_writer.write(proposal)
    proposal_output = proposal_writer.close()
    proposal_lock.update({"complete_mbo59_attached_before_retrospective_family_discovery": True,
        "mbo59_attached_proposal_set_sha256": base.sha256_json(proposals),
        "deterministic_double_derivation_passed": True, "old_comparison_populations_used_as_cap": False})
    proposal_lock["receipt_sha256"] = base.sha256_json({k: v for k, v in proposal_lock.items() if k != "receipt_sha256"})
    proposal_lock_path = out / "UNCAPPED_MBO_PROPOSAL_LOCK.json"; base.atomic_json(proposal_lock_path, proposal_lock)

    family_discovery = discover_mbo_families(proposals)
    family_check = discover_mbo_families(proposals_check)
    if base.sha256_json(proposals) != base.sha256_json(proposals_check) or base.sha256_json(family_discovery) != base.sha256_json(family_check):
        raise base.CensusError("retrospective MBO family determinism failure")
    family_path = out / "UNCAPPED_MBO_FAMILY_DISCOVERY.json"
    family_artifact = {"schema": "NG_EXHAUSTION_UNCAPPED_MBO_FAMILY_DISCOVERY_V1_20260825",
        "status": "POST_PROPOSAL_LOCK_RETROSPECTIVE_FULL_MBO59_CLASSIFICATION", **family_discovery,
        "proposal_lock_receipt_sha256": proposal_lock["receipt_sha256"],
        "proposal_clock_set_sha256": base.sha256_json([{key: row[key] for key in (
            "event_id", "ts_event_ns", "ts_recv_ns", "f_last_group_completion_ts_recv_ns",
            "threshold_crossing_ts_recv_ns", "event_known_by_ts_recv_ns", "max_contributing_ts_recv_ns",
            "feature_cutoff_ts_recv_ns", "outcome_availability_cutoff_ts_event_ns",
            "outcome_availability_cutoff_ts_recv_ns")} for row in proposals]),
        "causal_clock_fields_required": ["ts_event_ns", "ts_recv_ns", "event_known_by_ts_recv_ns",
            "f_last_group_completion_ts_recv_ns", "threshold_crossing_ts_recv_ns",
            "max_contributing_ts_recv_ns", "feature_cutoff_ts_recv_ns",
            "outcome_availability_cutoff_ts_event_ns", "outcome_availability_cutoff_ts_recv_ns"],
        "outcomes_accessed": False, "family_label_used_by_proposal_outcome_or_scorer": False}
    family_artifact["receipt_sha256"] = base.sha256_json(family_artifact); base.atomic_json(family_path, family_artifact)

    events = build_locked_proposal_events(proposals, selected)
    families = dict(sorted(Counter(str(x.get("family")) for x in events).items()))
    cutoff_writer = base.DeterministicGzipJsonlWriter(out / "V4_NATIVE_FULL_MBO_CAUSAL_CUTOFF_BINDINGS.jsonl.gz")
    evidence_writer = base.DeterministicGzipJsonlWriter(out / "V4_NATIVE_FULL_MBO_EVENT_EVIDENCE.jsonl.gz")
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
            "matched_not_after_cutoff": True, "source_dbn_key": binding["source_dbn_key"],
            "source_dbn_object": binding["source_dbn_object"],
            "source_dbn_sha256": binding["source_dbn_sha256"], "full_mbo_feature_vector_sha256": feature_hash,
            "ts_event_ns": event["causal_clocks"]["ts_event_ns"], "ts_recv_ns": event["causal_clocks"]["ts_recv_ns"],
            "f_last_group_completion_ts_recv_ns": event["causal_clocks"]["f_last_group_completion_ts_recv_ns"],
            "threshold_crossing_ts_recv_ns": event["causal_clocks"]["threshold_crossing_ts_recv_ns"],
            "event_known_by_ts_recv_ns": event["causal_clocks"]["event_known_by_ts_recv_ns"],
            "max_contributing_ts_recv_ns": event["causal_clocks"]["max_contributing_ts_recv_ns"],
            "feature_cutoff_ts_recv_ns": event["causal_clocks"]["feature_cutoff_ts_recv_ns"],
            "outcome_availability": event["outcome_availability"]})
        evidence = {"event_id": event["event_id"], "instrument_id": binding["instrument_id"],
            "source_dbn_key": binding["source_dbn_key"],
            "feature_cutoff_ts_recv_ns": binding["cutoff_ts_recv_ns"],
            "causal_clocks": event["causal_clocks"], "outcome_availability": event["outcome_availability"],
            "raw_actions_through_cutoff": binding["raw_actions_through_cutoff"],
            "full_depth_fifo_checkpoint": binding["full_depth_fifo_checkpoint"],
            "lifecycle_and_acm_feature_names": list(MBO_FEATURE_NAMES),
            "lifecycle_and_acm_feature_values": [features[x] for x in MBO_FEATURE_NAMES],
            "complete_raw_order_ids_retained": True, "complete_full_depth_fifo_retained": True}
        evidence_hash = base.sha256_json(evidence); evidence["evidence_sha256"] = evidence_hash
        evidence_writer.write(evidence)
        event["full_mbo_at_t0"] = {"causal_resolution": "INSTRUMENT_SPECIFIC_LATEST_GROUP_NOT_AFTER_TS_RECV_CUTOFF",
            "cutoff_ts_recv_ns": binding["cutoff_ts_recv_ns"], "matched_ts_recv_ns": binding["matched_ts_recv_ns"],
            "instrument_id": binding["instrument_id"], "feature_vector_sha256": feature_hash,
            "complete_evidence_sha256": evidence_hash, **features}
        row = base.compact_lineage_input(event)
        frozen22 = list(row["behavior_vector_full"])
        if len(frozen22) != 22:
            raise base.CensusError("frozen behavior-vector dimension drift")
        row["behavior_vector_frozen22"] = frozen22
        row["full_mbo_feature_names"] = list(MBO_FEATURE_NAMES)
        row["behavior_vector_full"] = frozen22 + [features[x] for x in MBO_FEATURE_NAMES]
        event_writer.write(event); lineage_writer.write(row)
    event_output, lineage_output = event_writer.close(), lineage_writer.close()
    cutoff_output, evidence_output = cutoff_writer.close(), evidence_writer.close()
    comparator_output, comparator_summary = write_comparator_match_graph(
        events, baseline, out / "UNCAPPED_MBO_TO_OLD_BASELINES_MATCH_GRAPH.jsonl.gz")

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
            "proposal_surface_replay_summary": replay_surfaces,
            "causal_feature_replay_summary": replay_features,
            "vector_dimension": FULL_NATIVE_VECTOR_DIMENSION, "frozen_component_dimension": 22,
            "mbo_component_dimension": len(MBO_FEATURE_NAMES), "mbo_feature_names": list(MBO_FEATURE_NAMES),
            "information_retention": {"raw_actions_with_order_ids_and_ts_recv": True,
                "full_depth_all_levels_and_fifo_order_ids_at_each_event_cutoff": True,
                "complete_lifecycle_and_exact_A_C_M_apply_effect_features": True,
                "T_used_for_flow_only": True, "history_predictors_use_full_frozen22_plus_mbo59": True,
                "field_drop_substitution_or_lossy_compression": False,
                "evidence_container_compression": "DETERMINISTIC_LOSSLESS_GZIP"},
            "seconds_output": prior._relative_output(seconds_output, out),
            "event_output": prior._relative_output(event_output, out),
            "lineage_output": prior._relative_output(lineage_output, out),
            "causal_cutoff_binding_output": prior._relative_output(cutoff_output, out),
            "complete_event_evidence_output": prior._relative_output(evidence_output, out),
            "causal_binding_semantics": "INSTRUMENT_SPECIFIC_LATEST_GROUP_NOT_AFTER_TS_RECV_CUTOFF",
            "uncapped_proposal_output": prior._relative_output(proposal_output, out),
            "uncapped_proposal_lock": _artifact(proposal_lock_path, out),
            "uncapped_family_discovery": _artifact(family_path, out),
            "proposal_surfaces": list(PROPOSAL_SURFACES),
            "proposal_count_cap": None, "family_count_cap": None,
            "composite_merge_semantics": "ONE_EVENT_FOR_SAME_INSTRUMENT_POLARITY_RECEIVE_SECOND_MULTI_SURFACE_CROSSING",
            "rearm_semantics": "PER_MECHANISM_DUPLICATE_SUPPRESSION_NOT_A_COUNT_OR_FAMILY_CAP",
            "family_semantics": {"retrospective_after_complete_proposal_set": True,
                "full_causal_mbo59_cluster_inputs": True, "arbitrary_content_derived_family_ids": True,
                "noise_or_unassigned_retained": True, "not_knowable_at_t0": True,
                "used_in_proposal_generation": False, "used_in_outcome_construction": False,
                "used_in_structural_scorer": False,
                "availability_cutoff_ts_event_ns": family_discovery["family_availability_cutoff_ts_event_ns"],
                "availability_cutoff_ts_recv_ns": family_discovery["family_availability_cutoff_ts_recv_ns"]},
            "old_baseline_counts_are_comparison_only": {
                "event_counts": baseline_receipt["event_counts"],
                "family_counts": baseline_receipt["family_counts"],
            },
            "old_baseline_match_graph_output": prior._relative_output(comparator_output, out),
            "old_baseline_match_graph_summary": comparator_summary,
            "sparse_lineage_output": prior._relative_output(sparse_lineage, out),
            "gain_output": prior._relative_output(structural["gain_output"], out),
            "structural_summary": _artifact(summary_path, out),
            "population_output": prior._relative_output(population, out),
            "crosswalk_index_output": prior._relative_output(index, out),
            "event_count": len(events), "family_counts": families,
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
