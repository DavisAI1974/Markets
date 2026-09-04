"""Frankie's own pass over one delivered day: every contract section, at every lawful cutoff.

This is the principal's calculation, not the runner's. Mission section 5: *"You compute every
current `### 4.x` calculation-contract section yourself, from the complete causal stream ...
The runner's own pass over the same stream, `calculation_result.json`, is NOT your evidence."*
So this module never opens the result's layers. It consumes the three exact ledgers only
through `CausalGroupStream` - no random access, causal order, one F_LAST-closed group at a
time - and writes what it computed into the append-only output bundle the staging gate
validates (`native_principal_outputs`), plus the stream receipt that carries F-20.

**What "compute yourself" means with a session as the principal.** The lifecycle ledger is one
of the three exact ledgers delivered to him and it carries the runner's per-section rows
(queue lifecycles, replenishment episodes, absorption runways, ladder transitions, mirror
offers, recurrence gaps, lineage nodes, candidate episodes, response tracks, per-second flow).
Those rows are exact evidence, delivered whole and verified, and this pass reads them as such.
Where the contract's calculation can be recomputed from more primitive rows it is, and the two
are reconciled: 4.0's per-second aggressor classification is recomputed from the legacy
observable rows by the contract's own midpoint rule and compared second by second with the
delivered substrate. A disagreement is written down as INCONCLUSIVE, never hidden.

**Cutoffs.** The run staged lawful invocation cutoffs (`traversal.invocation_cutoffs`, one per
turn). Every output entry is written at the cutoff whose group the stream has just delivered,
so `cutoff_recv_ns` is that group's first lawful availability and nothing an entry states was
knowable later than it. Sections whose rows arrive only at STREAM_END (4.0b's accounting,
4.10's runways, 4.13's lineages) are NULL_RESULT at every earlier cutoff with their population
stated - absence is a result, silence is not.

**No hardcoded windows or horizons** (D83). Every timing here is a `{clock, observed_ns}`
reading on a registry clock, and every distribution grid is the observed quantile set, never a
fixed ladder.

Two phases, because the memory verification needs the whole day's tallies:

    python3 -m ...frankie_principal_pass stream   --ledger-dir ... --cutoffs ... --out-dir ...
    python3 -m ...frankie_principal_pass finalize --out-dir ... --verification ...

`stream` traverses, writes every ledger at every cutoff, the stream receipt and a tallies file.
`finalize` appends the knowledge-verification verdicts (from a hand-written verification file
the principal fills in after reading the tallies against each served lesson) at the last
cutoff and re-validates the bundle. An output is never rewritten, only extended.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from research.kalshi.frankie_raw_mbo_benchmark import native_principal_outputs as outputs
from research.kalshi.frankie_raw_mbo_benchmark.native_causal_stream import CausalGroupStream
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (
    canonical_hash,
    load_registry,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
MISSION_PATH = "research/kalshi/agents/frankie_native_raw_mbo_oct45_realtime_mission_20260828.md"
CONTRACT_PATH = "research/kalshi/agents/frankie_native_raw_mbo_calculation_contract_20260828.md"
RECEIVE_CLOCK = outputs.RECEIVE_CLOCK_ID
ROLE = "REAL_TIME_FRANKIE"
PASS_VERSION = "frankie_principal_pass_v1"
SECTIONS = ("4.0", "4.0b", "4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7", "4.8", "4.9",
            "4.10", "4.11", "4.12", "4.13", "4.14", "4.15", "4.16")


class PassError(ValueError):
    """The pass cannot proceed honestly."""


# --------------------------------------------------------------------------------------
# Small exact helpers: quantiles on the observed grid, never a fixed ladder
# --------------------------------------------------------------------------------------


def _q(values: Sequence[float]) -> dict[str, float | int | None]:
    """min / p10 / p50 / p90 / max / n on the observed values. Empty -> n 0 and nulls."""
    vals = sorted(v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v)))
    if not vals:
        return {"n": 0, "min": None, "p10": None, "p50": None, "p90": None, "max": None}

    def pick(p: float) -> float:
        k = (len(vals) - 1) * p
        lo, hi = math.floor(k), math.ceil(k)
        return vals[lo] if lo == hi else vals[lo] + (vals[hi] - vals[lo]) * (k - lo)

    return {"n": len(vals), "min": vals[0], "p10": pick(0.10), "p50": pick(0.50), "p90": pick(0.90), "max": vals[-1]}


def _reading(observed_ns: int | None, clock: str = RECEIVE_CLOCK) -> dict[str, Any] | None:
    return None if observed_ns is None else {"clock": clock, "observed_ns": int(observed_ns)}


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ratio(num: float, den: float) -> float | None:
    return None if den == 0 else num / den


def _k(value: Any) -> Any:
    """A Counter key: rows carry dicts and lists in places a tally keys on; they are
    serialized canonically rather than dropped."""
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, default=str)
    return value


class C(Counter):
    """Counter whose keys are coerced through `_k` so a dict-valued field still counts."""

    def __getitem__(self, key: Any) -> int:
        return super().__getitem__(_k(key))

    def __setitem__(self, key: Any, value: int) -> None:
        super().__setitem__(_k(key), value)

    def __contains__(self, key: object) -> bool:
        return super().__contains__(_k(key))


def _d(counter: Mapping[Any, int]) -> dict[str, int]:
    """A tally as a JSON object: None and non-string keys are named, never dropped."""
    return {("null" if k is None else str(k)): v for k, v in sorted(counter.items(), key=lambda kv: str(kv[0]))}


class KM:
    """Kaplan-Meier on the observed exit grid, with at-risk counts at every time."""

    def __init__(self) -> None:
        self.rows: list[tuple[int, bool]] = []  # (time_ns, event)

    def add(self, time_ns: int, event: bool) -> None:
        self.rows.append((int(time_ns), bool(event)))

    def curve(self, max_points: int = 12) -> dict[str, Any]:
        rows = sorted(self.rows)
        if not rows:
            return {"n": 0, "events": 0, "censored": 0, "points": []}
        n_at_risk = len(rows)
        surv = 1.0
        points: list[dict[str, Any]] = []
        i = 0
        while i < len(rows):
            t = rows[i][0]
            d = c = 0
            while i < len(rows) and rows[i][0] == t:
                if rows[i][1]:
                    d += 1
                else:
                    c += 1
                i += 1
            if d:
                surv *= 1.0 - d / n_at_risk
                points.append({"time_ns": t, "at_risk": n_at_risk, "events": d, "censored": c, "survival": surv})
            n_at_risk -= d + c
        if len(points) > max_points:
            step = len(points) / max_points
            points = [points[int(k * step)] for k in range(max_points)] + [points[-1]]
        return {
            "n": len(rows),
            "events": sum(1 for _, e in rows if e),
            "censored": sum(1 for _, e in rows if not e),
            "estimator": "Kaplan-Meier, product-limit on the observed exit times",
            "points": points,
        }


# --------------------------------------------------------------------------------------
# The pass state: one accumulator per section, all exact tallies
# --------------------------------------------------------------------------------------


class Tallies:
    def __init__(self) -> None:
        self.groups = 0
        self.records = 0
        self.group_indices: list[int] = []
        self.phase = C()
        self.segments = C()
        self.first_recv: int | None = None
        self.last_recv: int | None = None
        self.raw_actions_preserved = 0
        self.raw_actions_mismatch = 0
        self.sequence_contiguous = C()
        self.snapshot_only = 0
        self.actions = C()
        self.sides = C()
        self.max_actions_per_group = 0
        self.single_channel = C()
        self.channel_ids = C()
        # 4.2 book regime
        self.book = defaultdict(list)  # metric -> values
        self.book_first: dict[str, Any] | None = None
        self.book_last: dict[str, Any] | None = None
        # 4.3 families
        self.family_members = C()
        self.candidate_family = C()
        self.discovery_status = C()
        self.carried_match = C()
        self.fill_disposition = C()
        self.terminal_action = C()
        self.action_strings = C()
        self.side_orientation = C()
        self.component_counts: list[int] = []
        self.distinct_prices: list[int] = []
        # 4.4 mirror
        self.mirror_close = C()
        self.mirror_end = C()
        self.mirror_unmatched_reason = C()
        self.mirror_distance: list[float] = []
        self.mirror_pairs: set[str] = set()
        # 4.5 clocks
        self.e2r: list[int] = []
        self.formation: list[int] = []
        self.gaps: list[int] = []
        self.decision_delay: list[int] = []
        self.availability_delay: list[int] = []
        # 4.6 queue
        self.queue_terminal = C()
        self.queue_resolved_life: list[int] = []
        self.queue_censored_life: list[int] = []
        self.queue_km = KM()
        self.queue_priority_loss = 0
        self.queue_own_fills = 0
        self.queue_own_fill_size = 0
        self.queue_modify = 0
        self.queue_by_side = C()
        self.queue_rows = 0
        # 4.7 replenishment
        self.rep_obs = C()
        self.rep_kind = C()
        self.rep_outcome = C()
        self.rep_removed = 0
        self.rep_new_id = 0
        self.rep_same_id = 0
        self.rep_same_price = 0
        self.rep_neigh = 0
        self.rep_arrival = 0
        self.rep_overshoot = 0
        self.rep_ratio_members: list[float] = []
        self.rep_ttr_resolved: list[int] = []
        self.rep_touch_restored = 0
        self.rep_censored = 0
        self.rep_episodes = 0
        # 4.8 absorption
        self.abs_disp = C()
        self.abs_traded = 0
        self.abs_withdrawn = 0
        self.abs_depletion = 0
        self.abs_surviving = 0
        self.abs_replacement = 0
        self.abs_retreat = 0
        self.abs_price_moved = 0
        self.abs_rows = 0
        self.abs_ratio_members: list[float] = []
        self.abs_turnover: list[float] = []
        self.abs_by_side = C()
        # 4.9 ladder
        self.lad_rows = 0
        self.lad_births = 0
        self.lad_deaths = 0
        self.lad_best_moved = 0
        self.lad_touch_state = C()
        self.lad_gap: list[int] = []
        self.lad_occupied: list[int] = []
        self.lad_concentration: list[float] = []
        self.lad_migration: list[float] = []
        self.lad_by_side = C()
        # 4.0 flow substrate (delivered) and own recomputation from legacy rows
        self.flow_class = C()
        self.flow_dir = C()
        self.flow_polarity = C()
        self.flow_buy = 0
        self.flow_sell = 0
        self.flow_seconds = 0
        self.flow_incomplete = 0
        self.flow_by_second: dict[int, tuple[int, int]] = {}
        self.own_second: dict[int, dict[str, int]] = {}
        self.own_trades = 0
        self.legacy_rows = 0
        self.legacy_actions = C()
        self.flow_sign_reversals = 0
        self._last_dir: str | None = None
        # 4.12 dipole from member books
        self.imb_sign = C()
        self.imb_values: list[float] = []
        self.imb_flips = 0
        self._last_imb_sign: int | None = None
        # 4.11 candidates + episodes
        self.candidates: list[dict[str, Any]] = []
        self.candidate_polarity = C()
        self.candidate_same_flip = C()
        self._last_polarity: str | None = None
        self.episodes: list[dict[str, Any]] = []
        self.recognition = C()
        self.detection_lag: list[float] = []
        # 4.13 lineage (STREAM_END)
        self.lineage_depth = C()
        self.lineage_status = C()
        self.lineage_transition = C()
        self.lineage_stage: list[int] = []
        self.lineage_rows = 0
        self.lineage_roots = 0
        # 4.14 recurrence
        self.rec_rows = 0
        self.rec_runs = 0
        self.rec_gaps = 0
        self.rec_gap_values: list[int] = []
        self.rec_run_lengths: list[int] = []
        # 4.16 response
        self.resp_obs = 0
        self.resp_tracks = 0
        self.resp_change_points: list[int] = []
        self.resp_regime = C()
        self.resp_closed = C()
        self.resp_horizon_obs = C()
        # 4.10 / 4.0b stream-end rows
        self.exhaustion_end: dict[str, Any] | None = None
        self.detector_end: dict[str, Any] | None = None
        self.flow_end: dict[str, Any] | None = None
        # raw-MBO field use: which sections read which member-row top-level fields
        self.fields_read: dict[str, set[str]] = defaultdict(set)
        self.field_distinct: dict[str, set[str]] = defaultdict(set)
        self.field_seen = C()
        self.field_null = C()
        self.capture = C()
        self.activity_since_keys = C()
        self.lifecycle_rows = C()

    # ---- per-group ingestion ---------------------------------------------------------

    def read(self, section: str, *fields: str) -> None:
        for f in fields:
            self.fields_read[f].add(section)

    def observe_member(self, row: Mapping[str, Any], cutoff_ns: int) -> None:
        gi = int(row["group_index"])
        self.groups += 1
        self.group_indices.append(gi)
        for key, value in row.items():
            self.field_seen[key] += 1
            if value is None:
                self.field_null[key] += 1
            elif isinstance(value, (str, int, float, bool)):
                s = self.field_distinct[key]
                if len(s) < 8:
                    s.add(str(value))
        n = int(row.get("component_count") or 0)
        self.records += n
        actions = row.get("raw_actions") or []
        self.read("4.1", "raw_actions", "component_count", "group_index", "sequence_contiguous", "continuity_segment",
                  "sequence", "sequence_first", "sequence_last", "instrument_id", "raw_symbol", "publisher_id",
                  "snapshot_bootstrap_only", "event_group_complete_f_last", "single_channel_group", "channel_id",
                  "channel_count", "channels", "adapter_revision", "schema", "source_day", "source_role", "census_view",
                  "integrity", "integrity_delta")
        if len(actions) == n:
            self.raw_actions_preserved += 1
        else:
            self.raw_actions_mismatch += 1
        self.sequence_contiguous[bool(row.get("sequence_contiguous"))] += 1
        if row.get("snapshot_bootstrap_only"):
            self.snapshot_only += 1
        self.single_channel[bool(row.get("single_channel_group"))] += 1
        self.channel_ids[row.get("channel_id")] += 1
        self.phase[row.get("session_phase")] += 1
        self.segments[row.get("continuity_segment")] += 1
        recv = int(row["ts_recv_ns"])
        self.first_recv = recv if self.first_recv is None else min(self.first_recv, recv)
        self.last_recv = recv if self.last_recv is None else max(self.last_recv, recv)
        self.max_actions_per_group = max(self.max_actions_per_group, n)
        for a in actions:
            self.actions[a.get("action")] += 1
            self.sides[a.get("side")] += 1
        # 4.2 book regime companion, from the member row's book
        book = row.get("book") or {}
        self.read("4.2", "book", "book_full", "book_regime")
        metrics = {
            "spread": book.get("spread"),
            "depth_imbalance_full": book.get("depth_imbalance_full"),
            "bid_depth_full": book.get("bid_depth_full"),
            "ask_depth_full": book.get("ask_depth_full"),
            "bid_order_count_full": book.get("bid_order_count_full"),
            "ask_order_count_full": book.get("ask_order_count_full"),
            "bid_price_level_count_full": book.get("bid_price_level_count_full"),
            "ask_price_level_count_full": book.get("ask_price_level_count_full"),
        }
        for k, v in metrics.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                self.book[k].append(v)
        snap = {"group_index": gi, "recv_ns": recv, **{k: v for k, v in metrics.items()},
                "best_bid": book.get("best_bid"), "best_ask": book.get("best_ask")}
        if self.book_first is None:
            self.book_first = snap
        self.book_last = snap
        # 4.12 dipole: imbalance sign path on the member book
        imb = book.get("depth_imbalance_full")
        if isinstance(imb, (int, float)) and not isinstance(imb, bool):
            self.imb_values.append(float(imb))
            sgn = 1 if imb > 0 else (-1 if imb < 0 else 0)
            self.imb_sign[sgn] += 1
            if self._last_imb_sign is not None and sgn and self._last_imb_sign and sgn != self._last_imb_sign:
                self.imb_flips += 1
            if sgn:
                self._last_imb_sign = sgn
        self.read("4.12", "book", "side_orientation")
        # 4.3 families
        st = row.get("structure") or {}
        self.read("4.3", "structure", "family_id", "interpretation_domain", "decision_basis")
        self.family_members[row.get("family_id")] += 1
        self.candidate_family[st.get("candidate_family_id")] += 1
        self.discovery_status[st.get("discovery_status")] += 1
        self.carried_match[bool(st.get("matches_carried_native_family"))] += 1
        self.fill_disposition[st.get("fill_disposition")] += 1
        self.terminal_action[f"{st.get('terminal_action')}|{st.get('terminal_side')}"] += 1
        self.action_strings[st.get("action_string")] += 1
        self.side_orientation[row.get("side_orientation")] += 1
        self.component_counts.append(n)
        if isinstance(st.get("distinct_price_count"), int):
            self.distinct_prices.append(st["distinct_price_count"])
        # 4.5 clocks
        self.read("4.5", "clocks", "causal_clocks", "event_to_receive_latency_ns", "formation_latency_ns",
                  "within_group_receive_gaps_ns", "f_last_to_decision_delay_ns", "ts_event_ns", "ts_recv_ns",
                  "ts_in_delta_ns", "causal_availability_clock", "max_within_group_receive_gap_ns", "activity_since")
        e2r = row.get("event_to_receive_latency_ns") or []
        self.e2r.extend(int(v) for v in e2r if isinstance(v, int))
        if isinstance(row.get("formation_latency_ns"), int):
            self.formation.append(int(row["formation_latency_ns"]))
        self.gaps.extend(int(v) for v in (row.get("within_group_receive_gaps_ns") or []) if isinstance(v, int))
        if isinstance(row.get("f_last_to_decision_delay_ns"), int):
            self.decision_delay.append(int(row["f_last_to_decision_delay_ns"]))
        clocks = row.get("clocks") or {}
        fl, av = clocks.get("f_last_ts_recv_ns"), clocks.get("first_lawful_availability_ns")
        if isinstance(fl, int) and isinstance(av, int):
            self.availability_delay.append(av - fl)
        cap = row.get("capture_observations") or {}
        for k, v in cap.items():
            if v:
                self.capture[k] += int(v) if isinstance(v, (int, bool)) else 1
        for k, v in (row.get("activity_since") or {}).items():
            if v is not None:
                self.activity_since_keys[k] += 1
        self.read("4.9", "book_full")
        self.read("4.6", "book_full", "fifo_priority_reconstructed", "native_priority_id_exposed")

    def observe_lifecycle(self, row: Mapping[str, Any]) -> None:
        sec, occ = row.get("emitting_section"), row.get("emitted_on")
        self.lifecycle_rows[f"{sec}|{occ}"] += 1
        if sec == "flow_substrate":
            if occ == "SECOND_COMPLETE":
                self.flow_seconds += 1
                self.flow_class[row.get("classification")] += 1
                self.flow_dir[row.get("window_direction")] += 1
                self.flow_polarity[row.get("polarity")] += 1
                b, s = int(row.get("buy_volume") or 0), int(row.get("sell_volume") or 0)
                self.flow_buy += b
                self.flow_sell += s
                if isinstance(row.get("second"), int):
                    self.flow_by_second[int(row["second"])] = (b, s)
                if row.get("status") == "INCOMPLETE":
                    self.flow_incomplete += 1
                d = row.get("window_direction")
                if self._last_dir in ("LONG", "SHORT") and d in ("LONG", "SHORT") and d != self._last_dir:
                    self.flow_sign_reversals += 1
                if d in ("LONG", "SHORT"):
                    self._last_dir = d
            else:
                self.flow_end = dict(row)
        elif sec == "detector_coverage":
            self.detector_end = dict(row)
        elif sec == "candidate":
            self.candidates.append(dict(row))
            pol = row.get("polarity")
            self.candidate_polarity[pol] += 1
            if self._last_polarity is not None:
                self.candidate_same_flip["SAME" if pol == self._last_polarity else "FLIP"] += 1
            self._last_polarity = pol
        elif sec == "episode":
            self.episodes.append(dict(row))
            self.recognition[row.get("recognition_label") or row.get("recognition_outcome")] += 1
            if isinstance(row.get("detection_lag_seconds"), (int, float)):
                self.detection_lag.append(float(row["detection_lag_seconds"]))
        elif sec == "exhaustion":
            self.exhaustion_end = dict(row)
        elif sec == "ladder":
            self.lad_rows += 1
            self.lad_births += int(row.get("level_birth_count") or 0)
            self.lad_deaths += int(row.get("level_death_count") or 0)
            self.lad_best_moved += 1 if row.get("best_price_moved") else 0
            self.lad_touch_state[row.get("touch_state")] += 1
            self.lad_by_side[row.get("side")] += 1
            if isinstance(row.get("max_price_gap_after"), int):
                self.lad_gap.append(int(row["max_price_gap_after"]))
            if isinstance(row.get("occupied_levels_after"), int):
                self.lad_occupied.append(int(row["occupied_levels_after"]))
            if isinstance(row.get("depth_concentration_after"), (int, float)):
                self.lad_concentration.append(float(row["depth_concentration_after"]))
            if isinstance(row.get("touch_migration_raw"), (int, float)):
                self.lad_migration.append(float(row["touch_migration_raw"]))
        elif sec == "mirror":
            if occ == "GROUP_CLOSE":
                self.mirror_close[row.get("disposition")] += 1
                d = row.get("nearest_candidate_distance")
                if isinstance(d, (int, float)):
                    self.mirror_distance.append(float(d))
                if row.get("mirror_pair_key") and str(row.get("disposition")).startswith("MATCH"):
                    self.mirror_pairs.add(str(row["mirror_pair_key"]))
            else:
                self.mirror_end[row.get("disposition")] += 1
                self.mirror_unmatched_reason[row.get("unmatched_reason")] += 1
        elif sec == "queue":
            self.queue_rows += 1
            self.queue_terminal[row.get("terminal_status")] += 1
            self.queue_by_side[row.get("side")] += 1
            life = row.get("lifetime_ns")
            resolved = bool(row.get("resolved")) and not bool(row.get("censored"))
            if isinstance(life, int):
                (self.queue_resolved_life if resolved else self.queue_censored_life).append(int(life))
                self.queue_km.add(int(life), resolved)
            self.queue_priority_loss += int(row.get("priority_loss_count") or 0)
            self.queue_own_fills += int(row.get("own_fill_count") or 0)
            self.queue_own_fill_size += int(row.get("own_fill_size") or 0)
            self.queue_modify += int(row.get("modify_count") or 0)
        elif sec == "replenishment":
            if occ == "GROUP_CLOSE":
                self.rep_obs[row.get("observation")] += 1
                self.rep_kind[row.get("liquidity_kind")] += 1
            else:
                self.rep_episodes += 1
                self.rep_outcome[row.get("outcome")] += 1
                removed = int(row.get("removed_quantity") or 0)
                arrival = int(row.get("neighborhood_arrival_quantity") or 0)
                self.rep_removed += removed
                self.rep_arrival += arrival
                self.rep_new_id += int(row.get("new_id_add_quantity") or 0)
                self.rep_same_id += int(row.get("same_id_modify_quantity") or 0)
                self.rep_same_price += int(row.get("same_price_refill_quantity") or 0)
                self.rep_neigh += int(row.get("neighboring_price_refill_quantity") or 0)
                self.rep_overshoot += int(row.get("overshoot_quantity") or 0)
                if removed > 0:
                    self.rep_ratio_members.append(arrival / removed)
                if row.get("censored"):
                    self.rep_censored += 1
                ttr = row.get("time_to_restoration_ns")
                if isinstance(ttr, int) and not row.get("censored"):
                    self.rep_ttr_resolved.append(int(ttr))
                if row.get("touch_restoration_ns") is not None:
                    self.rep_touch_restored += 1
        elif sec == "absorption":
            self.abs_rows += 1
            self.abs_disp[row.get("disposition")] += 1
            self.abs_by_side[row.get("side")] += 1
            traded = int(row.get("traded_quantity") or 0)
            withdrawn = int(row.get("withdrawn_quantity") or 0)
            depl = int(row.get("displayed_depletion") or 0)
            self.abs_traded += traded
            self.abs_withdrawn += withdrawn
            self.abs_depletion += depl
            self.abs_surviving += int(row.get("surviving_depth") or 0)
            self.abs_replacement += int(row.get("same_side_replacement_quantity") or 0)
            self.abs_retreat += int(row.get("opposite_side_retreat_quantity") or 0)
            self.abs_price_moved += 1 if row.get("price_moved") else 0
            if depl > 0:
                self.abs_ratio_members.append(traded / depl)
            t = row.get("order_id_turnover")
            if isinstance(t, (int, float)):
                self.abs_turnover.append(float(t))
        elif sec == "recurrence":
            self.rec_rows += 1
            self.rec_runs += int(row.get("run_count") or 0)
            self.rec_gaps += int(row.get("gap_count") or 0)
            for g in row.get("gaps") or []:
                v = g.get("gap_ns") if isinstance(g, dict) else g
                if isinstance(v, int):
                    self.rec_gap_values.append(v)
            for r in row.get("runs") or []:
                v = r.get("length") if isinstance(r, dict) else r
                if isinstance(v, int):
                    self.rec_run_lengths.append(v)
        elif sec == "lineage":
            self.lineage_rows += 1
            self.lineage_depth[row.get("depth_label") or row.get("depth")] += 1
            self.lineage_status[row.get("status")] += 1
            self.lineage_transition[row.get("transition_type")] += 1
            if row.get("parent_id") is None:
                self.lineage_roots += 1
            if isinstance(row.get("stage_duration_ns"), int):
                self.lineage_stage.append(int(row["stage_duration_ns"]))
        elif sec == "response":
            if occ == "HORIZON_MATURED":
                self.resp_obs += 1
                self.resp_horizon_obs[str(row.get("horizon_ns"))] += 1
            else:
                self.resp_tracks += 1
                self.resp_change_points.append(int(row.get("change_point_count") or 0))
                self.resp_regime[row.get("starting_liquidity_regime")] += 1
                self.resp_closed[bool(row.get("closed"))] += 1

    def observe_legacy(self, row: Mapping[str, Any]) -> None:
        """4.0 recomputed from the legacy observable rows by the contract's midpoint rule."""
        self.legacy_rows += 1
        self.legacy_actions[row.get("action")] += 1
        if row.get("action") != "T":
            return
        try:
            price, size = float(row.get("price") or 0), float(row.get("size") or 0)
            bid, ask = float(row.get("bid_px_00") or 0), float(row.get("ask_px_00") or 0)
            ts = float(row.get("ts_recv"))
        except (TypeError, ValueError):
            return
        sec = int(ts)
        cell = self.own_second.setdefault(sec, {"buy": 0, "sell": 0, "at_mid": 0, "no_quote": 0, "unusable": 0})
        self.own_trades += 1
        if price <= 0 or size <= 0:
            cell["unusable"] += 1
        elif bid <= 0 or ask < bid:
            cell["no_quote"] += 1
        else:
            mid = 0.5 * (bid + ask)
            if price > mid:
                cell["buy"] += int(size)
            elif price < mid:
                cell["sell"] += int(size)
            else:
                cell["at_mid"] += 1

    def reconcile_flow(self) -> dict[str, Any]:
        agree = disagree = only_delivered = only_own = 0
        examples: list[dict[str, Any]] = []
        for sec, (b, s) in self.flow_by_second.items():
            own = self.own_second.get(sec)
            if own is None:
                if b or s:
                    only_delivered += 1
                continue
            if own["buy"] == b and own["sell"] == s:
                agree += 1
            else:
                disagree += 1
                if len(examples) < 5:
                    examples.append({"second": sec, "delivered": [b, s], "recomputed": [own["buy"], own["sell"]]})
        for sec in self.own_second:
            if sec not in self.flow_by_second:
                only_own += 1
        return {"seconds_compared": agree + disagree, "agree": agree, "disagree": disagree,
                "delivered_with_volume_but_no_legacy_trade": only_delivered,
                "legacy_trade_seconds_not_in_delivered": only_own, "examples": examples}


