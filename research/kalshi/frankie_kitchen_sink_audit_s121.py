#!/usr/bin/env python3
"""S121 kitchen-sink causal completeness gate for Frankie blind recreations.

Policy is data-driven rather than a frozen allow-list: inventory everything DavisAI possesses for the
cell, prove whether it was available by the historical cutoff, and prove whether Frankie can access
it. Any possessed + causal-by-cutoff family that is not accessible is a hard STOP. The only deliberate
mask is target/future price-curve information (and derivatives contaminated by that future answer).
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class KitchenSinkStop(RuntimeError):
    pass


_ALLOWED_STATUS = {"ACCESSIBLE", "UNAVAILABLE_AT_CUTOFF", "FUTURE_MASKED", "NOT_POSSESSED"}
_REQUIRED_KEYS = (
    "family",
    "source",
    "possessed",
    "available_by_cutoff",
    "future_answer_contaminated",
    "accessible_to_frankie",
    "status",
    "evidence",
)


def validate_inventory(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or not rows:
        raise KitchenSinkStop("kitchen-sink inventory must be a non-empty sequence")

    seen: set[str] = set()
    omissions: list[str] = []
    accessible: list[str] = []
    future_masked: list[str] = []
    unavailable: list[str] = []

    for i, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise KitchenSinkStop(f"inventory row {i} must be an object")
        missing = [k for k in _REQUIRED_KEYS if k not in row]
        if missing:
            raise KitchenSinkStop(f"inventory row {i} missing keys {missing}")
        family = str(row["family"]).strip()
        if not family:
            raise KitchenSinkStop(f"inventory row {i} has empty family")
        if family in seen:
            raise KitchenSinkStop(f"duplicate kitchen-sink family {family!r}")
        seen.add(family)
        if not str(row["source"]).strip() or not str(row["evidence"]).strip():
            raise KitchenSinkStop(f"{family}: source and evidence must be explicit")

        possessed = row["possessed"]
        causal = row["available_by_cutoff"]
        contaminated = row["future_answer_contaminated"]
        accessible_now = row["accessible_to_frankie"]
        for name, value in (
            ("possessed", possessed), ("available_by_cutoff", causal),
            ("future_answer_contaminated", contaminated),
            ("accessible_to_frankie", accessible_now),
        ):
            if not isinstance(value, bool):
                raise KitchenSinkStop(f"{family}: {name} must be boolean")

        status = str(row["status"]).upper()
        if status not in _ALLOWED_STATUS:
            raise KitchenSinkStop(f"{family}: invalid status {status!r}")

        # The only lawful reason to possess causal information and withhold it is that the object is
        # itself the future answer or is contaminated by future-answer information.
        if possessed and causal and not contaminated and not accessible_now:
            omissions.append(family)

        if status == "ACCESSIBLE":
            if not (possessed and causal and accessible_now and not contaminated):
                raise KitchenSinkStop(f"{family}: ACCESSIBLE status contradicts row facts")
            accessible.append(family)
        elif status == "FUTURE_MASKED":
            if not (possessed and contaminated and not accessible_now):
                raise KitchenSinkStop(f"{family}: FUTURE_MASKED status contradicts row facts")
            future_masked.append(family)
        elif status == "UNAVAILABLE_AT_CUTOFF":
            if causal:
                raise KitchenSinkStop(f"{family}: UNAVAILABLE_AT_CUTOFF but available_by_cutoff=true")
            unavailable.append(family)
        elif status == "NOT_POSSESSED":
            if possessed:
                raise KitchenSinkStop(f"{family}: NOT_POSSESSED but possessed=true")

    if omissions:
        raise KitchenSinkStop(
            "possessed causal data silently omitted from Frankie access: " + ", ".join(sorted(omissions))
        )

    return {
        "status": "KITCHEN_SINK_COMPLETE",
        "families_total": len(seen),
        "accessible_count": len(accessible),
        "future_masked_count": len(future_masked),
        "unavailable_at_cutoff_count": len(unavailable),
        "accessible_families": sorted(accessible),
        "future_masked_families": sorted(future_masked),
    }


def assert_required_domains_present(rows: Sequence[Mapping[str, Any]]) -> None:
    """Guard against an inventory that is technically valid but obviously incomplete in scope.

    These are domain buckets, not a claim that each one must contain historical data for every cell.
    They ensure the inventory at least accounts for the major families Greg explicitly built.
    """
    names = " ".join(str(r.get("family", "")).lower() for r in rows if isinstance(r, Mapping))
    domains = {
        "brain/schema": ("brain", "schema", "plays"),
        "databento/market microstructure": ("databento", "mbo", "mbp", "order book", "tape"),
        "storage/EIA": ("storage", "eia"),
        "weather": ("weather", "noaa", "ecmwf", "gfs"),
        "fundamentals": ("fundamental", "production", "lng", "feedgas", "pipeline", "power"),
        "positioning/flows": ("position", "cot", "flow"),
        "vol/options": ("vol", "option"),
        "basis/contract structure": ("basis", "contract", "curve structure", "spread"),
        "calendar/events": ("calendar", "event", "expiry", "release"),
        "prior price/history": ("prior price", "history", "historical", "analogue", "analog"),
        "target future curve mask": ("target curve", "actual curve", "future price", "realized price"),
    }
    missing = [label for label, tokens in domains.items() if not any(t in names for t in tokens)]
    if missing:
        raise KitchenSinkStop("inventory does not account for required domain bucket(s): " + ", ".join(missing))
