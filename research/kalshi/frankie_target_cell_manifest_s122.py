#!/usr/bin/env python3
"""Compile and validate the exact target-cell kitchen-sink manifest for Frankie.

This is the machine seam between the real data-plane inventory and the S121
kitchen-sink gate. It deliberately does NOT infer historical availability,
freshness, possession, or Frankie access. Those facts must arrive as explicit
evidence from the target-cell inventory/export. Unknown facts STOP readiness.

Expected input is a JSON object with:
  target: {group, date, cutoff, namespace}
  rows: [
    {
      family, field, source, possessed, available_by_cutoff,
      future_answer_contaminated, accessible_to_frankie, status, evidence,
      freshness?, vintage?, packet_path?, access_reference?
    }, ...
  ]

Rows are field-level. The S121 family-level validator is then run over a strict
aggregation: one omitted possessed+causal field makes its entire family fail.
The target/future realized PRICE CURVE remains the only deliberate answer mask.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from frankie_kitchen_sink_audit_s121 import (
    KitchenSinkStop,
    assert_required_domains_present,
    validate_inventory,
)


class TargetCellManifestStop(KitchenSinkStop):
    pass


_REQUIRED_TARGET = ("group", "date", "cutoff", "namespace")
_REQUIRED_ROW = (
    "family", "field", "source", "possessed", "available_by_cutoff",
    "future_answer_contaminated", "accessible_to_frankie", "status", "evidence",
)
_ALLOWED_CLASSIFICATION = {
    "ACCESSIBLE", "UNAVAILABLE_AT_CUTOFF", "FUTURE_MASKED", "NOT_POSSESSED",
}


def _nonempty(value: Any) -> str:
    return str(value).strip()


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TargetCellManifestStop(f"cannot read target-cell manifest {path}: {exc}") from exc


def _row_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (_nonempty(row.get("family")), _nonempty(row.get("field")))


def validate_field_rows(rows: Sequence[Mapping[str, Any]]) -> None:
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or not rows:
        raise TargetCellManifestStop("target-cell rows must be a non-empty sequence")
    seen: set[tuple[str, str]] = set()
    for i, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise TargetCellManifestStop(f"target-cell row {i} must be an object")
        missing = [k for k in _REQUIRED_ROW if k not in row]
        if missing:
            raise TargetCellManifestStop(f"target-cell row {i} missing keys {missing}")
        family, field = _row_key(row)
        if not family or not field:
            raise TargetCellManifestStop(f"target-cell row {i} has empty family/field")
        key = (family, field)
        if key in seen:
            raise TargetCellManifestStop(f"duplicate target-cell field {family!r}/{field!r}")
        seen.add(key)
        if not _nonempty(row.get("source")) or not _nonempty(row.get("evidence")):
            raise TargetCellManifestStop(f"{family}/{field}: source and evidence must be explicit")
        for name in (
            "possessed", "available_by_cutoff", "future_answer_contaminated", "accessible_to_frankie"
        ):
            if not isinstance(row.get(name), bool):
                raise TargetCellManifestStop(f"{family}/{field}: {name} must be boolean")
        status = _nonempty(row.get("status")).upper()
        if status not in _ALLOWED_CLASSIFICATION:
            raise TargetCellManifestStop(f"{family}/{field}: invalid status {status!r}")

        possessed = row["possessed"]
        causal = row["available_by_cutoff"]
        contaminated = row["future_answer_contaminated"]
        accessible = row["accessible_to_frankie"]
        if possessed and causal and not contaminated and not accessible:
            raise TargetCellManifestStop(
                "possessed causal field silently omitted from Frankie access: "
                f"{family}/{field}"
            )
        if status == "ACCESSIBLE" and not (possessed and causal and accessible and not contaminated):
            raise TargetCellManifestStop(f"{family}/{field}: ACCESSIBLE contradicts row facts")
        if status == "FUTURE_MASKED" and not (possessed and contaminated and not accessible):
            raise TargetCellManifestStop(f"{family}/{field}: FUTURE_MASKED contradicts row facts")
        if status == "UNAVAILABLE_AT_CUTOFF" and causal:
            raise TargetCellManifestStop(f"{family}/{field}: unavailable-at-cutoff row says causal=true")
        if status == "NOT_POSSESSED" and possessed:
            raise TargetCellManifestStop(f"{family}/{field}: NOT_POSSESSED contradicts possessed=true")


def aggregate_families(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate field evidence without allowing a good field to hide a bad sibling."""
    validate_field_rows(rows)
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_nonempty(row["family"])].append(row)

    out: list[dict[str, Any]] = []
    for family in sorted(grouped):
        members = grouped[family]
        possessed = any(bool(r["possessed"]) for r in members)
        causal_clean = [
            r for r in members
            if r["possessed"] and r["available_by_cutoff"] and not r["future_answer_contaminated"]
        ]
        contaminated = bool(members) and all(bool(r["future_answer_contaminated"]) for r in members if r["possessed"])
        accessible = bool(causal_clean) and all(bool(r["accessible_to_frankie"]) for r in causal_clean)

        statuses = {_nonempty(r["status"]).upper() for r in members}
        if causal_clean:
            status = "ACCESSIBLE" if accessible else "ACCESSIBLE"  # validator will stop inaccessible siblings earlier
            available = True
            contaminated = False
        elif any(r["possessed"] and r["future_answer_contaminated"] for r in members):
            status = "FUTURE_MASKED"
            available = any(bool(r["available_by_cutoff"]) for r in members)
            contaminated = True
            accessible = False
        elif possessed:
            status = "UNAVAILABLE_AT_CUTOFF"
            available = False
            contaminated = False
            accessible = False
        else:
            status = "NOT_POSSESSED"
            available = False
            contaminated = False
            accessible = False

        evidence = "; ".join(
            f"{_nonempty(r['field'])}: {_nonempty(r['evidence'])}" for r in members
        )
        sources = sorted({_nonempty(r["source"]) for r in members})
        out.append({
            "family": family,
            "source": ", ".join(sources),
            "possessed": possessed,
            "available_by_cutoff": available,
            "future_answer_contaminated": contaminated,
            "accessible_to_frankie": accessible,
            "status": status,
            "evidence": evidence,
            "field_count": len(members),
            "field_statuses": sorted(statuses),
        })
    return out


