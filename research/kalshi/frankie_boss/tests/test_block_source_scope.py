"""The block scope binds only the committed, hash-pinned, seam-checked manifest."""
import json
from pathlib import Path

import pytest

from block_source_scope import block_source_scope
from causal_prefix import ScopeKind
from raw_mbo_source_manifest import manifest_hash

MANIFEST = Path(__file__).resolve().parents[1] / 'blocks' / 'BLOCK_20211004_20211006_SOURCE_MANIFEST.json'


def _manifest():
    return json.loads(MANIFEST.read_bytes())


def test_committed_block_manifest_binds_in_replay_order():
    manifest = _manifest()
    scope = block_source_scope(manifest, expected_manifest_hash=manifest['manifest_hash'])
    assert scope.kind is ScopeKind.RESULT_BEARING and scope.scope_id == manifest['manifest_hash']
    assert [m.member_key for m in scope.members] == [s['member_key'] for s in manifest['sources']]
    assert scope.members[0].mbo_records == 57027                       # Sunday re-pinned as member 0
    assert sum(m.mbo_records for m in scope.members) == manifest['total_mbo_records'] == 6471475
    assert scope.member_cursor_bounds(1) == (57027, 57027 + 1994358)


def test_block_manifest_hash_seams_and_member_fields_are_refused_when_wrong():
    manifest = _manifest()
    with pytest.raises(ValueError, match='pinned hash'):
        block_source_scope(manifest, expected_manifest_hash='0' * 64)
    tampered = dict(manifest); tampered['sources'] = [dict(s, mbo_records=s['mbo_records'] + 1) for s in manifest['sources']]
    with pytest.raises(ValueError, match='pinned hash'):                # the body no longer hashes to the pin
        block_source_scope(tampered, expected_manifest_hash=manifest['manifest_hash'])
    unsafe = dict(manifest, member_seams_close_groups=False); unsafe['manifest_hash'] = manifest_hash(unsafe)
    with pytest.raises(ValueError, match='F_LAST'):
        block_source_scope(unsafe, expected_manifest_hash=unsafe['manifest_hash'])
    reordered = dict(manifest, sources=list(reversed(manifest['sources']))); reordered['manifest_hash'] = manifest_hash(reordered)
    with pytest.raises(ValueError, match='replay order'):
        block_source_scope(reordered, expected_manifest_hash=reordered['manifest_hash'])