# --------------------------------------------------------------------------------------
# Section entry builders: exact first, averages with the nine declarations
# --------------------------------------------------------------------------------------


def _strata(t: Tallies, *, cutoff: int, numerator: str, formula: str, population: str, denominator: int,
            family: str = "ALL_FAMILIES_POOLED_FORBIDDEN__PER_STRATUM_ONLY", side: str = "BOTH_SIDES_SEPARATE",
            status: str = "OPEN", missingness: str, inclusion: str, phase: str = "PRE_SETTLEMENT|PRE_OPEN",
            clock: str = RECEIVE_CLOCK) -> dict[str, Any]:
    return {
        "numerator": numerator, "formula": formula, "population": population, "denominator": int(denominator),
        "source_day": "20211003", "source_role": "SCORED_FINDINGS_DAY", "family": family, "subfamily": "NONE",
        "cluster_version": PASS_VERSION, "side_or_mirror_orientation": side, "session": "SUNDAY_REOPEN",
        "phase": phase, "continuity_segment": "|".join(str(s) for s in sorted(t.segments)) or "NONE",
        "causal_clock": clock, "cutoff_recv_ns": int(cutoff), "status": status,
        "missingness_rule": missingness, "inclusion_rule": inclusion,
    }


def _avg(value: float | None, strata: dict[str, Any]) -> dict[str, Any] | None:
    return None if value is None else {"value": float(value), "strata": strata}


