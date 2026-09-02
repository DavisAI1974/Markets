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
from research.kalshi.frankie_raw_mbo_benchmark.native_key_alias import (
    apply_aliases,
    build_alias_table,
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


class SpanAndPhaseTests(unittest.TestCase):
    """A window is scoped by its span and its phases, not only by its date.

    The canary covers 88 contiguous minutes of Oct 1. Told only the date, a principal would
    reasonably write "on October 1" and mean a day. That is the project's recurring defect
    in miniature - a figure that is present, typed, plausible, and measuring something other
    than what its name implies.
    """

    def _emit_with(self, cutoffs):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            root, m_sha, c_sha = _repo_with_docs(root)
            body = _result(m_sha, c_sha, cutoffs=cutoffs)
            result = root / "calculation_result.json"
            result.write_text(json.dumps(body), encoding="utf-8")
            return emit(result, repo_root=root)

    def _cuts(self, spans_ns, phases):
        base = 1633046886987074241
        return [
            {"group_index": 100 * n, "source_day": "20211001", "session_phase": phases[n % len(phases)],
             "recv_ns": base + spans_ns[n], "first_lawful_availability_ns": base + spans_ns[n],
             "continuity_segment": 18904}
            for n in range(len(spans_ns))
        ]

    def test_the_span_is_stated_in_seconds_and_minutes(self):
        # 5,290 SECONDS is the canary's real span - 5.29e12 ns. Written first as 5.29e9,
        # which is 5.29 seconds, and the test caught it. Nanosecond fields are exactly where
        # an order-of-magnitude slip survives review, which is why the assertion names both
        # units.
        text = self._emit_with(self._cuts([0, 2_000_000_000, 5_290_000_000_000], ["PRE_SETTLEMENT"]))
        self.assertIn("Cutoff span: 5,290 seconds", text)
        self.assertIn("88.2 minutes", text)

    def test_it_is_not_described_as_the_session_length(self):
        text = self._emit_with(self._cuts([0, 5_290_000_000_000], ["PRE_SETTLEMENT"]))
        self.assertIn("not the session's length", text)

    def test_phases_covered_are_named_and_absence_is_distinguished(self):
        text = self._emit_with(self._cuts([0, 1_000_000_000], ["PRE_SETTLEMENT"]))
        self.assertIn("Session phases covered: PRE_SETTLEMENT", text)
        self.assertIn("different fact from observing it empty", text)

    def test_several_phases_are_all_listed(self):
        text = self._emit_with(self._cuts([0, 1_000_000_000], ["PRE_SETTLEMENT", "SETTLEMENT"]))
        self.assertIn("PRE_SETTLEMENT, SETTLEMENT", text)


class AliasedRowsReachTheEmitterTest(StopRuleTests):
    """The emitter must report the same per-section table whichever form the rows are in.

    This is the consumer that would have broken silently. `_lookup` on
    `layers.averaged_companions.rows` succeeds on an aliased layer, returns the right
    number of rows, and `row.get("section")` then returns None on every one - so the table
    would report three rows under `None` and the prompt would go out looking complete.
    Present, well-formed, wrong: the one shape a field-level check cannot catch, and the
    reason `read_averaged_rows` exists rather than a direct lookup.
    """

    @staticmethod
    def _alias(body):
        layer = body["layers"]["averaged_companions"]
        table = build_alias_table(layer["rows"])
        layer["rows"] = apply_aliases(layer["rows"], table)
        layer["key_alias_form"] = "ALIASED"
        layer["key_alias_legend"] = table

    @staticmethod
    def _section_table(text):
        """The per-section block only. The full prompt carries the temp result PATH."""
        head = text.index("### Averaged companion rows, by section")
        return text[head:text.index("### The", head)]

    def test_the_per_section_table_is_identical_in_both_forms(self):
        self.assertEqual(
            self._section_table(self._emit()),
            self._section_table(self._emit(mutate=self._alias)),
        )

    def test_the_section_labels_survive_aliasing(self):
        text = self._emit(mutate=self._alias)
        self.assertIn("| 4.12 | 2 |", text)
        self.assertIn("| 4.9 | 1 |", text)

    def test_no_section_is_reported_as_none(self):
        """The exact symptom of reading an aliased row without decoding it."""
        self.assertNotIn("| None |", self._emit(mutate=self._alias))
