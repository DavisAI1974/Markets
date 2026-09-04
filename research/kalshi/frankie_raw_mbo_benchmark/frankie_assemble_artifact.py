"""Assemble the committed principal findings artifact from the pass's receipts and the
principal's authored findings, and stage the run directory under principal_runs/<run_id>/.

Everything bound by hash comes from a file the pass or the delivery wrote; the only hand-authored
input is the findings list. The artifact carries `knowledge_use` exactly as the pass wrote it
from what it loaded (the staging read gate binds it to the bundle bytes inside the prompt).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent
SCHEMA = "FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_FINDINGS_V1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--run-dir", required=True, help="the pass out-dir (ledgers/, RECEIPT.json, stream_receipt.json, knowledge_use.json, tallies.json)")
    p.add_argument("--findings", required=True, help="the principal's authored findings JSON: {findings: [...], summary: {...}}")
    p.add_argument("--cutoffs", required=True)
    p.add_argument("--result", required=True, help="calculation_result.json, read for result_hash and identity only")
    p.add_argument("--delivery-receipt", required=True)
    p.add_argument("--knowledge-dir", required=True, help="KNOWLEDGE_BUNDLE.md / KNOWLEDGE_RECEIPT.json / KNOWLEDGE_PRECALL_RECEIPT.json")
    p.add_argument("--prompt", required=True)
    p.add_argument("--principal", required=True)
    p.add_argument("--dest", default=None, help="principal_runs/<run_id>/ (default: derived from the run id)")
    a = p.parse_args(argv)
    run = Path(a.run_dir)
    cut = json.loads(Path(a.cutoffs).read_text())
    res = json.loads(Path(a.result).read_text())
    ident = res["layers"]["identity_receipt"]
    delivery = json.loads(Path(a.delivery_receipt).read_text())
    stream = json.loads((run / "stream_receipt.json").read_text())
    outputs = json.loads((run / "RECEIPT.json").read_text())
    knowledge_use = json.loads((run / "knowledge_use.json").read_text())
    authored = json.loads(Path(a.findings).read_text())
    run_id = cut["run_id"]
    dest = Path(a.dest) if a.dest else PKG / "principal_runs" / run_id
    dest.mkdir(parents=True, exist_ok=True)
    artifact = {
        "schema": SCHEMA,
        "principal": a.principal,
        "arm": cut["arm"],
        "role": "REAL_TIME_FRANKIE",
        "evidence_result_hash": res["result_hash"],
        "controller_only": False,
        "actual_principal_invocation": True,
        "invocation_mechanism": "AGENT_SESSION",
        "evidence_read": {"exact_member_ledger": "READ", "exact_lifecycle_and_runway_ledger": "READ", "legacy_observable_rows": "READ"},
        "delivery_receipt_sha256": delivery["receipt_sha256"],
        "stream_receipt_sha256": stream["receipt_sha256"],
        "outputs_receipt_sha256": outputs["receipt_sha256"],
        "knowledge_receipt_sha256": knowledge_use["knowledge_receipt_sha256"],
        "knowledge_use": knowledge_use,
        "run_id": run_id,
        "source_day": cut["invocation_cutoffs"][0]["source_day"],
        "mission_sha256": ident["mission_sha256"],
        "calculation_contract_sha256": ident["calculation_contract_sha256"],
        "causal_clock": "ts_recv_ns",
        "continuity_segment": cut["invocation_cutoffs"][0]["continuity_segment"],
        "falsifier_f20": stream.get("falsifier_f20"),
        "stream_complete": stream.get("complete"),
        "groups_delivered": stream.get("groups_delivered"),
        "summary": authored.get("summary", {}),
        "findings": authored["findings"],
    }
    (dest / "frankie_principal_findings.json").write_text(json.dumps(artifact, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    # the run directory: everything the read-back and the next session need, repo-relative
    shutil.copy(a.prompt, dest / "FRANKIE_SPAWN_PROMPT.md")
    for name in ("KNOWLEDGE_BUNDLE.md", "KNOWLEDGE_RECEIPT.json", "KNOWLEDGE_PRECALL_RECEIPT.json"):
        shutil.copy(Path(a.knowledge_dir) / name, dest / name)
    shutil.copy(a.delivery_receipt, dest / "delivery_receipt.json")
    shutil.copy(run / "stream_receipt.json", dest / "stream_receipt.json")
    shutil.copy(run / "tallies.json", dest / "tallies.json")
    shutil.copy(a.cutoffs, dest / "cutoffs.json")
    out = dest / "principal_outputs"
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(run / "ledgers", out / "ledgers")
    shutil.copy(run / "RECEIPT.json", out / "RECEIPT.json")
    print(json.dumps({"artifact": str(dest / "frankie_principal_findings.json"), "artifact_sha256": sha(dest / "frankie_principal_findings.json"),
                      "findings": len(artifact["findings"]), "f20": (artifact["falsifier_f20"] or {}).get("verdict"), "outputs_dir": str(out)}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
