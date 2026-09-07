"""Pure synthetic paired-output tests; no chronology or model claim is made."""
from dataclasses import replace
import json
import math

import pytest

from research.kalshi.frankie_boss.granite_evaluation import (
    DecodeOutput, EvaluationPair, evaluate,
)
from research.kalshi.frankie_boss.state_serialization import serialize_state
from test_state_serialization import snapshot

TRAINING_HASHES = frozenset({'f' * 64})


def payload(state, i):
    return {
        'schema_version': 'BOSS_GRANITE_OUTPUT_SCHEMA_V1',
        'snapshot_hash': state.hash,
        'evidence_refs': [],
        'contradictions': [],
        'missing_evidence': [f'missing-{i}'],
        'hypotheses': [{'label': 'uncertain', 'support': [], 'against': []}],
        'evidence_verdict': ('CONSISTENT', 'CONFLICTED')[i % 2],
    }


def pairs(base_valid=160, tuned_valid=180, tuned_seconds=1.2):
    result = []
    for i in range(200):
        state = serialize_state(replace(snapshot(), as_of_ns=130 + i))
        text = json.dumps(payload(state, i))
        result.append(EvaluationPair(
            state,
            DecodeOutput(text if i < base_valid else 'bad json', 1.0, 1200),
            DecodeOutput(text if i < tuned_valid else 'bad json', tuned_seconds, 1200),
        ))
    return result


def run(items, **kwargs):
    return evaluate(items, training_snapshot_hashes=TRAINING_HASHES,
                    validation_scope='2021-10-01/PROBE_ONLY', **kwargs)


def alter(items, side, i, **fields):
    item = items[i]
    decoded = getattr(item, side)
    body = json.loads(decoded.text)
    body.update(fields)
    items[i] = replace(item, **{side: replace(decoded, text=json.dumps(body))})


def test_thresholds_are_inclusive_and_report_is_deterministic():
    items = pairs()
    report = run(items)
    assert report == run(items)
    assert report.passed
    assert report.base.l4_count == 160
    assert report.tuned.l4_count == 180
    assert report.tuned.l4_rate == .9
    assert report.l4_improvement == pytest.approx(.1)
    assert report.latency_ratio == pytest.approx(1.2)
    assert report.base.total_decode_seconds == 200
    assert report.tuned.total_decode_seconds == pytest.approx(240)
    assert report.failures == ()


def test_ninety_five_percent_passes_without_improvement():
    assert run(pairs(base_valid=200, tuned_valid=190)).passed


def test_acceptance_improvement_below_threshold_fails():
    result = run(pairs(tuned_valid=179))
    assert not result.passed
    assert 'acceptance' in result.failures


def test_hash_mismatch_is_counted_even_if_key_set_is_wrong():
    items = pairs(200, 200)
    alter(items, 'tuned', 0, snapshot_hash='e' * 64, unexpected=True)
    result = run(items)
    assert result.tuned.snapshot_hash_mismatch_count == 1
    assert 'snapshot_hash' in result.failures


def test_hash_mismatch_is_counted_even_if_schema_types_are_wrong():
    items = pairs(200, 200)
    alter(items, 'tuned', 0, snapshot_hash='e' * 64, hypotheses=False)
    assert 'snapshot_hash' in run(items).failures


def test_wrong_hash_in_base_does_not_fail_tuned_answer_wall():
    items = pairs(200, 200)
    alter(items, 'base', 0, snapshot_hash='e' * 64)
    result = run(items)
    assert result.base.snapshot_hash_mismatch_count == 1
    assert result.passed


def test_sixty_percent_unique_strings_boundary():
    items = pairs(200, 200)
    for i in range(200):
        alter(items, 'tuned', i, missing_evidence=[f'missing-{i % 120}'])
    assert run(items).passed
    alter(items, 'tuned', 119, missing_evidence=['missing-0'])
    assert 'content_diversity' in run(items).failures


def test_notes_and_missing_evidence_form_one_distinct_union():
    items = pairs(200, 200)
    for side in ('base', 'tuned'):
        for i in range(200):
            alter(items, side, i, contradictions=[{
                'a': {'row': 0, 'field': 'mid'},
                'b': {'row': 1, 'field': 'mid'}, 'note': f'missing-{i}',
            }])
    assert run(items).tuned.distinct_content_strings == 200


def test_evidence_verdict_ninety_percent_boundary_and_collapse():
    items = pairs(200, 200)
    for i in range(200):
        alter(items, 'tuned', i, evidence_verdict='CONSISTENT' if i < 180 else 'CONFLICTED')
    assert run(items).passed
    alter(items, 'tuned', 180, evidence_verdict='CONSISTENT')
    result = run(items)
    assert result.tuned.max_evidence_verdict_share == .905
    assert 'evidence_verdict_collapse' in result.failures