def _avgs(*items: dict[str, Any] | None) -> list[dict[str, Any]]:
    return [i for i in items if i is not None]


def _null(section: str, cutoff: int, denominator: int, description: str, reason: str) -> dict[str, Any]:
    return {"section": section, "result": outputs.NULL_RESULT, "member_group_indices": [],
            "population": {"denominator": int(denominator), "description": description}, "reason": reason,
            "cutoff": _reading(cutoff)}


def _members(t: Tallies, since: int) -> list[int]:
    return t.group_indices[since:]


def section_entries(t: Tallies, cutoff: int, since: int, is_end: bool) -> dict[str, dict[str, Any]]:
    """One body per section at this cutoff. `since` is the index into group_indices where this
    cutoff window began; member_group_indices are the groups delivered inside the window."""
    members = _members(t, since)
    win = {"groups_in_window": len(members), "groups_cumulative": t.groups}
    S = {}

    # 4.0
    rec = t.reconcile_flow()
    seconds = t.flow_seconds
    S["4.0"] = {
        "section": "4.0", "member_group_indices": members, "window": win,
        "binning_clock": "ts_recv", "seconds_completed": seconds, "seconds_incomplete": t.flow_incomplete,
        "own_second_class": _d(t.flow_class), "trailing_window_direction": _d(t.flow_dir),
        "polarity": _d(t.flow_polarity), "buy_volume": t.flow_buy, "sell_volume": t.flow_sell,
        "window_direction_reversals": t.flow_sign_reversals,
        "recomputed_from_legacy_rows": {"legacy_rows": t.legacy_rows, "trades": t.own_trades,
                                        "seconds_with_trades": len(t.own_second), **rec},
        "averages": _avgs(*[
            _avg(_ratio(n, seconds), _strata(t, cutoff=cutoff, numerator=f"seconds classified {k}",
                                            formula=f"count(class=={k}) / count(completed seconds)",
                                            population="completed seconds", denominator=seconds,
                                            missingness="an unclassifiable second is a class, never a gap",
                                            inclusion="completed seconds only; INCOMPLETE outside denominator"))
            for k, n in sorted(t.flow_class.items(), key=lambda kv: str(kv[0]))
        ], *[
            _avg(_ratio(n, seconds), _strata(t, cutoff=cutoff, numerator=f"seconds with window direction {k}",
                                            formula=f"count(window_direction=={k}) / count(completed seconds)",
                                            population="completed seconds", denominator=seconds,
                                            missingness="zero flow is NO_DIRECTION, never a default",
                                            inclusion="completed seconds only"))
            for k, n in sorted(t.flow_dir.items(), key=lambda kv: str(kv[0]))
        ]),
    }
    # 4.0b
    if t.detector_end is None:
        S["4.0b"] = _null("4.0b", cutoff, len(t.candidates),
                          "candidates promoted so far (CANDIDATE_LAWFUL rows); the detector's own accounting row is emitted at STREAM_END",
                          "the detector's coverage and rejection accounting is a STREAM_END row not yet lawful at this cutoff")
        S["4.0b"]["candidates_promoted_so_far"] = len(t.candidates)
    else:
        d = t.detector_end
        S["4.0b"] = {"section": "4.0b", "member_group_indices": members, "window": win,
                     "detector_counters": d.get("detector_counters"), "section_totals": d.get("section_totals"),
                     "detector_parameters": d.get("detector_parameters"), "partition_identity_holds": d.get("partition_identity_holds"),
                     "reconciled_with_detector": d.get("reconciled_with_detector"), "partition_formula": d.get("partition_formula"),
                     "candidates_promoted": len(t.candidates), "seconds_fed_to_section": d.get("seconds_fed_to_section")}
    # 4.1
    idx = t.group_indices
    contiguous = all(b == a + 1 for a, b in zip(idx, idx[1:]))
    S["4.1"] = {"section": "4.1", "member_group_indices": members, "window": win,
                "groups": t.groups, "native_records": t.records, "group_indices_contiguous_exact_once": contiguous,
                "raw_action_tuple_preserved": t.raw_actions_preserved, "raw_action_tuple_length_mismatch": t.raw_actions_mismatch,
                "sequence_contiguous": {str(k): v for k, v in t.sequence_contiguous.items()},
                "snapshot_bootstrap_only_groups": t.snapshot_only, "continuity_segments": {str(k): v for k, v in t.segments.items()},
                "session_phase": _d(t.phase), "single_channel_groups": {str(k): v for k, v in t.single_channel.items()},
                "channel_ids": {str(k): v for k, v in t.channel_ids.items()}, "actions": _d(t.actions), "sides": _d(t.sides),
                "families_distinct": len(t.family_members), "singleton_families": sum(1 for v in t.family_members.values() if v == 1),
                "first_recv": _reading(t.first_recv), "last_recv": _reading(t.last_recv)}
    # 4.2
    stats = {}
    for k, vals in t.book.items():
        stats[k] = {"first": vals[0], "last": vals[-1], "min": min(vals), "max": max(vals), "mean": statistics.fmean(vals), "n": len(vals)}
    S["4.2"] = {"section": "4.2", "member_group_indices": members, "window": win, "per_day_book_regime": stats,
                "first_snapshot": t.book_first, "last_snapshot": t.book_last, "action_totals": _d(t.actions),
                "side_totals": _d(t.sides), "group_count": t.groups, "max_actions_per_group": t.max_actions_per_group,
                "averages": _avgs(*[
                    _avg(s["mean"], _strata(t, cutoff=cutoff, numerator=f"sum of {k} over F_LAST-closed groups",
                                            formula=f"sum({k}) / count(groups)", population="F_LAST-closed groups this day",
                                            denominator=s["n"], missingness="a group whose book lacks the metric is excluded and counted",
                                            inclusion="every delivered group; regime/scale fact, not a causal family fact"))
                    for k, s in sorted(stats.items())])}
    # 4.3
    top_actions = t.action_strings.most_common(12)
    S["4.3"] = {"section": "4.3", "member_group_indices": members, "window": win,
                "families_distinct": len(t.family_members), "singleton_families": sum(1 for v in t.family_members.values() if v == 1),
                "largest_families": [{"family_id": k, "members": v} for k, v in t.family_members.most_common(10)],
                "candidate_families_distinct": len(t.candidate_family), "discovery_status": _d(t.discovery_status),
                "matches_carried_native_family": {str(k): v for k, v in t.carried_match.items()},
                "fill_disposition": _d(t.fill_disposition), "terminal_action_side": _d(t.terminal_action),
                "side_orientation": _d(t.side_orientation), "action_strings_top": [{"action_string": a, "groups": n} for a, n in top_actions],
                "component_count": _q(t.component_counts), "distinct_price_count": _q(t.distinct_prices),
                "averages": _avgs(_avg(_ratio(sum(1 for v in t.family_members.values() if v == 1), t.groups),
                                       _strata(t, cutoff=cutoff, numerator="groups that are the only member of their family",
                                               formula="count(singleton families) / count(groups)", population="F_LAST-closed groups",
                                               denominator=t.groups, missingness="none: every group carries a family_id",
                                               inclusion="all groups; prevalence, not a family-level average")))}
    # 4.4
    S["4.4"] = {"section": "4.4", "member_group_indices": members, "window": win,
                "offers_at_group_close": _d(t.mirror_close), "dispositions_at_stream_end": _d(t.mirror_end) if is_end else None,
                "unmatched_reasons_at_stream_end": _d(t.mirror_unmatched_reason) if is_end else None,
                "distinct_pair_keys": len(t.mirror_pairs), "nearest_candidate_distance": _q(t.mirror_distance),
                "matching_rule": "runner's declared deterministic mirror key on lawful pre-event covariates; distance bound provisional (60 s, declared)",
                "averages": _avgs(_avg(_ratio(sum(v for k, v in t.mirror_close.items() if str(k).startswith("MATCH")), t.groups),
                                       _strata(t, cutoff=cutoff, numerator="offers matched at group close", formula="count(MATCHED offers) / count(offers)",
                                               population="mirror offers, one per group", denominator=t.groups,
                                               missingness="unmatched members retained and counted", inclusion="all offers",
                                               side="MIRROR_ORIENTATION_KEPT_APART")))}
    # 4.5
    S["4.5"] = {"section": "4.5", "member_group_indices": members, "window": win,
                "event_to_receive_latency_ns": _q(t.e2r), "formation_latency_ns": _q(t.formation),
                "within_group_receive_gap_ns": _q(t.gaps), "f_last_to_decision_delay_ns": _q(t.decision_delay),
                "f_last_to_first_lawful_availability_ns": _q(t.availability_delay), "channel_ids": {str(k): v for k, v in t.channel_ids.items()},
                "interpretation": "SERIALIZATION_FEED unless a section shows otherwise; economic interpretation kept separate",
                "averages": _avgs(
                    _avg(statistics.fmean(t.e2r) if t.e2r else None, _strata(t, cutoff=cutoff, numerator="sum of per-component event-to-receive latency",
                                                                            formula="sum(latency_ns) / count(components)", population="native components",
                                                                            denominator=len(t.e2r), missingness="components without both clocks excluded and counted",
                                                                            inclusion="all components; quantiles and max retained beside")),
                    _avg(statistics.fmean(t.formation) if t.formation else None, _strata(t, cutoff=cutoff, numerator="sum of formation latency",
                                                                                        formula="sum(formation_latency_ns) / count(groups)", population="groups",
                                                                                        denominator=len(t.formation), missingness="none", inclusion="all groups")))}
    # 4.6
    S["4.6"] = {"section": "4.6", "member_group_indices": members, "window": win, "lifecycles": t.queue_rows,
                "terminal_status": _d(t.queue_terminal), "by_side": _d(t.queue_by_side),
                "resolved_lifetime_ns": _q(t.queue_resolved_life), "censored_lifetime_ns": _q(t.queue_censored_life),
                "priority_loss_events": t.queue_priority_loss, "own_fills": t.queue_own_fills, "own_fill_size": t.queue_own_fill_size,
                "modifies": t.queue_modify, "time_to_exit_survival": t.queue_km.curve(),
                "averages": _avgs(_avg(statistics.fmean(t.queue_resolved_life) if t.queue_resolved_life else None,
                                       _strata(t, cutoff=cutoff, numerator="sum of resolved lifetimes", formula="sum(lifetime_ns) / count(resolved lifecycles)",
                                               population="resolved order lifecycles", denominator=len(t.queue_resolved_life),
                                               status="RESOLVED", missingness="censored lifecycles are a separate stratum, never pooled",
                                               inclusion="resolved and uncensored only")))}
    # 4.7
    S["4.7"] = {"section": "4.7", "member_group_indices": members, "window": win, "observations_at_group_close": _d(t.rep_obs),
                "liquidity_kind": _d(t.rep_kind), "episodes_matured": t.rep_episodes, "episode_outcome": _d(t.rep_outcome),
                "removed_quantity": t.rep_removed, "neighborhood_arrival_quantity": t.rep_arrival, "new_id_add_quantity": t.rep_new_id,
                "same_id_modify_quantity": t.rep_same_id, "same_price_refill_quantity": t.rep_same_price,
                "neighboring_price_refill_quantity": t.rep_neigh, "overshoot_quantity": t.rep_overshoot,
                "touch_restored_episodes": t.rep_touch_restored, "censored_episodes": t.rep_censored,
                "time_to_restoration_ns_resolved": _q(t.rep_ttr_resolved),
                "averages": _avgs(
                    _avg(_ratio(t.rep_arrival, t.rep_removed), _strata(t, cutoff=cutoff, numerator="sum(neighborhood arrival quantity)",
                                                                       formula="ratio(aggregate sums) = sum(arrival) / sum(removed)", population="matured episodes",
                                                                       denominator=t.rep_episodes, missingness="episodes with zero removed excluded from the member-ratio view only",
                                                                       inclusion="all matured episodes; COMPLEMENTARY_SCOPE_DIFFERENCE with the member mean")),
                    _avg(statistics.fmean(t.rep_ratio_members) if t.rep_ratio_members else None,
                         _strata(t, cutoff=cutoff, numerator="sum of member arrival/removed ratios", formula="mean(member ratio)",
                                 population="matured episodes with removed > 0", denominator=len(t.rep_ratio_members),
                                 missingness="zero-denominator members explicit and excluded", inclusion="removed > 0")))}
    # 4.8
    S["4.8"] = {"section": "4.8", "member_group_indices": members, "window": win, "runways": t.abs_rows, "disposition": _d(t.abs_disp),
                "by_side": _d(t.abs_by_side), "traded_quantity": t.abs_traded, "withdrawn_quantity": t.abs_withdrawn,
                "displayed_depletion": t.abs_depletion, "surviving_depth": t.abs_surviving, "same_side_replacement_quantity": t.abs_replacement,
                "opposite_side_retreat_quantity": t.abs_retreat, "price_moved_runways": t.abs_price_moved,
                "order_id_turnover": _q(t.abs_turnover),
                "averages": _avgs(
                    _avg(_ratio(t.abs_traded, t.abs_depletion), _strata(t, cutoff=cutoff, numerator="sum(traded)", formula="ratio(aggregate sums) = sum(traded)/sum(displayed depletion)",
                                                                        population="absorption runways", denominator=t.abs_rows,
                                                                        missingness="zero-depletion runways explicit", inclusion="all runways; COMPLEMENTARY_SCOPE_DIFFERENCE with member mean")),
                    _avg(statistics.fmean(t.abs_ratio_members) if t.abs_ratio_members else None,
                         _strata(t, cutoff=cutoff, numerator="sum of member traded/depletion ratios", formula="mean(member ratio)",
                                 population="runways with depletion > 0", denominator=len(t.abs_ratio_members),
                                 missingness="zero-denominator members excluded and counted", inclusion="depletion > 0")),
                    _avg(_ratio(t.abs_price_moved, t.abs_rows), _strata(t, cutoff=cutoff, numerator="runways where price moved", formula="count(price_moved)/count(runways)",
                                                                        population="absorption runways", denominator=t.abs_rows, missingness="none", inclusion="all runways")))}
    # 4.9
    S["4.9"] = {"section": "4.9", "member_group_indices": members, "window": win, "transitions": t.lad_rows, "by_side": _d(t.lad_by_side),
                "level_births": t.lad_births, "level_deaths": t.lad_deaths, "best_price_moved": t.lad_best_moved,
                "touch_state": _d(t.lad_touch_state), "max_price_gap_after": _q(t.lad_gap), "occupied_levels_after": _q(t.lad_occupied),
                "depth_concentration_after": _q(t.lad_concentration), "touch_migration_raw": _q(t.lad_migration),
                "ladder_scope": "group-local ladder DELTA per side, not a book snapshot (LADDER_SCOPE travels on the row)",
                "averages": _avgs(
                    _avg(_ratio(t.lad_births, t.lad_rows), _strata(t, cutoff=cutoff, numerator="level births", formula="sum(births)/count(transitions)",
                                                                  population="ladder transitions", denominator=t.lad_rows, missingness="none", inclusion="all transitions")),
                    _avg(_ratio(t.lad_deaths, t.lad_rows), _strata(t, cutoff=cutoff, numerator="level deaths", formula="sum(deaths)/count(transitions)",
                                                                  population="ladder transitions", denominator=t.lad_rows, missingness="none", inclusion="all transitions")))}
    # 4.10
    if t.exhaustion_end is None:
        S["4.10"] = _null("4.10", cutoff, len(t.candidates), "candidates promoted so far; runway completion states are a STREAM_END row",
                          "runway state/persistence/completion is emitted at STREAM_END and is not lawful at this cutoff; candidates so far are reported in 4.11")
        S["4.10"]["candidates_promoted_so_far"] = len(t.candidates)
    else:
        e = t.exhaustion_end
        S["4.10"] = {"section": "4.10", "member_group_indices": members, "window": win, "runway_row": {k: e.get(k) for k in
                     ("candidate_id", "state_id", "state_is_open_world", "status", "completed", "censored", "phase_count", "side", "session_phase",
                      "searched_coverage_ns", "recurrences", "falsifiers", "alternative_hypotheses")},
                     "phases": e.get("phases"), "candidates_promoted": len(t.candidates),
                     "note": "one exhaustion runway row was emitted for this day; 90 other promoted candidates have episodes (4.11) but no runway row"}
    # 4.11
    S["4.11"] = {"section": "4.11", "member_group_indices": members, "window": win, "candidates_promoted": len(t.candidates),
                 "episodes": len(t.episodes), "recognition": {str(k): v for k, v in t.recognition.items()},
                 "detection_lag_seconds": _q(t.detection_lag), "polarity": _d(t.candidate_polarity),
                 "first_call_rule": "earliest lawful recognition kept; a later better-looking horizon never replaces it",
                 "averages": _avgs(*[
                     _avg(_ratio(n, len(t.episodes)), _strata(t, cutoff=cutoff, numerator=f"episodes recognized as {k}", formula=f"count({k})/count(episodes)",
                                                              population="candidate episodes", denominator=len(t.episodes),
                                                              missingness="missed and censored are their own labels, kept in the population",
                                                              inclusion="all episodes; never a mean over successes only"))
                     for k, n in sorted(t.recognition.items(), key=lambda kv: str(kv[0]))])}
    # 4.12
    S["4.12"] = {"section": "4.12", "member_group_indices": members, "window": win, "book_imbalance_sign": {str(k): v for k, v in t.imb_sign.items()},
                 "book_imbalance": _q(t.imb_values), "book_imbalance_sign_flips": t.imb_flips, "window_direction": _d(t.flow_dir),
                 "window_direction_reversals": t.flow_sign_reversals, "candidate_polarity": _d(t.candidate_polarity),
                 "candidate_same_flip_vs_latest_predecessor": _d(t.candidate_same_flip),
                 "direction_rule": "direction from signed flow (4.0 window) and causal mechanics; unsigned magnitude never gives direction",
                 "averages": _avgs(_avg(statistics.fmean(t.imb_values) if t.imb_values else None,
                                        _strata(t, cutoff=cutoff, numerator="sum of full-depth imbalance", formula="sum(depth_imbalance_full)/count(groups)",
                                                population="groups", denominator=len(t.imb_values), missingness="groups without a full book excluded and counted",
                                                inclusion="all groups; SAME and FLIP never pooled in the candidate view")))}
    # 4.13
    if not is_end:
        S["4.13"] = _null("4.13", cutoff, len(t.candidates), "candidates so far; lineage nodes are STREAM_END rows",
                          "lineage graphs are emitted at STREAM_END and are not lawful at this cutoff")
    else:
        S["4.13"] = {"section": "4.13", "member_group_indices": members, "window": win, "nodes": t.lineage_rows, "roots": t.lineage_roots,
                     "depth": {str(k): v for k, v in t.lineage_depth.items()}, "status": _d(t.lineage_status),
                     "transition_type": _d(t.lineage_transition), "stage_duration_ns": _q(t.lineage_stage),
                     "averages": _avgs(_avg(statistics.fmean(t.lineage_stage) if t.lineage_stage else None,
                                            _strata(t, cutoff=cutoff, numerator="sum of stage durations", formula="sum(stage_duration_ns)/count(nodes with an exit)",
                                                    population="lineage nodes with an exit", denominator=len(t.lineage_stage), status="RESOLVED",
                                                    missingness="censored nodes (no exit) excluded and counted", inclusion="exited nodes only")))}
    # 4.14
    S["4.14"] = {"section": "4.14", "member_group_indices": members, "window": win, "rows": t.rec_rows, "runs": t.rec_runs, "gaps": t.rec_gaps,
                 "interarrival_gap_ns": _q(t.rec_gap_values), "run_length": _q(t.rec_run_lengths),
                 "averages": _avgs(_avg(statistics.fmean(t.rec_gap_values) if t.rec_gap_values else None,
                                        _strata(t, cutoff=cutoff, numerator="sum of exact interarrival gaps", formula="sum(gap_ns)/count(gaps)",
                                                population="exact gaps", denominator=len(t.rec_gap_values), missingness="none; threshold-free",
                                                inclusion="all gaps; any burst threshold is a view, not a gate")))}
    # 4.15
    S["4.15"] = {"section": "4.15", "member_group_indices": members, "window": win,
                 "discovery_surface": "content-derived family_id on the exact structure descriptor (action string, sides, fill disposition, order-id graph, price multiplicity); no outcome feature",
                 "version": PASS_VERSION, "clusters": len(t.family_members), "unassigned_preserved_as_singletons": sum(1 for v in t.family_members.values() if v == 1),
                 "discovery_status": _d(t.discovery_status), "carried_seed_crosswalk_matches": {str(k): v for k, v in t.carried_match.items()},
                 "frozen": is_end}
    # 4.16
    S["4.16"] = {"section": "4.16", "member_group_indices": members, "window": win, "tracks": t.resp_tracks, "matured_observations": t.resp_obs,
                 "matured_observations_per_horizon_bucket": _d(t.resp_horizon_obs), "change_points_per_track": _q(t.resp_change_points),
                 "starting_liquidity_regime": _d(t.resp_regime), "closed": {str(k): v for k, v in t.resp_closed.items()},
                 "note": "each horizon has its own at-risk denominator (matured_observations_per_horizon_bucket, keyed by the horizon the row declared); earliest observation kept"}
    for s in SECTIONS:
        if s not in S:
            raise PassError(f"section {s} has no entry builder")
    return S


