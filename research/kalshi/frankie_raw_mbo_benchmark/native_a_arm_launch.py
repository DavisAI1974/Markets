"""The A-arm launch path: gates, traversal, checkpoints, artifacts. One entrypoint.

**Why this module exists.** Everything it wires was already built and none of it was on a
path that executes. `corrected_a_arm_execution_gate_20260828` was referenced by its own test
and nothing else - an unreferenced gate is not a gate. `periodic_checkpointer` was imported
by `native_replay_driver`, and no workflow dispatched the driver, so a save point could not
be written by anything. And both A-arm launch workflows fetched the roster, sealed a packet
and stopped: they reported `RUNNING_PRE_CALL` at 0 records because no compute ran at all.

So the gap was never a missing capability, it was a missing CALL SITE - the same shape as
the four group adapters, which were built, tested and fed by nothing. This module is the
call site.

**The order is the point, and it fails closed at each step.**

1. **Registry identity.** `validate_registry` proves the exact layer-identity set, the policy
   counts, the arm counts and the sealed set. Drift stops the run here.
2. **Pre-call layer receipt.** Every registered layer is enumerated with the status its
   policy demands and a real evidence hash. A run that cannot state what Frankie will be
   shown does not proceed to showing it.
3. **RT surface inventory.** The execution gate re-checks the same surfaces in its own
   vocabulary and, crucially, re-proves the Step-1/reveal wall is sealed. Two independent
   objects over one registry: a field-level check cannot catch a wrong-but-well-formed
   input, and only comparison against a second source settles it.
4. **The traversal**, with the checkpointer on it, so an out-of-memory death costs one save
   point rather than the whole run (D58 makes this a precondition of the box sizing).
5. **`finalize`**, which runs the calculation contract's eight section 6 acceptance gates
   and refuses partial promotion.

**Evidence hashes are computed, never asserted.** A layer's evidence receipt is a hash over
its declared source paths AND their actual bytes, so a receipt cannot be produced for a file
that is not there. Two `external:` paths - the A-memory prior package and its proof - carry
no repository bytes and resolve to the identities the mission pins; that substitution is
explicit here rather than hidden behind a default.

**This module produces EVIDENCE, never findings.** It never calls a model. At a lawful
cutoff the traversal stages a spawn request and moves on, per the corrected procedure: Sol
runs as an agent session over committed files, and `attach_principal_findings` is the only
route into the findings layer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from research.kalshi.frankie_raw_mbo_benchmark import native_ingestion_layer_registry as registry_gate
from research.kalshi.frankie_raw_mbo_benchmark import (
    corrected_a_arm_execution_gate_20260828 as execution_gate,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_calculation_runner import (
    NativeCalculationRun,
    RunIdentity,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_replay_driver import (
    ExchangeSessionRule,
    NativeReplayDriver,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_staging import SpawnStager
from research.kalshi.frankie_raw_mbo_benchmark.periodic_checkpointer import PeriodicCheckpointer

REPO_ROOT = Path(__file__).resolve().parents[3]

MISSION_PATH = (
    "research/kalshi/agents/frankie_native_raw_mbo_oct45_realtime_mission_20260828.md"
)
CONTRACT_PATH = (
    "research/kalshi/agents/frankie_native_raw_mbo_calculation_contract_20260828.md"
)
KNOWLEDGE_MANIFEST_PATH = (
    "research/kalshi/agents/frankie_native_raw_mbo_knowledge/KNOWLEDGE_MANIFEST_20260828.json"
)

EXTERNAL_SOURCE_IDENTITIES = {
    # The A-memory prior package and its proof receipt are not repository bytes; the mission
    # pins both identities, and section 9 of the prelaunch state says do not re-derive them.
    # Named here so the substitution is visible rather than being a silent fallback for any
    # path that happens to be absent - an absent file is otherwise an error, and stays one.
    "external:a_memory_prior_lessons_package": (
        "b487acfbbea8ac8a82f42ceb555e8334057e4004740af91b9127cd2ba71e1cf8"
    ),
    "external:a_memory_prior_lessons_package_proof": (
        "d54c61915c0d85c8b2630eb79d5e1b8911481c80883c56d75ba815fcfab20c05"
    ),
}

SEALED_POLICY = "SEALED_FOR_A_SCOPE"
SHADOW_POLICY = "PROVISIONAL_SHADOW"
STATIC_POLICIES = frozenset({"STATIC_REQUIRED_INPUT", "ARM_REQUIRED_INPUT"})
STREAM_POLICY = "CAUSAL_STREAM_REQUIRED"


class LaunchError(RuntimeError):
    """The launch path refused to proceed. Never downgraded to a warning."""


# --------------------------------------------------------------------------------------
# Evidence identity
# --------------------------------------------------------------------------------------
def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def evidence_receipt_sha256(source_paths: Sequence[str], *, repo_root: Path) -> str:
    """One hash over a layer's declared paths AND their bytes.

    The paths are inside the hash, not only the contents: two layers serving identical bytes
    from different declarations are different evidence, and a receipt that could not tell
    them apart would let a source be swapped without the hash moving.
    """
    parts: list[str] = []
    for declared in sorted(source_paths):
        pinned = EXTERNAL_SOURCE_IDENTITIES.get(declared)
        if pinned is not None:
            parts.append(f"{declared}\x1f{pinned}")
            continue
        path = repo_root / declared
        if not path.is_file():
            raise LaunchError(
                f"evidence source is missing and is not a pinned external identity: {declared}"
            )
        parts.append(f"{declared}\x1f{file_sha256(path)}")
    return hashlib.sha256("\x1e".join(parts).encode("utf-8")).hexdigest()


def _layer_evidence(registry: Mapping[str, Any], *, repo_root: Path) -> dict[str, str]:
    return {
        entry["layer_id"]: evidence_receipt_sha256(entry["source_paths"], repo_root=repo_root)
        for group in registry["groups"]
        for entry in group["entries"]
    }


# --------------------------------------------------------------------------------------
# Gate 2: the pre-call layer receipt
# --------------------------------------------------------------------------------------
def build_pre_call_receipt(
    *, arm: str, run_id: str, registry: Mapping[str, Any], repo_root: Path = REPO_ROOT
) -> dict[str, Any]:
    """Enumerate every registered layer with the status its own policy demands.

    The statuses are read off the policy rather than chosen, so this cannot report a layer
    ready that the registry says is sealed. `validate_pre_call_receipt` then re-derives the
    same expectations independently and rejects any disagreement.
    """
    evidence = _layer_evidence(registry, repo_root=repo_root)
    rows: list[dict[str, Any]] = []
    for group in registry["groups"]:
        policy = group["policy"]
        for entry in group["entries"]:
            layer_id = entry["layer_id"]
            if arm not in group["arms"]:
                rows.append({
                    "layer_id": layer_id, "status": "NOT_APPLICABLE",
                    "model_visible": False, "evidence_receipt_sha256": None,
                })
                continue
            if policy in STATIC_POLICIES:
                status, visible = "AVAILABLE", True
            elif policy == STREAM_POLICY:
                status, visible = "READY_CAUSAL_STREAM", False
            elif policy == SEALED_POLICY:
                status, visible = "SEALED", False
            elif policy == SHADOW_POLICY:
                # D5 keeps discovery out of this run and nothing opts the shadow layers in,
                # so they are DISABLED rather than READY. Reporting READY would be a claim
                # about a component that is not going to run.
                status, visible = "SHADOW_DISABLED", False
            else:
                status, visible = "PENDING", False
            rows.append({
                "layer_id": layer_id,
                "status": status,
                "model_visible": visible,
                "evidence_receipt_sha256": (
                    None if status == "PENDING" else evidence[layer_id]
                ),
            })
    receipt = {
        "schema": registry_gate.PRE_CALL_RECEIPT_SCHEMA,
        "stage": "PRE_CALL",
        "run_id": run_id,
        "arm": arm,
        "registry_sha256": registry["registry_sha256"],
        "layers": rows,
        "receipt_sha256": "",
    }
    receipt["receipt_sha256"] = registry_gate.canonical_hash(receipt, omit="receipt_sha256")
    return receipt


# --------------------------------------------------------------------------------------
# Gate 3: the RT surface inventory
# --------------------------------------------------------------------------------------
def build_rt_surface_inventory(
    *, arm: str, registry: Mapping[str, Any], repo_root: Path = REPO_ROOT
) -> dict[str, Any]:
    """The same registry in the execution gate's vocabulary, with the answer wall sealed.

    Deliberately a SECOND object over one registry rather than a reshaping of the first. The
    two gates disagree on purpose about what `model_visible` means at their own stage, and
    the sealed surfaces must come out SEALED in both - which is the check worth having, since
    a wrong-but-well-formed inventory is exactly what a field-level check cannot catch.
    """
    evidence = _layer_evidence(registry, repo_root=repo_root)
    rows: list[dict[str, Any]] = []
    for group in registry["groups"]:
        policy = group["policy"]
        for entry in group["entries"]:
            layer_id = entry["layer_id"]
            if layer_id not in execution_gate.SURFACE_IDS:
                # The eight arm/control bindings - the mission, the contract, the knowledge
                # manifest, the selected profile and the two arms' capsules - are not RT
                # SURFACES. They are bound by `RunIdentity`'s hashes and by the pre-call
                # receipt instead, and the gate's own SURFACE_IDS is the authority on which
                # ids those are. Filtering against it rather than against a group-name list
                # here means this cannot drift away from the gate.
                continue
            if policy == SEALED_POLICY:
                rows.append({
                    "surface_id": layer_id, "route": "SEALED", "availability": "SEALED",
                    "required_for_principal": False, "model_visible": False,
                    "evidence_receipt_sha256": None,
                })
                continue
            required = policy in STATIC_POLICIES or policy == STREAM_POLICY
            if required and arm not in group["arms"]:
                # An arm overlay that does not apply to this arm is not required OF it.
                required = False
            rows.append({
                "surface_id": layer_id,
                "route": "DIRECT" if required else "TOOL_ACCESSIBLE",
                "availability": "AVAILABLE" if required else "UNKNOWN",
                "required_for_principal": required,
                "model_visible": required,
                "evidence_receipt_sha256": evidence[layer_id] if required else None,
            })
    inventory = {
        "schema": execution_gate.SURFACE_SCHEMA,
        "arm": arm,
        "role": "REAL_TIME_FRANKIE",
        "surfaces": rows,
        "inventory_hash": "",
    }
    inventory["inventory_hash"] = execution_gate.canonical_hash(
        inventory, omit="inventory_hash"
    )
    return inventory


def run_pre_traversal_gates(
    *, arm: str, run_id: str, repo_root: Path = REPO_ROOT
) -> dict[str, Any]:
    """Steps 1-3. Returns the three gate receipts, or raises before anything runs."""
    registry = registry_gate.load_registry()
    registry_receipt = registry_gate.validate_registry(registry)
    pre_call = build_pre_call_receipt(
        arm=arm, run_id=run_id, registry=registry, repo_root=repo_root
    )
    pre_call_receipt = registry_gate.validate_pre_call_receipt(pre_call, registry=registry)
    inventory = build_rt_surface_inventory(arm=arm, registry=registry, repo_root=repo_root)
    surface_receipt = execution_gate.validate_rt_surface_inventory(inventory, arm=arm)
    if not surface_receipt["step1_sealed"]:
        raise LaunchError("the Step-1 answer wall is not sealed; the run does not start")
    return {
        "registry_gate": registry_receipt,
        "pre_call_layer_gate": pre_call_receipt,
        "rt_surface_gate": surface_receipt,
        "pre_call_receipt": pre_call,
        "rt_surface_inventory": inventory,
    }


# --------------------------------------------------------------------------------------
# The record source
# --------------------------------------------------------------------------------------
NATIVE_RECORD_FIELDS = (
    "instrument_id", "publisher_id", "channel_id", "order_id", "action", "side",
    "price", "size", "flags", "sequence", "ts_event", "ts_recv", "ts_in_delta",
)


def native_records(
    paths: Sequence[Path], *, limit: int | None = None
) -> Iterator[dict[str, Any]]:
    """Yield raw MBO records in file order, each naming the object and digest it came from.

    Yields MAPPINGS, not Databento record objects: the driver reads `source_dbn_object` off
    every record and refuses one that does not name its source, which a `MboMsg` cannot
    answer. Nothing is filtered but non-MBO message types, which carry no order event.
    """
    try:
        import databento as db
    except ImportError as exc:  # pragma: no cover - environment, not logic
        raise LaunchError("the databento package is required to read the native roster") from exc

    emitted = 0
    for path in paths:
        digest = file_sha256(path)
        store = db.DBNStore.from_file(str(path))
        symbols = None
        try:
            symbols = db.common.symbology.InstrumentMap()
            symbols.insert_metadata(store.metadata)
        except Exception:  # pragma: no cover - symbology is best effort, never load bearing
            symbols = None
        for record in store:
            if type(record).__name__ not in {"MboMsg", "MBOMsg"}:
                continue
            row = {field: getattr(record, field, None) for field in NATIVE_RECORD_FIELDS}
            row["source_dbn_object"] = str(path)
            row["source_dbn_sha256"] = digest
            row["raw_symbol"] = _symbol(symbols, row["instrument_id"], row["ts_recv"])
            yield row
            emitted += 1
            if limit is not None and emitted >= limit:
                return


def _symbol(symbols: Any, instrument_id: Any, ts_recv: Any) -> str | None:
    if symbols is None or instrument_id is None:
        return None
    try:
        return symbols.resolve(int(instrument_id), int(ts_recv))
    except Exception:  # pragma: no cover - an unresolved symbol is not a run failure
        return None


# --------------------------------------------------------------------------------------
# The launch
# --------------------------------------------------------------------------------------
def launch(
    *,
    arm: str,
    run_id: str,
    sources: Sequence[Path],
    source_manifest: Mapping[str, Any],
    out_dir: Path,
    code_commit: str,
    limit_records: int | None = None,
    checkpoint_every_records: int = 250_000,
    cadence_groups: int = 250_000,
    repo_root: Path = REPO_ROOT,
    records: Any = None,
) -> dict[str, Any]:
    """Gate, traverse, checkpoint, finalize. Returns the layered result plus the receipts.

    `records` overrides the DBN reader with an explicit iterable of native record mappings.
    It exists so the launch PATH - the three gates, the traversal, the checkpointer, the
    eight section 6 acceptance gates - can be exercised end to end where the roster is not
    reachable, which is every interactive session: the AWS credentials are GitHub-secret
    scoped, so only a workflow can read the real objects. What that leaves uncovered is
    `native_records` itself, the DBN decode. That is covered by the workflow's bounded slice
    and by nothing here, and it is stated rather than papered over.
    """
    gates = run_pre_traversal_gates(arm=arm, run_id=run_id, repo_root=repo_root)

    knowledge = json.loads((repo_root / KNOWLEDGE_MANIFEST_PATH).read_text(encoding="utf-8"))
    total_records = int(source_manifest["total_mbo_records"])
    identity = RunIdentity(
        run_id=run_id,
        arm=arm,
        mission_sha256=file_sha256(repo_root / MISSION_PATH),
        calculation_contract_sha256=file_sha256(repo_root / CONTRACT_PATH),
        knowledge_manifest_hash=knowledge["manifest_hash"],
        source_manifest_hash=source_manifest["manifest_hash"],
        # On a bounded slice the identity states the SLICE's record count, not the roster's.
        # Claiming the full roster while traversing part of it would put the coverage gate in
        # the position of comparing a real count against an aspiration.
        total_mbo_records=min(total_records, limit_records or total_records),
        code_commit=code_commit,
    )
    run = NativeCalculationRun(
        identity,
        replenishment_horizon_ns=60_000_000_000,
        response_horizons_ns=(1_000_000_000, 10_000_000_000, 60_000_000_000),
        response_horizon_version="a-arm-h1",
        response_value_names=("price_response",),
    )
    checkpoint_dir = out_dir / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpointer = PeriodicCheckpointer(
        run_id=run_id,
        controller="A_CHATGPT",
        memory_mode="CLEAN" if arm == "A_CLEAN" else "MEMORY",
        source_manifest_hash=source_manifest["manifest_hash"],
        total_mbo_records=identity.total_mbo_records,
        checkpoint_dir=checkpoint_dir,
        phase="RT_NATIVE_TRAVERSAL",
        every_records=checkpoint_every_records,
    )
    # What the spawn is staged AGAINST, content-addressed. `stage_spawn_request` refuses a
    # request that cannot name its evidence, and `load_principal_artifact` checks the
    # artifact came back against the same hash - so an artifact produced against a different
    # evidence surface is rejected instead of being read as findings about this one.
    evidence = {
        "run_id": run_id,
        "arm": arm,
        "mission_sha256": identity.mission_sha256,
        "calculation_contract_sha256": identity.calculation_contract_sha256,
        "knowledge_manifest_hash": identity.knowledge_manifest_hash,
        "source_manifest_hash": source_manifest["manifest_hash"],
        "registry_sha256": gates["pre_call_receipt"]["registry_sha256"],
        "pre_call_receipt_sha256": gates["pre_call_receipt"]["receipt_sha256"],
        "rt_surface_inventory_hash": gates["rt_surface_inventory"]["inventory_hash"],
    }
    evidence["result_hash"] = hashlib.sha256(
        json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    stager = SpawnStager(
        out_dir=out_dir / "spawn_requests",
        arm=arm,
        role="REAL_TIME_FRANKIE",
        evidence=evidence,
    )
    driver = NativeReplayDriver(
        identity=identity,
        session_rule=ExchangeSessionRule(),
        cadence=_GroupCadence(cadence_groups),
        run=run,
        checkpointer=checkpointer,
        stage_spawn=stager.stage,
    )
    # Sequence 0 before any interval save. The checkpointer REFUSES an interval save without
    # it rather than quietly writing an unanchored chain, which is how the missing call
    # surfaced the moment the launch path first ran - a defect that could not appear while
    # nothing dispatched the driver.
    checkpointer.seal_start(driver.adapter)
    stream = native_records(sources, limit=limit_records) if records is None else records
    driver.consume(stream)
    result = driver.finalize()
    result["gates"] = {
        key: gates[key]
        for key in ("registry_gate", "pre_call_layer_gate", "rt_surface_gate")
    }
    result["evidence_identity"] = dict(evidence)
    result["slice"] = {
        "record_source": "NATIVE_DBN_ROSTER" if records is None else "SUPPLIED_ITERABLE",
        "records_requested": limit_records,
        "roster_total_mbo_records": total_records,
        "is_bounded_slice": limit_records is not None,
        "sources": [str(path) for path in sources],
    }
    return result


class _GroupCadence:
    """Stage a spawn request every N groups. Supplied, never inferred inside the traversal."""

    def __init__(self, every_groups: int) -> None:
        if every_groups <= 0:
            raise LaunchError("cadence must be a positive number of groups")
        self.every_groups = every_groups

    def should_invoke(self, *, group_index: int, groups_since_last: int, **_: Any) -> bool:
        return group_index > 0 and groups_since_last >= self.every_groups


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--arm", required=True, choices=sorted(execution_gate.ALLOWED_ARMS))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--source", type=Path, action="append", default=[], required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--limit-records", type=int, default=None,
        help="bound the traversal to the first N native records; this is the dry-run slice",
    )
    parser.add_argument("--checkpoint-every-records", type=int, default=250_000)
    parser.add_argument("--cadence-groups", type=int, default=250_000)
    parser.add_argument(
        "--gates-only", action="store_true",
        help="run the three pre-traversal gates and stop; reads no market data at all",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.gates_only:
        gates = run_pre_traversal_gates(arm=args.arm, run_id=args.run_id)
        (args.out_dir / "pre_traversal_gates.json").write_text(
            json.dumps(gates, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps({
            "status": "PRE_TRAVERSAL_GATES_PASSED",
            "arm": args.arm,
            "registered_layer_count": gates["pre_call_layer_gate"]["registered_layer_count"],
            "required_input_count": gates["pre_call_layer_gate"]["required_input_count"],
            "answer_wall_sealed": gates["pre_call_layer_gate"]["answer_wall_sealed"],
            "surface_count": gates["rt_surface_gate"]["surface_count"],
        }, sort_keys=True))
        return 0

    manifest = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    result = launch(
        arm=args.arm,
        run_id=args.run_id,
        sources=list(args.source),
        source_manifest=manifest,
        out_dir=args.out_dir,
        code_commit=args.code_commit,
        limit_records=args.limit_records,
        checkpoint_every_records=args.checkpoint_every_records,
        cadence_groups=args.cadence_groups,
    )
    (args.out_dir / "calculation_result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    traversal = result["traversal"]
    print(json.dumps({
        "verdict": result["verdict"],
        "failed_gates": result["failed_gates"],
        "completion_status": result.get("completion_status"),
        "groups_seen": traversal["groups_seen"],
        "records_seen": traversal["records_seen"],
        "save_points": traversal["save_points"],
        "sections_fed": traversal["sections_fed"],
    }, sort_keys=True))
    # A non-ACCEPTED verdict is a failed run, and the exit code has to say so or a workflow
    # step will go green over a refused calculation.
    return 0 if result["verdict"] == "ACCEPTED" else 1


if __name__ == "__main__":
    sys.exit(main())