def compile_manifest(doc: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(doc, Mapping):
        raise TargetCellManifestStop("target-cell manifest root must be an object")
    target = doc.get("target")
    rows = doc.get("rows")
    if not isinstance(target, Mapping):
        raise TargetCellManifestStop("target metadata missing")
    missing_target = [k for k in _REQUIRED_TARGET if not _nonempty(target.get(k))]
    if missing_target:
        raise TargetCellManifestStop(f"target metadata missing/empty keys {missing_target}")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise TargetCellManifestStop("rows missing or not a sequence")

    families = aggregate_families(rows)
    # Scope first, then the S121 family validator. Both fail closed.
    assert_required_domains_present(families)
    summary = validate_inventory(families)

    canonical = {
        "manifest_version": "s122.1",
        "target": dict(target),
        "rows": [dict(r) for r in rows],
        "families": families,
        "summary": summary,
    }
    digest_payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    canonical["sha256"] = hashlib.sha256(digest_payload.encode("utf-8")).hexdigest()
    canonical["readiness"] = "READY_OFFLINE" if summary.get("status") == "KITCHEN_SINK_COMPLETE" else "STOP"
    return canonical


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", type=Path, help="field-level target-cell inventory JSON")
    ap.add_argument("--write", type=Path, help="write canonical compiled manifest")
    args = ap.parse_args()
    compiled = compile_manifest(_load_json(args.manifest))
    text = json.dumps(compiled, indent=2, sort_keys=True) + "\n"
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(text, encoding="utf-8")
        print(f"wrote {args.write} {compiled['sha256']}")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
