"""The Monday trading-day manifest derives from the STAGED block manifest's own measured halt counts (real data in git)."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'research' / 'kalshi' / 'frankie_boss' / 'operations'))
import derive_trading_day_manifest as D  # noqa: E402

BLOCK = json.loads((ROOT / 'research/kalshi/frankie_boss/blocks/BLOCK_20211004_20211006_SOURCE_MANIFEST.json').read_bytes())


def test_monday_takes_the_whole_20211003_partition_and_the_pre_halt_records_of_20211004():
    body = D.derive(BLOCK, '20211004')
    assert [(s['member_key'], s['mbo_records']) for s in body['sources']] == [
        ('glbx-mdp3-20211003.mbo.dbn.zst', 57027), ('glbx-mdp3-20211004.mbo.dbn.zst', 1975176)]
    assert body['total_mbo_records'] == 57027 + 1975176 == 2032203
    assert body['partial_members'] == [dict(member_key='glbx-mdp3-20211004.mbo.dbn.zst', partition_mbo_records=1994358, take=1975176,
                                            reason='records before the 21:00Z halt belong to this trading day; the rest are the next day')]
    assert body['block'] == body['trading_day'] == '20211004' and body['derived_from']['manifest_hash'] == BLOCK['manifest_hash']
    assert body['sources'][1]['sha256'] == BLOCK['sources'][1]['sha256'] and body['sources'][1]['size_bytes'] == BLOCK['sources'][1]['size_bytes']
    assert body['ingested'] is False and body['prefix'] == BLOCK['prefix'] and body['bucket'] == BLOCK['bucket']
    assert D.manifest_hash(body) == body['manifest_hash']
    D.block_source_scope(body, expected_manifest_hash=body['manifest_hash'])


def test_a_weekday_whose_partition_would_contribute_a_tail_is_refused_by_itself():
    with pytest.raises(ValueError, match='contributes a tail'):
        D.derive(BLOCK, '20211005')                    # Tuesday = the 20211004 partition's post-halt records + 20211005's pre-halt


def test_a_day_no_partition_touches_is_refused():
    with pytest.raises(ValueError, match='no partition of the block contributes'):
        D.derive(BLOCK, '20211011')


def test_a_manifest_whose_hash_or_sessions_do_not_reconcile_is_refused():
    bad = dict(BLOCK, manifest_hash='0' * 64)
    with pytest.raises(ValueError, match='hash-bound block source manifest'):
        D.derive(bad, '20211004')
    bad = json.loads(json.dumps(BLOCK)); bad['sessions'][1]['before_halt'] -= 1; bad['manifest_hash'] = D.manifest_hash(bad)
    with pytest.raises(ValueError, match='do not reconcile'):
        D.derive(bad, '20211004')
