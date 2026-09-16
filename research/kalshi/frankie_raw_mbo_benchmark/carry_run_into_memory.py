#!/usr/bin/env python3
"""Carry a committed Frankie run into his memory, gated, rendered, registered and verified - one command.

Greg, 2026-09-16: "there was supposed to be a workflow that did all that and updated him. we have
to make all of that automated because we won't be able to watch for jsons 24/7 for him." The
workflow (`.github/workflows/a_memory_findings_carry_20260903.yml`) ran four tools in order and
trusted whatever landed under `principal_runs/`; it never gated the output bundle a run cited,
never printed his two documents, and never left a receipt saying what was carried. This is the
tool that pipeline calls instead, per run, idempotent, fail-closed:

1. GATE. Load the run's output bundle (`principal_outputs/`): every chain re-verified, the
   receipt self-hash re-checked, `missing_ledger_ids` empty, and its `receipt_sha256` equal to
   the `outputs_receipt_sha256` the run's artifact cites. When the bundle was written against
   the registry and contract now on disk it is fully re-validated; a bundle filed under an
   earlier registry or contract cannot be (its pinned hashes differ by construction), so the
   receipt says FILED_UNDER_PRIOR_REGISTRY_OR_CONTRACT with both hashes, never "passed".
2. DOCUMENTS. Render the two run documents (what he learned, in his own words) from the
   bundle into the run directory, where the seed carries them. A run filed before the
   two-document contract has neither ledger; that is recorded as NOT_FILED, not invented.
3. CARRY. `build_a_memory_seed --write`, `register_a_memory_knowledge --write`,
   `rebind_registry_knowledge_layers --write`, `refresh_native_frankie_knowledge --write`,
   then every one of them `--check`. Any refusal stops the carry with its reason.
4. RECEIPT. `principal_runs/carry_receipts/<run_id>.json`: the gate verdict, the documents,
   and the seed, spec, registry and manifest hashes the carry left behind. Deterministic, so
   `--check` can recompute it and compare.

    python3 -m research.kalshi.frankie_raw_mbo_benchmark.carry_run_into_memory --write --run-id <run_id>
    python3 -m research.kalshi.frankie_raw_mbo_benchmark.carry_run_into_memory --check --all

Nothing here runs Frankie; a run that is not committed under `principal_runs/` does not exist
to this tool, and the workflow that invokes it waits on Greg's go.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from research.kalshi.frankie_raw_mbo_benchmark import native_principal_outputs as outputs  # noqa: E402
from research.kalshi.frankie_raw_mbo_benchmark import render_frankie_run_documents as documents  # noqa: E402
from research.kalshi.frankie_raw_mbo_benchmark.build_a_memory_seed import (  # noqa: E402
    FINDING_ARTIFACT_NAME,
    MISSION_PATH,
    PRINCIPAL_RUNS_DIR,
    SEED_PATH,
    SeedBuildError,
    own_a_memory_runs,
)
from research.kalshi.frankie_raw_mbo_benchmark.build_a_memory_seed import main as seed_main  # noqa: E402
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (  # noqa: E402
    REGISTRY_PATH,
    canonical_hash,
    load_registry,
)
from research.kalshi.frankie_raw_mbo_benchmark.rebind_registry_knowledge_layers import main as rebind_main  # noqa: E402
from research.kalshi.frankie_raw_mbo_benchmark.refresh_native_frankie_knowledge import (  # noqa: E402
    KnowledgeRefreshError,
    refresh,
)
from research.kalshi.frankie_raw_mbo_benchmark.register_a_memory_knowledge import SPEC_PATH  # noqa: E402
from research.kalshi.frankie_raw_mbo_benchmark.register_a_memory_knowledge import main as register_main  # noqa: E402

CARRY_RECEIPT_SCHEMA = "FRANKIE_A_MEMORY_CARRY_RECEIPT_V1"
CARRY_RECEIPTS_DIR = PRINCIPAL_RUNS_DIR + "carry_receipts/"
OUTPUT_BUNDLE_DIRNAME = "principal_outputs"
MANIFEST_PATH = "research/kalshi/agents/frankie_native_raw_mbo_knowledge/KNOWLEDGE_MANIFEST_20260828.json"

GATE_FULLY_VALIDATED = "FULLY_VALIDATED_AGAINST_CURRENT_REGISTRY_AND_CONTRACT"
GATE_PRIOR = "RECEIPT_AND_CHAINS_VERIFIED_FILED_UNDER_PRIOR_REGISTRY_OR_CONTRACT"
DOCUMENTS_NOT_FILED = "NOT_FILED_RUN_PREDATES_THE_TWO_DOCUMENT_CONTRACT"


class CarryError(ValueError):
    """The run cannot be carried honestly; nothing is written."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path, what: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CarryError(f"{what} is not readable: {path.name} ({exc})") from exc


