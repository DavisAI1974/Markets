"""Pinned calculation-layer sources: exact legacy tables without whole-file loads."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
import test_frankie_box_digest_render as FX

DG = FX.DG
MODULES = Path(__file__).resolve().parents[1] / 'deploy/aws/box'


def sources():
    sys.path.insert(0, str(MODULES))
    from frankie_box_digest_sources import BedrockSources
    return BedrockSources


def pinned(tmp_path, files):
    entries, reloaded = {}, {}
    tmp_path.mkdir(parents=True, exist_ok=True)
    for index, (name, value) in enumerate(files.items()):
        path = tmp_path / ('layer-%d.json' % index)
        raw = json.dumps(value, sort_keys=True, default=str).encode()
        path.write_bytes(raw)
        entries[name] = dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        reloaded[name] = json.loads(raw)
    return entries, reloaded


def assert_sources(tmp_path, files):
    entries, reloaded = pinned(tmp_path/'inputs', files)
    expected = DG.bedrock_tables(reloaded)
    with sources()(entries, tmp_path/'scratch') as actual:
        assert list(actual.tables) == list(expected)
        assert actual.layer_count == len(reloaded)
        assert actual.derived == sum(f.get('status') == 'derived' for f in reloaded.values())
        verdict = next((f.get('traversal') for f in reloaded.values()
                        if isinstance(f.get('traversal'), dict)), None) or {}
        assert DG._same(actual.verdict, verdict)
        for name, rows in expected.items():
            assert DG._same(list(actual.tables[name]), rows), name
            assert DG._same(list(actual.tables[name]), rows), 'source must replay: ' + name
            assert DG.render_table(name, list(actual.tables[name])) == DG.render_table(name, rows)
    return entries


@pytest.mark.parametrize('sections', [False, True])
def test_existing_calculation_layer_fixtures_match_persisted_json_tables(tmp_path, sections):
    files = FX._bedrock_files()
    if sections:
        files.update(FX._section_files())
    for f in files.values():
        f['traversal'] = dict(verdict='REJECTED', failed_gates=['coverage', 'denominators'],
                              groups=3, records=11, span_seconds=10.0)
    assert_sources(tmp_path, files)


def test_group_sort_column_union_carrier_counts_and_typed_values(tmp_path):
    files = {
        'first': dict(status='derived', member_rows=[
            dict(group_index=9, **{'queue[][]': [[1, 2], [3]], 'nested.value': -0.0}),
            dict(group_index=None, **{'queue[][]': [], 'nested.value': float('nan')}),
            dict(group_index=2, **{'queue[][]': None, 'nested.value': 1.0}),
        ]),
        'second': dict(status='derived', member_rows=[
            dict(group_index=2, ts_recv_ns=1633298403300150001, tail={'a.b': 1}),
            dict(group_index=9, ts_recv_ns=1633298403300150002, tail={}),
        ]),
        'inactive': dict(status='could_not', member_rows=[dict(group_index=9, **{'nested.value': 99})])
    }
    assert_sources(tmp_path, files)


def test_first_nonempty_lifecycle_wins_and_later_section_tables_replace_in_place(tmp_path):
    files = {
        'empty': dict(status='derived', lifecycle_sections=['z', 'a'], lifecycle_rows=[]),
        'winner': dict(status='derived', section='x', lifecycle_sections=['z', 'a'],
            lifecycle_rows=[dict(emitting_section='z', value=1), dict(emitting_section='a', value=2)],
            companion_rows=[dict(section='x', declaration={'ignored': True}, value='first')],
            declarations=[dict(value='first')], matching_rule=dict(value='first')),
        'later': dict(status='derived', section='y', lifecycle_sections=['z', 'a'],
            lifecycle_rows=[dict(emitting_section='a', value=999), dict(emitting_section='z', value=999)],
            first_last_pairs=[dict(value='middle')]),
        'replacement': dict(status='derived', section='x', companion_rows=[dict(value='last')],
            declarations=[dict(value='last')], matching_rule=dict(value='last')),
    }
    assert_sources(tmp_path, files)


@pytest.mark.parametrize('value', [2, 1.0, True, -0.0])
def test_member_conflict_refuses_and_retains_scratch(tmp_path, value):
    files = {'a': dict(status='derived', member_rows=[dict(group_index=0, value=1)]),
             'b': dict(status='derived', member_rows=[dict(group_index=0, value=value)])}
    entries, reloaded = pinned(tmp_path/'inputs', files)
    with pytest.raises(ValueError, match='conflict'):
        DG.bedrock_tables(reloaded)
    with pytest.raises(ValueError, match='conflict'):
        with sources()(entries, tmp_path/'scratch'):
            pass
    assert (tmp_path/'scratch').is_dir()
    assert list((tmp_path/'scratch').iterdir())


def test_member_missing_group_key_refuses(tmp_path):
    entries, _ = pinned(tmp_path/'inputs', {'a': dict(status='derived', member_rows=[dict(x=1)])})
    with pytest.raises(ValueError, match='group_index'):
        with sources()(entries, tmp_path/'scratch'):
            pass


@pytest.mark.parametrize('change', ['hash', 'bytes', 'truncated', 'trailing'])
def test_pins_and_complete_json_are_required(tmp_path, change):
    entries, _ = pinned(tmp_path/'inputs', {'a': dict(status='derived', member_rows=[dict(group_index=0)])})
    entry = entries['a']
    path = Path(entry['path'])
    if change == 'hash':
        entry['sha256'] = '0' * 64
    elif change == 'bytes':
        entry['bytes'] += 1
    else:
        raw = path.read_bytes()
        raw = raw[:-1] if change == 'truncated' else raw + b' null'
        path.write_bytes(raw)
        entry.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError):
        with sources()(entries, tmp_path/'scratch'):
            pass
    assert path.exists() and (tmp_path/'scratch').exists()


def test_snapshot_replays_after_original_changes_and_existing_scratch_is_preserved(tmp_path):
    entries, reloaded = pinned(tmp_path/'inputs', {'a': dict(status='derived', member_rows=[dict(group_index=0, x=1)])})
    scratch = tmp_path/'scratch'
    with sources()(entries, scratch) as actual:
        Path(entries['a']['path']).write_bytes(b'changed original')
        assert DG._same(list(actual.tables['bedrock.members']), DG.bedrock_tables(reloaded)['bedrock.members'])
    retained = {p: p.read_bytes() for p in scratch.rglob('*') if p.is_file()}
    with pytest.raises(FileExistsError):
        with sources()(entries, scratch):
            pass
    assert retained == {p: p.read_bytes() for p in scratch.rglob('*') if p.is_file()}


def test_no_whole_file_loading_or_legacy_materialization(tmp_path, monkeypatch):
    entries, _ = pinned(tmp_path/'inputs', {'a': dict(status='derived',
        member_rows=[dict(group_index=i, text='unique-%d' % i) for i in range(3000)])})
    cls = sources()
    def forbidden(*args, **kwargs):
        raise AssertionError('whole-file/table materialization forbidden')
    monkeypatch.setattr(Path, 'read_bytes', forbidden)
    monkeypatch.setattr(Path, 'read_text', forbidden)
    monkeypatch.setattr(json, 'load', forbidden)
    monkeypatch.setattr(DG, 'bedrock_tables', forbidden)
    with cls(entries, tmp_path/'scratch') as actual:
        assert sum(1 for _ in actual.tables['bedrock.members']) == 3000


def test_json_duplicate_array_keys_use_last_value_and_preserve_row_key_order(tmp_path):
    path = tmp_path/'input.json'
    raw = b'{"status":"derived","member_rows":[{"group_index":9}],"member_rows":[{"z":1,"group_index":2,"a":3}]}'
    path.write_bytes(raw)
    entry = dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    with sources()({'a': entry}, tmp_path/'scratch') as actual:
        expected = DG.bedrock_tables({'a': json.loads(raw)})
        assert DG._same(list(actual.tables['bedrock.members']), expected['bedrock.members'])
        assert list(next(iter(actual.tables['bedrock.members']))) == ['z', 'group_index', 'a']


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux ru_maxrss units')
def test_fresh_process_source_rows_and_distinct_groups_have_bounded_memory(tmp_path, capsys):
    code = r'''
import hashlib, json, pathlib, resource, sys, tracemalloc
sys.path.insert(0, sys.argv[1])
from frankie_box_digest_sources import BedrockSources
n = int(sys.argv[2])
root = pathlib.Path(sys.argv[3]); root.mkdir()
path = root/'layer.json'
with path.open('w') as f:
    f.write('{"status":"derived","member_rows":[')
    for i in range(n):
        if i: f.write(',')
        json.dump(dict(group_index=i, value='value-%08d' % i, ts_recv_ns=1633298403300150001+i), f)
    f.write(']}')
with path.open('rb') as f: digest = hashlib.file_digest(f, 'sha256').hexdigest()
entry = dict(path=str(path), bytes=path.stat().st_size, sha256=digest)
tracemalloc.start()
with BedrockSources({'a': entry}, root/'scratch') as source:
    assert sum(1 for _ in source.tables['bedrock.members']) == n
_, peak = tracemalloc.get_traced_memory()
print(json.dumps(dict(rows=n, python_peak_bytes=peak,
    rss_peak_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)))
'''
    records = []
    for n in (4000, 40000):
        result = subprocess.run([sys.executable, '-c', code, str(MODULES), str(n), str(tmp_path/str(n))],
                                check=True, capture_output=True, text=True, timeout=180)
        records.append(json.loads(result.stdout))
    with capsys.disabled():
        print('\nDIGEST_SOURCE_MEMORY_REGRESSION ' + json.dumps(records), flush=True)
    small, large = records
    assert large['python_peak_bytes'] <= small['python_peak_bytes'] + 2 * 1024 * 1024
    assert large['rss_peak_bytes'] <= small['rss_peak_bytes'] + 16 * 1024 * 1024
