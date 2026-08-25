from __future__ import annotations

import json
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from research.kalshi.frankie_causal_operational_context_20260824 import (
    CausalDecisionStateSnapshotAdapter,
    RegistryCoverageOracle,
)
from research.kalshi.frankie_causal_runtime_tools_20260824 import (
    CausalEvidenceJournal,
    CausalRuntimeToolBackend,
    MAX_HISTORY_RECORD_SCAN,
    MAX_RAW_EVENT_RECORD_SPAN,
    MAX_RAW_EVENTS,
    MAX_TOOL_OUTPUT_BYTES,
    validate_causal_evidence_journal,
)
from research.kalshi.frankie_full_stack_runtime_contracts_20260824 import CausalPrefixBinding
from research.kalshi.ng_exhaustion_frankie_fullstack_october_20260824 import (
    CausalSecondJsonlWriter,
)


def _binding(cutoff: float = 10.5) -> CausalPrefixBinding:
    return CausalPrefixBinding(
        run_id="run-tools",
        causal_cutoff=cutoff,
        event_known_by=cutoff,
        causal_prefix_hash="1" * 64,
        state_prefix_hash="2" * 64,
        knowledge_manifest_hash="3" * 64,
    )


def _snapshot():
    paths = tuple(f"block_{b:02d}.field_{i:02d}" for b in range(44) for i in range(44))
    oracle = RegistryCoverageOracle.create(
        paths=paths,
        source_ids=("fixture-registry",),
        source_hashes=("4" * 64,),
    )
    return CausalDecisionStateSnapshotAdapter(oracle).snapshot(
        run_id="run-tools",
        decision_day="20211001",
        evaluated_at=10.5,
        canonical_state={"block_00": {"field_00": 1, "field_01": None}},
        canonical_source_id="fixture-s135",
        canonical_source_sha256="5" * 64,
    )


def _causal_file(path: Path) -> None:
    writer = CausalSecondJsonlWriter.create(path, run_id="run-tools", flush_interval_records=1)
    for sequence, cutoff in enumerate((10.0, 20.0)):
        writer.append_second(
            binding=_binding(cutoff),
            state={"sequence": sequence, "raw_events": [{"id": f"e{sequence}", "known_by": cutoff}]},
            delta={"sequence": sequence},
            integrity={"ok": True},
            decision={"type": "NO_LOCK", "owner": "CAUSAL_OBSERVATION_ONLY", "primary_lock": False},
        )
    writer.close()


def _stable_hash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


