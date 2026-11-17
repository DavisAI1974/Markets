"""ROOT tape, on the raw files held in markets-data only (no made-up message, ever)."""
import datetime as dt
import json
import os
import re
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
ROWS = Path(os.environ.get('ROOT_ROWS', REPO.parent))      # the folder that holds rows-<trade day>/ (markets-data)


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


def test_only_the_four_trade_days_reach_a_calculation():
    """Greg: none of the hours outside the 4 trade days are used in calculations. Every tick that passes the gate is
    inside one of the four trade days (6 pm to 5 pm Eastern); every trade-day tick of the four passes; nothing else."""
    from root.calendar import TRADE_DAY, trade_day_bounds
    for day in DAYS:
        week = tape.read_week(TAPE, day)
        passed = [int(r['ts_event']) for _, _, r in tape.for_calculations(week)]
        spans = [trade_day_bounds(d) for d in tape.BUILT_TRADE_DAYS]
        assert passed and all(any(o <= t < h for o, h in spans) for t in passed)
        expected = sum(1 for _, _, r, kind in tape.ticks(week) if kind == tape.TICK and
                       label(int(r['ts_event']))[0] == TRADE_DAY and label(int(r['ts_event']))[1] in tape.BUILT_TRADE_DAYS)
        assert len(passed) == expected
        rejected = {label(int(r['ts_event']))[0] if label(int(r['ts_event']))[0] != TRADE_DAY else
                    str(label(int(r['ts_event']))[1]) for _, _, r, kind in tape.ticks(week)
                    if kind == tape.TICK and not tape.calculation_eligible(int(r['ts_event']))}
        assert not rejected & {str(d) for d in tape.BUILT_TRADE_DAYS}
    week2 = tape.read_week(TAPE, dt.date(2023, 10, 17))
    assert not any(label(int(r['ts_event']))[1] == dt.date(2023, 10, 16) for _, _, r in tape.for_calculations(week2))


def test_calculation_code_cannot_read_the_tape_itself():
    """Calculations live in root/calcs/ and receive ticks only through tape.for_calculations(). A calculation file
    that names the raw readers fails here, so nothing outside the four trade days can reach one by accident."""
    forbidden = ('DBNStore', 'read_week', 'TapeFolder', '.ticks(', 'tape.ticks', '.records', 'dbn.zst',
                 # nor may one open a stored file itself: the stored rows come through tape.rows_for_calculations()
                 'parquet', 'pyarrow', 'read_table', 'stored_row_files', 'glob', 'Path', 'read_text', 'read_bytes')
    opens_a_file = re.compile(r'(?<![\w.])open\(')                  # the built-in open(, not a name ending in open
    for path in sorted((REPO / 'root' / 'calcs').glob('**/*.py')):
        text = path.read_text()
        found = [w for w in forbidden if w in text] + opens_a_file.findall(text)
        assert not found, (f'{path.relative_to(REPO)} reads the tape or a stored file itself ({found}); use '
                           f'tape.for_calculations() or tape.rows_for_calculations()')
    gate = (REPO / 'root' / 'tape.py').read_text()
    assert 'def for_calculations' in gate and 'def rows_for_calculations' in gate
    assert gate.count('calculation_eligible(') >= 3          # its definition, and once inside each gate


def test_the_rows_gate_passes_exactly_the_ticks_the_tape_gate_passes():
    """A calculation that reads the stored rows gets them through tape.rows_for_calculations(). For every trade day
    whose stored rows are at hand it passes exactly the positions tape.for_calculations() passes for that trade
    day: no row of a 5 pm to 6 pm stretch, of the Sunday start-up or of another trade day, and none missing."""
    import pytest
    held = [d for d in DAYS if (ROWS / f'rows-{d:%Y%m%d}').is_dir()]
    if not held:
        pytest.skip(f'no stored rows under {ROWS} (set ROOT_ROWS to the folder that holds rows-<trade day>/)')
    for day in held:
        week = tape.read_week(TAPE, day)
        base = tape.position_base(week)
        through_tape = [base[f] + r for f, r, record in tape.for_calculations(week)
                        if label(int(record['ts_event']))[1] == day]
        through_rows = [position for position, _ in tape.rows_for_calculations(ROWS / f'rows-{day:%Y%m%d}', day, [])]
        assert through_rows and through_rows == through_tape
