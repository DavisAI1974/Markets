import sqlite3
import tempfile
import unittest
from pathlib import Path

from research.kalshi.frankie_boss.c15_journal import SCHEMA, canonical_bytes, evidence_hash, pack
from research.kalshi.frankie_boss.compact_journal import CompactReader, CompactWriter

from committed_ingest import CommittedIngest


def add(writer, payload):
    envelope = dict(schema=SCHEMA, ordinal=writer.count, previous_hash=writer.head_hash,
                    kind="INPUT", payload=payload)
    writer.add((writer.count, "INPUT", canonical_bytes(pack(envelope)), evidence_hash(envelope)))


class CommittedIngestTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "journal.compact.sqlite"

    def test_follows_committed_blocks_while_writer_is_open(self):
        with CompactWriter(self.path) as writer:
            ingest = CommittedIngest(self.path)
            add(writer, {"cursor": 0, "record": {"wire_bytes": b"first"}})
            self.assertEqual(ingest.read_block(), [])
            self.assertFalse(ingest.sealed)

            writer.flush()
            first = ingest.read_block()
            self.assertEqual(first[0]["payload"]["record"]["wire_bytes"], b"first")
            self.assertEqual(ingest.read_block(), [])
            self.assertFalse(ingest.sealed)

            add(writer, {"cursor": 1, "record": {"wire_bytes": b"second"}})
            writer.seal(expected_count=writer.count, expected_head_hash=writer.head_hash)
            second = ingest.read_block()
            self.assertEqual([entry["ordinal"] for entry in first + second], [0, 1])
            self.assertEqual(ingest.read_block(), [])
            self.assertTrue(ingest.sealed)
            with CompactReader(self.path, expected_count=2, expected_head_hash=writer.head_hash) as reader:
                self.assertEqual(first + second, list(reader.entries()))

    def test_refuses_a_block_with_the_wrong_previous_hash(self):
        with CompactWriter(self.path) as writer:
            add(writer, {"cursor": 0})
            writer.flush()
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE blocks SET previous='wrong'")
        with self.assertRaisesRegex(ValueError, "continuity"):
            CommittedIngest(self.path).read_block()

    def test_refuses_a_seal_that_disagrees_with_the_consumed_prefix(self):
        with CompactWriter(self.path) as writer:
            add(writer, {"cursor": 0})
            writer.seal(expected_count=writer.count, expected_head_hash=writer.head_hash)
        ingest = CommittedIngest(self.path)
        self.assertEqual(len(ingest.read_block()), 1)
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE seal SET head='wrong'")
        with self.assertRaisesRegex(ValueError, "seal"):
            ingest.read_block()


if __name__ == "__main__":
    unittest.main()