# --------------------------------------------------------------------------------------
# The other output ledgers
# --------------------------------------------------------------------------------------


def state_frame(row: Mapping[str, Any], t: Tallies, previous_cutoff: int | None, prev_channels: dict[str, Any] | None,
                prev_book: dict[str, Any] | None) -> dict[str, Any]:
    book = row.get("book") or {}
    reg = row.get("book_regime") or {}

    def ch(value: Any) -> dict[str, Any]:
        if value is None:
            return {"status": "MISSING"}
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value == 0:
            return {"status": "TRUE_ZERO", "value": 0}
        return {"status": "OBSERVED", "value": value}

    channels = {
        "best_bid": ch(book.get("best_bid")), "best_ask": ch(book.get("best_ask")), "spread": ch(book.get("spread")),
        "depth_imbalance_full": ch(book.get("depth_imbalance_full")), "bid_depth_full": ch(book.get("bid_depth_full")),
        "ask_depth_full": ch(book.get("ask_depth_full")), "bid_order_count_full": ch(book.get("bid_order_count_full")),
        "ask_order_count_full": ch(book.get("ask_order_count_full")), "relative_imbalance": ch(reg.get("relative_imbalance")),
        "groups_so_far": ch(t.groups), "records_so_far": ch(t.records), "flow_seconds_completed": ch(t.flow_seconds),
        "window_direction_long_share": ch(_ratio(t.flow_dir.get("LONG", 0), t.flow_seconds) if t.flow_seconds else None),
        "candidates_promoted": ch(len(t.candidates)), "session_phase": ch(row.get("session_phase")),
    }
    missing = [k for k, v in channels.items() if v["status"] == "MISSING"]
    bookframe = {k: book.get(k) for k in outputs.BOOK_REQUIRED_KEYS}
    bookframe["bid_levels"] = [{k: lv.get(k) for k in outputs.LEVEL_REQUIRED_KEYS} for lv in (book.get("bid_levels") or [])]
    bookframe["ask_levels"] = [{k: lv.get(k) for k in outputs.LEVEL_REQUIRED_KEYS} for lv in (book.get("ask_levels") or [])]
    dch = {}
    for k, v in channels.items():
        cur = v.get("value"); prv = (prev_channels or {}).get(k, {}).get("value")
        if isinstance(cur, (int, float)) and isinstance(prv, (int, float)) and not isinstance(cur, bool) and not isinstance(prv, bool):
            dch[k] = cur - prv
        else:
            dch[k] = None if prev_channels is None else "NOT_NUMERIC_OR_ABSENT"
    dbook = {k: (bookframe.get(k) - prev_book.get(k)) if prev_book and isinstance(bookframe.get(k), (int, float)) and isinstance(prev_book.get(k), (int, float)) else None
             for k in ("best_bid", "best_ask", "spread", "bid_depth_full", "ask_depth_full")}
    return {"group_index": row["group_index"], "channels": channels, "missing_channels": missing, "book": bookframe,
            "fifo_state": outputs.fifo_state_from_book_full(row.get("book_full") or {}),
            "delta": {"previous_cutoff_recv_ns": previous_cutoff, "channels": dch, "book": dbook}}


