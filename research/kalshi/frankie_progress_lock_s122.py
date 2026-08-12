#!/usr/bin/env python3
"""Machine-enforced S122 progress lock.

This is deliberately separate from the historical S114 OPEN_ITEMS registry.  The
old registry is provenance; this lock records current effective truth until that
large historical store is migrated without losing its history.

It prevents three regressions that cost paid/review time:
  * treating the stale 1717-point snapshot as current instead of 1914/44/1222;
  * treating old-brain unread fields as unavailable to Frankie;
  * treating implemented S115-S122 mechanisms as unbuilt because an S114 item
    still says OPEN.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
LOCK = HERE / "frankie_progress_lock_s122.json"
OPEN_ITEMS = HERE / "OPEN_ITEMS.json"
DATA_REGISTRY = HERE / "data_registry.py"
STALE_STORE = HERE / "store" / "data_points.json"


class ProgressLockError(RuntimeError):
    pass


def load_lock() -> dict[str, Any]:
    return json.loads(LOCK.read_text(encoding="utf-8"))


def effective_item_state(item_id: str, raw_status: str | None = None) -> dict[str, str]:
    """Return current effective state without erasing historical registry provenance."""
    lock = load_lock()
    if item_id in lock["fully_done"]:
        return {"state": "DONE", "reason": lock["fully_done"][item_id]}
    if item_id in lock["implemented_do_not_rebuild_evidence_pending"]:
        return {
            "state": "IMPLEMENTED_EVIDENCE_PENDING",
            "reason": lock["implemented_do_not_rebuild_evidence_pending"][item_id],
        }
    if item_id in lock["partial_not_rebuild"]:
        return {"state": "PARTIAL", "reason": lock["partial_not_rebuild"][item_id]}
    if item_id in lock["must_verify_current_code_before_calling_open"]:
        return {
            "state": "VERIFY_CURRENT_CODE",
            "reason": lock["must_verify_current_code_before_calling_open"][item_id],
        }
    if item_id in lock["genuine_or_measured_open_after_reconciliation"]:
        return {
            "state": "OPEN_RECONCILED",
            "reason": lock["genuine_or_measured_open_after_reconciliation"][item_id],
        }
    return {"state": raw_status or "UNCLASSIFIED", "reason": "no S122 override"}


def reconciled_open_items(registry: Mapping[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in registry.get("items", []):
        iid = str(item.get("id", ""))
        eff = effective_item_state(iid, str(item.get("status", "")))
        row = dict(item)
        row["historical_status"] = item.get("status")
        row["effective_s122_state"] = eff["state"]
        row["effective_s122_reason"] = eff["reason"]
        out.append(row)
    return out


def assert_lock() -> dict[str, Any]:
    lock = load_lock()
    m = lock["measurement"]
    if (m["served"], m["decision_state_blocks"], m["served_unread"]) != (1914, 44, 1222):
        raise ProgressLockError("current measurement regressed from 1914 served / 44 blocks / 1222 unread")
    if m["status"] != "CURRENT_ACCEPTED_MEASUREMENT":
        raise ProgressLockError("1914 measurement is not marked current")
    if not lock["rules"]["unread_does_not_mean_unavailable_to_frankie"]:
        raise ProgressLockError("unread was incorrectly converted into Frankie inaccessibility")
    if not lock["rules"]["future_target_curve_masked"]:
        raise ProgressLockError("future target curve mask was relaxed")
    if not lock["rules"]["spawn_py_protected"]:
        raise ProgressLockError("spawn.py protection was relaxed")

    raw = json.loads(OPEN_ITEMS.read_text(encoding="utf-8"))
    rows = {r.get("id"): r for r in reconciled_open_items(raw)}
    for iid in lock["fully_done"]:
        if iid in rows and rows[iid]["effective_s122_state"] != "DONE":
            raise ProgressLockError(f"{iid} regressed from DONE")
    for iid in lock["implemented_do_not_rebuild_evidence_pending"]:
        if iid in rows and rows[iid]["effective_s122_state"] != "IMPLEMENTED_EVIDENCE_PENDING":
            raise ProgressLockError(f"{iid} lost implementation evidence")

    # The old committed store is allowed to exist for provenance, but it can never
    # be promoted to current truth.  If present, prove it is the known stale object.
    stale = None
    if STALE_STORE.exists():
        old = json.loads(STALE_STORE.read_text(encoding="utf-8"))
        stale = {"served": old.get("n_served"), "unread": old.get("n_served_unread")}
        if stale == {"served": 1914, "unread": 1222}:
            stale = None
        elif stale.get("served") and stale["served"] > 1914:
            raise ProgressLockError("a newer generated store exists; refresh S122 current measurement instead of ignoring it")

    src = DATA_REGISTRY.read_text(encoding="utf-8")
    stale_literals = {
        "forward wind / solar generation forecast": "A-51/G-5 current code says forward forcing is built",
        "zero-change and seasonal-normal baselines": "A-1 is DONE",
        "grid_stack gen_mwh['WAT'] (hydro, per BA)": "A-16 is DONE",
    }
    present_stale_claims = [name for name in stale_literals if name in src]

    return {
        "status": "LOCKED",
        "current_measurement": m,
        "historical_registry_session": raw.get("current_session"),
        "fully_done_locked": len(lock["fully_done"]),
        "implemented_evidence_pending_locked": len(lock["implemented_do_not_rebuild_evidence_pending"]),
        "later_done_locked": len(lock["later_done_do_not_rebuild"]),
        "stale_store_observed": stale,
        "stale_data_registry_claims_detected": present_stale_claims,
        "next_migration": "make data_registry.py consume this lock / remove stale hard-coded gap claims when regenerating the 1914+ store",
    }


def main() -> int:
    print(json.dumps(assert_lock(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
