"""Contract checks use the retained real Sunday schedule as historical evidence."""
import copy
import importlib
import json
from pathlib import Path
import sys
import types

import pytest

HERE = Path(__file__).resolve().parents[1]
package = types.ModuleType('trading_day_boundary')
package.__path__ = [str(HERE)]
sys.modules[package.__name__] = package
day = importlib.import_module('trading_day_boundary.trading_day_schedule')
legacy = importlib.import_module('trading_day_boundary.verified_sunday_schedule')


def schedule():
    old = json.loads((HERE / 'tests/fixtures/actual_sunday_schedule_v1.json').read_bytes())
    # Use retained evidence, two of its closed cutoffs, to exercise arbitrary roster length.
    steps = copy.deepcopy(old['steps'][:2])
    steps[0]['feedback_available_through'] = {k: v for k, v in steps[1].items() if k != 'feedback_available_through'}
    steps[1]['feedback_available_through'] = copy.deepcopy(old['terminal_delivery'])
    body = {k: v for k, v in old.items() if k != 'schedule_sha256'}
    body.update(schema=day.SCHEMA, steps=steps, step_count=2, trading_day='20211004',
                source_manifest_hash='a' * 64, source_partitions=['glbx-mdp3-20211003.mbo.dbn.zst'],
                source_record_count=old['terminal_delivery']['records_delivered'],
                journal_count=2 * old['terminal_delivery']['records_delivered'],
                journal_hash='b' * 64, journal_sha256='c' * 64,
                cutoff_rule='retained closed cutoffs for contract test')
    return day.seal(body)


def test_trading_day_schedule_round_trips_sorted_json_with_declared_counts():
    value = schedule()
    transported = json.loads(json.dumps(value, sort_keys=True))
    assert legacy.verified_schedule(transported, expected_digest=value['schedule_sha256']) == value
    assert day.counts(value) == (57027, 2)


@pytest.mark.parametrize('field', ['model_context_rows', 'cutoff_rule', 'journal_hash', 'source_record_count'])
def test_missing_schedule_fields_are_named_and_refused(field):
    value = schedule()
    value[field] = None
    with pytest.raises(ValueError, match=field):
        day.seal({k: v for k, v in value.items() if k != 'schedule_sha256'})


def test_schedule_refuses_tampering_and_inconsistent_denominators():
    value = schedule()
    changed = copy.deepcopy(value)
    changed['trading_day'] = '20211005'
    with pytest.raises(ValueError):
        day.verify(changed, expected_digest=value['schedule_sha256'])
    changed = {k: v for k, v in value.items() if k != 'schedule_sha256'}
    changed['source_record_count'] += 1
    with pytest.raises(ValueError, match='record'):
        day.seal(changed)


def test_feedback_boundary_must_equal_next_cutoff_or_terminal():
    value = schedule()
    value['steps'][0]['feedback_available_through']['as_of'] += 1
    with pytest.raises(ValueError, match='feedback'):
        day.seal({k: v for k, v in value.items() if k != 'schedule_sha256'})


def test_launch_declaration_exposes_all_missing_values_without_guessing():
    declaration = json.loads((HERE / 'blocks/MONDAY_20211004_LAUNCH.json').read_bytes())
    missing = day.missing_launch_fields(declaration)
    assert {'model_context_rows', 'cutoff_rule', 'cutoffs', 'ingestion_receipt',
            'mapping', 'source_contract', 'publish_route'} <= set(missing)
    with pytest.raises(ValueError, match='model_context_rows'):
        day.require_launch_fields(declaration)


def test_legacy_schedule_remains_byte_identity_compatible():
    value = json.loads((HERE / 'tests/fixtures/actual_sunday_schedule_v1.json').read_bytes())
    assert legacy.verified_schedule(value, expected_digest=value['schedule_sha256']) == value