class CausalRuntimeToolTest(unittest.TestCase):
 def test_realized_weather_proxy_is_quarantined_identically_in_both_lanes(self) -> None:
  with tempfile.TemporaryDirectory() as directory:
   paths = tuple(f"block_{b}.field_{i}" for b in range(44) for i in range(44)) + ("weather.gw_hdd",)
   oracle = RegistryCoverageOracle.create(
       paths=paths, source_ids=("registry",), source_hashes=("a" * 64,)
   )
   snapshot = CausalDecisionStateSnapshotAdapter(oracle).snapshot(
       run_id="run-tools", decision_day="20211001", evaluated_at=10.5,
       canonical_state={"weather": {"gw_hdd": 99.0}},
       canonical_source_id="S135", canonical_source_sha256="b" * 64,
   )
   journal = CausalEvidenceJournal.create(Path(directory) / "evidence.jsonl", run_id="run-tools")
   backend = CausalRuntimeToolBackend(
       snapshot=snapshot, binding=_binding(), causal_state_path=None,
       evidence_journal=journal, commit_sha="c" * 40,
   )
   for lane in ("S135_CONTROL", "FULL_PROVISIONAL_COMBINED"):
    result = backend.open_session(_binding(), lane).execute(
        f"weather-{lane}", "decision_state_search",
        {"query": "weather.gw_hdd", "cursor": 0, "limit": 10},
    ).result
    self.assertEqual(len(result["fields"]), 1)
    self.assertIsNone(result["fields"][0]["value"])
    self.assertEqual(result["fields"][0]["status"], "UNAVAILABLE")
    self.assertEqual(
        result["fields"][0]["missing_reason"],
        "UNAVAILABLE_CAUSAL_QUARANTINE_SAME_DAY_REALIZED_WEATHER",
    )
   journal.close()

 def test_snapshot_tools_page_every_field_and_share_exact_hash_across_sessions(self) -> None:
  with tempfile.TemporaryDirectory() as directory:
   tmp_path = Path(directory)
   journal = CausalEvidenceJournal.create(tmp_path / "evidence.jsonl", run_id="run-tools")
   backend = CausalRuntimeToolBackend(
        snapshot=_snapshot(),
        binding=_binding(),
        causal_state_path=None,
        evidence_journal=journal,
        commit_sha="6" * 40,
    )
   names = {row["name"] for row in backend.definitions}
   self.assertTrue({
       "decision_state_manifest", "decision_state_list", "decision_state_search",
       "decision_state_read"
   } <= names)
   left = backend.open_session(_binding(), "S135_CONTROL")
   right = backend.open_session(_binding(), "FULL_PROVISIONAL_COMBINED")
   self.assertEqual(left.execute("m1", "decision_state_manifest", {}).result["snapshot_hash"], backend.snapshot.snapshot_hash)
   self.assertEqual(right.execute("m2", "decision_state_manifest", {}).result["snapshot_hash"], backend.snapshot.snapshot_hash)
   listed = left.execute(
       "l0", "decision_state_list", {"cursor": 0, "limit": 10}
   ).result
   self.assertEqual(len(listed["fields"]), 10)
   searched = left.execute(
       "q0", "decision_state_search", {"query": "field_01", "cursor": 0, "limit": 50}
   ).result
   self.assertTrue(searched["fields"])

   seen: list[str] = []
   cursor = 0
   call = 0
   while cursor is not None:
        result = left.execute(
            f"p{call}", "decision_state_read", {"cursor": cursor, "limit": 500}
        ).result
        seen.extend(row["path"] for row in result["fields"])
        cursor = result["next_cursor"]
        call += 1
   self.assertEqual(seen, [field.path for field in backend.snapshot.fields])
   self.assertEqual(len(seen), 1936)
   self.assertNotEqual(journal.head_hash, "0" * 64)
   self.assertGreater(journal.record_count, 0)
   journal.close()

   rows = [json.loads(line) for line in (tmp_path / "evidence.jsonl").read_text().splitlines()]
   self.assertEqual(rows[0]["event_type"], "CODE_IDENTITY")
   self.assertTrue({row["event_type"] for row in rows} >= {"TOOL_READ", "CODE_IDENTITY"})


 def test_prior_state_delta_and_raw_events_are_causally_bounded_and_denials_persist(self) -> None:
  with tempfile.TemporaryDirectory() as directory:
   tmp_path = Path(directory)
   causal_path = tmp_path / "causal-state.jsonl"
   _causal_file(causal_path)
   journal = CausalEvidenceJournal.create(tmp_path / "evidence.jsonl", run_id="run-tools")
   session = CausalRuntimeToolBackend(
        snapshot=_snapshot(),
        binding=_binding(10.5),
        causal_state_path=causal_path,
        evidence_journal=journal,
        commit_sha="7" * 40,
    ).open_session()

   state = session.execute("s0", "prior_causal_state", {"sequence": 0})
   self.assertEqual(state.status, "OK")
   self.assertEqual(state.result["state"]["sequence"], 0)
   self.assertEqual(session.execute("d0", "prior_causal_delta", {"sequence": 0}).result["delta"], {"sequence": 0})
   events = session.execute(
        "r0", "raw_event_range", {"start_sequence": 0, "end_sequence": 1}
    )
   self.assertEqual([row["id"] for row in events.result["events"]], ["e0"])
   denied = session.execute("s1", "prior_causal_state", {"sequence": 1})
   self.assertEqual(denied.status, "DENIED")
   journal.record_answer_access(allowed=False, reason="sealed until primary freeze")
   journal.close()

   rows = [json.loads(line) for line in (tmp_path / "evidence.jsonl").read_text().splitlines()]
   self.assertTrue({row["event_type"] for row in rows} >= {
        "TOOL_READ", "TOOL_DENY", "RAW_EVENT_RANGE", "ANSWER_ACCESS"
   })
   self.assertTrue(all("record_hash" in row for row in rows))
   validation = validate_causal_evidence_journal(tmp_path / "evidence.jsonl", run_id="run-tools")
   self.assertEqual(validation["record_count"], len(rows))

 def test_rehashed_history_with_different_knowledge_identity_is_denied(self) -> None:
  with tempfile.TemporaryDirectory() as directory:
   tmp_path = Path(directory)
   causal_path = tmp_path / "causal-state.jsonl"
   _causal_file(causal_path)
   rows = [json.loads(line) for line in causal_path.read_text().splitlines()]
   rows[0]["binding"]["knowledge_manifest_hash"] = "9" * 64
   for index, row in enumerate(rows):
    if index:
     row["prior_record_hash"] = rows[index - 1]["record_hash"]
    core = {
        "schema": row["schema"], "run_id": row["run_id"], "sequence": row["sequence"],
        "causal_cutoff": row["causal_cutoff"], "binding": row["binding"],
        "content_hash": row["content_hash"], "prior_record_hash": row["prior_record_hash"],
    }
    row["record_hash"] = _stable_hash(core)
   causal_path.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows))
   journal = CausalEvidenceJournal.create(tmp_path / "evidence.jsonl", run_id="run-tools")
   session = CausalRuntimeToolBackend(
       snapshot=_snapshot(), binding=_binding(), causal_state_path=causal_path,
       evidence_journal=journal, commit_sha="8" * 40,
   ).open_session(_binding(), "S135_CONTROL")
   execution = session.execute("drift", "prior_causal_state", {"sequence": 0})
   self.assertEqual(execution.status, "DENIED")
   self.assertIn("knowledge manifest mismatch", execution.result["reason"])
   journal.close()

 def test_history_tools_enforce_record_event_byte_and_range_caps_without_read_text(self) -> None:
  with tempfile.TemporaryDirectory() as directory:
   tmp_path = Path(directory)
   causal_path = tmp_path / "causal-state.jsonl"
   _causal_file(causal_path)
   journal = CausalEvidenceJournal.create(tmp_path / "evidence.jsonl", run_id="run-tools")
   session = CausalRuntimeToolBackend(
       snapshot=_snapshot(), binding=_binding(10.5), causal_state_path=causal_path,
       evidence_journal=journal, commit_sha="a" * 40,
   ).open_session()
   self.assertEqual(
       session.execute(
           "range-cap", "raw_event_range",
           {"start_sequence": 0, "end_sequence": MAX_RAW_EVENT_RECORD_SPAN + 1},
       ).status,
       "DENIED",
   )
   self.assertEqual(
       session.execute(
           "record-cap", "prior_causal_state", {"sequence": MAX_HISTORY_RECORD_SCAN}
       ).status,
       "DENIED",
   )
   with mock.patch.object(Path, "read_text", side_effect=AssertionError("must stream")):
    self.assertEqual(
        session.execute("streamed", "prior_causal_state", {"sequence": 0}).status,
        "OK",
    )
   journal.close()

  with tempfile.TemporaryDirectory() as directory:
   tmp_path = Path(directory)
   for label, state in (
       ("events", {"raw_events": [{"id": index, "known_by": 10.0} for index in range(MAX_RAW_EVENTS + 1)]}),
       ("bytes", {"payload": "x" * (MAX_TOOL_OUTPUT_BYTES + 1), "raw_events": []}),
       ("future", {"raw_events": [{"id": "future", "known_by": 11.0}]}),
   ):
    causal_path = tmp_path / f"{label}.jsonl"
    writer = CausalSecondJsonlWriter.create(causal_path, run_id="run-tools", flush_interval_records=1)
    writer.append_second(
        binding=_binding(10.0), state=state, delta={}, integrity={"ok": True},
        decision={"type": "NO_LOCK", "owner": "CAUSAL_OBSERVATION_ONLY", "primary_lock": False},
    )
    writer.close()
    journal = CausalEvidenceJournal.create(tmp_path / f"{label}-evidence.jsonl", run_id="run-tools")
    session = CausalRuntimeToolBackend(
        snapshot=_snapshot(), binding=_binding(10.5), causal_state_path=causal_path,
        evidence_journal=journal, commit_sha="b" * 40,
    ).open_session()
    tool = "prior_causal_state" if label == "bytes" else "raw_event_range"
    arguments = {"sequence": 0} if label == "bytes" else {"start_sequence": 0, "end_sequence": 0}
    execution = session.execute(label, tool, arguments)
    self.assertEqual(execution.status, "DENIED")
    journal.close()


if __name__ == "__main__":
    unittest.main()
