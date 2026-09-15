"""Focused tests for explicit CPU policy and ordered parallel journal verification.

No market data, model inference, cloud access, or result-bearing run is performed.
"""
import os

from c15_journal import EvidenceJournal
from cpu_runtime import CpuRuntimePolicy
from verified_journal_reader import VerifiedJournalReader


def test_policy_defaults_to_declared_32_cpu_budget():
    policy = CpuRuntimePolicy()
    assert policy.workers == 32
    assert policy.torch_intraop_threads == 32
    assert policy.torch_interop_threads == 1
    assert policy.worker_internal_threads == 1


def test_parallel_reader_matches_single_worker_exactly(tmp_path, monkeypatch):
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


def test_environment_selects_worker_count(tmp_path, monkeypatch):
    journal = EvidenceJournal(tmp_path / "journal.sqlite", create=True)
    journal.append("ROW", {"index": 0})
    monkeypatch.setenv("FRANKIE_CPU_WORKERS", "3")
    reader = VerifiedJournalReader(journal.path, expected_count=journal.count,
                                   expected_head_hash=journal.head_hash)
    try:
        assert reader.workers == 3
    finally:
        reader.close(); journal.close()