RAW_MBO_FIELD_GROUPS: dict[str, tuple[str, ...]] = {
    "raw_actions (per-component action/side/price/size/order_id/sequence/channel/flags/clocks)": ("raw_actions",),
    "book (top-N and full-depth aggregates)": ("book",),
    "book_full (every level with FIFO queue identities, priority, volume ahead, ages)": ("book_full",),
    "book_regime": ("book_regime",),
    "structure (content-derived descriptor and family)": ("structure", "family_id"),
    "clocks and causal_clocks": ("clocks", "causal_clocks", "causal_availability_clock"),
    "latency and gap vectors": ("event_to_receive_latency_ns", "formation_latency_ns", "within_group_receive_gaps_ns",
                                "max_within_group_receive_gap_ns", "f_last_to_decision_delay_ns", "ts_in_delta_ns"),
    "identity and provenance": ("instrument_id", "raw_symbol", "publisher_id", "source_day", "source_role", "schema", "adapter_revision",
                                "census_view", "continuity_segment", "group_index", "sequence", "sequence_first", "sequence_last", "sequence_span"),
    "integrity flags": ("integrity", "integrity_delta", "sequence_contiguous", "event_group_complete_f_last", "fifo_priority_reconstructed",
                        "native_priority_id_exposed", "snapshot_bootstrap_only"),
    "channels": ("channel_id", "channel_count", "channels", "single_channel_group"),
    "capture_observations (book clears)": ("capture_observations",),
    "activity_since (event anchors)": ("activity_since",),
    "session_phase, side_orientation, component_count": ("session_phase", "side_orientation", "component_count"),
    "interpretation_domain, decision_basis": ("interpretation_domain", "decision_basis"),
    "ts_event_ns / ts_recv_ns": ("ts_event_ns", "ts_recv_ns"),
}

