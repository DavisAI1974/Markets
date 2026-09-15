"""New Frankie integration boundaries; no source replay or model inference."""
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from c15_journal import EvidenceJournal, pack
from compact_journal import CompactWriter, CompactReader
from frankie_journal_reader import FrankieCompactReader, available_cpus, worker_budget
from compact_journal_snapshot import snapshot_compact_prefix
from verified_journal_reader import VerifiedJournalReader


class FrankieCompactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original = self.root/'source.sqlite'
        journal = EvidenceJournal(self.original, create=True)
        for cursor in range(5):
            raw = dict(flags=128, exact_integer=10**18+cursor)
            journal.append('INPUT',dict(cursor=cursor,record=raw,
                source_member_index=0,session_id='s'))
            journal.append('APPLIED',dict(cursor=cursor,raw_record=raw,
                source_member_index=0,session_id='s',
                normalized=dict(ts_event_ns=cursor,ts_recv_ns=cursor+1),
                terminal_prefix_hash=str(cursor)*64,record_count=cursor+1,group_count=cursor+1,
                observation=dict(orders=[dict(id=9,price=100,size=3)]),
                full_frankie_fields=dict(bytes=b'\x00\xff',tuple=(False,-0.0),list=[1,True])))
        self.count,self.head=journal.count,journal.head_hash
        self.original_entries=list(journal.entries())
        journal.close()
        db=sqlite3.connect(self.original)
        self.rows=db.execute('SELECT ordinal,kind,body,digest FROM entries ORDER BY ordinal').fetchall()
        db.close()
        self.compact=self.root/'compact.sqlite'
        with CompactWriter(self.compact) as writer:
            for i,row in enumerate(self.rows):
                writer.add(row)
                if i%4==3: writer.flush()
            writer.seal(expected_count=self.count,expected_head_hash=self.head)
        self.digest=hashlib.sha256(self.compact.read_bytes()).hexdigest()

    def test_parallel_full_envelopes_and_progress(self):
        probes=[]
        with FrankieCompactReader(self.compact,expected_count=self.count,
                expected_head_hash=self.head,workers=2,emit=probes.append) as reader:
            self.assertEqual(pack(list(reader.entries())),pack(self.original_entries))
        self.assertEqual(probes[-1]['percent'],100)
        self.assertLessEqual(len(probes[-1]['worker_cpus']),2)

    def test_cutoff_inside_block_keeps_exact_bytes_and_reuses_whole_blocks(self):
        target=self.root/'prefix.sqlite'
        receipt=snapshot_compact_prefix(self.original,target,compact_path=self.compact,
            compact_sha256=self.digest,parent_count=self.count,parent_head_hash=self.head,
            through_cursor=2,workers=2)
        self.assertEqual(receipt['journal_count'],6)
        with CompactReader(target,expected_count=6,expected_head_hash=self.rows[5][3]) as reader:
            self.assertEqual(list(reader.rows()),self.rows[:6])
        with sqlite3.connect(target) as dest, sqlite3.connect(self.compact) as source:
            self.assertEqual(dest.execute('SELECT body FROM blocks WHERE start=0').fetchone(),
                             source.execute('SELECT body FROM blocks WHERE start=0').fetchone())
        dest.close();source.close()
        with FrankieCompactReader(target,expected_count=6,
                expected_head_hash=self.rows[5][3],workers=1) as reader:
            self.assertEqual(pack(list(reader.entries())),pack(self.original_entries[:6]))
        self.assertEqual(hashlib.sha256(self.compact.read_bytes()).hexdigest(),self.digest)

    def test_broken_worker_seam_is_rejected(self):
        with sqlite3.connect(self.compact) as db:
            db.execute("UPDATE blocks SET previous=? WHERE start=4",('f'*64,))
        db.close()
        with FrankieCompactReader(self.compact,expected_count=self.count,
                expected_head_hash=self.head,workers=2) as reader:
            with self.assertRaises(ValueError):
                list(reader.entries())

    def test_physical_pin_mismatch_creates_no_prefix(self):
        target=self.root/'no-prefix.sqlite'
        with self.assertRaisesRegex(ValueError,'physical'):
            snapshot_compact_prefix(self.original,target,compact_path=self.compact,
                compact_sha256='0'*64,parent_count=self.count,parent_head_hash=self.head,through_cursor=2)
        self.assertFalse(target.exists())

    def test_cpu_budget_uses_allocation_and_reserves_consumer(self):
        cpus=available_cpus()
        self.assertEqual(worker_budget(48),tuple((cpus[1:] or cpus)[:48]))
        with self.assertRaises(ValueError):worker_budget(True)


if __name__=='__main__':
    unittest.main()
