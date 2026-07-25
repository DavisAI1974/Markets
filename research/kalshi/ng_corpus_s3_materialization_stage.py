#!/usr/bin/env python3
"""Operational S3 materialization stage that emits every downstream inventory artifact.

The underlying attestation already validates exact remote object identity, checksum,
local bytes, and observed definition identity. This wrapper also persists the nested
inventory-compiler receipt as a standalone artifact so the later definition-byte gate
cannot accidentally consume a stale receipt from a different materialization run.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import ng_corpus_inventory_plan_compiler as inventory_compiler
import ng_corpus_s3_materialization_attestation as materialization

SCHEMA = "ng_corpus_s3_materialization_stage.v1"


def compile_stage(
    *,
    spec_path: Path,
    inventory_spec_out: Path,
    plan_out: Path,
    inventory_receipt_out: Path,
    receipt_out: Path,
) -> dict[str, str]:
    source_spec = materialization._load_json(spec_path)
    inventory_spec, plan, receipt = materialization.build_attested_plan(
        source_spec, spec_dir=spec_path.parent
    )
    materialization.validate_receipt(receipt)
    nested = receipt.get("inventory_compiler_receipt")
    if not isinstance(nested, dict):
        raise materialization.CorpusS3MaterializationError(
            "materialization receipt is missing nested inventory compiler receipt"
        )
    inventory_compiler.validate_receipt(nested)
    materialization._write(inventory_spec_out, inventory_spec)
    materialization._write(plan_out, plan)
    materialization._write(inventory_receipt_out, nested)
    materialization._write(receipt_out, receipt)
    return {
        "schema": SCHEMA,
        "status": receipt["status"],
        "materialization_receipt_fingerprint": receipt["receipt_fingerprint"],
        "inventory_compiler_receipt_fingerprint": nested["receipt_fingerprint"],
        "plan_fingerprint": plan["plan_fingerprint"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--inventory-spec-out", type=Path, required=True)
    parser.add_argument("--plan-out", type=Path, required=True)
    parser.add_argument("--inventory-receipt-out", type=Path, required=True)
    parser.add_argument("--receipt-out", type=Path, required=True)
    args = parser.parse_args(argv)
    summary = compile_stage(
        spec_path=args.spec,
        inventory_spec_out=args.inventory_spec_out,
        plan_out=args.plan_out,
        inventory_receipt_out=args.inventory_receipt_out,
        receipt_out=args.receipt_out,
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
