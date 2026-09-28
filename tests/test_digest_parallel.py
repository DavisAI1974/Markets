"""The parallel table writer against the serial ones (review 2026-09-28, required item 2): the same rows give the same
bytes from frankie_box_digest_parallel.write_table_parallel (rows split into parts on helper processes),
frankie_box_digest_stream.write_table and frankie_box_digest_render.render_table, for every DIGEST_V8 form, including
the forms whose state crosses a part boundary (keys-once objects read against the previous row's last object, packed
lists against the previous row's first, dictionary numbering and the cutoff decided at the first occurrence)."""
import os
from pathlib import Path
import sys

import pytest

import test_frankie_box_digest_render as FX

BOX = Path(__file__).resolve().parents[1] / 'deploy/aws/box'
sys.path.insert(0, str(BOX))
import frankie_box_digest_parallel as P   # noqa: E402
import frankie_box_digest_render as DG    # noqa: E402
import frankie_box_digest_stream as TS    # noqa: E402

CPUS = sorted(os.sched_getaffinity(0))[:2]


def _v8_rows():
    """Rows that exercise every V8 form (structure only; the values are arbitrary test integers and labels)."""
    rows = []
    for i in range(40):
        row = dict(group_index=i, recv_ns=1000 + 7919 * i * i, emitted_at_recv_ns=1000 + 7919 * i * i,
                   episodes=[dict(opened_recv_ns=500 + i, closed_recv_ns=500 + i + (i % 3), basis='BIRTH' if i % 4 else 'RESET',
                                  note='residual of initial ahead, current ahead; fills' if i % 5 == 0 else 'plain')
                             for _ in range(1 + i % 3)],
                   offsets=[0, 0, 1, 0, -1, 0, 0, 0][:3 + i % 5], offsets_count=3 + i % 5,
                   label='a repeated label long enough to be worth a dictionary entry' if i % 2 else 'SA',
                   nested=[dict(a=dict(b=[1, 2]), c=None, d=True, e=0.25)] if i % 6 == 0 else [])
        if i % 3 == 0:
            row['sparse_a'] = i
            row['sparse_b'] = 'x%d' % (i % 2)
        rows.append(row)
    return rows


def _tables():
    tables = dict(FX._tables())
    tables['v8'] = _v8_rows()
    for name, rows in DG.bedrock_tables(FX._bedrock_files()).items():
        tables[name] = rows
    for name, rows in DG.bedrock_tables(FX._section_files()).items():
        tables.setdefault(name, rows)
    tables.pop('legacy_structure_observables')      # cross-table derived: never written in parallel
    return tables


