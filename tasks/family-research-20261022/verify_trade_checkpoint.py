"""Check new evidence against original prints and saved compact bytes, without rehashing frozen sources."""
import ast
import csv
import gzip
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'artifacts/sqlite-triage/20261022/families'
OUT = BASE / 'trade-lifecycle-targeted-v1'


def rows(name):
    with gzip.open(OUT / name, 'rt', encoding='utf-8') as handle:
        for line in handle:
            yield json.loads(line)


with (BASE / 'price-curve-timestamps.csv').open(newline='', encoding='utf-8') as handle:
    original = list(csv.DictReader(handle))
assert len(original) == 30739
for count, record in enumerate(rows('every-trade-evidence-bundle.jsonl.gz'), 1):
    source = original[count - 1]
    assert record['trade_ordinal'] == count - 1
    assert record['original_trade'] == source
    for key, value in record['exact_clocks'].items():
        assert type(value) is int and value == int(source[key])
    assert record['original_second_set']['line_number'] == count
assert count == len(original)

pin = json.loads((BASE / 'dipole-audit-v1/complete_component_input_receipt.json').read_text())
transport = json.loads((OUT / 'bounded-second-set-read-receipt.json').read_text())
buffers = {}
for member in transport['source_members']:
    parts = []
    for chunk in member['chunks']:
        path = ROOT / chunk['path']
        assert path.resolve().is_relative_to(OUT.resolve())
        assert path.stat().st_size == chunk['compressed_bytes'] < 100_000_000
        data = gzip.decompress(path.read_bytes())
        assert len(data) == chunk['uncompressed_bytes']
        parts.append(data)
    data = b''.join(parts)
    assert len(data) == member['bytes']
    buffers[member['original_member'].rsplit('/', 1)[-1]] = data
clocks = np.frombuffer(buffers['clocks-i64.bin'], dtype='<i8').reshape(pin['rows'], len(pin['clock_names']))
raw64 = np.frombuffer(buffers['raw-components-f64.bin'], dtype='<f8').reshape(pin['rows'], len(pin['names']))
source32 = np.frombuffer(buffers['components-f32.bin'], dtype='<f4').reshape(pin['rows'], len(pin['names']))
states = np.frombuffer(buffers['states-u8.bin'], dtype='u1').reshape(pin['rows'], len(pin['names']))
views = 0
for count, record in enumerate(rows('every-trade-original-second-set.jsonl.gz'), 1):
    source = original[count - 1]
    assert record['trade_ordinal'] == count - 1
    assert record['trade_input_cursor'] == int(source['trade_input_cursor'])
    for key in ['at_trade_input', 'at_emission_group_close', 'previous_input', 'last_completed_group_before_trade']:
        view = record[key]
        if 'source_row_index' not in view:
            assert view['disposition'] in ['EXACT_CURSOR_ABSENT', 'NO_PREVIOUS_COMPLETED_GROUP']
            continue
        views += 1
        index = view['source_row_index']
        assert view['clocks'] == {name: int(clocks[index, i]) for i, name in enumerate(pin['clock_names'])}
        assert view['clocks']['instrument_id'] == int(source['instrument_id'])
        assert list(view['numbers']) == pin['names']
        for i, name in enumerate(pin['names']):
            number = view['numbers'][name]
            assert number['raw_float64_hex'] == float(raw64[index, i]).hex()
            assert number['raw_float64'] == (float(raw64[index, i]) if np.isfinite(raw64[index, i]) else None)
            assert number['source_float32'] == (float(source32[index, i]) if np.isfinite(source32[index, i]) else None)
            assert number['state_code'] == int(states[index, i])
            assert number['state'] == pin['component_state_names'][int(states[index, i])]
    assert record['at_trade_input']['clocks']['event_ns'] == int(source['event_ns'])
    assert record['at_trade_input']['clocks']['receive_ns'] == int(source['receive_ns'])
    assert record['at_emission_group_close']['clocks']['known_by_ns'] == int(source['available_ns'])
assert count == len(original)

root_receipt = json.loads((OUT / 'root-and-order-evidence-receipt.json').read_text())
for count, record in enumerate(rows('every-trade-root-record-links.jsonl.gz'), 1):
    assert record['trade_ordinal'] == count - 1
    for key in ['last_completed_group_original_record_lines', 'emission_group_original_record_lines']:
        assert all(1 <= line <= root_receipt['original_root_native_measurement_rows'] for line in record[key])
assert count == len(original)
group_count = 0
for group in rows('original-native-trade-groups.jsonl.gz'):
    group_count += 1
    for source in group['original_trade_prints']:
        assert source == original[int(source['source_ordinal'])]
        assert int(source['group_close_input_cursor']) == group['group_close_input_cursor']
assert group_count == 29797

large = [p.relative_to(ROOT).as_posix() for p in OUT.rglob('*') if p.is_file() and p.stat().st_size >= 100_000_000]
assert not large
syntax = []
for name in ['targeted_trade_lifecycle_pass.py', 'read_bounded_second_set.py', 'finalize_trade_evidence.py',
             'attach_trade_root_and_order_evidence.py', 'audit_trade_dipole_overlay.py', 'verify_trade_checkpoint.py']:
    path = ROOT / 'tasks/family-research-20261022' / name
    ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    syntax.append(name)
result = dict(status='PASSED_NEW_CHECKPOINT_PRESERVATION_CHECKS', original_trades=30739,
              original_fields_checked_on_every_trade=True, dropped_trades=0,
              second_set_source_views_checked=views, original_compact_rows=pin['rows'],
              compact_values_states_clocks_match_saved_original_bytes=True,
              native_groups=group_count, all_root_link_trade_ordinals_checked=True,
              helper_syntax_checked=syntax, files_at_or_above_100MB=large,
              frozen_input_database_or_archive_rehash=False,
              scientific_semantic_gate='NOT_PASSED; this preservation check does not certify mechanisms or models')
(OUT / 'checkpoint-verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, indent=2), flush=True)
