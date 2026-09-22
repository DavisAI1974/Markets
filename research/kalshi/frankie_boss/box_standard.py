"""The box standard (Greg, 2026-09-17: TARGET_BOXES = 1189 is the gold standard for every day we ingest going forward).

Each partition of a journal becomes exactly one box; the entries per box are DERIVED from the day's entry count so a day
of the Sunday's size (114,054 entries) lands on 1,189 boxes of 96, and a big day clamps at the format's MAX_ROWS ceiling
and takes the fewest boxes the format allows (arithmetic, not a choice). Importable from the package and flat (the ingest
tool runs on the box with only the markets root on PYTHONPATH; journal_stack_execution and the tests import flat).
"""
try:
    from .compact_journal import MAX_ROWS
except ImportError:
    from compact_journal import MAX_ROWS

TARGET_BOXES = 1189


def partition_entries_for(count, *, target=TARGET_BOXES, ceiling=MAX_ROWS):
    """Entries per partition, and therefore per box, for a journal of `count` entries."""
    if type(count) is not int or count <= 0:
        raise ValueError('positive entry count required')
    return max(1, min(ceiling, -(-count // target)))
