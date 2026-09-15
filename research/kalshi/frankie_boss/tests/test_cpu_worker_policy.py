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
    finally:
        reader.close(); journal.close()