@pytest.mark.parametrize('name', sorted(_tables()))
def test_parallel_bytes_equal_the_serial_writers(tmp_path, name):
    rows = _tables()[name]
    expected = DG.render_table(name, rows)
    assert DG._same(DG.parse_table(expected)[1], [dict(r) for r in rows])
    serial = tmp_path / 'serial.txt'
    TS.write_table(serial, name, rows, tmp_path / 'serial-scratch')
    assert serial.read_text(encoding='utf-8') == expected
    size = max(1, -(-len(rows) // 3))
    specs = [dict(kind='inline', rows=rows[i:i + size]) for i in range(0, len(rows), size)] or [dict(kind='inline', rows=[])]
    parallel = tmp_path / 'parallel.txt'
    proof = P.write_table_parallel(parallel, name, specs, tmp_path / 'parallel-scratch', CPUS, reserve=0)
    assert proof['verified'] is True and proof['rows'] == len(rows)
    assert parallel.read_text(encoding='utf-8') == expected


def test_v8_rows_use_every_v8_form():
    block = DG.render_table('v8', _v8_rows())
    head, _, body = block.partition('\n')
    lines = block.split('\n')
    assert any(line.startswith('shapes: episodes=basis,closed_recv_ns,note,opened_recv_ns') for line in lines)
    assert any(line.startswith('lengths: ') and 'offsets_count=offsets' in line for line in lines)
    assert ' R' in body or '\tR' in body                     # keys-once objects
    assert ' P' in body or '\tP' in body or '\nP' in body    # packed digits
    assert '<' in body                                        # a same-row reference (emitted_at_recv_ns == recv_ns)
    columns = head.split('columns: ')[1].split('\t')
    assert columns.index('sparse_a') > columns.index('label')   # the sparse columns sit after the ones every row carries
    assert 'SSA' in body and '"SA"' not in block              # a two-letter string stays inline (the dictionary cutoff)
    assert '@0="a repeated label long enough to be worth a dictionary entry"' in block


def test_the_disk_reserve_is_a_parameter(tmp_path):
    rows = _v8_rows()
    with pytest.raises(P.DiskReserve):
        P.write_table_parallel(tmp_path / 't.txt', 'v8', [dict(kind='inline', rows=rows)], tmp_path / 'scratch', CPUS,
                               reserve=1 << 62)


def _fuzz_tables(seed, count):
    import random
    rnd = random.Random(seed)
    keys = ['a', 'recv_ns', 'b_event_ns', 'k', 'label']
    names = ['recv_ns', 'emitted_at_recv_ns', 'x', 'objs', 'ids', 'ids_count', 's', 'f']

    def scalar():
        return rnd.choice([None, True, False, 0, 1, -1, 7, -12345678901, 2 ** 63 - 1, 0.5, -0.0, float('nan'), float('inf'), 1e-9,
                           'x', '', 'a,b', 'c;d', '^', '<3', '?', 'Jnot json', 'S', '-', 'T', 'with space', 'tab\there',
                           [1, 2], {'n': 1}, [], {}])

    def value(c):
        if c == 'objs':
            if rnd.random() < 0.15:
                return rnd.choice([[], None, [1, 2], [{'a': 1}, 3]])
            return [{k: (rnd.randint(-5, 5) * rnd.choice([1, 1000003]) if k.endswith('_ns') and rnd.random() < 0.8 else scalar())
                     for k in rnd.sample(keys, rnd.randint(0, len(keys)))} for _ in range(rnd.randint(1, 4))]
        if c == 'ids':
            return [rnd.randint(-3, 3) * rnd.choice([1, 1000]) for _ in range(rnd.randint(0, 9))]
        if c in ('recv_ns', 'emitted_at_recv_ns', 'x'):
            return rnd.choice([rnd.randint(0, 10 ** 6) * 1000003, 5, None, True]) if rnd.random() < 0.3 else 1633298400000000000 + rnd.randint(0, 10 ** 9)
        top = scalar()
        return '{}' if top == {} else top    # a top-level empty mapping is spelled as a string by DG._spell before any table

    for _ in range(count):
        cols = rnd.sample(names, rnd.randint(1, len(names)))
        rows = []
        for i in range(rnd.randint(1, 12)):
            row = {c: value(c) for c in cols if rnd.random() < 0.85}
            if 'ids' in row and 'ids_count' in cols and rnd.random() < 0.9:
                row['ids_count'] = len(row['ids'])
            if 'recv_ns' in row and 'emitted_at_recv_ns' in cols and rnd.random() < 0.6:
                row['emitted_at_recv_ns'] = row['recv_ns']
            if rows and rnd.random() < 0.25:
                row = dict(rows[-1])
            if row:
                rows.append(row)
        if rows:
            yield rows


def test_v8_fuzz_round_trips_and_the_serial_writers_agree(tmp_path):
    for i, rows in enumerate(_fuzz_tables(20260928, 600)):
        block = DG.render_table('fuzz', rows)
        assert DG._same(DG.parse_table(block)[1], [dict(r) for r in rows]), block
        if i % 20 == 0:
            path = tmp_path / ('s%d.txt' % i)
            TS.write_table(path, 'fuzz', rows, tmp_path / ('scratch-%d' % i))
            assert path.read_text(encoding='utf-8') == block


def test_v8_fuzz_parallel_parts_agree(tmp_path):
    for i, rows in enumerate(_fuzz_tables(9, 12)):
        size = max(1, -(-len(rows) // 3))
        specs = [dict(kind='inline', rows=rows[j:j + size]) for j in range(0, len(rows), size)]
        path = tmp_path / ('p%d.txt' % i)
        P.write_table_parallel(path, 'fuzz', specs, tmp_path / ('scratch-%d' % i), CPUS, reserve=0)
        assert path.read_text(encoding='utf-8') == DG.render_table('fuzz', rows)
