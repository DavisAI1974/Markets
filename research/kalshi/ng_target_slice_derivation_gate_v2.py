#!/usr/bin/env python3
"""Plan-bound deterministic target-shard derivation attestation.

V1 re-derives exact target bytes from verified broad sources. V2 additionally binds the
inspection-plan fingerprint that selected those target files, so basis regeneration cannot
substitute a different target plan while retaining the same receipt/catalog summaries.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping

import ng_target_slice_derivation_gate as v1

SCHEMA = "ng_target_slice_derivation_gate.v2"
READY_STATUS = "TARGET_SLICE_DERIVATION_ATTESTED_V2"
BLOCKED_STATUS = "TARGET_SLICE_DERIVATION_BLOCKED_V2"


class TargetSliceDerivationV2Error(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise TargetSliceDerivationV2Error(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise TargetSliceDerivationV2Error(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _upgrade(base: Mapping[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(dict(base))
    value.pop("fingerprint", None)
    parent = value.get("target_slice_broad_lineage_gate") or {}
    plan_fingerprint = parent.get("target_inspection_plan_fingerprint")
    if not isinstance(plan_fingerprint, str) or not plan_fingerprint:
        raise TargetSliceDerivationV2Error(
            "target broad-lineage gate is missing target inspection plan fingerprint"
        )
    value["schema"] = SCHEMA
    value["status"] = (
        READY_STATUS if base.get("status") == v1.READY_STATUS else BLOCKED_STATUS
    )
    value["target_inspection_plan_fingerprint"] = plan_fingerprint
    value["target_plan_bound_to_derivation"] = True
    value["basis_may_substitute_target_plan"] = False
    value["fingerprint"] = v1._fp(value)
    return value


def _build(
    lineage_gate: Mapping[str, Any], *, verify_files: bool
) -> dict[str, Any]:
    base = v1.build_gate(lineage_gate, verify_files=verify_files)
    return _upgrade(base)


def build_gate(
    lineage_gate: Mapping[str, Any], *, verify_files: bool = True
) -> dict[str, Any]:
    value = _build(lineage_gate, verify_files=verify_files)
    validate_gate(value, verify_files=verify_files)
    return value


def validate_gate(
    value: Mapping[str, Any], *, verify_files: bool = True
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != v1._fp(checked):
        raise TargetSliceDerivationV2Error(
            "target-slice derivation v2 schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    v1._authority(checked, label="target-slice derivation v2 gate")
    if checked.get("target_plan_bound_to_derivation") is not True:
        raise TargetSliceDerivationV2Error("target inspection plan must be bound to derivation")
    if checked.get("basis_may_substitute_target_plan") is not False:
        raise TargetSliceDerivationV2Error("basis may not substitute the target inspection plan")
    parent = checked.get("target_slice_broad_lineage_gate") or {}
    if checked.get("target_inspection_plan_fingerprint") != parent.get(
        "target_inspection_plan_fingerprint"
    ):
        raise TargetSliceDerivationV2Error(
            "target inspection plan fingerprint differs from broad-lineage evidence"
        )
    rebuilt = _build(parent, verify_files=verify_files)
    if v1._canonical(rebuilt) != v1._canonical(checked):
        raise TargetSliceDerivationV2Error(
            "target-slice derivation v2 does not match deterministic reconstruction"
        )
    return checked


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=False)
    build = sub.add_parser("build")
    build.add_argument("--lineage-gate", type=Path, required=True)
    build.add_argument("--out", type=Path, required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--gate", type=Path, required=True)
    validate.add_argument("--skip-file-verification", action="store_true")
    return parser


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    if args.command == "build":
        result = build_gate(_load(args.lineage_gate), verify_files=True)
        _write(args.out, result)
        print(
            json.dumps(
                {
                    "out": str(args.out),
                    "status": result["status"],
                    "target_inspection_plan_fingerprint": result[
                        "target_inspection_plan_fingerprint"
                    ],
                    "exact_derivation_count": result["exact_derivation_count"],
                    "blocker_count": len(result["blockers"]),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "validate":
        validate_gate(_load(args.gate), verify_files=not args.skip_file_verification)
        print("[ng_target_slice_derivation_gate_v2] gate VALID")
        return 0
    parser.error("select build or validate")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
