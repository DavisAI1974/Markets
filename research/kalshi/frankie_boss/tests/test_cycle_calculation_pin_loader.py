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
