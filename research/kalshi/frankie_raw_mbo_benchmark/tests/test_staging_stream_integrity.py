"""Real admission checks with independently constructed synthetic receipt witnesses."""
import copy
import hashlib
import json
import pytest
from research.kalshi.frankie_raw_mbo_benchmark import native_staging as module
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import canonical_hash
from research.kalshi.frankie_raw_mbo_benchmark.native_causal_stream import STREAM_RECEIPT_SCHEMA
from research.kalshi.frankie_raw_mbo_benchmark.fetch_frankie_ledgers import RECEIPT_SCHEMA
from research.kalshi.frankie_raw_mbo_benchmark.tests.outputs_bundle_fixture import build_bundle, write_bundle


def receipt_pair():
    digest = hashlib.sha256(b'synthetic exact bytes').hexdigest()
    delivery = dict(schema=RECEIPT_SCHEMA, run_id='synthetic-run', ledgers={name: dict(status='VERIFIED', plain_bytes_expected=21, plain_bytes_observed=21, plain_sha256_expected=digest, plain_sha256_observed=digest) for name in module.EXACT_LEDGERS})
    delivery['receipt_sha256'] = canonical_hash(delivery, omit='receipt_sha256')
    stream = dict(schema=STREAM_RECEIPT_SCHEMA, run_id='synthetic-run', arm='A_MEMORY', complete=True, withheld_consumed=True)
    for name in ('member_ledger','lifecycle_ledger','legacy_ledger'):
        stream[name] = dict(observed_bytes=21, observed_sha256=digest)
    stream['receipt_sha256'] = canonical_hash(stream, omit='receipt_sha256')
    artifact = dict(schema=module.PRINCIPAL_FINDINGS_SCHEMA, principal='synthetic-agent', arm='A_MEMORY', role='REAL_TIME_FRANKIE', run_id='synthetic-run', evidence_result_hash='a'*64, controller_only=False, actual_principal_invocation=True, evidence_read={name:'READ' for name in module.EXACT_LEDGERS}, findings=[], delivery_receipt_sha256=delivery['receipt_sha256'], stream_receipt_sha256=stream['receipt_sha256'])
    return artifact, delivery, stream


def test_delivered_admission_requires_actual_complete_bound_receipts(tmp_path):
    artifact, delivery, stream = receipt_pair()
    bundle = write_bundle(build_bundle(delivery_receipt_sha256=delivery['receipt_sha256'], knowledge_receipt_sha256='e'*64), tmp_path/'outputs')
    artifact['outputs_receipt_sha256'] = bundle['receipt_sha256']
    path = tmp_path/'artifact.json'
    path.write_text(json.dumps(artifact))
    execution, _ = module.load_principal_artifact(path, expected_evidence_hash='a'*64, outputs_dir=tmp_path/'outputs', knowledge_receipt_sha256='e'*64, delivery_receipt=delivery, stream_receipt=stream, expected_run_id='synthetic-run', render_report=False)
    assert execution['stream_receipt_sha256'] == stream['receipt_sha256']
    with pytest.raises(module.StagingError):
        module.load_principal_artifact(path, expected_evidence_hash='a'*64, outputs_dir=tmp_path/'outputs', knowledge_receipt_sha256='e'*64, render_report=False)


@pytest.mark.parametrize('fault', ['partial','no_stream','no_delivery','unfinished','undrained','foreign_arm','foreign_run','changed_bytes','changed_digest','stale_hash'])
def test_admission_refuses_partial_unbound_or_changed_consumption(fault):
    artifact, delivery, stream = receipt_pair()
    if fault == 'partial': artifact['evidence_read'][module.EXACT_LEDGERS[0]] = 'PARTIAL'
    elif fault == 'no_stream': stream = None
    elif fault == 'no_delivery': delivery = None
    elif fault == 'unfinished': stream['complete'] = False
    elif fault == 'undrained': stream['withheld_consumed'] = False
    elif fault == 'foreign_arm': stream['arm'] = 'A_CLEAN'
    elif fault == 'foreign_run': stream['run_id'] = 'foreign'
    elif fault == 'changed_bytes': stream['legacy_ledger']['observed_bytes'] += 1
    elif fault == 'changed_digest': stream['lifecycle_ledger']['observed_sha256'] = 'f'*64
    elif fault == 'stale_hash': stream['run_id'] = 'tampered'
    if stream is not None and fault != 'stale_hash':
        stream['receipt_sha256'] = canonical_hash(stream, omit='receipt_sha256')
        artifact['stream_receipt_sha256'] = stream['receipt_sha256']
    with pytest.raises(module.StagingError):
        module._validate_consumption(artifact, delivery, stream, expected_run_id='synthetic-run')


def test_actual_causal_stream_receipt_binds_all_three_physical_files(tmp_path):
    from research.kalshi.frankie_raw_mbo_benchmark.tests.test_native_causal_stream import member_row, write_ledger, BASE
    from research.kalshi.frankie_raw_mbo_benchmark.native_causal_stream import CausalGroupStream
    paths = [write_ledger(tmp_path/'member.jsonl', [member_row(0,BASE)]), write_ledger(tmp_path/'lifecycle.jsonl', []), write_ledger(tmp_path/'legacy.jsonl', [])]
    stream = CausalGroupStream(*paths, run_id='synthetic-run', arm='A_MEMORY')
    list(stream.iterate())
    stream.drain_withheld()
    observed = stream.stream_receipt()
    artifact, delivery, _ = receipt_pair()
    for name, path in zip(module.EXACT_LEDGERS, paths):
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        delivery['ledgers'][name].update(plain_bytes_expected=len(raw),plain_bytes_observed=len(raw),plain_sha256_expected=digest,plain_sha256_observed=digest)
    delivery['receipt_sha256'] = canonical_hash(delivery, omit='receipt_sha256')
    artifact.update(delivery_receipt_sha256=delivery['receipt_sha256'],stream_receipt_sha256=observed['receipt_sha256'])
    module._validate_consumption(artifact, delivery, observed, expected_run_id='synthetic-run')


def test_artifact_mutation_inside_gate_cannot_change_the_file_being_attributed(tmp_path):
    artifact, delivery, stream = receipt_pair()
    bundle = write_bundle(build_bundle(delivery_receipt_sha256=delivery['receipt_sha256'],knowledge_receipt_sha256='e'*64),tmp_path/'outputs')
    artifact['outputs_receipt_sha256'] = bundle['receipt_sha256']
    path = tmp_path/'artifact.json'
    path.write_text(json.dumps(artifact))
    def mutate(*args, **kwargs):
        path.write_text('{}')
        return {}
    with pytest.raises(module.StagingError, match='changed'):
        module.load_principal_artifact(path,expected_evidence_hash='a'*64,outputs_dir=tmp_path/'outputs',knowledge_receipt_sha256='e'*64,delivery_receipt=delivery,stream_receipt=stream,knowledge_use_gate=mutate,render_report=False)


@pytest.mark.parametrize("run_id", [None, "foreign-run"])
def test_delivery_run_identity_must_match_even_with_identical_bytes(run_id):
    artifact, delivery, stream = receipt_pair()
    if run_id is None:
        delivery.pop("run_id")
    else:
        delivery["run_id"] = run_id
    delivery["receipt_sha256"] = canonical_hash(delivery, omit="receipt_sha256")
    artifact["delivery_receipt_sha256"] = delivery["receipt_sha256"]
    with pytest.raises(module.StagingError):
        module._validate_consumption(artifact, delivery, stream, expected_run_id="synthetic-run")
