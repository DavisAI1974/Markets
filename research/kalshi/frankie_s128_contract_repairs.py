#!/usr/bin/env python3
"""S128 narrow serving/contract repairs learned from the g24 blind+refine run.

This module does NOT add a signal family, alter specialist roles, change the price mask,
or touch spawn.py.  It repairs four explicit contract/availability defects:

1. storage survey consensus: use the existing forward consensus poll store when a
   decision-time-visible snapshot exists; never synthesize a consensus and never use a
   post-cutoff revision;
2. scored-leg structure after a roll: keep the one-shot price mask and make current-leg
   price structure MACHINE-READABLY unavailable rather than leaving a prose-only caveat;
3. magnitude.emission_ceiling_check: formally declare the existing play unavailable at
   packet build until a real served input contract exists; do not reverse-engineer one;
4. HE24->HE1 handoff: carry authoritative typed containers separating forecast-derived
   state from realized-after-close state while retaining the flat legacy fields for older
   readers.

The intended integration pattern is the same as S121/S126: install this adapter in the
current process or use frankie_s128_decision_state.py for state construction.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ET = ZoneInfo("America/New_York")
UTC = dt.timezone.utc
_FORWARD_CONSENSUS_PATHS = (
    ROOT / "data" / "kalshi" / "consensus.jsonl",
    Path("data/kalshi/consensus.jsonl"),
)
_EMISSION_PLAY = "magnitude.emission_ceiling_check"
_ORIGINAL_FULL_BRAIN = None


def _parse_ts(value: Any) -> dt.datetime | None:
    if not value:
        return None
    s = str(value).strip()
    try:
        x = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if x.tzinfo is None:
        x = x.replace(tzinfo=UTC)
    return x.astimezone(UTC)


def _parse_event_ts(value: Any) -> dt.datetime | None:
    """ForexFactory/faireconomy event timestamp. Naive fallback is ET, never UTC."""
    if not value:
        return None
    s = str(value).strip()
    try:
        x = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if x.tzinfo is None:
        x = x.replace(tzinfo=ET)
    return x.astimezone(UTC)


def _parse_bcf(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = re.search(r"[-+]?\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(m.group(0)) if m else None


def _decision_cutoff_utc(day: dt.date) -> dt.datetime:
    prior = day - dt.timedelta(days=1)
    return dt.datetime.combine(prior, dt.time(20, 0), tzinfo=ET).astimezone(UTC)


def _load_forward_rows() -> list[dict[str, Any]]:
    p = next((p for p in _FORWARD_CONSENSUS_PATHS if p.is_file()), None)
    if p is None:
        return []
    rows: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(r, dict):
            rows.append(r)
    return rows


def _visible_forecast_snapshot(rec: dict[str, Any], cutoff: dt.datetime) -> tuple[float, str, str] | None:
    """Return (bcf, observed_at, basis) using ONLY a snapshot proven visible at cutoff."""
    hist = rec.get("forecast_history") or []
    candidates: list[tuple[dt.datetime, float, str]] = []
    for h in hist:
        if not isinstance(h, dict):
            continue
        seen = _parse_ts(h.get("observed_at"))
        val = _parse_bcf(h.get("forecast"))
        if seen is not None and val is not None and seen < cutoff:
            candidates.append((seen, val, "forecast_history"))
    if candidates:
        seen, val, basis = max(candidates, key=lambda x: x[0])
        return val, seen.isoformat().replace("+00:00", "Z"), basis

    # Legacy rows have only the latest value. It is safe for an earlier cutoff ONLY when the
    # entire row's last poll was already before that cutoff. If it was updated later, the earlier
    # vintage is unknowable and MUST remain absent.
    last = _parse_ts(rec.get("last_polled_at"))
    val = _parse_bcf(rec.get("forecast"))
    if last is not None and val is not None and last < cutoff:
        return val, last.isoformat().replace("+00:00", "Z"), "legacy_latest_proven_before_cutoff"
    return None


def forward_storage_consensus(day8: str, rows: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """Nearest Natural Gas Storage forecast visible before D-1 20:00 ET.

    This is an existing-source serving fallback. It never reads/serves `actual`, and a later
    revision cannot travel backward because `_visible_forecast_snapshot` is cutoff-gated.
    """
    D = dt.date(int(day8[:4]), int(day8[4:6]), int(day8[6:]))
    cutoff = _decision_cutoff_utc(D)
    choices: list[tuple[dt.datetime, dict[str, Any]]] = []
    for rec in rows if rows is not None else _load_forward_rows():
        title = str(rec.get("title") or "").lower()
        if "natural gas storage" not in title:
            continue
        event = _parse_event_ts(rec.get("date"))
        if event is None or event.astimezone(ET).date() < D:
            continue
        choices.append((event, rec))
    for event, rec in sorted(choices, key=lambda x: x[0]):
        snap = _visible_forecast_snapshot(rec, cutoff)
        if snap is None:
            continue
        value, observed_at, basis = snap
        event_et = event.astimezone(ET)
        print_date = event_et.date()
        return {
            "for_report_date": (print_date - dt.timedelta(days=6)).isoformat(),
            "print_date": print_date.isoformat(),
            "print_dow": event_et.strftime("%a"),
            "print_time_et": event_et.strftime("%H:%M"),
            "print_datetime_utc": event.isoformat().replace("+00:00", "Z"),
            "print_schedule_note": "forward consensus poll event timestamp; holiday timing follows source event",
            "days_to_print": (print_date - D).days,
            "consensus_chg_bcf": value,
            "source": "consensus_poll:faireconomy/forexfactory",
            "final_capture_is_post_print": False,
            "consensus_pre_print_bcf": value,
            "consensus_pre_print_snapshot_utc": observed_at,
            "n_estimates": 1,
            "range_low_bcf": None,
            "range_high_bcf": None,
            "house_disagreement_bcf": None,
            "estimates": [{
                "source": "consensus_poll:faireconomy/forexfactory",
                "value_bcf": value,
                "snapshot_utc": observed_at,
                "pre_print": True,
                "snapshot_basis": basis,
            }],
            "forward_store_provenance": {
                "raw_title": rec.get("title"),
                "raw_event_date": rec.get("date"),
                "snapshot_basis": basis,
                "decision_cutoff_utc": cutoff.isoformat().replace("+00:00", "Z"),
                "rule": "strictly before D-1 20:00 ET; no interpolation; no seasonal substitute",
            },
        }
    return None


def _merge_forward_consensus(day8: str, row: dict[str, Any]) -> None:
    fallback = forward_storage_consensus(day8)
    if fallback is None:
        return
    existing = row.get("storage_consensus")
    if not isinstance(existing, dict):
        existing = {"as_of": f"{day8[:4]}-{day8[4:6]}-{day8[6:]}",
                    "last_print": None, "next_print": None, "source": "storage_consensus_v1"}
    else:
        existing = dict(existing)
    nxt = existing.get("next_print")
    if isinstance(nxt, dict) and nxt.get("consensus_chg_bcf") is not None:
        return
    # If the historical archive knows the upcoming schedule, require the same print date. This
    # prevents a generic calendar row from silently replacing a known holiday-shifted print.
    if isinstance(nxt, dict) and nxt.get("print_date") and nxt.get("print_date") != fallback.get("print_date"):
        return
    existing["next_print"] = fallback
    existing["source"] = "storage_consensus_v1 + consensus_poll_forward_snapshot"
    existing["s128_forward_fallback"] = True
    row["storage_consensus"] = existing


def _mark_scored_leg_structure(row: dict[str, Any]) -> None:
    sl = row.get("scored_leg")
    if not isinstance(sl, dict):
        return
    leg = sl.get("leg")
    frozen_leg = sl.get("frozen_structural_blocks_describe")
    if not leg or not frozen_leg or leg == frozen_leg:
        return
    status = {
        "status": "UNAVAILABLE_ONE_SHOT_PRICE_MASK",
        "scored_leg": leg,
        "frozen_price_blocks_describe": frozen_leg,
        "price_fields_usable_for_scored_leg": False,
        "safe_live_calendar_source": "flow_calendar",
        "rule": ("Do not import price-derived contract_structure/options_surface/squeeze_watch from the "
                 "anchor leg onto the scored leg. Deterministic calendar facts may remain live; current-"
                 "leg price structure is UNKNOWN under the one-shot price mask, never inferred."),
    }
    sl = dict(sl)
    sl["current_scored_leg_price_structure"] = status
    row["scored_leg"] = sl
    for name in ("contract_structure", "options_surface", "squeeze_watch"):
        blk = row.get(name)
        if not isinstance(blk, dict):
            continue
        blk = dict(blk)
        blk["scored_leg_usable"] = False
        blk["describes_leg"] = frozen_leg
        blk["scored_leg_unavailable_reason"] = "UNAVAILABLE_ONE_SHOT_PRICE_MASK"
        blk["safe_live_calendar_source"] = "flow_calendar"
        row[name] = blk


def decision_state(days: list[str], mask_after: str | None = None, group: str | None = None) -> dict[str, Any]:
    """Canonical forecast_harness decision state + S128 contract-only post-processing."""
    import forecast_harness as fh
    out = fh.decision_state(days, mask_after=mask_after, group=group)
    for day in days:
        row = out.get(day)
        if not isinstance(row, dict):
            continue
        _merge_forward_consensus(day, row)
        _mark_scored_leg_structure(row)
    out["_play_input_availability"] = {
        _EMISSION_PLAY: {
            "status": "UNAVAILABLE_NO_SERVED_INPUT",
            "action": "STAND_DOWN",
            "rule": ("No registered served input currently satisfies this play. Do not synthesize or "
                     "reverse-engineer a ceiling. This is a serving-contract status, not a request to "
                     "add a new datapoint family."),
        }
    }
    build = out.get("_state_build")
    if isinstance(build, dict):
        build["s128_contract_repairs"] = [
            "forward_consensus_snapshot_fallback",
            "post_roll_scored_leg_structure_unavailable",
            "emission_ceiling_play_formally_unavailable",
        ]
    return out


def _decorate_full_brain(served: dict[str, Any]) -> dict[str, Any]:
    out = dict(served)
    plays = out.get("plays") or {}
    if isinstance(plays, list):
        pids = {str(x.get("id")) for x in plays if isinstance(x, dict)}
    elif isinstance(plays, dict):
        pids = set(map(str, plays))
    else:
        pids = set()
    if _EMISSION_PLAY in pids:
        fs = dict(out.get("_frankie_serving") or {})
        availability = dict(fs.get("play_input_availability") or {})
        availability[_EMISSION_PLAY] = {
            "status": "UNAVAILABLE_NO_SERVED_INPUT",
            "action": "STAND_DOWN",
            "rule": "do not reconstruct; re-enable only when a real served input contract is registered",
        }
        fs["play_input_availability"] = availability
        out["_frankie_serving"] = fs
    return out


def full_brain(view: dict[str, Any]) -> dict[str, Any]:
    """S120 full brain unchanged, plus formal play-input availability metadata."""
    import frankie_s118_redo as s120
    fn = _ORIGINAL_FULL_BRAIN or s120.full_brain
    return _decorate_full_brain(fn(view))


def typed_handoff_state(state: dict[str, Any] | None, source: str) -> dict[str, Any] | None:
    """Add authoritative typed containers without deleting legacy flat fields."""
    if state is None:
        return None
    if source not in {"blind", "actual"}:
        raise ValueError(f"source must be blind|actual, got {source!r}")
    clean = {k: v for k, v in state.items() if k != "_handoff_contract"}
    if source == "blind":
        contract = {
            "state_kind": "forecast_derived_at_prior_cutoff",
            "authoritative_container": "forecast_derived_at_prior_cutoff",
            "forecast_derived_at_prior_cutoff": clean,
            "realized_exit_state_after_close": None,
            "consumer_rule": "BLIND may consume only forecast_derived_at_prior_cutoff; realized exit is unavailable.",
        }
    else:
        contract = {
            "state_kind": "realized_exit_state_after_close",
            "authoritative_container": "realized_exit_state_after_close",
            "forecast_derived_at_prior_cutoff": None,
            "realized_exit_state_after_close": clean,
            "consumer_rule": "REFINE/LIVE may consume realized_exit_state_after_close; do not relabel it as a Friday-cutoff forecast.",
        }
    out = dict(clean)
    out["_handoff_contract"] = contract
    return out


def install_brain() -> None:
    """Install only the S128 full-brain availability annotation; idempotent."""
    global _ORIGINAL_FULL_BRAIN
    import frankie_s118_redo as s120
    import frankie_group_forecast_s118 as base
    if _ORIGINAL_FULL_BRAIN is None:
        _ORIGINAL_FULL_BRAIN = s120.full_brain
    s120.full_brain = full_brain
    s120.compact_brain = full_brain
    base._compact_brain = full_brain


def install_handoff() -> None:
    """Type handoff exit states while keeping group_he24 legacy flat readers functional."""
    import group_he24_he1_handoff as hh
    if not hasattr(hh, "_s128_original_exit_state"):
        hh._s128_original_exit_state = hh.exit_state
    if not hasattr(hh, "_s128_original_exit_state_blind"):
        hh._s128_original_exit_state_blind = hh.exit_state_blind

    def _actual(gid, day):
        return typed_handoff_state(hh._s128_original_exit_state(gid, day), "actual")

    def _blind(gid, day, blind_days, prev_close):
        return typed_handoff_state(
            hh._s128_original_exit_state_blind(gid, day, blind_days, prev_close), "blind"
        )

    hh.exit_state = _actual
    hh.exit_state_blind = _blind


def install() -> None:
    install_brain()
    install_handoff()


if __name__ == "__main__":
    print(json.dumps({
        "status": "READY",
        "repairs": [
            "forward_consensus_snapshot_fallback",
            "post_roll_scored_leg_structure_unavailable",
            "emission_ceiling_play_formally_unavailable",
            "typed_forecast_vs_realized_handoff",
        ],
    }, indent=2))
