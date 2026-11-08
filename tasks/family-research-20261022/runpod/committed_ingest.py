"""Read verified blocks of an in-progress compact ingest without claiming a day receipt."""

import sqlite3
from contextlib import closing
from pathlib import Path

from research.kalshi.frankie_boss.compact_journal import FORMAT
from research.kalshi.frankie_boss.frankie_journal_reader import FrankieCompactReader
from research.kalshi.frankie_boss.verified_journal_reader import GENESIS_HASH


class CommittedIngest:
    """Single ordered consumer of an existing append-only compact journal.

    An empty read can mean the writer has yet to commit another block. Only
    sealed=True means end of stream. The caller still needs the full ingest
    receipt to publish results from the stream.
    """

    def __init__(self, path):
        self.path = Path(path)
        self.file_identity = self._file_identity()
        self.next_ordinal = 0
        self.head = GENESIS_HASH
        self.sealed = False

    def _file_identity(self):
        if self.path.is_symlink():
            raise ValueError("compact journal must be an ordinary file")
        stat = self.path.stat()
        return stat.st_dev, stat.st_ino

    def read_block(self):
        if self.sealed:
            return []
        if self._file_identity() != self.file_identity:
            raise ValueError("compact journal was replaced")
        with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            # Look up the block and terminal seal in a single short snapshot.
            db.execute("BEGIN")
            block = db.execute(
                "SELECT start,count,previous,head FROM blocks "
                "WHERE start>=? ORDER BY start LIMIT 1", (self.next_ordinal,)
            ).fetchone()
            seals = db.execute("SELECT format,count,head FROM seal LIMIT 2").fetchall()
        if block is None:
            if seals:
                if seals != [(FORMAT, self.next_ordinal, self.head)]:
                    raise ValueError("compact seal differs from the verified stream")
                self.sealed = True
            return []
        start, count, previous, head = block
        if start != self.next_ordinal or previous != self.head:
            raise ValueError("compact block continuity differs from the verified stream")
        entries, _ = FrankieCompactReader.block_task(self.path, block)
        if self._file_identity() != self.file_identity:
            raise ValueError("compact journal was replaced")
        self.next_ordinal += count
        self.head = head
        return entries
