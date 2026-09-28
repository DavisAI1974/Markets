"""Digest save points: a rerun of the same calculation root reuses only tables and merge shards whose key AND bytes
match; anything else is rebuilt, never reused and never failed on."""
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import sys

import pytest

import test_frankie_box_digest_render as FX

BOX = Path(__file__).resolve().parents[1] / 'deploy/aws/box'
sys.path.insert(0, str(BOX))

import frankie_box_digest_document as D  # noqa: E402
import frankie_box_digest_sources as S  # noqa: E402

LEGACY = ('legacy_price', 'legacy_native_signed_flow', 'legacy_per_second_roll20', 'legacy_book_imbalance',
          'legacy_structure_observables')


def receipt(seed='a'):
    layers = {name: dict(status='derived', path='derived/%s.json' % name, bytes=1, sha256=hashlib.sha256((seed + name).encode()).hexdigest())
              for name in LEGACY}
    return dict(rows=dict(path='p', count=8, kinds={'input': 4}, head='a' * 64, head_is_request_source_hash=True),
                input_records=4, legacy_rows=4, f_last_groups=4, failure_count=0, pin_group='test', layers=layers)


def inputs():
    tables = FX._tables()
    prices = [dict(ts_recv=1633298400000000001 + i, price=5.5 + i / 100, size=i + 1) for i in range(4)]
    return dict(prices=prices, frames=tables['legacy_book_imbalance'], structures=tables['legacy_structure_observables'],
                roll=[float('nan'), 1.0, 1.0 / 5.0, 1.0 / 3.0], first=10, buys=[0.0, 1.0, 2.0, 3.0],
                sells=[0.0, 0.0, 2.0, 1.0])


def run(tmp_path, attempt, value=None, target=None):
    data = inputs()
    target = target or tmp_path / ('digest-%s.md' % attempt)
    proof = D.write_digest(target, value or receipt(), {}, iter(data['prices']), iter(data['frames']),
                           iter(data['structures']), data['roll'], data['first'], data['buys'], data['sells'],
                           bedrock_entries={}, scratch_directory=tmp_path / 'derived' / ('.digest-' + attempt))
    return target.read_bytes(), proof


@pytest.fixture
def written(monkeypatch):
    calls = []
    original = D.TS.write_table

    def counted(path, name, *a, **k):
        calls.append(name)
        return original(path, name, *a, **k)
    monkeypatch.setattr(D.TS, 'write_table', counted)
    return calls


def test_rerun_reuses_every_verified_legacy_table_with_identical_bytes(tmp_path, written):
    first, _ = run(tmp_path, 'a')
    written.clear()
    second, _ = run(tmp_path, 'b')
    assert written == []
    assert second == first


def test_no_receipts_from_an_older_runtime_rebuilds_everything(tmp_path, written):
    first, _ = run(tmp_path, 'a')
    for receipt_path in (tmp_path / 'derived' / '.digest-a').glob('table-*.save.json'):
        receipt_path.unlink()
    written.clear()
    second, _ = run(tmp_path, 'b')
    assert len(written) == 5
    assert second == first


def test_changed_legacy_inputs_rebuild_every_legacy_table(tmp_path, written):
    run(tmp_path, 'a')
    written.clear()
    run(tmp_path, 'b', value=receipt('changed'))
    assert len(written) == 5


def test_same_size_changed_table_bytes_are_rebuilt_not_reused_or_failed(tmp_path, written):
    first, _ = run(tmp_path, 'a')
    table = tmp_path / 'derived' / '.digest-a' / 'table-0000.txt'
    raw = bytearray(table.read_bytes())
    raw[-2] = ord('X') if raw[-2] != ord('X') else ord('Y')
    table.write_bytes(bytes(raw))
    written.clear()
    second, _ = run(tmp_path, 'b')
    assert written[0] == 'legacy_price' and len(written) == 5   # the prefix breaks at table 0
    assert second == first


def test_changed_context_database_is_rebuilt(tmp_path, written):
    run(tmp_path, 'a')
    context = tmp_path / 'derived' / '.digest-a' / 'table-0002' / 'table.sqlite'
    with context.open('ab') as handle:
        handle.write(b'\0')
    written.clear()
    run(tmp_path, 'b')
    assert written[:1] == ['legacy_book_imbalance'] and len(written) == 3


def test_code_identity_change_rebuilds(tmp_path, written, monkeypatch):
    run(tmp_path, 'a')
    identity = D._code_identity()
    monkeypatch.setattr(D, '_code_identity', lambda: dict(identity, changed='1'))
    written.clear()
    run(tmp_path, 'b')
    assert len(written) == 5


