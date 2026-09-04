#!/usr/bin/env python3
"""Assemble REAL_TIME_FRANKIE's findings artifact for run frankie-a-memory-rt-33746436209-1.

Inputs are all this session's own: the stream receipt the pass wrote, the validated output
bundle receipt, the knowledge dispositions, and the findings list written by hand from the
pass's tallies (findings_own.json). Copies the staged prompt, the three knowledge files, the
delivery receipt and cutoffs.json beside the artifact, and runs the knowledge-use read gate.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import canonical_hash
from research.kalshi.frankie_raw_mbo_benchmark.native_knowledge_delivery import validate_knowledge_use_files

RUN_DIR = Path("research/kalshi/frankie_raw_mbo_benchmark/principal_runs/frankie-a-memory-rt-33746436209-1")
WORK = Path("data/sunday_run/own_pass")
RUN_ID = "frankie-a-memory-rt-33746436209-1"
EVIDENCE_RESULT_HASH = "c406eee730401de16165b46091ac3042a1ca49d9025bbaefa9aa272bf52e420b"
DELIVERY_RECEIPT_SHA = "3420045aecc9c225ce77bf47a184cc2b262685177998f51ff94585b0b3149d1b"
KNOWLEDGE_RECEIPT_SHA = "6dc5825b578ac6fd3a6afa5b13c76bcd359a857d738610e64b02efb654891ea4"
COPIES = [
    "data/sunday_spawn_prompt.md",
    "data/sunday_receipts/knowledge/KNOWLEDGE_BUNDLE.md",
    "data/sunday_receipts/knowledge/KNOWLEDGE_RECEIPT.json",
    "data/sunday_receipts/knowledge/KNOWLEDGE_PRECALL_RECEIPT.json",
    "data/sunday_delivery/delivery_receipt.json",
    "data/sunday_receipts/cutoffs.json",
]


def main() -> int:
    stream_receipt = json.loads((RUN_DIR / "stream_receipt.json").read_text())
    stream_sha = canonical_hash(stream_receipt, omit="receipt_sha256")
    assert stream_sha == stream_receipt["receipt_sha256"], "stream receipt hash does not recompute"
    validated = json.loads((WORK / "validated_receipt.json").read_text())
    bundle_receipt = json.loads((RUN_DIR / "principal_outputs" / "RECEIPT.json").read_text())
    assert validated["receipt_sha256"] == bundle_receipt["receipt_sha256"], "bundle receipt on disk is not the validated one"
    kreceipt = json.loads(Path("data/sunday_receipts/knowledge/KNOWLEDGE_RECEIPT.json").read_text())
    start = {d["id"]: d for d in json.loads(Path("data/sunday_run/knowledge_inspected_at_start.json").read_text())}
    from frankie_own_finalize_20211003 import LATER_INSPECTIONS  # noqa: E402  (same directory)
    later = {d["id"]: d["reason"] for d in LATER_INSPECTIONS}
    dispositions = {}
    for a in kreceipt["artifacts"]:
        if a["id"] in later:
            dispositions[a["id"]] = {"disposition": "INSPECTED", "reason": later[a["id"]]}
        else:
            d = start[a["id"]]
            dispositions[a["id"]] = {"disposition": d["disposition"], "reason": d["reason"]}
    knowledge_use = {
        "schema": "FRANKIE_PRINCIPAL_KNOWLEDGE_USE_V1",
        "knowledge_receipt_sha256": KNOWLEDGE_RECEIPT_SHA,
        "profile_id": kreceipt["profile_id"], "arm": kreceipt["arm"], "role": kreceipt["role"],
        "manifest_hash": kreceipt["manifest_hash"], "context_bundle_sha256": kreceipt["context_bundle_sha256"],
        "dispositions": dispositions,
    }
    use_receipt = validate_knowledge_use_files(knowledge_use, knowledge_receipt_path="data/sunday_receipts/knowledge/KNOWLEDGE_RECEIPT.json",
                                               bundle_path="data/sunday_receipts/knowledge/KNOWLEDGE_BUNDLE.md", prompt_path="data/sunday_spawn_prompt.md")
    findings = json.loads((RUN_DIR / "findings_own.json").read_text())
    f20 = stream_receipt["falsifier_f20"]
    artifact = {
        "schema": "FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_FINDINGS_V1",
        "principal": "claude-fable-5-1",
        "arm": "A_MEMORY",
        "role": "REAL_TIME_FRANKIE",
        "evidence_result_hash": EVIDENCE_RESULT_HASH,
        "controller_only": False,
        "actual_principal_invocation": True,
        "evidence_read": {"exact_member_ledger": "READ", "exact_lifecycle_and_runway_ledger": "READ", "legacy_observable_rows": "READ"},
        "delivery_receipt_sha256": DELIVERY_RECEIPT_SHA,
        "stream_receipt_sha256": stream_sha,
        "outputs_receipt_sha256": validated["receipt_sha256"],
        "run_id": RUN_ID,
        "source_day": "20211003",
        "session": {"session_id": "session_014m3YsXKuT773qhNQLuWahu", "model": "claude-fable-5-1", "mechanism": "AGENT_SESSION"},
        "stream_consumed": {"groups_delivered": stream_receipt["groups_delivered"], "complete": stream_receipt["complete"], "bytes_delivered": stream_receipt["bytes_delivered"],
                            "lifecycle_rows_read": stream_receipt["lifecycle_ledger"]["rows_read"], "lifecycle_rows_attached": stream_receipt["lifecycle_ledger"]["rows_attached"],
                            "legacy_rows_read": stream_receipt["legacy_ledger"]["rows_read"], "legacy_rows_attached": stream_receipt["legacy_ledger"]["rows_attached"]},
        "falsifier_f20": {"verdict": f20["verdict"], "withheld_no_own_clock_total": f20["withheld_no_own_clock_total"], "withheld_close_occasion_total": f20["withheld_close_occasion_total"],
                          "before_wiring": f20["before_wiring"], "as_written_by_my_stream": True},
        "knowledge_receipt_sha256": KNOWLEDGE_RECEIPT_SHA,
        "knowledge_use": knowledge_use,
        "knowledge_use_receipt_hash": use_receipt["knowledge_use_receipt_hash"],
        "own_computation": {"pass_code": "principal_runs/frankie-a-memory-rt-33746436209-1/frankie_own_pass_20211003.py", "finalize_code": "principal_runs/frankie-a-memory-rt-33746436209-1/frankie_own_finalize_20211003.py",
                            "runner_calculation_result_read": False, "note": "every contract section was computed by the pass from the member rows' raw_actions, book_full FIFO state and clocks and from the legacy observable rows; the delivered lifecycle rows were used only for second-by-second and candidate-by-candidate reconciliation, written down agree/disagree"},
        "findings": findings,
    }
    out = RUN_DIR / "frankie_principal_findings.json"
    out.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for src in COPIES:
        shutil.copy2(src, RUN_DIR / Path(src).name)
    print("artifact written", out, "findings", len(findings), "knowledge_use_receipt_hash", use_receipt["knowledge_use_receipt_hash"])
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(RUN_DIR))
    sys.exit(main())
