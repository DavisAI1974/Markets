"""The stop rule, and the hash check that makes the mission uneditable mid-flight.

What these pin is not the prompt's prose. It is that the emitter REFUSES rather than
emitting a prompt with a hole in it - `spawn.py`'s rule, which exists because a refine
directive once asserted a calendar premise that `flow_calendar` contradicted and the false
premise reached a posterior. A premise that cannot be typed cannot be wrong.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark.emit_frankie_spawn import (
    CONTRACT_PATH,
    EmitError,
    MISSION_PATH,
    emit,
)


def _repo_with_docs(directory: Path, mission: bytes = b"mission bytes\n",
                    contract: bytes = b"contract bytes\n") -> tuple[Path, str, str]:
    for rel, body in ((MISSION_PATH, mission), (CONTRACT_PATH, contract)):
        path = directory / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    return (directory, hashlib.sha256(mission).hexdigest(),
            hashlib.sha256(contract).hexdigest())


def _result(mission_sha: str, contract_sha: str, *, verdict="ACCEPTED", cutoffs=None,
            days=("20211003",)):
    cuts = cutoffs if cutoffs is not None else [
        {"group_index": 2281 * n, "source_day": days[n % len(days)],
         "session_phase": "PRE_SETTLEMENT", "recv_ns": 1633298413318097271 + n,
         "first_lawful_availability_ns": 1633298413318097271 + n,
         "continuity_segment": 18904}
        for n in range(1, 4)
    ]
    return {
        "verdict": verdict,
        "failed_gates": [],
        "completion_status": "EVIDENCE_ONLY",
        "result_hash": "cb685e0e" + "0" * 56,
        "slice": {"sources": ["/opt/frankie-a-arm-run/sources/glbx-mdp3-20211003.mbo.dbn.zst"]},
        "traversal": {
            "invocation_cutoffs": cuts,
            "sections_fed": {"4.6_queue_rows_applied": 57027, "4.16_response_tracks": 91},
        },
        "layers": {
            "identity_receipt": {
                "arm": "A_CLEAN",
                "run_id": "frankie-a-clean-rt-1-1",
                "mission_sha256": mission_sha,
                "calculation_contract_sha256": contract_sha,
                "coverage": {"records_seen": 57027, "groups_seen": 43569,
                             "groups_f_last_closed": 43569, "cursor_discontinuities": 0,
                             "duplicate_group_indices": 0, "fifo_reconstruction_failures": 0},
            },
            "averaged_companions": {"rows": [{"section": "4.12"}, {"section": "4.9"},
                                             {"section": "4.12"}]},
        },
    }


class StopRuleTests(unittest.TestCase):
    def _emit(self, mutate=None, mission=b"mission bytes\n"):
        """`mission` is what lands ON DISK; the run always binds the ORIGINAL bytes.

        The first version of this helper hashed whatever it wrote, so an "edited" mission
        matched its own binding and the test passed while proving nothing - the same shape
        as a guard whose firing branch never executes.
        """
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            root, _, c_sha = _repo_with_docs(root, mission=mission)
            m_sha = hashlib.sha256(b"mission bytes\n").hexdigest()
            body = _result(m_sha, c_sha)
            if mutate:
                mutate(body)
            result = root / "calculation_result.json"
            result.write_text(json.dumps(body), encoding="utf-8")
            return emit(result, repo_root=root)

    def test_a_complete_run_emits_every_required_slot(self):
        text = self._emit()
        for needle in ("REAL_TIME_FRANKIE", "A_CLEAN", "cb685e0e",
                       "the runner calculates, you interpret",
                       "FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_FINDINGS_V1",
                       "4.6_queue_rows_applied", "glbx-mdp3-20211003.mbo.dbn.zst"):
            self.assertIn(needle, text, needle)

    def test_an_edited_mission_halts_rather_than_binding_him_to_bytes_the_run_never_saw(self):
        # Section 10's first bullet: this mission's exact bytes and SHA-256 were loaded into
        # Frankie. Editing between traversal and spawn would break it invisibly.
        with self.assertRaises(EmitError) as caught:
            self._emit(mission=b"mission bytes EDITED\n")
        self.assertIn("Section 10", str(caught.exception))

    def test_a_refused_calculation_is_not_spawned_against(self):
        with self.assertRaises(EmitError) as caught:
            self._emit(lambda body: body.update(verdict="REJECTED"))
        self.assertIn("not ACCEPTED", str(caught.exception))

    def test_a_missing_lookup_names_itself(self):
        with self.assertRaises(EmitError) as caught:
            self._emit(lambda body: body["layers"]["identity_receipt"].pop("mission_sha256"))
        self.assertIn("mission_sha256", str(caught.exception))

    def test_a_run_that_staged_no_cutoff_halts(self):
        # The cadence defect that would have produced a finished run with nothing to spawn
        # against. It must stop here rather than emit a prompt over zero decision points.
        with self.assertRaises(EmitError) as caught:
            self._emit(lambda body: body["traversal"].update(invocation_cutoffs=[]))
        self.assertIn("no lawful decision point", str(caught.exception))

    def test_no_default_is_ever_substituted_for_a_slot(self):
        with self.assertRaises(EmitError):
            self._emit(lambda body: body["layers"]["identity_receipt"].update(run_id=""))


class SingleDayTests(unittest.TestCase):
    """A one-day slice of a four-day mission is stated, not left to be inferred."""

    def _emit_for(self, days):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            root, m_sha, c_sha = _repo_with_docs(root)
            body = _result(m_sha, c_sha, days=days)
            result = root / "calculation_result.json"
            result.write_text(json.dumps(body), encoding="utf-8")
            return emit(result, repo_root=root)

    def test_one_day_says_so_and_marks_cross_day_questions_unanswerable(self):
        text = self._emit_for(("20211003",))
        self.assertIn("ONE DAY: 20211003", text)
        self.assertIn("unanswerable on this slice", text)

    def test_several_days_carry_no_such_caveat(self):
        text = self._emit_for(("20211001", "20211003", "20211004"))
        self.assertNotIn("ONE DAY", text)


if __name__ == "__main__":
    unittest.main()
