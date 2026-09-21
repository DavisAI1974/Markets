"""Loader error paths and the sidecar compare for the per-cycle calculation pin (ship findings, 2026-09-20)."""
import json
from pathlib import Path

import pytest

from research.kalshi.frankie_boss.frankie_principal_adapter import (
    CYCLE_CALCULATION_PINS_PATH, CYCLE_CALCULATION_PINS_SCHEMA, load_cycle_calculation_pin)


def committed():
    return json.loads(Path(CYCLE_CALCULATION_PINS_PATH).read_bytes())


def write(tmp_path, document):
    path = tmp_path / 'pins.json'
    path.write_bytes(json.dumps(document).encode())
    return path


def test_index_outside_the_sunday_range_or_not_an_int_is_refused():
    for index in (-1, 19, '0', 0.0, None):
        with pytest.raises(ValueError, match='valid Sunday cycle index'):
            load_cycle_calculation_pin(index)


def test_absent_file_is_refused(tmp_path):
    with pytest.raises(ValueError, match='is absent'):
        load_cycle_calculation_pin(0, tmp_path / 'missing.json')


def test_wrong_schema_or_pins_shape_is_refused(tmp_path):
    with pytest.raises(ValueError, match='is not ' + CYCLE_CALCULATION_PINS_SCHEMA):
        load_cycle_calculation_pin(0, write(tmp_path, dict(committed(), schema='OTHER')))
    with pytest.raises(ValueError, match='is not ' + CYCLE_CALCULATION_PINS_SCHEMA):
        load_cycle_calculation_pin(0, write(tmp_path, dict(committed(), pins={})))


def test_uncovered_and_doubly_covered_cycles_are_refused(tmp_path):
    document = committed()
    document['pins'] = [pin for pin in document['pins'] if 0 not in pin['cycles']]
    with pytest.raises(ValueError, match='cycle 0 is covered by 0 pins'):
        load_cycle_calculation_pin(0, write(tmp_path, document))
    document = committed()
    document['pins'].append(dict(document['pins'][0]))
    with pytest.raises(ValueError, match='cycle 0 is covered by 2 pins'):
        load_cycle_calculation_pin(0, write(tmp_path, document))


def test_pin_missing_a_required_field_or_a_malformed_receipt_is_refused(tmp_path):
    for key in ('group', 'defined_on', 'calculations', 'registry_layers', 'source_receipts'):
        document = committed()
        document['pins'][0][key] = [] if isinstance(document['pins'][0][key], list) else ''
        with pytest.raises(ValueError, match='lacks ' + key):
            load_cycle_calculation_pin(0, write(tmp_path, document))
    document = committed()
    document['pins'][0]['source_receipts'][0] = {'path': 'x'}
    with pytest.raises(ValueError, match='needs path, bytes and sha256'):
        load_cycle_calculation_pin(0, write(tmp_path, document))


def test_loaded_pin_carries_the_file_witness_and_index(tmp_path):
    pin = load_cycle_calculation_pin(3)
    assert pin['cycle_index'] == 3 and pin['pins_witness']['path'] == str(Path(CYCLE_CALCULATION_PINS_PATH))
    assert len(pin['pins_witness']['sha256']) == 64 and pin['pins_witness']['bytes'] > 0
    copied = write(tmp_path, committed())
    moved = load_cycle_calculation_pin(3, copied)
    assert moved['pins_witness']['path'] == str(copied) and moved['group'] == pin['group']


# ---- the bedrock (Greg, 2026-09-21: "All 3"; SPEC_CYCLE0_BEDROCK_20260921.md pin-bedrock) -------------------------

def test_a_pin_without_bedrock_loads_with_an_empty_bedrock_layer_list():
    for index in (1, 2, 3):
        assert load_cycle_calculation_pin(index)['bedrock_layers'] == []


def test_malformed_bedrock_is_refused(tmp_path):
    document = committed()
    document['pins'][0]['bedrock'] = {}
    with pytest.raises(ValueError, match='bedrock must be a non-empty list'):
        load_cycle_calculation_pin(0, write(tmp_path, document))
    document = committed()
    document['pins'][0]['bedrock'] = []
    with pytest.raises(ValueError, match='bedrock must be a non-empty list'):
        load_cycle_calculation_pin(0, write(tmp_path, document))
    document = committed()
    document['pins'][0]['bedrock'] = ['derived_geometry']
    with pytest.raises(ValueError, match='bedrock entry must be a pin-shaped mapping'):
        load_cycle_calculation_pin(0, write(tmp_path, document))
    for key in ('group', 'defined_on', 'calculations', 'registry_layers', 'source_receipts'):
        document = committed()
        entry = dict(document['pins'][0]['bedrock'][0])
        entry[key] = [] if isinstance(entry[key], list) else ''
        document['pins'][0]['bedrock'][0] = entry
        with pytest.raises(ValueError, match='bedrock entry lacks ' + key):
            load_cycle_calculation_pin(0, write(tmp_path, document))
    document = committed()
    entry = json.loads(json.dumps(document['pins'][0]['bedrock'][0]))
    entry['source_receipts'][0] = {'path': 'x'}
    document['pins'][0]['bedrock'][0] = entry
    with pytest.raises(ValueError, match='needs path, bytes and sha256'):
        load_cycle_calculation_pin(0, write(tmp_path, document))


def test_a_bedrock_group_no_cycle_pins_as_its_own_is_refused(tmp_path):
    document = committed()
    document['pins'][0]['bedrock'][0] = dict(document['pins'][0]['bedrock'][0], group='ghost_group')
    with pytest.raises(ValueError, match='bedrock group ghost_group is pinned to 0 cycles of its own'):
        load_cycle_calculation_pin(0, write(tmp_path, document))
    document = committed()
    document['pins'][0]['bedrock'][0] = dict(document['pins'][0]['bedrock'][0], group=document['pins'][0]['group'])
    with pytest.raises(ValueError, match='is pinned to 0 cycles of its own'):
        load_cycle_calculation_pin(0, write(tmp_path, document))


def test_a_bedrock_entry_that_differs_from_its_own_pin_is_refused(tmp_path):
    document = committed()
    entry = json.loads(json.dumps(document['pins'][0]['bedrock'][0]))
    entry['registry_layers'] = entry['registry_layers'][:-1]
    entry['calculations'] = entry['calculations'][:-1]
    document['pins'][0]['bedrock'][0] = entry
    with pytest.raises(ValueError, match='bedrock group derived_geometry differs from its own pin'):
        load_cycle_calculation_pin(0, write(tmp_path, document))


def test_a_bedrock_layer_outside_the_registry_is_refused(tmp_path):
    document = committed()
    ghost = dict(document['pins'][1], registry_layers=document['pins'][1]['registry_layers'] + ['ghost_layer'])
    document['pins'][1] = ghost
    document['pins'][0]['bedrock'][0] = dict(ghost)
    with pytest.raises(ValueError, match='bedrock layer ghost_layer is not a registry calculation layer'):
        load_cycle_calculation_pin(0, write(tmp_path, document))
