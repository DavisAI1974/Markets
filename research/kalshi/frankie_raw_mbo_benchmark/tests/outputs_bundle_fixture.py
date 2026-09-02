"""A lawful output bundle with a configurable identity, for the staging and read-back tests.

`test_native_principal_outputs.complete_bundle` fixes the arm (A_CLEAN), the run id and the
receipt hashes it binds to. The staging gate has to be exercised on the arm every spawn now
targets (A_MEMORY, D86) and bound to the delivery and knowledge receipts a specific artifact
cites, so this builds the same lawful two-cutoff bundle over the same REAL member frames and
parameterises only the identity. Every per-ledger body comes from the outputs persona's own
builders, imported and not restated: the ledger shapes are theirs to define.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from research.kalshi.frankie_raw_mbo_benchmark import native_principal_outputs as outputs
from research.kalshi.frankie_raw_mbo_benchmark.tests import test_native_principal_outputs as fx


def build_bundle(
    *,
    delivery_receipt_sha256: str,
    knowledge_receipt_sha256: str,
    arm: str = "A_MEMORY",
    role: str = "REAL_TIME_FRANKIE",
    run_id: str = "run-readback-0001",
    registry: dict[str, Any] | None = None,
    contract_text: str | None = None,
) -> outputs.OutputBundle:
    """Every required ledger, two cutoffs, bound to the receipts given."""
    registry = registry or fx.registry_today()
    contract_text = contract_text or fx.contract_today()
    frames = fx.real_frames()
    first, second = frames[-2], frames[-1]
    c1, c2 = first["ts_recv_ns"], second["ts_recv_ns"]
    bundle = outputs.OutputBundle(
        run_id=run_id, arm=arm, role=role, registry=registry, contract_text=contract_text,
        knowledge_receipt_sha256=knowledge_receipt_sha256,
        delivery_receipt_sha256=delivery_receipt_sha256,
    )
    invariants = dict(fx.run_hash_body("START"))
    invariants.pop("phase")
    invariants.pop("state_sha256")
    invariants["contract_sha256"] = bundle.contract_sha256
    invariants["run_id"] = bundle.run_id
    hashes = bundle.ledger("output_source_state_manifest_code_model_run_hashes")
    hashes.append(c1, {"phase": "START", "state_sha256": fx.sha_of("state-0"), **invariants})

    receipts = bundle.ledger("output_knowledge_retrieval_receipts")
    receipts.append(c1, fx.knowledge_receipt_body())
    receipts.append(
        c1,
        fx.knowledge_receipt_body(
            receipt_id="kr-0002", layer_id="native_calculation_contract", sha256=bundle.contract_sha256
        ),
    )

    invocations = bundle.ledger("output_provider_invocation_response_receipts")
    invocations.append(c1, fx.invocation_body(0))
    invocations.append(c2, fx.invocation_body(1))

    state = bundle.ledger("output_state_and_state_delta_movie")
    state.append(c1, fx.state_frame(first, cutoff=c1, previous_cutoff=None))
    carried = {
        "spread": {
            "status": "PAST_CARRY", "value": first["book"]["spread"],
            "source_recv_ns": c1, "age": fx.reading(c2 - c1),
        },
        "dipole": {"status": "MISSING"},
        "signed_flow": {"status": "OBSERVED", "value": -12},
    }
    state.append(c2, fx.state_frame(second, cutoff=c2, previous_cutoff=c1, channels=carried))

    reasoning = bundle.ledger("output_frankie_reasoning_movie")
    reasoning.append(c1, fx.reasoning_body(role=role, knowledge_retrievals=["kr-0001", "kr-0002"]))
    reasoning.append(c2, fx.reasoning_body(role=role, helper_invocations=[fx.helper()]))

    probability = bundle.ledger("output_probability_movie")
    probability.append(c1, fx.probability_body(evaluation=fx.reading(c1)))
    locked = probability.append(
        c2,
        fx.probability_body(
            snapshot_id="snap-1", evaluation=fx.reading(c2), lock_state="FIRST_LOCK",
            probabilities={"PERSIST": 0.7, "COLLAPSE": 0.3},
        ),
    )

    bundle.ledger("output_candidate_discoveries").append(
        c1,
        fx.candidate_body(
            first_lawful_availability_ns=c1, recognition={"label": "T0", "lead": fx.reading(0)}
        ),
    )
    locks = bundle.ledger("output_first_locks_and_no_locks")
    locks.append(c1, fx.lock_body())
    first_lock = fx.lock_body(
        lock_state="FIRST_LOCK", probability_entry_hash=locked["entry_hash"], lock_at=fx.reading(c2)
    )
    first_lock.pop("reason")
    locks.append(c2, first_lock)

    bundle.ledger("output_negative_sparse_inconclusive_ledger").append(c2, fx.negative_body())
    bundle.ledger(
        "output_answer_wall_access_receipts",
        empty_reason="no answer-wall access was made; A scope is blind by construction",
    )

    for index, section in enumerate(bundle.contract_sections):
        ledger = bundle.ledger(f"contract_section_{section}")
        if index == 0:
            ledger.append(
                c1,
                fx.section_body(
                    section, cutoff=c1, member_group_indices=[], averages=[], result="NULL_RESULT",
                    population={"denominator": 0, "description": "no completed second before the first cutoff"},
                ),
            )
        ledger.append(c2, fx.section_body(section, cutoff=c2))

    raw = bundle.ledger("raw_mbo_classification")
    for name in ("order_id", "price_raw", "size", "flags", "ts_event_ns", "ts_recv_ns", "book", "book_full", "activity_full", "clocks"):
        raw.append(c2, fx.raw_mbo_body(field_or_group=name))
    bundle.ledger("knowledge_verification").append(
        c2,
        fx.verification_body(
            knowledge_receipt_sha256=knowledge_receipt_sha256,
            evidence={"member_group_indices": [1, 2], "cutoff_recv_ns": c2},
        ),
    )
    hashes.append(c2, {"phase": "END", "state_sha256": fx.sha_of("state-2"), **invariants})
    return bundle


def write_bundle(bundle: outputs.OutputBundle, out_dir: Path) -> dict[str, Any]:
    """Write the bundle under `out_dir/` (ledgers/ + RECEIPT.json) and return its receipt."""
    return outputs.write_bundle(bundle, out_dir)
