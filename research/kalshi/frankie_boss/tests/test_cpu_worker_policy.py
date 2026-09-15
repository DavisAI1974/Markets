"""Focused tests for explicit native CPU policy and ordered parallel journal verification.

No market data, model inference, cloud access, or result-bearing run is performed.
"""
import pytest

from c15_journal import EvidenceJournal
from cpu_runtime import CpuRuntimePolicy, policy_from_environment
from verified_journal_reader import VerifiedJournalReader


def test_policy_keeps_journal_and_torch_budgets_separate():
    policy = CpuRuntimePolicy(journal_verify_workers=4, torch_intraop_threads=8)
    assert policy.journal_verify_workers == 4
    assert policy.torch_intraop_threads == 8
    assert policy.torch_interop_threads == 1
    assert policy.worker_internal_threads == 1


def test_policy_rejects_multithreaded_reader_workers():
    with pytest.raises(ValueError, match="single-threaded internally"):
        CpuRuntimePolicy(journal_verify_workers=4, torch_intraop_threads=8,
                         worker_internal_threads=2)


def test_policy_from_environment_requires_independent_knobs(monkeypatch):
    monkeypatch.setenv("FRANKIE_JOURNAL_VERIFY_WORKERS", "4")
    monkeypatch.setenv("FRANKIE_TORCH_INTRAOP_THREADS", "8")
    monkeypatch.setenv("FRANKIE_TORCH_INTEROP_THREADS", "1")
    policy = policy_from_environment()
    assert policy == CpuRuntimePolicy(journal_verify_workers=4,
                                      torch_intraop_threads=8,
                                      torch_interop_threads=1)


def test_parallel_reader_matches_single_worker_exactly(tmp_path):
    journal = EvidenceJournal(tmp_path / "journal.sqlite", create=True)
    for index in range(257):
        journal.append("ROW", {"index": index, "payload": bytes([index % 256]) * (1 + index % 17)})
    single = VerifiedJournalReader(journal.path, expected_count=journal.count,
                                   expected_head_hash=journal.head_hash, workers=1)
    parallel = VerifiedJournalReader(journal.path, expected_count=journal.count,
                                     expected_head_hash=journal.head_hash, workers=4)
    try:
        assert list(parallel.entries()) == list(single.entries())
        assert parallel.count == single.count == journal.count
        assert parallel.head_hash == single.head_hash == journal.head_hash
    finally:
        parallel.close(); single.close(); journal.close()


def test_environment_selects_only_journal_worker_count(tmp_path, monkeypatch):
    journal = EvidenceJournal(tmp_path / "journal.sqlite", create=True)
    journal.append("ROW", {"index": 0})
    monkeypatch.setenv("FRANKIE_JOURNAL_VERIFY_WORKERS", "3")
    monkeypatch.setenv("FRANKIE_CPU_WORKERS", "99")  # stale variable must have no effect
    reader = VerifiedJournalReader(journal.path, expected_count=journal.count,
                                   expected_head_hash=journal.head_hash)
    try:
        assert reader.workers == 3
        assert reader._executor is None  # a tail-only open spawns nothing
    finally:
        reader.close(); journal.close()


def test_parallel_reader_rejects_at_the_same_row_as_single_worker(tmp_path):
    """Corrupt one row deep inside a batch: both paths must raise the same error at the same ordinal.

    A 5-row journal cannot catch this (chunksize degenerates to 1); 64 rows with 4 workers
    puts ordinal 37 inside a multi-row chunk, which is where the chunked map failed early.
    """
    import sqlite3
    journal = EvidenceJournal(tmp_path / "journal.sqlite", create=True)
    for index in range(64):
        journal.append("ROW", {"index": index})
    count, head = journal.count, journal.head_hash
    journal.close()
    raw = sqlite3.connect(tmp_path / "journal.sqlite")
    for operation in ("update", "delete"):
        raw.execute("DROP TRIGGER forbid_" + operation)
    raw.execute("UPDATE entries SET body = X'7b7d' WHERE ordinal = 37")  # '{}' : valid JSON, invalid envelope
    raw.commit(); raw.close()
    seen = {}
    for workers in (1, 4):
        reader = VerifiedJournalReader(tmp_path / "journal.sqlite", expected_count=count, expected_head_hash=head, workers=workers)
        consumed, error = 0, None
        try:
            for _ in reader.entries():
                consumed += 1
        except Exception as exc:
            error = (type(exc).__name__, str(exc))
        finally:
            reader.close()
        seen[workers] = (consumed, error)
    assert seen[1] == seen[4]
    assert seen[1][0] == 37 and seen[1][1] is not None