def test_code_identity_covers_the_format_and_the_row_producing_code():
    names = set(D._code_identity())
    assert {'frankie_box_digest_render.py', 'frankie_box_digest_stream.py', 'sources._Members', 'sources._Rows',
            'document.per_second_rows', 'document._bedrock_table_job', 'parallel._source_rows'} <= names


def test_a_missing_receipt_breaks_the_legacy_prefix_from_there_on(tmp_path, written):
    run(tmp_path, 'a')
    (tmp_path / 'derived' / '.digest-a' / 'table-0002.save.json').unlink()
    written.clear()
    run(tmp_path, 'b')
    assert written == ['legacy_book_imbalance', 'legacy_structure_observables', 'structure_families']


def test_corrupt_receipt_is_skipped(tmp_path, written):
    run(tmp_path, 'a')
    (tmp_path / 'derived' / '.digest-a' / 'table-0000.save.json').write_text('{"schema":')
    written.clear()
    run(tmp_path, 'b')
    assert len(written) == 5


def test_receipt_pointing_outside_its_directory_is_skipped(tmp_path, written):
    run(tmp_path, 'a')
    receipt_path = tmp_path / 'derived' / '.digest-a' / 'table-0000.save.json'
    value = json.loads(receipt_path.read_bytes())
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    (elsewhere / 'table-0000.txt').write_bytes(Path(value['path']).read_bytes())
    value['path'] = str(elsewhere / 'table-0000.txt')
    receipt_path.write_text(json.dumps(value))
    written.clear()
    run(tmp_path, 'b')
    assert len(written) == 5


# ---- merge shards ------------------------------------------------------------------------------------------------

def shard_file(tmp_path, attempt, shard, payload=b'shard bytes'):
    root = tmp_path / 'derived' / ('.digest-' + attempt) / 'calculation-layers'
    root.mkdir(parents=True, exist_ok=True)
    output = root / ('merge-%02d.sqlite' % shard)
    output.write_bytes(payload)
    return root, output


def test_saved_shard_requires_key_and_exact_bytes(tmp_path):
    identity = [[0, 'layer', 'b' * 64]]
    key = S.merge_shard_key(identity)
    old, output = shard_file(tmp_path, 'a', 3)
    S._save_shard(old, 3, key, output)
    new = tmp_path / 'derived' / '.digest-b' / 'calculation-layers'
    new.mkdir(parents=True)
    assert S._saved_shard(new, 3, key) == str(output)
    assert S._saved_shard(new, 3, S.merge_shard_key([[0, 'layer', 'c' * 64]])) is None
    output.write_bytes(b'shard bytez')                      # same size, other bytes
    assert S._saved_shard(new, 3, key) is None


def test_merge_key_does_not_move_with_the_table_code_but_moves_with_the_merge_code(monkeypatch):
    identity = [[0, 'layer', 'b' * 64]]
    before = S.merge_shard_key(identity)
    monkeypatch.setattr(S._Members, '__iter__', lambda self: iter(()))     # a bedrock table change
    assert S.merge_shard_key(identity) == before
    assert set(S.MERGE_CODE) >= {'_merge_shard', '_decoded', '_payload', '_dump', '_group_key', '_member_row',
                                 '_prepare_fragments', '_fragment_rows', '_prepared_database', '_prepare_published',
                                 '_prepare_layer', 'DG._same', 'DG._leaf_count'}
    monkeypatch.setitem(S.MERGE_CODE, '_merge_shard', lambda job: None)
    assert S.merge_shard_key(identity) != before


def test_merge_shard_output_is_unchanged_for_a_small_layer(tmp_path):
    """The merge function itself is not touched by the save points: a two-group layer merges to the same rows."""
    prepared = tmp_path / 'rows.sqlite'
    db = sqlite3.connect(prepared)
    db.execute('CREATE TABLE rows (layer INTEGER, field TEXT, ordinal INTEGER, section TEXT, payload TEXT)')
    db.execute('CREATE TABLE member_keys (ordinal INTEGER PRIMARY KEY, group_key TEXT, shard INTEGER)')
    for ordinal, (group, value) in enumerate([(1, 5), (2, 6), (1, 5)]):
        db.execute('INSERT INTO rows VALUES (0,?,?,NULL,?)', ('member_rows', ordinal,
                   json.dumps(dict(group_index=group, v=value))))
        db.execute('INSERT INTO member_keys VALUES (?,?,0)', (ordinal, S._group_key(group)))
    db.commit()
    db.close()
    output = S._merge_shard((0, [(0, 'layer', str(prepared))], str(tmp_path / 'merge-00.sqlite')))
    rows = sqlite3.connect(output).execute('SELECT group_key,column_name,ordinal FROM members ORDER BY 1,3').fetchall()
    one, two = S._group_key(1), S._group_key(2)
    assert rows == [(one, 'group_index', 0), (one, 'v', 1), (two, 'group_index', 0), (two, 'v', 1)]