def run_directory(root: Path, run_id: str) -> str:
    """The committed run directory (repo-relative, trailing slash) for a run id, discovered."""
    for directory, found in own_a_memory_runs(root):
        if found == run_id:
            return directory
    raise CarryError(f"no committed A_MEMORY run {run_id!r} under {PRINCIPAL_RUNS_DIR}; a run that is not committed does not exist to the carry")


def gate_output_bundle(root: Path, directory: str) -> dict[str, Any]:
    """Step 1: the bundle the run cites, re-verified, and its standing against the current contract."""
    artifact = _read_json(root / directory / FINDING_ARTIFACT_NAME, "principal findings artifact")
    if not isinstance(artifact, Mapping):
        raise CarryError("principal findings artifact is not an object")
    cited = artifact.get("outputs_receipt_sha256")
    if not isinstance(cited, str) or not cited:
        raise CarryError(f"{directory}{FINDING_ARTIFACT_NAME} cites no outputs_receipt_sha256; a run without its outputs taught nothing and is not carried")
    outputs_dir = root / directory / OUTPUT_BUNDLE_DIRNAME
    try:
        bundle = outputs.load_bundle(outputs_dir)
    except outputs.PrincipalOutputError as exc:
        raise CarryError(f"{directory}{OUTPUT_BUNDLE_DIRNAME}: {exc}") from exc
    receipt = _read_json(outputs_dir / outputs.RECEIPT_FILENAME, "output bundle receipt")
    if receipt.get("receipt_sha256") != cited:
        raise CarryError(f"the artifact cites outputs receipt {cited} and the bundle on disk has receipt {receipt.get('receipt_sha256')}; the findings were filed beside a different set of outputs")
    if receipt.get("missing_ledger_ids"):
        raise CarryError(f"the run's own receipt lists missing ledgers {receipt['missing_ledger_ids']}; an incomplete bundle is not carried")
    for key in ("run_id", "arm", "delivery_receipt_sha256", "knowledge_receipt_sha256"):
        if bundle.get(key) != artifact.get(key):
            raise CarryError(f"bundle {key} {bundle.get(key)!r} is not the artifact's {artifact.get(key)!r}")
    registry = load_registry()
    contract_text = outputs.CONTRACT_PATH.read_text(encoding="utf-8")
    required_now = outputs.required_ledger_ids(registry, contract_text)
    filed_required = list(receipt.get("required_ledger_ids", []))
    current = {"registry_sha256": registry["registry_sha256"], "contract_sha256": outputs.contract_sha256_of(contract_text)}
    filed = {"registry_sha256": bundle.get("registry_sha256"), "contract_sha256": bundle.get("contract_sha256")}
    verdict: dict[str, Any] = {
        "outputs_receipt_sha256": cited,
        "ledgers": len(bundle.get("ledgers", {})),
        "required_ledger_ids_at_filing": filed_required,
        "required_set_delta_since_filing": {
            "added": [lid for lid in required_now if lid not in filed_required],
            "removed": [lid for lid in filed_required if lid not in required_now],
        },
        "filed_against": filed,
        "current": current,
    }
    # The required set is derived in code as well as from the contract text (the two run
    # documents were added on 2026-09-16 with no contract edit), so "same contract" means the
    # same pinned hashes AND the same required set; anything else is a prior contract.
    if filed == current and set(filed_required) == set(required_now):
        try:
            outputs.validate_output_bundle(
                bundle, registry=registry, contract_text=contract_text,
                knowledge_receipt_sha256=artifact.get("knowledge_receipt_sha256"),
                delivery_receipt_sha256=artifact.get("delivery_receipt_sha256"),
            )
        except outputs.PrincipalOutputError as exc:
            raise CarryError(f"the output bundle was refused by the validator: {exc}") from exc
        verdict["status"] = GATE_FULLY_VALIDATED
    else:
        verdict["status"] = GATE_PRIOR
    return verdict


