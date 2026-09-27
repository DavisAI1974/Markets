"""Adopting a stopped ROOT's merge shards: only provably complete shards from byte-identical merge code get receipts,
and the restarted merge then finds and reuses them."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pytest

BOX = Path(__file__).resolve().parents[1] / 'deploy/aws/box'
sys.path.insert(0, str(BOX))

import frankie_box_adopt_merge as A  # noqa: E402
import frankie_box_digest_sources as S  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def prepared_layer(layers, index, pin):
    root = layers / ('prepare-%06d' % index)
    root.mkdir(parents=True)
    database = root / 'rows.sqlite'
    db = sqlite3.connect(database)
    db.execute('CREATE TABLE rows (layer INTEGER, field TEXT, ordinal INTEGER, section TEXT, payload TEXT)')
    db.execute('CREATE TABLE member_keys (ordinal INTEGER PRIMARY KEY, group_key TEXT, shard INTEGER)')
    for ordinal in range(3 * S.SHARDS):
        group = S._group_key(ordinal)
        db.execute('INSERT INTO rows VALUES (?,?,?,NULL,?)', (index, 'member_rows', ordinal,
                   json.dumps({'group_index': ordinal, 'v%d' % index: index})))
        db.execute('INSERT INTO member_keys VALUES (?,?,?)', (ordinal, group, ordinal % S.SHARDS))
    db.commit()
    db.close()
    receipt = dict(schema=S.PREPARED_SCHEMA, index=index, pin={k: pin.get(k) for k in ('path', 'bytes', 'sha256', 'encoding')},
                   database=str(database), database_bytes=database.stat().st_size,
                   meta=dict(status='derived'), counts=dict(member_rows=3 * S.SHARDS))
    (root / 'receipt.json').write_text(json.dumps(receipt))
    return database


@pytest.fixture
def stopped_root(tmp_path):
    directory = tmp_path / 'full-root'
    work = directory / 'work'
    layers = work / 'derived' / '.digest-old' / 'calculation-layers'
    layers.mkdir(parents=True)
    (directory / 'calculation.lock').touch()
    pins = {'bedrock.a': dict(path='/p/a', bytes=1, sha256='a' * 64, encoding='gzip-json', bedrock=True),
            'bedrock.b': dict(path='/p/b', bytes=2, sha256='b' * 64, encoding='gzip-json', bedrock=True)}
    receipt = dict(layers=dict({'legacy_price': dict(status='derived', sha256='c' * 64)}, **pins))
    (work / 'derive.json').write_text(json.dumps(receipt))
    sources = [(i, name, str(prepared_layer(layers, i, pin))) for i, (name, pin) in enumerate(pins.items())]
    for shard in range(S.SHARDS):
        S._merge_shard((shard, sources, str(layers / ('merge-%02d.sqlite' % shard))))
    return directory, layers, [[i, name, pin['sha256']] for i, (name, pin) in enumerate(pins.items())]


def test_adopted_shards_are_found_by_the_restarted_merge(stopped_root):
    directory, layers, identity = stopped_root
    report = A.adopt(directory, '.digest-old', REPO)
    assert report['adopted'] == S.SHARDS
    new_root = layers.parent.parent / '.digest-new' / 'calculation-layers'
    key = S.merge_shard_key(identity)
    assert all(S._saved_shard(new_root, shard, key) == str(layers / ('merge-%02d.sqlite' % shard))
               for shard in range(S.SHARDS))


def test_refuses_while_the_root_is_locked(stopped_root):
    directory, layers, _ = stopped_root
    with (directory / 'calculation.lock').open('a') as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # flock locks are per open file description: a second open in this process conflicts like another process
        with pytest.raises(ValueError, match='still running'):
            A.adopt(directory, '.digest-old', REPO)
    assert not list(layers.glob('merge-*.save.json'))


def test_a_shard_with_a_journal_or_no_committed_rows_is_not_adopted(stopped_root):
    directory, layers, _ = stopped_root
    (layers / 'merge-03.sqlite-journal').write_bytes(b'hot')
    db = sqlite3.connect(layers / 'merge-05.sqlite')
    db.execute('DELETE FROM members')
    db.commit()
    db.close()
    report = A.adopt(directory, '.digest-old', REPO)
    by_shard = {r['shard']: r for r in report['shards']}
    assert not by_shard[3]['adopted'] and 'journal' in by_shard[3]['reason']
    assert not by_shard[5]['adopted'] and 'no committed rows' in by_shard[5]['reason']
    assert report['adopted'] == S.SHARDS - 2
    assert not (layers / 'merge-03.save.json').exists() and not (layers / 'merge-05.save.json').exists()


def test_changed_old_merge_code_adopts_nothing(stopped_root, tmp_path):
    directory, layers, _ = stopped_root
    old = tmp_path / 'old'
    shutil.copytree(BOX, old / 'deploy/aws/box')
    source = old / 'deploy/aws/box/frankie_box_digest_sources.py'
    text = source.read_text()
    source.write_text(text.replace("    db.execute('PRAGMA cache_size=-65536')", "    db.execute('PRAGMA cache_size=-65537')", 1))
    with pytest.raises(ValueError, match='_merge_shard'):
        A.adopt(directory, '.digest-old', old)
    assert not list(layers.glob('merge-*.save.json'))


def test_an_existing_receipt_is_never_overwritten(stopped_root):
    directory, layers, _ = stopped_root
    (layers / 'merge-00.save.json').write_text('{}')
    report = A.adopt(directory, '.digest-old', REPO)
    assert report['shards'][0] == dict(shard=0, adopted=False, reason='a receipt already exists')
    assert (layers / 'merge-00.save.json').read_text() == '{}'


def test_the_running_root_runtime_has_the_same_merge_code_as_this_checkout(tmp_path):
    """b35e79b7 is the runtime of the ROOT running on 2026-09-27; its shards are adoptable only if this holds."""
    old = tmp_path / 'b35'
    old.mkdir()
    archive = subprocess.run(['git', '-C', str(REPO), 'archive', 'b35e79b7', 'deploy/aws/box'], capture_output=True, check=False)
    if archive.returncode:
        pytest.skip('b35e79b7 is not in this clone')
    subprocess.run(['tar', '-x', '-C', str(old)], input=archive.stdout, check=True)
    assert A.old_merge_code(old / 'deploy/aws/box') == S.merge_shard_key([])['code']
