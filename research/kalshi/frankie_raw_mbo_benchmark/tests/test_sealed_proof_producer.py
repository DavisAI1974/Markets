import hashlib
import json

import pytest

from research.kalshi.frankie_raw_mbo_benchmark import native_sealed_absence as sealed
from research.kalshi.frankie_raw_mbo_benchmark.native_knowledge_delivery import (
    build_knowledge_delivery, write_knowledge_delivery,
)


@pytest.fixture
def inputs(tmp_path):
    delivery = build_knowledge_delivery(arm='A_MEMORY', role='REAL_TIME_FRANKIE')
    paths = write_knowledge_delivery(delivery, tmp_path)
    prompt = tmp_path / 'prompt.md'
    prompt.write_bytes(b'The actual principal prompt.\n')
    receipt = tmp_path / 'delivery.json'
    receipt.write_text(json.dumps({'run_prefix': 's3://run/sunday', 'ledgers': {}}))
    return dict(prompt=prompt, knowledge_receipt=paths['receipt'],
                knowledge_bundle=paths['bundle'], delivery_receipt=receipt,
                output=tmp_path / 'sealed-proof.json')


def test_producer_writes_a_nonvacuous_proof_bound_to_exact_prompt_and_bundle(inputs):
    proof = sealed.write_sealed_proof(**inputs)
    assert json.loads(inputs['output'].read_bytes()) == proof
    assert proof['all_absent'] is True and proof['tokens_checked'] > 0
    assert proof['surfaces_scanned']['prompt']['sha256'] == hashlib.sha256(inputs['prompt'].read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        sealed.write_sealed_proof(**inputs)


def test_contaminated_prompt_never_produces_a_file(inputs):
    inputs['prompt'].write_bytes(b'target_ground_truth_onset_time')
    with pytest.raises(sealed.SealedAbsenceError, match='prompt'):
        sealed.write_sealed_proof(**inputs)
    assert not inputs['output'].exists()


def test_wrong_knowledge_bytes_never_produce_a_proof(inputs):
    inputs['knowledge_bundle'].write_bytes(b'replaced knowledge')
    with pytest.raises(ValueError):
        sealed.write_sealed_proof(**inputs)
    assert not inputs['output'].exists()


def test_missing_delivered_paths_are_refused(inputs):
    inputs['delivery_receipt'].write_text('{}')
    with pytest.raises(sealed.SealedAbsenceError, match='delivered paths'):
        sealed.write_sealed_proof(**inputs)
    assert not inputs['output'].exists()