def render_run_documents(root: Path, directory: str, *, write: bool) -> dict[str, Any]:
    """Step 2: the two documents, rendered from the bundle or recorded as not filed."""
    outputs_dir = root / directory / OUTPUT_BUNDLE_DIRNAME
    bundle = outputs.load_bundle(outputs_dir)
    ledgers = bundle.get("ledgers", {})
    present = [lid for lid in outputs.RUN_DOCUMENT_LEDGERS if lid in ledgers]
    if not present:
        return {"status": DOCUMENTS_NOT_FILED, "files": {}}
    if len(present) != len(outputs.RUN_DOCUMENT_LEDGERS):
        raise CarryError(f"the bundle carries {present} but not both run-document ledgers; one document without the other is refused")
    try:
        rendered = documents.render_documents(bundle)
    except documents.RenderError as exc:
        raise CarryError(str(exc)) from exc
    files: dict[str, Any] = {}
    for name, text in rendered.items():
        path = root / directory / name
        raw = text.encode("utf-8")
        if path.is_file() and path.read_bytes() == raw:
            state = "CURRENT"
        elif write:
            path.write_bytes(raw)
            state = "WRITTEN"
        else:
            state = "STALE"
        files[name] = {"state": state, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    return {"status": "RENDERED", "files": files}


def _tool(name: str, code: int) -> None:
    if code != 0:
        raise CarryError(f"{name} refused (exit {code}); see its message above")


def rebuild_memory(root: Path, *, write: bool) -> None:
    """Step 3: the four carry tools, write then check; every refusal stops the carry."""
    if root.resolve() != REPO.resolve():
        raise CarryError("the carry tools rebind and refresh the registry of their own checkout; --repo-root must be this checkout")
    root_arg = ["--repo-root", str(root)]
    if write:
        _tool("build_a_memory_seed --write", seed_main(["--write", *root_arg]))
        _tool("register_a_memory_knowledge --write", register_main(["--write", *root_arg]))
        _tool("rebind_registry_knowledge_layers --write", rebind_main(["--write"]))
        try:
            refresh(root / SPEC_PATH, root, write=True)
        except KnowledgeRefreshError as exc:
            raise CarryError(f"refresh_native_frankie_knowledge --write refused: {exc}") from exc
    _tool("build_a_memory_seed --check", seed_main(["--check", *root_arg]))
    _tool("register_a_memory_knowledge --check", register_main(["--check", *root_arg]))
    _tool("rebind_registry_knowledge_layers --check", rebind_main(["--check"]))
    try:
        refresh(root / SPEC_PATH, root, write=False)
    except KnowledgeRefreshError as exc:
        raise CarryError(f"refresh_native_frankie_knowledge --check refused: {exc}") from exc


def carry_receipt(root: Path, run_id: str, directory: str, gate: Mapping[str, Any], docs: Mapping[str, Any]) -> dict[str, Any]:
    """Step 4: what this carry left behind, by hash; deterministic so --check can recompute it."""
    receipt = {
        "schema": CARRY_RECEIPT_SCHEMA,
        "run_id": run_id,
        "run_directory": directory,
        "output_bundle_gate": dict(gate),
        "documents": dict(docs),
        "memory": {
            "seed": {"path": SEED_PATH, "sha256": _sha256(root / SEED_PATH)},
            "mission": {"path": MISSION_PATH, "sha256": _sha256(root / MISSION_PATH)},
            "knowledge_sources": {"path": SPEC_PATH, "sha256": _sha256(root / SPEC_PATH)},
            "knowledge_manifest": {"path": MANIFEST_PATH, "sha256": _sha256(root / MANIFEST_PATH)},
            "registry": {"path": str(Path(REGISTRY_PATH).resolve().relative_to(REPO.resolve()).as_posix()), "sha256": load_registry()["registry_sha256"]},
        },
    }
    receipt["receipt_sha256"] = canonical_hash(receipt, omit="receipt_sha256")
    return receipt


def _receipt_path(root: Path, run_id: str) -> Path:
    return root / CARRY_RECEIPTS_DIR / f"{run_id}.json"


def carry(root: Path | str, run_id: str, *, write: bool) -> dict[str, Any]:
    root = Path(root)
    directory = run_directory(root, run_id)
    gate = gate_output_bundle(root, directory)
    docs = render_run_documents(root, directory, write=write)
    stale_docs = [name for name, row in docs.get("files", {}).items() if row["state"] == "STALE"]
    if stale_docs and not write:
        raise CarryError(f"run documents {stale_docs} are stale on disk; run --write")
    rebuild_memory(root, write=write)
    receipt = carry_receipt(root, run_id, directory, gate, docs)
    path = _receipt_path(root, run_id)
    rendered = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(rendered)
    elif not path.is_file():
        raise CarryError(f"no carry receipt at {CARRY_RECEIPTS_DIR}{run_id}.json; this run was never carried - run --write")
    elif path.read_bytes() != rendered:
        raise CarryError(f"the carry receipt for {run_id} is not the one recomputed from disk; the memory moved since the run was carried - run --write")
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="carry the run(s): render, rebuild, verify, receipt")
    mode.add_argument("--check", action="store_true", help="exit 1 if any run is not carried exactly as its receipt says")
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--run-id", default=None, help="the run to carry, by its own run_id")
    which.add_argument("--all", action="store_true", help="every committed A_MEMORY run, in run-id order")
    parser.add_argument("--repo-root", default=str(REPO), help="the checkout (must be this one)")
    args = parser.parse_args(argv)
    root = Path(args.repo_root)
    try:
        run_ids = [run_id for _directory, run_id in own_a_memory_runs(root)] if args.all else [args.run_id]
        if not run_ids:
            raise CarryError(f"no committed A_MEMORY run under {PRINCIPAL_RUNS_DIR}")
        results = {run_id: carry(root, run_id, write=args.write) for run_id in run_ids}
    except (CarryError, SeedBuildError, outputs.PrincipalOutputError, OSError, ValueError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    for run_id, receipt in results.items():
        print(f"{'CARRIED' if args.write else 'PASS'}  {run_id}: gate {receipt['output_bundle_gate']['status']}, documents {receipt['documents']['status']}, receipt {receipt['receipt_sha256'][:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
