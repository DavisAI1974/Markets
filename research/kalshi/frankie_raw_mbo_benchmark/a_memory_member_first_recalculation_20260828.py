"""A-memory member-first recalculation over the hash-bound native ledger.

Walks the A-memory ledger (`EXPECTED_A_MEMORY_GROUPS` = 4,256,603 F_LAST-closed groups
over `EXPECTED_A_MEMORY_RECORDS` = 5,667,689 native records) and recomputes, per MEMBER
rather than per summary, the structures the open-world discovery contract declares: the
action string, the side string, the mirror pair key, and the fill disposition. It emits a
family index, an adjacency index, a mirror-pair index and a per-day index, each with a
receipt carrying the counts and hashes it was built from.

`discovery_contract()` states the seeds it works against - `P/O/S/X` structural states and
`SAME`/`FLIP` transition orientations - and states them as SEEDS: `legacy_seed_is_allowlist`
is False and the unmatched policy is `PRESERVE_AND_CHARACTERIZE`, so a structure that
matches nothing is kept and described rather than forced into the nearest known label.

Structural state assignment is deliberately deferred (`DEFER_TO_CAUSAL_FRANKIE_RESEARCH`):
this module establishes members and their identities, not what they mean.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from research.kalshi.frankie_raw_mbo_benchmark.native_mirror import (
    mirror_identity as native_mirror_identity,
)
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import V4MboAdapter


EXPECTED_A_MEMORY_LEDGER_SHA256 = (
    "bc0788b51a719d39f5024f10007f4c74e96ff3361a21b66d662d9fadf1a67d8f"
)
EXPECTED_A_MEMORY_GROUPS = 4_256_603
EXPECTED_A_MEMORY_RECORDS = 5_667_689


BOOK_FIELDS = (
    "spread",
    "depth_imbalance_full",
    "bid_depth_full",
    "ask_depth_full",
    "bid_order_count_full",
    "ask_order_count_full",
    "bid_price_level_count_full",
    "ask_price_level_count_full",
)

CARRIED_NATIVE_ACTION_FAMILIES = frozenset(
    {
        "A",
        "AN",
        "C",
        "CN",
        "M",
        "MN",
        "TFC",
        "TFCN",
        "TFM",
        "TFMN",
        "TFFCC",
        "TFFCCN",
        "TFFFCCCN",
        "TFFFFCCCCN",
        "TFFFFFCCCCCN",
        "TFFCM",
        "TFFCMN",
        "TFTFCMN",
        "TFTFCCN",
        "TFACN",
        "TFCAN",
        "TN",
    }
)


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def discovery_contract() -> dict[str, Any]:
    return {
        "structural_state_seeds": {
            "P": "persistent_exhaustion",
            "O": "collapsed_opposite_flow_reversal",
            "S": "collapsed_same_flow_reload",
            "X": "collapsed_sparse_indeterminate",
        },
        "transition_orientation_seeds": ["SAME", "FLIP"],
        "open_world": True,
        "maximum_family_count": None,
        "unmatched_policy": "PRESERVE_AND_CHARACTERIZE",
        "legacy_seed_is_allowlist": False,
        "structural_state_assignment": "DEFER_TO_CAUSAL_FRANKIE_RESEARCH",
    }


def action_string(actions: Iterable[dict[str, Any]]) -> str:
    return "".join(str(row.get("action", "?")) for row in actions)


def side_string(actions: Iterable[dict[str, Any]]) -> str:
    return "".join(str(row.get("side", "?")) for row in actions)


def mirror_identity(sides: str) -> dict[str, str]:
    """Delegates to the single mechanical mirror key required by contract 4.4.

    The definition moved to `native_mirror` unchanged - same side swap, same pair key,
    same CANONICAL/MIRROR orientation - and this remains its only caller. The move was a
    verbatim extraction, proven output-identical over twelve side strings in
    `tests/test_native_mirror.py`; it is not a change of meaning and it makes no claim
    about section 4.12.
    """
    return native_mirror_identity(sides)


def fill_disposition(actions: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(actions)
    fill_ids = {int(row.get("order_id") or 0) for row in rows if row.get("action") == "F"}
    fill_ids.discard(0)
    cancel_ids = {int(row.get("order_id") or 0) for row in rows if row.get("action") == "C"}
    modify_ids = {int(row.get("order_id") or 0) for row in rows if row.get("action") == "M"}
    cancelled = sorted(fill_ids & cancel_ids)
    modified = sorted(fill_ids & modify_ids)
    both = sorted(set(cancelled) & set(modified))
    unresolved = sorted(fill_ids - cancel_ids - modify_ids)

    if not fill_ids:
        label = "NO_FILL_IDS"
    elif both:
        label = "SAME_ID_CANCEL_AND_MODIFY"
    elif cancelled and modified:
        label = "SPLIT_CANCEL_MODIFY"
    elif cancelled:
        label = "CANCEL"
    elif modified:
        label = "MODIFY"
    else:
        label = "UNRESOLVED"
    if unresolved and label != "UNRESOLVED":
        label += "_WITH_UNRESOLVED"

    signature = {
        "fill_id_count": len(fill_ids),
        "cancelled_fill_id_count": len(cancelled),
        "modified_fill_id_count": len(modified),
        "same_id_cancel_modify_count": len(both),
        "unresolved_fill_id_count": len(unresolved),
    }
    return {
        "class": label,
        "filled_order_ids": sorted(fill_ids),
        "cancelled_fill_order_ids": cancelled,
        "modified_fill_order_ids": modified,
        "same_id_cancel_modify_order_ids": both,
        "unresolved_fill_order_ids": unresolved,
        "signature": signature,
    }


def describe_structure(actions: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(actions)
    if not rows:
        raise ValueError("an F_LAST group must contain at least one native action")
    actions_text = action_string(rows)
    sides_text = side_string(rows)
    disposition = fill_disposition(rows)
    action_counts = Counter(str(row.get("action", "?")) for row in rows)
    side_counts = Counter(str(row.get("side", "?")) for row in rows)
    price_values = sorted(
        {
            int(row["price_raw"])
            for row in rows
            if row.get("price_raw") is not None
            and abs(int(row["price_raw"])) < 9_000_000_000_000_000_000
        }
    )
    order_ids = sorted({int(row.get("order_id") or 0) for row in rows} - {0})
    descriptor = {
        "action_string": actions_text,
        "side_string": sides_text,
        "action_counts": dict(sorted(action_counts.items())),
        "side_counts": dict(sorted(side_counts.items())),
        "terminal_action": str(rows[-1].get("action", "?")),
        "terminal_side": str(rows[-1].get("side", "?")),
        "component_count": len(rows),
        "distinct_price_count": len(price_values),
        "distinct_order_id_count": len(order_ids),
        "fill_disposition_signature": disposition["signature"],
    }
    candidate_id = "ow-" + canonical_hash(descriptor)[:20]
    carried = actions_text in CARRIED_NATIVE_ACTION_FAMILIES
    return {
        **descriptor,
        "candidate_family_id": candidate_id,
        "matches_carried_native_family": carried,
        "carried_native_family": actions_text if carried else None,
        "discovery_status": "CARRIED_SEED_MATCH" if carried else "OPEN_WORLD_CANDIDATE",
        "price_raw_min": price_values[0] if price_values else None,
        "price_raw_max": price_values[-1] if price_values else None,
        "price_raw_span": price_values[-1] - price_values[0] if price_values else None,
        "order_ids": order_ids,
        "fill_disposition": disposition,
        "mirror": mirror_identity(sides_text),
    }


def book_values(book: dict[str, Any] | None) -> dict[str, int | float | None]:
    if book is None:
        return {key: None for key in BOOK_FIELDS}
    return {key: book.get(key) for key in BOOK_FIELDS}


def _sign(value: int | float | None) -> str:
    if value is None:
        return "NA"
    if value > 0:
        return "+"
    if value < 0:
        return "-"
    return "0"


def book_transition(
    before: dict[str, Any] | None, after: dict[str, Any] | None
) -> dict[str, Any]:
    before_values = book_values(before)
    after_values = book_values(after)
    delta: dict[str, int | float | None] = {}
    for key in BOOK_FIELDS:
        left = before_values[key]
        right = after_values[key]
        delta[key] = None if left is None or right is None else right - left
    signature = "|".join(f"{key}:{_sign(delta[key])}" for key in BOOK_FIELDS)
    return {
        "before": before_values,
        "after": after_values,
        "delta": delta,
        "sign_signature": signature,
        "exact_transition_id": "state-" + canonical_hash(
            {"before": before_values, "after": after_values, "delta": delta}
        )[:20],
    }


def _adapter_record(raw: dict[str, Any]) -> dict[str, Any]:
    required = (
        "instrument_id",
        "publisher_id",
        "channel_id",
        "order_id",
        "action",
        "side",
        "price_raw",
        "size",
        "flags",
        "sequence",
        "ts_event_ns",
        "ts_recv_ns",
        "ts_in_delta_ns",
    )
    missing = [key for key in required if key not in raw]
    if missing:
        raise RuntimeError(f"native action is missing required fields: {missing}")
    return {
        "instrument_id": raw["instrument_id"],
        "publisher_id": raw["publisher_id"],
        "channel_id": raw["channel_id"],
        "order_id": raw["order_id"],
        "action": raw["action"],
        "side": raw["side"],
        "price": raw["price_raw"],
        "size": raw["size"],
        "flags": raw["flags"],
        "sequence": raw["sequence"],
        "ts_event": raw["ts_event_ns"],
        "ts_recv": raw["ts_recv_ns"],
        "ts_in_delta": raw["ts_in_delta_ns"],
    }


def reconstruct_group(adapter: Any, group: dict[str, Any], *, expected_cursor: int) -> dict[str, Any]:
    if group.get("causal_availability_clock") != "ts_recv_ns":
        raise RuntimeError("group causal availability clock is not ts_recv_ns")
    if group.get("mbp_substitute_used") is not False:
        raise RuntimeError("group permits an MBP substitute")
    if group.get("seconds_collapse_used", False) is not False:
        raise RuntimeError("group used a seconds collapse")
    if group.get("step1_derived_input_used", False) is not False:
        raise RuntimeError("group used Step-1-derived input")
    if group.get("full_depth_reconstructable_from_checkpoint_and_raw_actions") is not True:
        raise RuntimeError("group does not prove full-depth reconstruction")
    if group.get("fifo_reconstructable_from_checkpoint_and_raw_actions") is not True:
        raise RuntimeError("group does not prove FIFO reconstruction")

    compact = group.get("compact_event_frame")
    if not isinstance(compact, dict) or compact.get("event_group_complete_f_last") is not True:
        raise RuntimeError("group is not an F_LAST-closed native event group")
    if int(group.get("completed_mbo_records_before", -1)) != int(expected_cursor):
        raise RuntimeError("group native-record cursor is discontinuous")

    actions = group.get("raw_actions")
    if not isinstance(actions, list) or not actions:
        raise RuntimeError("group has no raw native actions")
    expected_after = int(expected_cursor) + len(actions)
    if int(group.get("completed_mbo_records_after", -1)) != expected_after:
        raise RuntimeError("group native-record count does not match its exact actions")
    final = actions[-1]
    if not bool(final.get("is_last")) or not (int(final.get("flags", 0)) & (1 << 7)):
        raise RuntimeError("group final native action is not F_LAST")

    frames: list[dict[str, Any]] = []
    for raw in actions:
        record = _adapter_record(raw)
        frame, _ = adapter.apply(
            record,
            raw_symbol=raw.get("raw_symbol"),
            source_dbn_object=raw.get("source_dbn_object"),
            source_dbn_sha256=raw.get("source_dbn_sha256"),
        )
        if frame is not None:
            frames.append(frame)
    if len(frames) != 1:
        raise RuntimeError(f"expected exactly one F_LAST frame, observed {len(frames)}")
    frame = frames[0]
    if int(frame["ts_recv_ns"]) != int(compact.get("ts_recv_ns", -1)):
        raise RuntimeError("reconstructed F_LAST receive clock does not match the ledger")
    if int(frame["ts_event_ns"]) != int(compact.get("ts_event_ns", -1)):
        raise RuntimeError("reconstructed event clock does not match the ledger")
    if int(frame["ts_recv_ns"]) != int(final["ts_recv_ns"]):
        raise RuntimeError("F_LAST availability is not the final action receive clock")
    return frame


class StratifiedAverages:
    def __init__(self, *, retain_member_indices: bool = True) -> None:
        self.retain_member_indices = retain_member_indices
        self._rows: dict[tuple[str, ...], dict[str, Any]] = {}

    def add(
        self,
        *,
        source_day: str,
        family_id: str,
        side_string: str,
        continuity_segment: str,
        causal_phase: str,
        clock_basis: str,
        group_index: int,
        values: dict[str, int | float | None],
    ) -> None:
        key = (
            source_day,
            family_id,
            side_string,
            continuity_segment,
            causal_phase,
            clock_basis,
        )
        row = self._rows.setdefault(
            key,
            {
                "denominator_n": 0,
                "sums": defaultdict(float),
                "counts": Counter(),
                "member_group_indices": [],
            },
        )
        row["denominator_n"] += 1
        if self.retain_member_indices:
            row["member_group_indices"].append(int(group_index))
        for field in BOOK_FIELDS:
            value = values.get(field)
            if value is not None:
                row["sums"][field] += float(value)
                row["counts"][field] += 1

    def rows(self) -> list[dict[str, Any]]:
        result = []
        for key in sorted(self._rows):
            source_day, family_id, sides, segment, phase, clock = key
            raw = self._rows[key]
            means = {
                field: (
                    raw["sums"][field] / raw["counts"][field]
                    if raw["counts"][field]
                    else None
                )
                for field in BOOK_FIELDS
            }
            result.append(
                {
                    "source_day": source_day,
                    "family_id": family_id,
                    "side_string": sides,
                    "continuity_segment": segment,
                    "causal_phase": phase,
                    "clock_basis": clock,
                    "denominator_n": raw["denominator_n"],
                    "field_denominators": dict(sorted(raw["counts"].items())),
                    "means": means,
                    "member_group_indices": list(raw["member_group_indices"]),
                    "reconciliation_label": "COEQUAL_WITH_EXACT_MEMBERS",
                }
            )
        return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class DeterministicGzipJsonlWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._raw = path.open("wb")
        self._gzip = gzip.GzipFile(
            filename="", mode="wb", fileobj=self._raw, compresslevel=1, mtime=0
        )
        self._uncompressed_hash = hashlib.sha256()
        self.rows = 0

    def write(self, row: dict[str, Any]) -> None:
        payload = (
            json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
        ).encode("utf-8")
        self._gzip.write(payload)
        self._uncompressed_hash.update(payload)
        self.rows += 1

    def close(self) -> dict[str, Any]:
        self._gzip.close()
        self._raw.close()
        return {
            "filename": self.path.name,
            "rows": self.rows,
            "uncompressed_jsonl_sha256": self._uncompressed_hash.hexdigest(),
            "gzip_sha256": sha256_file(self.path),
            "bytes": self.path.stat().st_size,
        }


def _write_json(path: Path, value: Any) -> dict[str, Any]:
    payload = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)
    return {
        "filename": path.name,
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def _source_day(source_name: str) -> str:
    match = re.search(r"(20\d{2})(\d{2})(\d{2})", source_name)
    if not match:
        return source_name
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"


def _source_role(source_day: str) -> str:
    """All four roster days are scored and all four produce findings, so they share a role.

    The earlier warmup/held-out split described a design in which October 1 and 3 were only
    context. Keeping it would imply two populations where there is one, and days are already
    kept apart by source_day in every stratum key.
    """
    if source_day in {"2021-10-01", "2021-10-03", "2021-10-04", "2021-10-05"}:
        return "SCORED_FINDINGS_DAY"
    return "UNSPECIFIED_TEST_SOURCE"


def _new_daily_metrics() -> dict[str, Any]:
    return {
        "event_groups": 0,
        "actions": Counter(),
        "sides": Counter(),
        "max_group_actions": 0,
        "stats": {
            field: {"n": 0, "sum": 0.0, "first": None, "last": None, "min": None, "max": None}
            for field in BOOK_FIELDS
        },
    }


def _update_daily_metrics(
    metrics: dict[str, Any], actions: list[dict[str, Any]], book: dict[str, Any]
) -> None:
    metrics["event_groups"] += 1
    metrics["max_group_actions"] = max(metrics["max_group_actions"], len(actions))
    for action in actions:
        metrics["actions"][str(action["action"])] += 1
        metrics["sides"][str(action["side"])] += 1
    for field in BOOK_FIELDS:
        value = book.get(field)
        if value is None:
            continue
        stat = metrics["stats"][field]
        if stat["n"] == 0:
            stat["first"] = value
            stat["min"] = value
            stat["max"] = value
        stat["n"] += 1
        stat["sum"] += value
        stat["last"] = value
        stat["min"] = min(stat["min"], value)
        stat["max"] = max(stat["max"], value)


def _compact_daily_metrics(
    source_name: str, source_role: str, metrics: dict[str, Any]
) -> dict[str, Any]:
    result = {
        "source_name": source_name,
        "source_role": source_role,
        "event_groups": metrics["event_groups"],
        "actions": dict(sorted(metrics["actions"].items())),
        "sides": dict(sorted(metrics["sides"].items())),
        "max_group_actions": metrics["max_group_actions"],
    }
    for field in BOOK_FIELDS:
        stat = metrics["stats"][field]
        result[field] = (
            {
                "first": stat["first"],
                "last": stat["last"],
                "min": stat["min"],
                "max": stat["max"],
                "mean": stat["sum"] / stat["n"],
            }
            if stat["n"]
            else None
        )
    return result


def _compact_native_actions(actions: list[dict[str, Any]]) -> list[list[Any]]:
    return [
        [
            row.get("action"),
            row.get("side"),
            row.get("price_raw"),
            row.get("size"),
            row.get("order_id"),
            row.get("ts_event_ns"),
            row.get("ts_recv_ns"),
            row.get("flags"),
            row.get("sequence"),
            row.get("channel_id"),
        ]
        for row in actions
    ]


def _order_links(
    active_orders: dict[int, dict[str, Any]],
    *,
    group_index: int,
    group_hash: str,
    close_recv_ns: int,
    actions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    links: dict[tuple[int, int], dict[str, Any]] = {}
    for row in actions:
        action = str(row.get("action"))
        order_id = int(row.get("order_id") or 0)
        if action == "R":
            active_orders.clear()
            continue
        if order_id == 0:
            continue
        prior = active_orders.get(order_id)
        if prior is not None and prior["group_index"] != group_index:
            key = (order_id, int(prior["group_index"]))
            links[key] = {
                "order_id": order_id,
                "prior_group_index": prior["group_index"],
                "prior_group_hash": prior["group_hash"],
                "prior_action": prior["action"],
                "current_first_action": action,
                "receive_gap_ns": int(row["ts_recv_ns"]) - int(prior["ts_recv_ns"]),
            }
        if action == "C":
            active_orders.pop(order_id, None)
        elif action in {"A", "F", "M"}:
            active_orders[order_id] = {
                "group_index": group_index,
                "group_hash": group_hash,
                "action": action,
                "ts_recv_ns": close_recv_ns,
            }
    return [links[key] for key in sorted(links)]


def _run_row(run: dict[str, Any]) -> dict[str, Any]:
    averages = StratifiedAverages()
    for member in run["members"]:
        averages.add(
            source_day=member["source_day"],
            family_id=member["candidate_family_id"],
            side_string=member["side_string"],
            continuity_segment=member["continuity_segment"],
            causal_phase="MAXIMAL_EXACT_FAMILY_RUN",
            clock_basis="F_LAST_TS_RECV_NS",
            group_index=member["group_index"],
            values=member["book"]["after"],
        )
    companion = averages.rows()[0]
    first = run["members"][0]
    last = run["members"][-1]
    identity = {
        "source_name": first["source_name"],
        "continuity_segment": first["continuity_segment"],
        "candidate_family_id": first["candidate_family_id"],
        "side_string": first["side_string"],
        "start_group_index": first["group_index"],
        "end_group_index": last["group_index"],
    }
    return {
        **identity,
        "run_id": "run-" + canonical_hash(identity)[:20],
        "member_count": len(run["members"]),
        "member_group_indices": [row["group_index"] for row in run["members"]],
        "start_f_last_ts_recv_ns": first["clocks"]["f_last_availability_ts_recv_ns"],
        "end_f_last_ts_recv_ns": last["clocks"]["f_last_availability_ts_recv_ns"],
        "duration_ns": (
            last["clocks"]["f_last_availability_ts_recv_ns"]
            - first["clocks"]["f_last_availability_ts_recv_ns"]
        ),
        "averaged_companion": companion,
    }


def _validate_expected_observations(
    observations_path: Path | None, calculated: list[dict[str, Any]]
) -> str:
    if observations_path is None:
        return "NOT_REQUESTED"
    payload = json.loads(observations_path.read_text(encoding="utf-8"))
    expected = payload.get("source_metrics")
    if expected is None:
        raise RuntimeError("observations file has no source_metrics")
    if expected != calculated:
        raise RuntimeError("member-first daily companions drift from diagnostic source_metrics")
    return "EXACT_MATCH"


def run_recalculation(
    *,
    ledger_path: Path,
    out_dir: Path,
    expected_ledger_sha256: str,
    expected_group_count: int,
    expected_record_count: int,
    observations_path: Path | None = None,
    progress_every: int = 250_000,
) -> dict[str, Any]:
    ledger_path = Path(ledger_path)
    out_dir = Path(out_dir)
    if not ledger_path.is_file():
        raise RuntimeError(f"native ledger is absent: {ledger_path}")
    observed_sha = sha256_file(ledger_path)
    if observed_sha != expected_ledger_sha256:
        raise RuntimeError(
            f"native ledger SHA-256 mismatch: expected {expected_ledger_sha256}, observed {observed_sha}"
        )
    if out_dir.exists():
        raise RuntimeError(f"output directory already exists: {out_dir}")
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=out_dir.name + ".tmp.", dir=out_dir.parent))

    adapter = V4MboAdapter()
    member_writer = DeterministicGzipJsonlWriter(temporary / "exact-members.jsonl.gz")
    run_writer = DeterministicGzipJsonlWriter(temporary / "exact-runs.jsonl.gz")
    family_index: dict[str, dict[str, Any]] = {}
    adjacency = Counter()
    mirror_pairs = Counter()
    daily_metrics: dict[str, dict[str, Any]] = {}
    active_orders: dict[int, dict[str, Any]] = {}
    previous_book: dict[str, Any] | None = None
    previous_source: str | None = None
    previous_member: dict[str, Any] | None = None
    current_run: dict[str, Any] | None = None
    continuity_number = 0
    cursor = 0
    groups = 0
    open_world_groups = 0
    started = time.monotonic()

    try:
        with gzip.open(ledger_path, "rt", encoding="utf-8") as handle:
            for line in handle:
                group = json.loads(line)
                if int(group.get("group_index", -1)) != groups:
                    raise RuntimeError("event-group index is discontinuous")
                actions = group.get("raw_actions")
                if not isinstance(actions, list) or not actions:
                    raise RuntimeError("event group contains no exact native actions")
                source_name = str(actions[0].get("source_dbn_object"))
                if not source_name or source_name == "None":
                    raise RuntimeError("event group has no source DBN identity")
                if any(str(row.get("source_dbn_object")) != source_name for row in actions):
                    raise RuntimeError("event group crosses source DBN identities")

                reset_present = any(row.get("action") == "R" for row in actions)
                if source_name != previous_source or reset_present:
                    continuity_number += 1
                    active_orders.clear()
                    previous_book = None
                    previous_member = None
                continuity_segment = f"segment-{continuity_number:06d}"

                frame = reconstruct_group(adapter, group, expected_cursor=cursor)
                cursor = int(group["completed_mbo_records_after"])
                structure = describe_structure(actions)
                transition = book_transition(previous_book, frame["book"])
                source_day = _source_day(source_name)
                source_role = _source_role(source_day)
                daily = daily_metrics.setdefault(source_name, _new_daily_metrics())
                _update_daily_metrics(daily, actions, frame["book"])
                close_recv_ns = int(frame["ts_recv_ns"])
                first_recv_ns = int(actions[0]["ts_recv_ns"])
                links = _order_links(
                    active_orders,
                    group_index=groups,
                    group_hash=str(group["group_hash"]),
                    close_recv_ns=close_recv_ns,
                    actions=actions,
                )
                member = {
                    "schema": "FRANKIE_A_MEMORY_EXACT_MEMBER_V1",
                    "group_index": groups,
                    "group_hash": group["group_hash"],
                    "source_name": source_name,
                    "source_day": source_day,
                    "source_role": source_role,
                    "continuity_segment": continuity_segment,
                    "completed_mbo_records_before": group["completed_mbo_records_before"],
                    "completed_mbo_records_after": group["completed_mbo_records_after"],
                    "instrument_id": frame["instrument_id"],
                    "candidate_family_id": structure["candidate_family_id"],
                    "discovery_status": structure["discovery_status"],
                    "matches_carried_native_family": structure["matches_carried_native_family"],
                    "carried_native_family": structure["carried_native_family"],
                    "action_string": structure["action_string"],
                    "side_string": structure["side_string"],
                    "mirror": structure["mirror"],
                    "mechanics": {
                        key: structure[key]
                        for key in (
                            "action_counts",
                            "side_counts",
                            "terminal_action",
                            "terminal_side",
                            "component_count",
                            "distinct_price_count",
                            "distinct_order_id_count",
                            "price_raw_min",
                            "price_raw_max",
                            "price_raw_span",
                            "order_ids",
                            "fill_disposition",
                        )
                    },
                    "structural_state": "OPEN_WORLD_UNASSIGNED",
                    "transition_orientation": "OPEN_WORLD_UNASSIGNED",
                    "clocks": {
                        "event_ts_ns": int(frame["ts_event_ns"]),
                        "first_component_ts_recv_ns": first_recv_ns,
                        "f_last_availability_ts_recv_ns": close_recv_ns,
                        "formation_latency_ns": close_recv_ns - first_recv_ns,
                        "decision_asof_ts_recv_ns": close_recv_ns,
                    },
                    "book": transition,
                    "native_action_tuple_fields": [
                        "action",
                        "side",
                        "price_raw",
                        "size",
                        "order_id",
                        "ts_event_ns",
                        "ts_recv_ns",
                        "flags",
                        "sequence",
                        "channel_id",
                    ],
                    "native_action_tuples": _compact_native_actions(actions),
                    "prior_order_links": links,
                    "previous_group": (
                        {
                            "group_index": previous_member["group_index"],
                            "group_hash": previous_member["group_hash"],
                            "candidate_family_id": previous_member["candidate_family_id"],
                            "receive_gap_ns": close_recv_ns
                            - previous_member["clocks"]["f_last_availability_ts_recv_ns"],
                        }
                        if previous_member is not None
                        else None
                    ),
                }

                family = family_index.setdefault(
                    structure["candidate_family_id"],
                    {
                        "candidate_family_id": structure["candidate_family_id"],
                        "action_string": structure["action_string"],
                        "side_string": structure["side_string"],
                        "discovery_status": structure["discovery_status"],
                        "matches_carried_native_family": structure[
                            "matches_carried_native_family"
                        ],
                        "carried_native_family": structure["carried_native_family"],
                        "mechanical_descriptor": {
                            key: structure[key]
                            for key in (
                                "action_counts",
                                "side_counts",
                                "terminal_action",
                                "terminal_side",
                                "component_count",
                                "distinct_price_count",
                                "distinct_order_id_count",
                                "fill_disposition_signature",
                            )
                        },
                        "count": 0,
                        "count_by_source_day": Counter(),
                        "first_group_index": groups,
                        "last_group_index": groups,
                        "example_group_indices": [],
                    },
                )
                family["count"] += 1
                family["count_by_source_day"][source_day] += 1
                family["last_group_index"] = groups
                if len(family["example_group_indices"]) < 10:
                    family["example_group_indices"].append(groups)
                if structure["discovery_status"] == "OPEN_WORLD_CANDIDATE":
                    open_world_groups += 1

                mirror = structure["mirror"]
                mirror_pairs[
                    (
                        source_name,
                        structure["action_string"],
                        mirror["mirror_pair_key"],
                        mirror["orientation"],
                    )
                ] += 1
                if previous_member is not None:
                    adjacency[
                        (
                            source_name,
                            continuity_segment,
                            previous_member["candidate_family_id"],
                            member["candidate_family_id"],
                        )
                    ] += 1

                run_key = (
                    source_name,
                    continuity_segment,
                    member["candidate_family_id"],
                    member["side_string"],
                )
                if current_run is None or current_run["key"] != run_key:
                    if current_run is not None:
                        run_writer.write(_run_row(current_run))
                    current_run = {"key": run_key, "members": []}
                current_run["members"].append(member)
                member_writer.write(member)

                previous_book = frame["book"]
                previous_member = member
                previous_source = source_name
                groups += 1
                if progress_every and groups % progress_every == 0:
                    elapsed = time.monotonic() - started
                    print(
                        json.dumps(
                            {
                                "status": "IN_PROGRESS",
                                "groups": groups,
                                "records": cursor,
                                "elapsed_seconds": round(elapsed, 3),
                            },
                            sort_keys=True,
                        ),
                        flush=True,
                    )

        if current_run is not None:
            run_writer.write(_run_row(current_run))
        adapter.assert_groups_closed()
        if groups != int(expected_group_count):
            raise RuntimeError(
                f"group denominator mismatch: expected {expected_group_count}, observed {groups}"
            )
        if cursor != int(expected_record_count):
            raise RuntimeError(
                f"record denominator mismatch: expected {expected_record_count}, observed {cursor}"
            )

        member_file = member_writer.close()
        run_file = run_writer.close()
        daily_rows = [
            _compact_daily_metrics(name, _source_role(_source_day(name)), daily_metrics[name])
            for name in daily_metrics
        ]
        observation_status = _validate_expected_observations(observations_path, daily_rows)

        family_rows = []
        for family_id in sorted(family_index):
            row = dict(family_index[family_id])
            row["count_by_source_day"] = dict(sorted(row["count_by_source_day"].items()))
            family_rows.append(row)
        family_file = _write_json(
            temporary / "family-index.json",
            {
                "schema": "FRANKIE_A_MEMORY_OPEN_WORLD_FAMILY_INDEX_V1",
                "discovery_contract": discovery_contract(),
                "families": family_rows,
            },
        )
        adjacency_file = _write_json(
            temporary / "adjacency-index.json",
            {
                "schema": "FRANKIE_A_MEMORY_EXACT_ADJACENCY_INDEX_V1",
                "edges": [
                    {
                        "source_name": key[0],
                        "continuity_segment": key[1],
                        "from_candidate_family_id": key[2],
                        "to_candidate_family_id": key[3],
                        "count": count,
                    }
                    for key, count in sorted(adjacency.items())
                ],
            },
        )
        mirror_file = _write_json(
            temporary / "mirror-pair-index.json",
            {
                "schema": "FRANKIE_A_MEMORY_MIRROR_PAIR_INDEX_V1",
                "pairs": [
                    {
                        "source_name": key[0],
                        "action_string": key[1],
                        "mirror_pair_key": key[2],
                        "orientation": key[3],
                        "count": count,
                    }
                    for key, count in sorted(mirror_pairs.items())
                ],
            },
        )
        daily_file = _write_json(
            temporary / "daily-averaged-companions.json",
            {
                "schema": "FRANKIE_A_MEMORY_DAILY_AVERAGED_COMPANIONS_V1",
                "reconciliation_label": "COEQUAL_WITH_EXACT_MEMBER_LEDGER",
                "sources": daily_rows,
            },
        )

        receipt = {
            "schema": "FRANKIE_A_MEMORY_MEMBER_FIRST_RECALCULATION_RECEIPT_V1",
            "classification": "READ_ONLY_RETROSPECTIVE_DERIVATION",
            "objective": "A_MEMORY_OUTPUT_IMPROVEMENT_NOT_ARM_COMPARISON",
            "input": {
                "ledger_path": str(ledger_path),
                "ledger_sha256": observed_sha,
            },
            "completed_event_groups": groups,
            "completed_native_mbo_records": cursor,
            "distinct_candidate_families": len(family_rows),
            "open_world_candidate_groups": open_world_groups,
            "discovery_contract": discovery_contract(),
            "daily_averaged_companion_verification": observation_status,
            "invariants": {
                "every_group_emitted_exactly_once": member_file["rows"] == groups,
                "all_groups_f_last_closed": True,
                "native_actions_preserved_by_exact_tuple": True,
                "full_depth_reconstructed": True,
                "fifo_adapter_used": True,
                "step1_used": False,
                "reveal_or_scoring_used": False,
                "forecaster_used": False,
                "other_arm_used": False,
                "supplemental_enriched_or_rerun_only_input_used": False,
                "a_clean_output_used_as_evidence": False,
                "principal_model_invoked": False,
                "lock_or_freeze_created": False,
                "historical_family_count_used_as_gate": False,
                "unmatched_members_dropped": False,
            },
            "artifacts": {
                "exact_members": member_file,
                "exact_runs": run_file,
                "family_index": family_file,
                "adjacency_index": adjacency_file,
                "mirror_pair_index": mirror_file,
                "daily_averaged_companions": daily_file,
            },
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
        _write_json(temporary / "receipt.json", receipt)
        temporary.replace(out_dir)
        return receipt
    except Exception:
        try:
            member_writer._gzip.close()
            member_writer._raw.close()
            run_writer._gzip.close()
            run_writer._raw.close()
        finally:
            shutil.rmtree(temporary, ignore_errors=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--expected-ledger-sha256", default=EXPECTED_A_MEMORY_LEDGER_SHA256
    )
    parser.add_argument("--expected-group-count", type=int, default=EXPECTED_A_MEMORY_GROUPS)
    parser.add_argument("--expected-record-count", type=int, default=EXPECTED_A_MEMORY_RECORDS)
    parser.add_argument("--progress-every", type=int, default=250_000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    receipt = run_recalculation(
        ledger_path=args.ledger,
        out_dir=args.out_dir,
        expected_ledger_sha256=args.expected_ledger_sha256,
        expected_group_count=args.expected_group_count,
        expected_record_count=args.expected_record_count,
        observations_path=args.observations,
        progress_every=args.progress_every,
    )
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
