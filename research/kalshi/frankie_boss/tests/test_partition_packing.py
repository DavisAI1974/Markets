"""Partition length sets the box count, and nothing else.

Greg, 2026-09-17: about 1,200 boxes, not 7,129. Each partition becomes exactly one block, so the
old hardcoded 16 was the whole story (114,054 first-run entries / 16 = 7,129). PACKED
is now 96, which puts the first run at 1,189 boxes.

What must NOT change is what comes out: the projected entries, their order, the count and the head
hash are the journal, and they are invariant under packing. The compact container's bytes DO change
- that is the point - so this file proves the invariance directly rather than asserting it.
"""
from functools import partial
from pathlib import Path
import os
import sqlite3
import sys

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE), str(HERE / 'tests'), str(HERE.parents[2])]

from test_single_pass_finalization import fixture                    # noqa: E402
from journal_stack_execution import (MigratingConformanceReader, TARGET_BOXES,   # noqa: E402
                                     partition_entries_for)
from single_pass_finalization import finalize_snapshot               # noqa: E402
from compact_journal import CompactReader, MAX_ROWS                  # noqa: E402

RECORDS = 60            # -> 120 entries, so the standard and the old 16 differ on the same journal
PACKED = 96             # the Sunday's derived length, passed explicitly: a 120-entry fixture is far
                        # below the regime partition_entries_for() is for (see the derivation test)


def run(directory, name, partition_entries):
    source, scope, state, expected, physical = fixture(str(directory / name), RECORDS)
    target = directory / f'{name}.sqlite'
    factory = partial(MigratingConformanceReader, output=target, worker_cpus=WORKERS,
                      emit=lambda row: None, partition_entries=partition_entries)
    result = finalize_snapshot(source, scope, state, expected_scope_hash=scope.genesis_hash(),
                               expected_state_hash=state['state_hash'], expected_physical_sha256=physical,
                               reader_factory=factory)
    with CompactReader(target, expected_count=2 * RECORDS,
                       expected_head_hash=state['journal_hash']) as reader:
        entries = list(reader.entries())
    with sqlite3.connect(target) as db:
        blocks = db.execute('SELECT count(*), sum(count) FROM blocks').fetchone()
    return result, entries, blocks


WORKERS = sorted(os.sched_getaffinity(0))[1:3]


@pytest.mark.skipif(len(WORKERS) < 1, reason='needs at least one CPU besides the parent')
def test_packing_changes_the_box_count_and_nothing_that_is_the_journal(tmp_path):
    packed, packed_entries, packed_blocks = run(tmp_path, 'packed', PACKED)
    split, split_entries, split_blocks = run(tmp_path, 'split', 16)

    # The journal itself is invariant: same entries, same bytes, same order, same seal.
    assert packed_entries == split_entries
    assert packed.completion == split.completion
    assert [e['ordinal'] for e in packed_entries] == list(range(2 * RECORDS))

    # Only the packing differs, and it differs exactly as the arithmetic says.
    assert packed_blocks[1] == split_blocks[1] == 2 * RECORDS
    assert split_blocks[0] == -(-2 * RECORDS // 16)
    assert packed_blocks[0] == -(-2 * RECORDS // PACKED)
    assert packed_blocks[0] < split_blocks[0]


def test_the_standard_is_the_box_count_and_the_length_is_derived_from_it():
    assert TARGET_BOXES == 1189                       # Greg, 2026-09-17: the gold standard going forward
    sunday = 114054                                   # 57,027 records x INPUT/APPLIED
    assert partition_entries_for(sunday) == 96
    assert -(-sunday // 96) == 1189                   # the Sunday reaches the standard exactly
    assert -(-sunday // 16) == 7129                   # what the old hardcoded literal produced

    # A day too large to hold 1,189 boxes takes the biggest box the format allows and says so in
    # arithmetic, not by silently choosing something else.
    weekday = 3988716
    assert weekday / TARGET_BOXES > MAX_ROWS          # 3,355 per box would be needed; the ceiling is 256
    assert partition_entries_for(weekday) == MAX_ROWS
    assert -(-weekday // MAX_ROWS) == 15581

    # Monotone and bounded on both sides, so no day can derive a length the format refuses.
    for count in (1, 2, TARGET_BOXES, TARGET_BOXES + 1, sunday, weekday, 40_000_000):
        assert 1 <= partition_entries_for(count) <= MAX_ROWS

    # Declared, not hidden: a journal smaller than the target cannot reach it, and the derivation
    # degenerates to one entry per box. No real session is anywhere near this - the SMALLEST day we
    # will see is the Sunday reopen at 114,054 entries, 96x above the boundary - so the regime is
    # recorded rather than papered over with an invented floor.
    assert partition_entries_for(TARGET_BOXES) == 1
    assert partition_entries_for(2 * TARGET_BOXES) == 2
    assert sunday > 90 * TARGET_BOXES


@pytest.mark.parametrize('count', [0, -1, 96.0, '96', None])
def test_a_journal_size_that_is_not_a_positive_count_is_refused(count):
    with pytest.raises(ValueError, match='positive entry count'):
        partition_entries_for(count)


@pytest.mark.parametrize('bad', [0, -1, MAX_ROWS + 1, 96.0, '96'])
def test_a_partition_length_outside_the_block_row_bound_is_refused(tmp_path, bad):
    with pytest.raises(ValueError, match='partition entries'):
        MigratingConformanceReader('s.sqlite', expected_count=1, expected_head_hash='h',
                                   output=tmp_path / 'o.sqlite', worker_cpus=(1,),
                                   emit=lambda row: None, partition_entries=bad)
