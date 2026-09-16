"""Every journal reader class exposes the same surface; this is what would have caught the cycle-1 gap.

The host installs VerifiedJournalReader for raw prefixes and FrankieCompactReader (a CompactReader)
for compact ones, and the consumers (context_session.run, NativeForecastLearner.step, the
prepared-context cache) call entries / verify / stored_tail / close / count / head_hash on whatever
they were given. The writer class EvidenceJournal shares the read surface but keeps append.
"""
import inspect
import unittest
from research.kalshi.frankie_boss.c15_journal import EvidenceJournal
from research.kalshi.frankie_boss.compact_journal import CompactReader
from research.kalshi.frankie_boss.frankie_journal_reader import FrankieCompactReader
from research.kalshi.frankie_boss.verified_journal_reader import VerifiedJournalReader

READ_SURFACE = ('entries', 'verify', 'stored_tail', 'close')
READERS = (VerifiedJournalReader, CompactReader, FrankieCompactReader)


class ReaderContract(unittest.TestCase):
    def test_every_reader_has_the_read_surface_and_refuses_append(self):
        for cls in READERS:
            for name in READ_SURFACE:
                self.assertTrue(callable(getattr(cls, name, None)), f'{cls.__name__} lacks {name}()')
            self.assertTrue(callable(getattr(cls, 'append', None)), f'{cls.__name__} must define append() to refuse it')
            source = inspect.getsource(getattr(cls, 'append'))
            self.assertIn('raise PermissionError', source, f'{cls.__name__}.append must refuse')

    def test_verify_signatures_agree(self):
        expected = ('count', 'head_hash')
        for cls in READERS + (EvidenceJournal,):
            params = inspect.signature(cls.verify).parameters
            self.assertEqual(tuple(p for p in params if p != 'self'), expected, cls.__name__)
            self.assertTrue(all(params[p].kind is inspect.Parameter.KEYWORD_ONLY for p in expected), cls.__name__)

    def test_writer_shares_the_read_surface(self):
        for name in ('entries', 'verify', 'close'):
            self.assertTrue(callable(getattr(EvidenceJournal, name, None)), name)


if __name__ == '__main__':
    unittest.main()
