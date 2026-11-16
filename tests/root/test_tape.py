"""ROOT tape, on the raw files held in markets-data only (no made-up message, ever)."""
import datetime as dt
import json
import os
import shutil
from pathlib import Path

import pytest

from root import tape
from root.calendar import STARTUP, label

REPO = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get('MARKETS_DATA', REPO.parent / 'markets-data'))
TAPE = DATA / 'data' / 'nymex_mbo' / 'ng_v0_oct2023'
pytestmark = pytest.mark.skipif(not (TAPE / 'MANIFEST.json').exists(),
                                reason=f'the raw tape is not at {TAPE}; set MARKETS_DATA')
DAYS = [dt.date(2023, 10, d) for d in (2, 3, 17, 18)]


@pytest.fixture(scope='module')
def receipts():
    return {d: tape.check_week(TAPE, d) for d in DAYS}


def test_every_record_is_accounted_for(receipts):
    manifest = {f['file']: f['records'] for f in json.loads((TAPE / 'MANIFEST.json').read_text())['files']}
    for r in receipts.values():
        for f in r['files']:
            assert f['records'] == manifest[f['file']] == f['vendor_snapshot_records'] + f['ticks']
            assert sum(f['ticks_for_this_box'].values()) == f['ticks']
            assert sum(f['ticks_by_label'].values()) == f['ticks']


def test_the_sunday_relisting_is_ticks_and_later_files_open_with_the_vendor_restatement(receipts):
    week = tape.read_week(TAPE, dt.date(2023, 10, 2))
    sunday, monday = week
    assert sunday.vendor_snapshot == 0 and sunday.records['action'][0] == tape.CLEAR
    snap = tape.flag_bits()['F_SNAPSHOT']
    relisted = sunday.records[1:343]
    assert ((relisted['flags'] & snap) != 0).all()
    assert all(label(t)[0] == STARTUP for t in relisted['ts_event'].tolist())
    assert monday.vendor_snapshot == 733
    files = receipts[dt.date(2023, 10, 2)]['files']
    assert files[1]['vendor_snapshot_actions'] == {'R': 1, 'A': 732}


def test_one_contract_and_every_field(receipts):
    for r in receipts.values():
        assert r['contract_instrument_id'] == 150611
        for f in r['files']:
            assert set(tape.record_fields()) <= set(f['fields'])


def test_what_each_box_writes(receipts):
    oct2, oct3 = receipts[dt.date(2023, 10, 2)]['files'], receipts[dt.date(2023, 10, 3)]['files']
    assert oct2[0]['ticks_for_this_box'] == {'written': oct2[0]['ticks']}          # the start-up is written for Oct 2
    assert oct3[0]['ticks_for_this_box'] == {'warm-up': oct3[0]['ticks']}         # and is warm-up for Oct 3
    stretch_before_oct3 = oct3[1]['ticks_by_label']['5 pm to 6 pm stretch']
    assert oct3[1]['ticks_for_this_box']['written'] == stretch_before_oct3 + oct3[1]['ticks_by_label'][
        'trade day 2023-10-03']
    oct17 = receipts[dt.date(2023, 10, 17)]['files']
    assert oct17[0]['ticks_for_this_box'] == {'warm-up': oct17[0]['ticks']}       # Oct 16 is not built


def test_no_maybe_bad_book_and_bad_receive_times_only_at_the_start_up(receipts):
    for r in receipts.values():
        for f in r['files']:
            assert f['tick_flags']['F_MAYBE_BAD_BOOK'] == 0
            if f['file'].endswith(('20231001.dbn.zst', '20231015.dbn.zst')):
                assert f['tick_flags']['F_BAD_TS_RECV'] == f['ticks_by_label'][STARTUP]
            else:
                assert f['tick_flags']['F_BAD_TS_RECV'] == 0


def copy_tape(dst: Path, drop: str = None, change_sha: str = None):
    manifest = json.loads((TAPE / 'MANIFEST.json').read_text())
    for f in manifest['files']:
        if f['file'] != drop:
            os.symlink(TAPE / f['file'], dst / f['file'])
        if f['file'] == change_sha:
            f['sha256'] = '0' * len(f['sha256'])
    (dst / 'MANIFEST.json').write_text(json.dumps(manifest))


def test_a_withheld_file_is_refused(tmp_path):
    copy_tape(tmp_path, drop='NG_v0_mbo_20231016.dbn.zst')
    with pytest.raises(FileNotFoundError, match='NG_v0_mbo_20231016'):
        tape.read_week(tmp_path, dt.date(2023, 10, 18))


def test_a_changed_fingerprint_is_refused(tmp_path):
    copy_tape(tmp_path, change_sha='NG_v0_mbo_20231017.dbn.zst')
    with pytest.raises(ValueError, match='NG_v0_mbo_20231017.*fingerprint'):
        tape.read_week(tmp_path, dt.date(2023, 10, 18))
