#!/usr/bin/env python3
"""Canonical S135 sequential CURRENT-FRANKIE group runner.

This module turns the S133/S135 sequencing contract into an executable state machine:

    prior legal state -> owner forecast -> validate -> SHA freeze -> reveal completed day
    -> score the frozen artifact -> carry completed state -> next owner

For a normal Friday-to-Monday boundary the route is E -> A weekend bridge -> B. Specialist A
bridges legally completed Friday state plus only genuinely available weekend information; A never
owns Monday's forecast. The configured day owner and the owner's S132 curve are preserved verbatim.

The runner does not modify the brain, roles, schema, spawn.py, or datapoint universe. It never
hydrates missing historical inputs. Realized target evidence is requested only after that day's
forecast has been frozen.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import importlib
import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping

VERSION = "S135_SEQUENTIAL_GROUP_RUNNER_V1"
MODES = {"BLIND", "REFINE"}
_DATE8 = re.compile(r"(?<!\d)(20\d{6})(?!\d)")
_ISO = re.compile(r"(?<!\d)(20\d{2})-(\d{2})-(\d{2})(?!\d)")
FORBIDDEN_BRIDGE_OUTCOME_KEYS = {
    "actual_close", "actual_day_move_usd", "realized_close", "realized_day_move_usd",
    "final_session_close", "target_outcome",
}


class RunContractError(RuntimeError):
    """Fail-closed violation of the S135 sequential replay contract."""


def _norm_day(value: str) -> str:
    day = str(value).replace("-", "")
    if len(day) != 8 or not day.isdigit() or not day.startswith("20"):
        raise RunContractError(f"invalid decision day {value!r}")
    return day


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise RunContractError(f"forecast is not canonical-JSON serializable: {exc}") from exc


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _weekday(day: str) -> int:
    day = _norm_day(day)
    return dt.date(int(day[:4]), int(day[4:6]), int(day[6:8])).weekday()


def _is_friday_to_monday(previous: str, current: str) -> bool:
    return _weekday(previous) == 4 and _weekday(current) == 0


def _forbidden_keys(obj: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(obj, Mapping):
        for key, value in obj.items():
            if str(key).lower() in FORBIDDEN_BRIDGE_OUTCOME_KEYS:
                found.add(str(key))
            found.update(_forbidden_keys(value))
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            found.update(_forbidden_keys(value))
    return found


def _dates_in(obj: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(obj, Mapping):
        for key, value in obj.items():
            found.update(_dates_in(key))
            found.update(_dates_in(value))
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            found.update(_dates_in(value))
    elif isinstance(obj, str):
        found.update(_DATE8.findall(obj))
        for year, month, day in _ISO.findall(obj):
            found.add(year + month + day)
    return found


@dataclass(frozen=True)
class DayPlan:
    day: str
    owner: str
    leg: str


@dataclass(frozen=True)
class GroupRunSpec:
    group: str
    mode: str
    days: tuple[DayPlan, ...]
    anchor_date: str | None
    mask_after: str | None

    @classmethod
    def from_group(cls, gid: str, mode: str = "BLIND", *, config_module: Any | None = None) -> "GroupRunSpec":
        if config_module is None:
            config_module = importlib.import_module("group_config")
        group = str(gid).lower()
        if group not in config_module.GROUPS:
            raise RunContractError(f"unknown group {gid!r}")
        run_mode = str(mode).upper()
        if run_mode not in MODES:
            raise RunContractError(f"mode must be one of {sorted(MODES)}, got {mode!r}")
        cfg = config_module.GROUPS[group]
        raw_days = tuple(_norm_day(d) for d in cfg.get("days") or ())
        if not raw_days:
            raise RunContractError(f"group {group} has no configured days")
        if list(raw_days) != sorted(raw_days) or len(set(raw_days)) != len(raw_days):
            raise RunContractError(f"group {group} days must be unique and chronological")
        owners = config_module.owner_map(group)
        plans: list[DayPlan] = []
        for day in raw_days:
            owner = str(owners.get(day) or "").upper()
            if owner not in set("ABCDE"):
                raise RunContractError(f"group {group} day {day} has invalid/missing owner {owner!r}")
            leg = str(config_module.leg_for(group, day) or "")
            if not leg:
                raise RunContractError(f"group {group} day {day} has no scored contract leg")
            plans.append(DayPlan(day=day, owner=owner, leg=leg))
        for prev, cur in zip(plans, plans[1:]):
            if _is_friday_to_monday(prev.day, cur.day) and (prev.owner != "E" or cur.owner != "B"):
                raise RunContractError(
                    f"group {group} weekend owner route must be Friday E -> A bridge -> Monday B; "
                    f"configured {prev.day}:{prev.owner} -> {cur.day}:{cur.owner}"
                )
        return cls(
            group=group,
            mode=run_mode,
            days=tuple(plans),
            anchor_date=_norm_day(cfg["anchor_date"]) if cfg.get("anchor_date") else None,
            mask_after=_norm_day(cfg["mask_after"]) if cfg.get("mask_after") else None,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "group": self.group,
            "mode": self.mode,
            "anchor_date": self.anchor_date,
            "mask_after": self.mask_after,
            "days": [vars(day) for day in self.days],
        }


@dataclass(frozen=True)
class FrozenForecast:
    day: str
    owner: str
    leg: str
    canonical_json: str
    sha256: str

    @classmethod
    def create(cls, plan: DayPlan, output: Mapping[str, Any]) -> "FrozenForecast":
        text = _canonical_json(dict(output))
        return cls(plan.day, plan.owner, plan.leg, text, _hash_text(text))

    def thaw_verified(self) -> dict[str, Any]:
        if _hash_text(self.canonical_json) != self.sha256:
            raise RunContractError(f"frozen forecast hash mismatch for {self.day}")
        value = json.loads(self.canonical_json)
        if not isinstance(value, dict):
            raise RunContractError(f"frozen forecast for {self.day} is not an object")
        return value


class SequentialReplayLedger:
    """Deterministic freeze/reveal/carry ledger; no model or data-source policy lives here."""

    def __init__(self, spec: GroupRunSpec, *, initial_prior_session: Mapping[str, Any] | None = None):
        self.spec = spec
        self._cursor = 0
        self._phase = "READY_TO_FREEZE"
        self._frozen: dict[str, FrozenForecast] = {}
        self._revealed: dict[str, dict[str, Any]] = {}
        self._scores: dict[str, Any] = {}
        self._bridges: dict[str, dict[str, Any]] = {}
        self._events: list[dict[str, Any]] = []
        self._initial_prior = (
            self._validate_prior(initial_prior_session, self.spec.days[0].day) if initial_prior_session else None
        )

    @property
    def complete(self) -> bool:
        return self._cursor >= len(self.spec.days)

    @property
    def events(self) -> tuple[dict[str, Any], ...]:
        return tuple(copy.deepcopy(self._events))

    def _active(self) -> DayPlan:
        if self.complete:
            raise RunContractError("group ledger already complete")
        return self.spec.days[self._cursor]

    @staticmethod
    def _validate_prior(session: Mapping[str, Any], target_day: str) -> dict[str, Any]:
        if not isinstance(session, Mapping):
            raise RunContractError("completed prior-session context must be an object")
        row = copy.deepcopy(dict(session))
        session_day = _norm_day(str(row.get("date") or ""))
        target = _norm_day(target_day)
        if session_day >= target:
            raise RunContractError(
                f"completed prior-session context must be strictly earlier than target: {session_day} >= {target}"
            )
        own_or_future = sorted(day for day in _dates_in(row) if day >= target)
        if own_or_future:
            raise RunContractError(
                f"completed prior-session context contains own/future date(s) {own_or_future} for target {target}"
            )
        return row

    def carry_for(self, target_day: str) -> dict[str, Any] | None:
        plan = self._active()
        target = _norm_day(target_day)
        if target != plan.day:
            raise RunContractError(f"carry requested for {target}, active day is {plan.day}")
        if self._phase != "READY_TO_FREEZE":
            raise RunContractError(f"carry requested while ledger phase is {self._phase}")
        if self._cursor == 0:
            return copy.deepcopy(self._initial_prior)
        previous = self.spec.days[self._cursor - 1]
        if previous.day not in self._revealed:
            raise RunContractError(f"prior day {previous.day} has not been revealed after freeze")
        return self._validate_prior(self._revealed[previous.day], target)

    def freeze(
        self,
        day: str,
        output: Mapping[str, Any],
        *,
        validator: Callable[[Mapping[str, Any], str], None] | None = None,
    ) -> FrozenForecast:
        plan = self._active()
        target = _norm_day(day)
        if target != plan.day:
            raise RunContractError(f"out-of-order freeze {target}; expected {plan.day}")
        if self._phase != "READY_TO_FREEZE":
            raise RunContractError(f"cannot freeze {target} while ledger phase is {self._phase}")
        if not isinstance(output, Mapping):
            raise RunContractError("forecast output must be an object")
        if validator is not None:
            validator(output, plan.owner)
        frozen = FrozenForecast.create(plan, output)
        self._frozen[target] = frozen
        self._phase = "FROZEN"
        self._events.append(
            {"event": "FORECAST_FROZEN", "day": target, "owner": plan.owner, "sha256": frozen.sha256}
        )
        return frozen

    def reveal(self, day: str, completed_session: Mapping[str, Any]) -> dict[str, Any]:
        plan = self._active()
        target = _norm_day(day)
        if target != plan.day:
            raise RunContractError(f"out-of-order reveal {target}; expected {plan.day}")
        if self._phase != "FROZEN" or target not in self._frozen:
            raise RunContractError(f"cannot reveal {target} before its forecast is frozen")
        if not isinstance(completed_session, Mapping):
            raise RunContractError("revealed completed session must be an object")
        actual = copy.deepcopy(dict(completed_session))
        actual_day = _norm_day(str(actual.get("date") or ""))
        if actual_day != target:
            raise RunContractError(f"revealed session date {actual_day} != frozen day {target}")
        self._revealed[target] = actual
        self._phase = "REVEALED"
        self._events.append(
            {"event": "SESSION_REVEALED", "day": target, "after_freeze_sha256": self._frozen[target].sha256}
        )
        return copy.deepcopy(actual)

    def record_weekend_bridge(self, monday_day: str, bridge: Mapping[str, Any]) -> dict[str, Any]:
        plan = self._active()
        monday = _norm_day(monday_day)
        if monday != plan.day or self._cursor == 0:
            raise RunContractError("weekend bridge must target the active Monday after a completed Friday")
        previous = self.spec.days[self._cursor - 1]
        if not _is_friday_to_monday(previous.day, monday):
            raise RunContractError(f"{previous.day}->{monday} is not a Friday-to-Monday transition")
        if previous.owner != "E" or plan.owner != "B":
            raise RunContractError("weekend bridge requires configured E -> A bridge -> B route")
        if previous.day not in self._revealed:
            raise RunContractError("Friday completed state must be frozen/revealed before A weekend bridge")
        if not isinstance(bridge, Mapping):
            raise RunContractError("weekend bridge output must be an object")
        leaked = sorted(_forbidden_keys(bridge))
        if leaked:
            raise RunContractError(f"weekend bridge contains forbidden target outcome field(s): {leaked}")
        row = copy.deepcopy(dict(bridge))
        self._bridges[monday] = row
        self._events.append(
            {"event": "WEEKEND_BRIDGED", "from": previous.day, "via": "A", "to": monday, "forecast_owner": "B"}
        )
        return copy.deepcopy(row)

    def weekend_bridge_for(self, monday_day: str) -> dict[str, Any] | None:
        return copy.deepcopy(self._bridges.get(_norm_day(monday_day)))

    def score_frozen(
        self,
        day: str,
        scorer: Callable[[DayPlan, Mapping[str, Any], Mapping[str, Any]], Any],
    ) -> Any:
        plan = self._active()
        target = _norm_day(day)
        if target != plan.day:
            raise RunContractError(f"out-of-order score {target}; expected {plan.day}")
        if self._phase != "REVEALED":
            raise RunContractError(f"cannot score {target} before freeze then reveal")
        frozen = self._frozen[target].thaw_verified()
        actual = copy.deepcopy(self._revealed[target])
        score = scorer(plan, frozen, actual)
        self._scores[target] = copy.deepcopy(score)
        self._events.append(
            {"event": "FROZEN_ARTIFACT_SCORED", "day": target, "sha256": self._frozen[target].sha256}
        )
        return copy.deepcopy(score)

    def advance(self, day: str) -> None:
        plan = self._active()
        target = _norm_day(day)
        if target != plan.day:
            raise RunContractError(f"out-of-order advance {target}; expected {plan.day}")
        if self._phase != "REVEALED":
            raise RunContractError(f"cannot advance {target}; freeze and reveal must complete first")
        self._cursor += 1
        self._phase = "COMPLETE" if self.complete else "READY_TO_FREEZE"

    def frozen_record(self, day: str) -> FrozenForecast:
        target = _norm_day(day)
        if target not in self._frozen:
            raise RunContractError(f"day {target} has not been frozen")
        return self._frozen[target]

    def summary(self) -> dict[str, Any]:
        return {
            "group": self.spec.group,
            "mode": self.spec.mode,
            "complete": self.complete,
            "frozen": {day: frozen.sha256 for day, frozen in self._frozen.items()},
            "revealed_days": list(self._revealed),
            "scored_days": list(self._scores),
            "weekend_bridge_days": list(self._bridges),
            "events": list(self.events),
        }


def runner_contract_manifest() -> dict[str, Any]:
    return {
        "version": VERSION,
        "freeze_before_reveal": True,
        "sha256_freeze": True,
        "score_frozen_artifact_only": True,
        "completed_prior_session_only_after_reveal": True,
        "same_day_future_prior_context_blocked": True,
        "target_data_provider_called_after_freeze": True,
        "friday_e_to_a_to_monday_b": True,
        "a_does_not_own_monday_forecast": True,
        "configured_owner_curve_preserved_verbatim": True,
        "coordinator_averaging": False,
        "fixed_curve_clock": False,
        "abstain_flattening": False,
        "hydration": "REJECTED_NOT_USED",
        "new_datapoint_family": False,
        "architecture_varies_by_group": False,
        "group_dates_owner_leg_from_group_config": True,
    }


def _require_preflight_gate(spec: GroupRunSpec, result: Mapping[str, Any] | None) -> None:
    if not isinstance(result, Mapping):
        raise RunContractError("actual group execution requires an explicit S135 preflight result")
    if result.get("run_gate") != "PASS":
        raise RunContractError(f"S135 preflight run_gate is not PASS: {result.get('run_gate')!r}")
    checks = result.get("mandatory_checks")
    if not isinstance(checks, Mapping) or len(checks) != 21 or not all(value is True for value in checks.values()):
        raise RunContractError("S135 preflight must contain 21/21 passing mandatory checks")
    group_spec = result.get("group_run_spec") or {}
    if str(group_spec.get("group") or "").lower() != spec.group:
        raise RunContractError("S135 preflight group does not match requested group")
    if result.get("state_check") is None:
        raise RunContractError("S135 preflight must include the staged state check before execution")


def _default_validate(runtime: Any, output: Mapping[str, Any], gid: str, plan: DayPlan) -> None:
    runtime.base._validate_day(dict(output), gid, plan.day, plan.owner)
    runtime.validate_owner_output(output, plan.owner, task="day_forecast")


def _assert_packet_outcome_wall(runtime: Any, packet: Mapping[str, Any], gid: str, day: str) -> None:
    s133 = getattr(runtime, "s133", None)
    s120 = getattr(s133, "s120", None) if s133 is not None else None
    wall = getattr(s120, "assert_no_outcome_leak", None) if s120 is not None else None
    if wall is None:
        raise RunContractError("CURRENT FRANKIE outcome wall is unavailable after weekend bridge injection")
    wall(json.dumps(packet, sort_keys=True), gid, day)


def run_group(
    spec: GroupRunSpec,
    *,
    forecast_fn: Callable[[DayPlan, str, Mapping[str, Any]], Mapping[str, Any]],
    preflight_result: Mapping[str, Any] | None = None,
    reveal_fn: Callable[[str, str], Mapping[str, Any]] | None = None,
    score_fn: Callable[[DayPlan, Mapping[str, Any], Mapping[str, Any]], Any] | None = None,
    weekend_bridge_fn: Callable[[DayPlan, str, Mapping[str, Any]], Mapping[str, Any]] | None = None,
    initial_prior_session: Mapping[str, Any] | None = None,
    namespace: str = "current_frankie_s135",
    template: str = "BLD-1",
    runtime_module: Any | None = None,
) -> SequentialReplayLedger:
    """Execute one group through the state-gated S135 sequential state machine."""
    _require_preflight_gate(spec, preflight_result)
    if forecast_fn is None:
        raise RunContractError("forecast_fn is required; runner will not invent or silently select a model backend")
    if score_fn is None:
        raise RunContractError("score_fn is required; canonical group runs must score the immutable frozen artifact")
    if (
        any(_is_friday_to_monday(a.day, b.day) for a, b in zip(spec.days, spec.days[1:]))
        and weekend_bridge_fn is None
    ):
        raise RunContractError(
            "group contains Friday-to-Monday boundary; Specialist A weekend bridge callback is required before execution"
        )
    if runtime_module is None:
        runtime_module = importlib.import_module("frankie_s135_current_runtime")
    runtime_module.install()
    if reveal_fn is None:
        reveal_fn = importlib.import_module("group_mbo_engine").per_day_evidence

    ledger = SequentialReplayLedger(spec, initial_prior_session=initial_prior_session)
    for index, plan in enumerate(spec.days):
        prior = ledger.carry_for(plan.day)
        bridge = None
        if index > 0:
            previous = spec.days[index - 1]
            if _is_friday_to_monday(previous.day, plan.day):
                if prior is None:
                    raise RunContractError("Friday completed state missing at weekend bridge")
                bridge_prompt, bridge_packet = runtime_module.packet_sequential(
                    "BLD-2", spec.group, plan.day, "A", namespace,
                    prior_session=prior,
                    provenance="S135 frozen-then-revealed Friday completed session",
                )
                bridge_out = weekend_bridge_fn(plan, bridge_prompt, bridge_packet)
                runtime_module.validate_owner_output(bridge_out, "A", task="weekend_bridge")
                bridge = ledger.record_weekend_bridge(plan.day, bridge_out)

        if prior is None:
            prompt, packet = runtime_module.packet(template, spec.group, plan.day, plan.owner, namespace)
        else:
            prompt, packet = runtime_module.packet_sequential(
                template, spec.group, plan.day, plan.owner, namespace,
                prior_session=prior,
                provenance="S135 frozen-then-revealed completed prior-session evidence",
            )
        if bridge is not None:
            packet = copy.deepcopy(dict(packet))
            packet["s135_weekend_bridge_context"] = {
                "via_specialist": "A",
                "owns_monday_forecast": False,
                "monday_owner": plan.owner,
                "bridge": bridge,
            }
            _assert_packet_outcome_wall(runtime_module, packet, spec.group, plan.day)

        output = forecast_fn(plan, prompt, packet)
        ledger.freeze(
            plan.day,
            output,
            validator=lambda out, owner, current=plan: _default_validate(runtime_module, out, spec.group, current),
        )
        # Legal boundary: the target-evidence provider is not called until the SHA freeze exists.
        actual = reveal_fn(spec.group, plan.day)
        ledger.reveal(plan.day, actual)
        ledger.score_frozen(plan.day, score_fn)
        ledger.advance(plan.day)
    return ledger


def _preflight_report(spec: GroupRunSpec) -> dict[str, Any]:
    return {
        "status": "PASS",
        "runner_contract": runner_contract_manifest(),
        "group_run_spec": spec.as_dict(),
        "execution_note": (
            "Preflight only: no target evidence read and no blind run started. Actual execution additionally "
            "requires a 21/21 staged-state preflight result plus explicit forecast/bridge/score adapters."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="S135 canonical sequential CURRENT-FRANKIE group runner")
    ap.add_argument("--group", required=True, help="canonical group_config id, e.g. g24")
    ap.add_argument("--mode", choices=("blind", "refine"), default="blind")
    ap.add_argument("--preflight-only", action="store_true")
    args = ap.parse_args()
    spec = GroupRunSpec.from_group(args.group, args.mode)
    if not args.preflight_only:
        raise SystemExit(
            "S135 refuses CLI execution without explicit state preflight and backend adapters. "
            "Use run_group(...) from the canonical driver; --preflight-only is safe standalone."
        )
    print(json.dumps(_preflight_report(spec), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