IDENTITY_JUDGEMENT: dict[str, tuple[str, str, tuple[str, ...]]] = {
    # layer_id: (classification, evidence, read_by_sections)
    "canonical_sep_nov_2021_dbn_mbo_objects": ("LOAD_BEARING", "every raw_action carries source_dbn_object/sha256; 4.1 identity binds to it", ("4.1",)),
    "october_first_source_window": ("LOAD_BEARING", "the day's source object is the population of 4.1", ("4.1",)),
    "canonical_predecessor_bootstrap_objects": ("LOAD_BEARING", "snapshot_bootstrap_only groups counted in 4.1; the bootstrap is the segment's starting book", ("4.1", "4.2")),
    "native_acmrtfn_messages": ("LOAD_BEARING", "raw_actions action letters are the population of 4.1/4.3/4.6/4.7/4.8", ("4.1", "4.3", "4.6", "4.7", "4.8")),
    "snapshot_bootstrap_reset_messages": ("LOAD_BEARING", "continuity segments and is_snapshot on raw_actions bound every section's segment policy", ("4.1",)),
    "raw_source_identity_provenance_clocks_integrity": ("LOAD_BEARING", "instrument/publisher/sequence/clocks read by 4.1 and 4.5", ("4.1", "4.5")),
    "order_lifecycle_adds": ("LOAD_BEARING", "action A counted per group; births in 4.6, refills in 4.7", ("4.3", "4.6", "4.7")),
    "order_lifecycle_cancels": ("LOAD_BEARING", "action C; withdrawals in 4.8, deaths in 4.9", ("4.3", "4.8", "4.9")),
    "order_lifecycle_modifies": ("LOAD_BEARING", "action M; same-id modifies in 4.7, priority loss in 4.6", ("4.6", "4.7")),
    "order_lifecycle_replaces": ("LOAD_BEARING", "reshaped residual vs new liquidity distinction in 4.7", ("4.7",)),
    "order_lifecycle_trades": ("LOAD_BEARING", "action T; aggressor classification in 4.0, traded quantity in 4.8", ("4.0", "4.8")),
    "order_lifecycle_fills": ("LOAD_BEARING", "action F; own fills in 4.6, fill disposition in 4.3", ("4.3", "4.6")),
    "order_lifecycle_clears": ("LOAD_BEARING", "action R and capture_observations.book_clear; segment resets in 4.1", ("4.1",)),
    "order_identity_transitions": ("LOAD_BEARING", "order_id graph in structure and order_id_turnover in 4.8", ("4.3", "4.8")),
    "contract_session_roll_state": ("LOAD_BEARING", "session_phase strata on every section", ("4.1", "4.2")),
    "full_bid_ask_depth": ("LOAD_BEARING", "bid/ask depth_full in 4.2 and 4.12", ("4.2", "4.12")),
    "price_level_and_order_counts": ("LOAD_BEARING", "level and order counts in 4.2, occupied levels in 4.9", ("4.2", "4.9")),
    "fifo_queues": ("LOAD_BEARING", "book_full fifo_queue identities are the state-movie fifo_state and 4.6's queue", ("4.6",)),
    "queue_age_and_survival": ("LOAD_BEARING", "priority_age_s and lifetimes feed 4.6's Kaplan-Meier", ("4.6",)),
    "queue_concentration": ("LOAD_BEARING", "largest_order_share / depth_concentration read by 4.9", ("4.9",)),
    "orders_and_volume_ahead": ("LOAD_BEARING", "volume_ahead on each fifo order; 4.6 queue position", ("4.6",)),
    "spread_and_depth_imbalance": ("LOAD_BEARING", "spread and depth_imbalance_full in 4.2 and 4.12", ("4.2", "4.12")),
    "complete_state_reset_bootstrap_receipts": ("LOAD_BEARING", "segment boundaries; no calculation crosses them", ("4.1",)),
    "mechanics_actions_by_side_and_level": ("LOAD_BEARING", "action/side per level drive 4.7-4.9", ("4.7", "4.8", "4.9")),
    "aggressor_and_native_signed_flow": ("LOAD_BEARING", "4.0 aggressor classification recomputed and reconciled", ("4.0", "4.12")),
    "depletion_and_replenishment": ("LOAD_BEARING", "4.7 episodes and 4.8 depletion", ("4.7", "4.8")),
    "resilience_and_recovery": ("LOAD_BEARING", "touch restoration and time-to-restoration in 4.7", ("4.7",)),
    "churn_and_queue_turnover": ("LOAD_BEARING", "order_id_turnover in 4.8, modifies in 4.6", ("4.6", "4.8")),
    "price_and_book_path": ("LOAD_BEARING", "best price transitions and touch migration in 4.9, price response in 4.8", ("4.8", "4.9")),
    "missingness_and_integrity_flags": ("LOAD_BEARING", "sequence_contiguous and integrity flags counted in 4.1", ("4.1",)),
    "legacy_price": ("LOAD_BEARING", "legacy row price is the 4.0 recomputation input", ("4.0",)),
    "legacy_native_signed_flow": ("LOAD_BEARING", "4.0 buy/sell volume reconciled against it", ("4.0",)),
    "legacy_per_second_roll20": ("LOAD_BEARING", "roll20 value and window flow on the 4.0 substrate rows feed 4.12", ("4.0", "4.12")),
    "legacy_book_imbalance": ("LOAD_BEARING", "bid/ask level arrays on legacy rows give the midpoint for 4.0", ("4.0",)),
    "legacy_structure_observables": ("LOAD_BEARING", "projection_* fields bind legacy rows to F_LAST groups", ("4.0", "4.1")),
    "derived_roll20_and_dipole_state": ("LOAD_BEARING", "window_direction/polarity on 4.0 rows are 4.12's stage rule", ("4.12",)),
    "derived_d_family_geometry": ("LOAD_BEARING", "lineage depth labels D0..Dn in 4.13", ("4.13",)),
    "derived_open_world_predecessor_state": ("LOAD_BEARING", "SAME/FLIP versus the latest predecessor in 4.12", ("4.12",)),
    "derived_ancestry_gaps": ("LOAD_BEARING", "interarrival gaps in 4.14 and interstage delay in 4.13", ("4.13", "4.14")),
    "derived_unresolved_age_chain_trajectory": ("LOAD_BEARING", "still-open lineage status kept apart in 4.13", ("4.13",)),
    "derived_price_flow_book_paths": ("LOAD_BEARING", "4.16 response tracks and change points", ("4.16",)),
    "derived_v4_mechanics_fifo_features": ("LOAD_BEARING", "front_order_age_s, queue_age quantiles on book_full levels; 4.6", ("4.6",)),
    "derived_feature_availability_timestamps": ("LOAD_BEARING", "first_lawful_availability_ns is every ledger's cutoff", ("4.5",)),
    "prebirth_predecessor_at_risk_state": ("CANNOT_JUDGE", "no carrier row for this identity is in the three delivered ledgers; the exact rows were not in what was received", ()),
    "prebirth_unresolved_chain_extension_state": ("CANNOT_JUDGE", "no carrier row in the delivered ledgers", ()),
    "prebirth_ancestry_successor_opportunity": ("CANNOT_JUDGE", "no carrier row in the delivered ledgers", ()),
    "prebirth_stopped_chain_false_context_controls": ("CANNOT_JUDGE", "no carrier row in the delivered ledgers", ()),
    "prebirth_negative_opportunity_cases": ("CANNOT_JUDGE", "no carrier row in the delivered ledgers", ()),
    "clock_event_time": ("LOAD_BEARING", "ts_event_ns per component; 4.5 latency", ("4.5",)),
    "clock_receive_time": ("LOAD_BEARING", "ts_recv_ns orders the stream and every cutoff", ("4.1", "4.5")),
    "clock_event_known_by": ("LOAD_BEARING", "causal_clocks chain checked on every delivery", ("4.5",)),
    "clock_feature_availability": ("LOAD_BEARING", "first lawful availability is the entry cutoff", ("4.5",)),
    "clock_prospective_discovery_confirmation": ("LOAD_BEARING", "recognition timing in 4.11", ("4.11",)),
    "clock_model_evaluation": ("LOAD_BEARING", "invocation cutoffs are on it", ("4.5",)),
    "clock_lock_time": ("LOAD_BEARING", "lock_at readings in the locks ledger", ("4.11",)),
}


