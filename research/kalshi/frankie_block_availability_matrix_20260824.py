#!/usr/bin/env python3
"""Machine-readable causal availability policy for every canonical S135 block."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable


def _rows(names: Iterable[str], cadence: str, rule: str, clock: str) -> dict[str, dict[str, str]]:
    return {
        name: {"cadence_class": cadence, "availability_rule": rule, "clock_source": clock}
        for name in names
    }


BLOCK_AVAILABILITY_POLICY: dict[str, dict[str, str]] = {
    **_rows(
        ("dow", "holiday", "flow_calendar", "model_cycles_et", "eia_storage_print_et",
         "cot_publication_et", "globex_reopen_et", "session_close_et", "settle_window_et",
         "scored_leg"),
        "STATIC_SESSION_CALENDAR", "STATIC_OR_PREFIX", "deterministic exchange/report calendar",
    ),
    **_rows(
        ("firehose_present",), "LIVE_PREFIX_STATE", "STATIC_OR_PREFIX",
        "causal MBO prefix binding",
    ),
    **_rows(
        ("cash_basis", "contract_structure", "options_surface", "squeeze_watch",
         "tape_conditions", "vol_regime"),
        "PRIOR_SESSION_OR_SETTLE", "PRIOR_DATE", "vintage_asof/asof_session/asof_prior_session",
    ),
    **_rows(
        ("storage", "storage_regional", "stor_surprise_basis"),
        "EIA_STORAGE_RELEASE", "REQUIRE_EXPLICIT_CLOCK",
        "print_datetime_utc/available_at/authoritative release calendar",
    ),
    **_rows(
        ("storage_vintage",), "EIA_STORAGE_VINTAGE", "REQUIRE_EXPLICIT_CLOCK",
        "print_datetime_utc",
    ),
    **_rows(
        ("storage_consensus",), "PREPRINT_CONSENSUS", "REQUIRE_EXPLICIT_CLOCK",
        "consensus_pre_print_snapshot_utc/print_datetime_utc",
    ),
    **_rows(
        ("grid_stack",), "EIA930_PERIOD_PLUS_2", "PERIOD_PLUS_3D", "period",
    ),
    **_rows(
        ("nuclear_outages",), "NRC_DAILY_REPORT", "REPORT_DATE_PLUS_2D",
        "explicit publication timestamp or conservative period+2d",
    ),
    **_rows(
        ("solar",), "MIXED_SOLAR_GEOMETRY_AND_EIA930", "REQUIRE_EXPLICIT_CLOCK",
        "EIA-930 publication timestamp required for mixed block",
    ),
    **_rows(
        ("cot", "steo_vintage", "ngwu_balance"), "PUBLISHED_REPORT",
        "REQUIRE_EXPLICIT_CLOCK", "publication_ts/knowable_from",
    ),
    **_rows(
        ("weather_forecast", "weather_forecast_cycle", "weather_forcing_forecast",
         "freeze_risk", "model_disagreement"),
        "FORECAST_CYCLE", "REQUIRE_EXPLICIT_CLOCK", "asof_utc/knowable_from",
    ),
    **_rows(
        ("weather",), "FULL_DAY_REALIZED_OR_REVISED", "QUARANTINE_REALIZED",
        "full-day aggregate unavailable during prefix",
    ),
    **_rows(
        ("curve_regime", "stor_surprise", "stor_surprise_sign"),
        "DERIVED_REQUIRES_PARENT_CLOCK", "REQUIRE_EXPLICIT_CLOCK",
        "no independently proven availability metadata",
    ),
    **_rows(
        ("blocks_emitted[0]", "blocks_emitted[1]", "blocks_emitted[2]", "blocks_emitted[3]",
         "built_utc", "frozen_structure_stale", "group", "mask_after", "note"),
        "BUILD_DIAGNOSTIC", "QUARANTINE_BUILD_METADATA", "post-hoc state build metadata",
    ),
}


def matrix_for_blocks(blocks: Iterable[str]) -> dict[str, Any]:
    rows: dict[str, dict[str, str]] = {}
    for block in sorted(set(blocks)):
        policy = BLOCK_AVAILABILITY_POLICY.get(block)
        if policy is None:
            # Synthetic unit-test registry blocks are intentionally visible as
            # fixtures; any unknown production block is fail-closed below.
            if block.startswith("block_"):
                policy = {
                    "cadence_class": "SYNTHETIC_TEST_FIXTURE",
                    "availability_rule": "STATIC_OR_PREFIX",
                    "clock_source": "fixture cutoff",
                }
            else:
                policy = {
                    "cadence_class": "UNVERIFIED",
                    "availability_rule": "REQUIRE_EXPLICIT_CLOCK",
                    "clock_source": "UNVERIFIED_REGISTRY_BLOCK",
                }
        rows[block] = dict(policy)
    core = {"block_count": len(rows), "blocks": rows}
    digest = hashlib.sha256(
        json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()
    return {**core, "matrix_hash": digest}


__all__ = ["BLOCK_AVAILABILITY_POLICY", "matrix_for_blocks"]