def test_latency_uses_total_decode_times_not_mean_sample_ratios():
    items = pairs(200, 200, 1.0)
    items[0] = replace(items[0], base=replace(items[0].base, decode_seconds=.001))
    assert run(items).passed
    assert 'latency' in run(pairs(200, 200, 1.20001)).failures


@pytest.mark.parametrize('size', [0, 199, 201])
def test_exactly_two_hundred_pairs_required(size):
    items = pairs()
    items = items[:size] if size <= 200 else items + [items[0]]
    with pytest.raises(ValueError, match='200'):
        run(items)


def test_duplicate_state_rejected():
    items = pairs()
    items[-1] = items[0]
    with pytest.raises(ValueError, match='unique'):
        run(items)


def test_training_overlap_rejected():
    items = pairs()
    with pytest.raises(ValueError, match='training'):
        evaluate(items, training_snapshot_hashes={items[0].snapshot.hash},
                 validation_scope='2021-10-01/PROBE_ONLY')


@pytest.mark.parametrize('hashes', [set(), {'bad'}, {'G' * 64}])
def test_explicit_valid_training_hash_inventory_required(hashes):
    with pytest.raises(ValueError, match='training'):
        evaluate(pairs(), training_snapshot_hashes=hashes,
                 validation_scope='2021-10-01/PROBE_ONLY')


def test_scope_declaration_required_but_is_not_inferred_from_synthetic_timestamps():
    with pytest.raises(ValueError, match='scope'):
        evaluate(pairs(), training_snapshot_hashes=TRAINING_HASHES,
                 validation_scope='2021-10-04/HELD_OUT')


@pytest.mark.parametrize('seconds', [0, -1, math.nan, math.inf, True, '1'])
def test_invalid_decode_times_rejected(seconds):
    items = pairs()
    items[0] = replace(items[0], tuned=replace(items[0].tuned, decode_seconds=seconds))
    with pytest.raises(ValueError, match='decode'):
        run(items)


@pytest.mark.parametrize('budget', [0, -1, True, 1200.0, 1201])
def test_fixed_equal_integer_token_budget_required(budget):
    items = pairs()
    items[0] = replace(items[0], tuned=replace(items[0].tuned, token_budget=budget))
    with pytest.raises(ValueError, match='budget'):
        run(items)


def test_no_schema_valid_outputs_fail_evidence_verdict_gate_without_crashing():
    report = run(pairs(0, 0))
    assert report.tuned.schema_valid_count == 0
    assert report.tuned.max_evidence_verdict_share is None
    assert 'evidence_verdict_collapse' in report.failures


def test_evidence_verdict_denominator_excludes_malformed_outputs():
    items = pairs(200, 190)
    for i in range(190):
        alter(items, 'tuned', i, evidence_verdict='CONSISTENT' if i < 172 else 'CONFLICTED')
    report = run(items)
    assert report.tuned.schema_valid_count == 190
    assert report.tuned.max_evidence_verdict_share == 172 / 190
    assert 'evidence_verdict_collapse' in report.failures


def test_malformed_schema_does_not_inflate_content_diversity():
    items = pairs(200, 200)
    alter(items, 'tuned', 0, hypotheses=False, missing_evidence=['not-counted'])
    report = run(items)
    assert report.tuned.schema_valid_count == 199
    assert report.tuned.distinct_content_strings == 199


def test_l3_bad_reference_excluded_from_content_and_verdict_denominator():
    items = pairs(200, 200)
    alter(items, 'tuned', 0, evidence_refs=[{'row': 1000, 'field': 'mid'}])
    report = run(items)
    assert report.tuned.schema_valid_count == 199
    assert report.tuned.l4_count == 199
    assert report.tuned.distinct_content_strings == 199

    assert report.sample_count == 200
    assert sum(dict(report.tuned.evidence_verdict_counts).values()) == 199


def test_non_string_echo_counts_as_mismatch_even_at_l2():
    items = pairs(200, 200)
    alter(items, 'tuned', 0, snapshot_hash=False)
    assert 'snapshot_hash' in run(items).failures


def test_overflowing_total_decode_time_rejected():
    items = pairs(200, 200, 1e308)
    with pytest.raises(ValueError, match='decode'):
        run(items)


def test_invalid_text_rejected_as_bad_measurement():
    items = pairs()
    items[0] = replace(items[0], tuned=replace(items[0].tuned, text=None))
    with pytest.raises(ValueError, match='text'):
        run(items)


def test_unverified_echoes_are_reported_separately_from_observed_mismatches():
    report = run(pairs(200, 190))
    assert report.tuned.snapshot_hash_unverified_count == 10
    assert report.tuned.snapshot_hash_mismatch_count == 0


def test_missing_echo_is_unverified():
    items = pairs(200, 200)
    body = json.loads(items[0].tuned.text)
    del body['snapshot_hash']
    items[0] = replace(items[0], tuned=replace(items[0].tuned, text=json.dumps(body)))
    assert run(items).tuned.snapshot_hash_unverified_count == 1