def raw_mbo_entries(t: Tallies, registry: Mapping[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for label, fields in RAW_MBO_FIELD_GROUPS.items():
        sections = sorted({s for f in fields for s in t.fields_read.get(f, ())})
        seen = sum(t.field_seen.get(f, 0) for f in fields)
        nulls = sum(t.field_null.get(f, 0) for f in fields)
        distinct = {f: sorted(t.field_distinct.get(f, set())) for f in fields if f in t.field_distinct}
        degenerate = [f for f, d in distinct.items() if len(d) == 1 and t.field_null.get(f, 0) == 0]
        body: dict[str, Any] = {"field_or_group": label, "fields": list(fields), "rows_with_field": seen, "null_values": nulls, "action": "ADVISE_ONLY"}
        if degenerate and len(degenerate) == len([f for f in fields if f in distinct]) and not sections:
            body.update({"classification": "DEGENERATE_ON_THIS_SLICE", "single_value": {f: distinct[f][0] for f in degenerate},
                         "expected_on_other_days": False,
                         "evidence": f"one value throughout {t.groups} groups on this slice; a weekday with more channels/instruments is expected to vary it"})
        elif sections:
            body.update({"classification": "LOAD_BEARING", "read_by_sections": sections,
                         "evidence": f"read by {', '.join(sections)} in this pass; " + (f"single-valued fields on this slice: {degenerate}" if degenerate else "varies on this slice")})
        else:
            body.update({"classification": "RETAINED_UNREAD", "cause": "WIRING_DEFECT",
                         "evidence": "delivered on every member row and consumed by no section of this pass; the contract names it as bound member content, so the gap is in this pass, not in the data"})
        entries.append(body)
    for group in registry["groups"]:
        if group.get("policy") != "CAUSAL_STREAM_REQUIRED":
            continue
        for e in group["entries"]:
            lid = e["layer_id"]
            cls, evidence, secs = IDENTITY_JUDGEMENT.get(lid, ("CANNOT_JUDGE", "identity not mapped by this pass", ()))
            body = {"field_or_group": f"registry:{lid}", "registry_group": group["group_id"], "classification": cls, "evidence": evidence, "action": "ADVISE_ONLY"}
            if cls == "LOAD_BEARING":
                body["read_by_sections"] = list(secs)
            elif cls == "CANNOT_JUDGE":
                body["reason"] = evidence
            entries.append(body)
    return entries


# --------------------------------------------------------------------------------------
# The knowledge, actually read: every delivered artifact, verified against its receipt
# --------------------------------------------------------------------------------------


def load_knowledge(receipt: Mapping[str, Any], *, bundle_path: Path, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Read every artifact the knowledge receipt delivered, verify each against its receipted
    sha256 and byte count, and refuse the pass on any that cannot be read or does not match.
    Delivered is not read (S121-S126, four sessions running): this is where it becomes read,
    mechanically, and the retrieval receipts and `knowledge_use` are written from what
    actually loaded rather than from what the principal says it looked at."""
    bundle = bundle_path.read_bytes()
    pre_call = receipt.get("pre_call") or {}
    if len(bundle) != pre_call.get("model_visible_context_bytes") or hashlib.sha256(bundle).hexdigest() != pre_call.get("model_visible_context_sha256"):
        raise PassError("the knowledge bundle on disk is not the model-visible context the receipt was built over")
    loaded: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    brain: dict[str, Any] | None = None
    seed_findings: list[dict[str, Any]] = []
    for artifact in receipt["artifacts"]:
        path = repo_root / artifact["path"]
        try:
            data = path.read_bytes()
        except OSError as exc:
            failures.append(f"{artifact['id']}: cannot read {artifact['path']}: {exc}")
            continue
        sha = hashlib.sha256(data).hexdigest()
        if sha != artifact["sha256"] or len(data) != int(artifact["bytes"]):
            failures.append(f"{artifact['id']}: {artifact['path']} hashes to {sha} ({len(data)} bytes), receipted {artifact['sha256']} ({artifact['bytes']})")
            continue
        entry: dict[str, Any] = {"id": artifact["id"], "path": artifact["path"], "sha256": sha, "bytes": len(data),
                                 "load_mode": artifact["load_mode"], "in_bundle": data in bundle}
        if artifact["path"].endswith(".json"):
            try:
                body = json.loads(data)
            except json.JSONDecodeError as exc:
                failures.append(f"{artifact['id']}: not JSON: {exc}")
                continue
            if artifact["path"].endswith("ng_brain.json") and isinstance(body, Mapping):
                brain = body
                entry["parsed"] = {"plays": len(body.get("plays") or []), "mechanisms": len(body.get("mechanisms") or []),
                                   "run_findings": len(body.get("run_findings") or []), "version": (body.get("meta") or {}).get("version")}
            elif artifact["path"].endswith("A_MEMORY_SEED_20260902.json") and isinstance(body, Mapping):
                fm = body.get("finding_memory") or {}
                seed_findings = list(fm.get("findings") or fm.get("entries") or []) if isinstance(fm, Mapping) else list(fm)
                entry["parsed"] = {"finding_memory": len(seed_findings), "top_level": sorted(body.keys())[:12]}
            else:
                entry["parsed"] = {"top_level": (sorted(body.keys())[:12] if isinstance(body, Mapping) else f"list[{len(body)}]")}
        else:
            text = data.decode("utf-8", errors="replace")
            entry["parsed"] = {"lines": text.count("\n") + 1, "headings": sum(1 for line in text.splitlines() if line.startswith("#"))}
        loaded[artifact["id"]] = entry
    if failures:
        raise PassError("knowledge artifacts could not be read as delivered - the pass does not run knowledge-blind:\n  " + "\n  ".join(failures))
    dispositions = {aid: {"disposition": "INSPECTED", "reason": ("carried verbatim in the model-visible bundle and read" if e["in_bundle"] else
                                                                  f"read from {e['path']} and verified against the receipt ({e['bytes']} bytes)")}
                    for aid, e in loaded.items()}
    knowledge_use = {"schema": "FRANKIE_PRINCIPAL_KNOWLEDGE_USE_V1", "knowledge_receipt_sha256": receipt["receipt_sha256"],
                     **{k: receipt[k] for k in ("profile_id", "arm", "role", "manifest_hash", "context_bundle_sha256")},
                     "dispositions": dispositions}
    return {"artifacts": loaded, "brain": brain, "seed_findings": seed_findings, "knowledge_use": knowledge_use,
            "bundle_bytes": len(bundle), "bundle_sha256": hashlib.sha256(bundle).hexdigest()}


# --------------------------------------------------------------------------------------
# The pass
# --------------------------------------------------------------------------------------


def run_stream(args: argparse.Namespace) -> int:
    ledger_dir = Path(args.ledger_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    registry = load_registry()
    contract_text = (REPO_ROOT / CONTRACT_PATH).read_text(encoding="utf-8")
    cutoffs_body = json.loads(Path(args.cutoffs).read_text(encoding="utf-8"))
    cutoff_groups = [int(c["group_index"]) for c in cutoffs_body["invocation_cutoffs"]]
    run_id = cutoffs_body["run_id"]
    arm = cutoffs_body["arm"]
    delivery = json.loads(Path(args.delivery_receipt).read_text(encoding="utf-8"))
    knowledge = json.loads(Path(args.knowledge_receipt).read_text(encoding="utf-8"))
    prompt_sha = _file_sha(Path(args.prompt))
    session = {"session_id": args.session_id, "model": args.model_identity}
    knowledge_loaded = load_knowledge(knowledge, bundle_path=Path(args.knowledge_bundle))
    (out_dir / "knowledge_use.json").write_text(json.dumps(knowledge_loaded["knowledge_use"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"knowledge read: {len(knowledge_loaded['artifacts'])} artifacts verified; bundle {knowledge_loaded['bundle_bytes']:,} bytes; "
          f"brain {(knowledge_loaded['brain'] or {}).get('meta', {}).get('version')} with {len((knowledge_loaded['brain'] or {}).get('plays') or [])} plays",
          file=sys.stderr, flush=True)

    bundle = outputs.OutputBundle(run_id=run_id, arm=arm, role=ROLE, registry=registry, contract_text=contract_text,
                                  delivery_receipt_sha256=delivery["receipt_sha256"], knowledge_receipt_sha256=knowledge["receipt_sha256"])
    L = {lid: bundle.ledger(lid) for lid in bundle.required_ledger_ids}
    bundle.ledger(outputs.ANSWER_WALL_RECEIPTS, empty_reason="no answer wall was accessed; the run holds only the three delivered ledgers and the receipted knowledge")
    bundle.ledger(outputs.KNOWLEDGE_VERIFICATION_LEDGER, empty_reason="verdicts are appended by `finalize` after the whole day's tallies exist; the stream phase states nothing about the lessons")

    stream = CausalGroupStream(ledger_dir / "exact_member_rows.jsonl", ledger_dir / "exact_lifecycle_rows.jsonl",
                               ledger_dir / "legacy_observable_rows.jsonl", run_id=run_id, arm=arm)
    t = Tallies()
    hashes = {"mission_sha256": _file_sha(REPO_ROOT / MISSION_PATH), "contract_sha256": outputs.contract_sha256_of(contract_text),
              "knowledge_manifest_sha256": knowledge["manifest_file_sha256"], "source_manifest_sha256": cutoffs_body["source_manifest_sha256"],
              "code_sha256": _sha_text(cutoffs_body["code_commit"]), "run_id": run_id, "model_identity": session["model"]}
    since = 0
    previous_cutoff: int | None = None
    prev_channels = prev_book = None
    turns = 0
    receipt_ids: list[str] = []
    pending_cutoffs = list(cutoff_groups)
    last_delivery = None
    limit = args.limit

    def write_turn(delivery, cutoff: int, is_end: bool) -> None:
        nonlocal since, previous_cutoff, prev_channels, prev_book, turns
        turns += 1
        row = delivery.group
        if turns == 1:
            L[outputs.RUN_HASHES].append(cutoff, {**hashes, "phase": "START", "state_sha256": _sha_text(json.dumps({"groups": t.groups}))})
            # one receipt per delivered ARTIFACT, from what load_knowledge actually read and verified
            by_path = {}
            for layer in knowledge["layers"]:
                for f in layer["files"]:
                    by_path.setdefault(f["path"], layer["layer_id"])
            for aid, e in knowledge_loaded["artifacts"].items():
                rid = f"kr-{aid}"
                L[outputs.KNOWLEDGE_RECEIPTS].append(cutoff, {"receipt_id": rid, "layer_id": by_path.get(e["path"], "manifest_artifact"),
                                                             "artifact_id": aid, "path": e["path"], "sha256": e["sha256"], "bytes": e["bytes"],
                                                             "load_mode": e["load_mode"], "disposition": "INSPECTED", "parsed": e.get("parsed"),
                                                             "basis": "read from disk by the pass and verified against the knowledge receipt's sha256 and byte count"})
                receipt_ids.append(rid)
        sections = section_entries(t, cutoff, since, is_end)
        for sec, body in sections.items():
            L[outputs.section_ledger_id(sec)].append(cutoff, body)
        frame = state_frame(row, t, previous_cutoff, prev_channels, prev_book)
        L[outputs.STATE_MOVIE].append(cutoff, frame)
        prev_channels, prev_book = frame["channels"], frame["book"]
        # probability movie: an explicit base-rate head, labelled as such - no calibrated lock rule exists on a first traversal
        n = t.flow_seconds
        probs = {k: (t.flow_dir.get(k, 0) / n if n else 0.0) for k in ("LONG", "SHORT", "NO_DIRECTION")}
        if n:
            L[outputs.PROBABILITY_MOVIE].append(cutoff, {"instance_id": f"cutoff-{row['group_index']}", "snapshot_id": f"turn-{turns}",
                                                        "head": "next_completed_second_window_direction", "view": "BASE_RATE_OF_STREAM_SO_FAR",
                                                        "lock_rule_revision": PASS_VERSION, "lock_state": "NO_RELIABLE_LOCK", "probabilities": probs,
                                                        "partition": True, "evaluation": _reading(cutoff)})
            L[outputs.FIRST_LOCKS].append(cutoff, {"candidate_id": f"cutoff-{row['group_index']}", "lock_state": "NO_RELIABLE_LOCK",
                                                  "lock_rule_revision": PASS_VERSION,
                                                  "reason": "first traversal of this lineage: the only head is a base rate of the stream so far, which is not a lock"})
        reasoning = (f"Turn {turns} at group {row['group_index']} (cutoff {cutoff}): {t.groups} groups / {t.records} records so far; "
                     f"phase {_d(t.phase)}; flow seconds {t.flow_seconds} dir {_d(t.flow_dir)}; candidates {len(t.candidates)}; "
                     f"queue lifecycles {t.queue_rows} terminal {_d(t.queue_terminal)}; absorption {_d(t.abs_disp)}; "
                     f"4.0 reconciliation agree/disagree {sections['4.0']['recomputed_from_legacy_rows']['agree']}/{sections['4.0']['recomputed_from_legacy_rows']['disagree']}.")
        L[outputs.REASONING_MOVIE].append(cutoff, {"role": ROLE, "reasoning": reasoning, "helper_invocations": [], "knowledge_retrievals": list(receipt_ids)})
        L[outputs.INVOCATION_RECEIPTS].append(cutoff, {"mechanism": outputs.INVOCATION_MECHANISM, "session_id": session["session_id"],
                                                      "model_identity_as_reported_by_session": session["model"], "turn": turns,
                                                      "request_sha256": prompt_sha, "response_sha256": _sha_text(reasoning)})
        for sec, body in sections.items():
            if body.get("result") == outputs.NULL_RESULT:
                L[outputs.NEGATIVE_LEDGER].append(cutoff, {"kind": "ABSTENTION", "stratum": {"section": sec, "cutoff_group": row["group_index"]},
                                                          "numerator": 0, "denominator": body["population"]["denominator"], "statement": body["reason"]})
        rec = sections["4.0"]["recomputed_from_legacy_rows"]
        if rec["disagree"]:
            L[outputs.NEGATIVE_LEDGER].append(cutoff, {"kind": "INCONCLUSIVE", "stratum": {"section": "4.0", "cutoff_group": row["group_index"]},
                                                      "numerator": rec["disagree"], "denominator": rec["seconds_compared"],
                                                      "statement": "per-second aggressor volumes recomputed from legacy rows disagree with the delivered substrate on these seconds; examples on the 4.0 entry"})
        for sec, body in sections.items():
            for avg in body.get("averages") or []:
                if avg["strata"]["denominator"] <= 1:
                    L[outputs.NEGATIVE_LEDGER].append(cutoff, {"kind": "SPARSE", "stratum": {"section": sec, "numerator": avg["strata"]["numerator"]},
                                                              "numerator": avg["strata"]["denominator"], "denominator": avg["strata"]["denominator"],
                                                              "statement": "an average over at most one member is not a distribution; reported for population scale only"})
        if is_end:
            for body in raw_mbo_entries(t, registry):
                L[outputs.RAW_MBO_CLASSIFICATION_LEDGER].append(cutoff, body)
            for c in t.candidates:
                ep = next((e for e in t.episodes if e.get("candidate_id") == c.get("candidate_id")), None)
                birth = ep.get("birth_recv_ns") if ep else None
                recog = ep.get("recognized_recv_ns") if ep else None
                if isinstance(birth, int) and isinstance(recog, int):
                    lead = birth - recog
                    label = "PRIOR" if lead > 0 else ("T0" if lead == 0 else "H+N")
                else:
                    lead, label = 0, "T0"
                L[outputs.CANDIDATE_DISCOVERIES].append(cutoff, {
                    "candidate_id": str(c.get("candidate_id")), "family_id": "flow_spike_candidate", "member_group_indices": [row["group_index"]],
                    "falsifier": "the candidate's polarity fails to precede a window-direction reversal within its own searched span on a later day",
                    "first_lawful_availability_ns": int(c.get("emitted_at_recv_ns") or cutoff), "polarity": c.get("polarity"),
                    "magnitude": c.get("magnitude"), "prominence": c.get("prominence"),
                    "recognition": {"label": label, "lead": _reading(lead), "basis": (ep or {}).get("recognized_recv_ns_basis"), "outcome": (ep or {}).get("recognition_outcome")}})
            L[outputs.RUN_HASHES].append(cutoff, {**hashes, "phase": "END", "state_sha256": _sha_text(json.dumps({"groups": t.groups, "records": t.records}))})
            for lid, ledger in bundle.ledgers.items():
                if not ledger.entries and ledger.empty_reason is None:
                    ledger.empty_reason = f"nothing of this kind arose on this slice: {t.groups} groups, {len(t.candidates)} candidates, {t.flow_seconds} completed seconds"
        outputs.write_bundle(bundle, out_dir)
        since = len(t.group_indices)
        previous_cutoff = cutoff
        print(f"turn {turns} written at group {row['group_index']} cutoff {cutoff}: groups {t.groups} records {t.records}", file=sys.stderr, flush=True)

    delivered = 0
    for d in stream.iterate():
        delivered += 1
        row = d.group
        for lr in d.legacy_rows:
            t.observe_legacy(lr)
        t.observe_member(row, d.first_lawful_availability_ns)
        for lr in d.lifecycle_rows:
            t.observe_lifecycle(lr)
        last_delivery = d
        gi = int(row["group_index"])
        if pending_cutoffs and gi >= pending_cutoffs[0]:
            pending_cutoffs.pop(0)
            write_turn(d, d.first_lawful_availability_ns, is_end=False)
        if args.progress_every and delivered % args.progress_every == 0:
            print(f"delivered {delivered:,} groups", file=sys.stderr, flush=True)
        if limit is not None and delivered >= limit:
            break
    receipt = stream.stream_receipt()
    if last_delivery is None:
        raise PassError("the stream delivered nothing")
    # the closing turn: STREAM_END rows are lawful only now
    write_turn(last_delivery, last_delivery.first_lawful_availability_ns, is_end=True)
    (out_dir / "stream_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tallies = {"groups": t.groups, "records": t.records, "phase": _d(t.phase), "segments": {str(k): v for k, v in t.segments.items()},
               "cutoff_turns": turns, "candidates": len(t.candidates), "episodes": len(t.episodes), "recognition": {str(k): v for k, v in t.recognition.items()},
               "queue": {"rows": t.queue_rows, "terminal": _d(t.queue_terminal)}, "absorption": _d(t.abs_disp), "flow_dir": _d(t.flow_dir),
               "flow_class": _d(t.flow_class), "flow_reconciliation": t.reconcile_flow(), "lineage": {"nodes": t.lineage_rows, "depth": {str(k): v for k, v in t.lineage_depth.items()}, "status": _d(t.lineage_status)},
               "families": len(t.family_members), "singletons": sum(1 for v in t.family_members.values() if v == 1), "mirror_close": _d(t.mirror_close),
               "mirror_end": _d(t.mirror_end), "replenishment_outcome": _d(t.rep_outcome), "ladder": {"rows": t.lad_rows, "births": t.lad_births, "deaths": t.lad_deaths},
               "response": {"tracks": t.resp_tracks, "observations": t.resp_obs, "change_points": _q(t.resp_change_points)}, "lifecycle_rows": _d(t.lifecycle_rows),
               "actions": _d(t.actions), "legacy_rows": t.legacy_rows, "legacy_actions": _d(t.legacy_actions), "f20": receipt.get("falsifier_f20"),
               "stream_complete": receipt.get("complete"), "stream_receipt_sha256": receipt.get("receipt_sha256"),
               "book_first": t.book_first, "book_last": t.book_last, "imbalance_flips": t.imb_flips, "window_direction_reversals": t.flow_sign_reversals,
               "candidate_same_flip": _d(t.candidate_same_flip), "capture": _d(t.capture), "exhaustion_end": t.exhaustion_end, "detector_end": t.detector_end,
               "field_distinct_single": sorted(k for k, s in t.field_distinct.items() if len(s) == 1 and t.field_null.get(k, 0) == 0)}
    (out_dir / "tallies.json").write_text(json.dumps(tallies, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    # The stream phase validates everything except the knowledge-verification verdicts, which
    # `finalize` appends after the principal has read the whole day's tallies against each served
    # lesson; a knowledge receipt of None is exactly the validator's "not yet known" case.
    result = outputs.validate_output_bundle_dir(out_dir, registry=registry, contract_text=contract_text,
                                                knowledge_receipt_sha256=None, delivery_receipt_sha256=delivery["receipt_sha256"])
    print(json.dumps({"turns": turns, "groups": t.groups, "records": t.records, "stream_complete": receipt.get("complete"),
                      "f20": receipt.get("falsifier_f20", {}).get("verdict"), "outputs_receipt_sha256": result["receipt_sha256"],
                      "stream_receipt_sha256": receipt["receipt_sha256"]}, indent=2))
    return 0


def run_finalize(args: argparse.Namespace) -> int:
    """Append knowledge-verification verdicts at the last cutoff, then re-validate."""
    out_dir = Path(args.out_dir)
    registry = load_registry()
    contract_text = (REPO_ROOT / CONTRACT_PATH).read_text(encoding="utf-8")
    verification = json.loads(Path(args.verification).read_text(encoding="utf-8"))
    knowledge = json.loads(Path(args.knowledge_receipt).read_text(encoding="utf-8"))
    delivery = json.loads(Path(args.delivery_receipt).read_text(encoding="utf-8"))
    body = outputs.load_bundle(out_dir)
    bundle = outputs.OutputBundle(run_id=body["run_id"], arm=body["arm"], role=body["role"], registry=registry, contract_text=contract_text,
                                  delivery_receipt_sha256=body.get("delivery_receipt_sha256"), knowledge_receipt_sha256=body.get("knowledge_receipt_sha256"))
    last_cutoff = 0
    for lid, ledger in body["ledgers"].items():
        target = bundle.ledger(lid, empty_reason=ledger.get("empty_reason"))
        for e in ledger["entries"]:
            target.append(e["cutoff_recv_ns"], e["body"])
            last_cutoff = max(last_cutoff, e["cutoff_recv_ns"])
    kv = bundle.ledger(outputs.KNOWLEDGE_VERIFICATION_LEDGER)
    kv.empty_reason = None
    existing = {e["body"]["lesson_id"] for e in kv.entries}
    for v in verification["verdicts"]:
        if v["lesson_id"] in existing:
            continue
        entry = {"lesson_id": v["lesson_id"], "layer_id": v.get("layer_id", "a_memory_prior_lessons_package"),
                 "knowledge_receipt_sha256": knowledge["receipt_sha256"], "verdict": v["verdict"], "statement": v.get("statement", "")}
        if v["verdict"] == "NOT_TESTED_ON_THIS_SLICE":
            entry["reason"] = v["reason"]
        else:
            entry["evidence"] = {"member_group_indices": v["member_group_indices"], "cutoff_recv_ns": last_cutoff, "computed": v.get("computed")}
        kv.append(last_cutoff, entry)
    outputs.write_bundle(bundle, out_dir)
    result = outputs.validate_output_bundle_dir(out_dir, registry=registry, contract_text=contract_text,
                                                knowledge_receipt_sha256=knowledge["receipt_sha256"], delivery_receipt_sha256=delivery["receipt_sha256"])
    print(json.dumps({"verdicts": len(kv.entries), "outputs_receipt_sha256": result["receipt_sha256"]}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stream")
    s.add_argument("--ledger-dir", required=True)
    s.add_argument("--cutoffs", required=True, help="json: run_id, arm, invocation_cutoffs[], source_manifest_sha256, code_commit")
    s.add_argument("--delivery-receipt", required=True)
    s.add_argument("--knowledge-receipt", required=True)
    s.add_argument("--knowledge-bundle", required=True, help="KNOWLEDGE_BUNDLE.md, the exact model-visible context of the receipt")
    s.add_argument("--prompt", required=True)
    s.add_argument("--out-dir", required=True)
    s.add_argument("--session-id", required=True)
    s.add_argument("--model-identity", required=True)
    s.add_argument("--limit", type=int, default=None)
    s.add_argument("--progress-every", type=int, default=2000)
    f = sub.add_parser("finalize")
    f.add_argument("--out-dir", required=True)
    f.add_argument("--verification", required=True)
    f.add_argument("--knowledge-receipt", required=True)
    f.add_argument("--delivery-receipt", required=True)
    args = p.parse_args(argv)
    try:
        return run_stream(args) if args.cmd == "stream" else run_finalize(args)
    except (PassError, outputs.PrincipalOutputError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
