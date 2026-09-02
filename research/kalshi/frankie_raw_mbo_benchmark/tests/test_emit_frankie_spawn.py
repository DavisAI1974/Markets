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


#: The fixture mission must carry section 9a or the emitter refuses, which is the point of
#: the gate: a mission that does not ASK the raw-MBO question cannot be spawned against.
MISSION_BYTES = b"mission bytes\n### 9a. The raw MBO\n"


def _repo_with_docs(directory: Path, mission: bytes = MISSION_BYTES,
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
    def _emit(self, mutate=None, mission=MISSION_BYTES):
        """`mission` is what lands ON DISK; the run always binds the ORIGINAL bytes.

        The first version of this helper hashed whatever it wrote, so an "edited" mission
        matched its own binding and the test passed while proving nothing - the same shape
        as a guard whose firing branch never executes.
        """
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            root, _, c_sha = _repo_with_docs(root, mission=mission)
            m_sha = hashlib.sha256(MISSION_BYTES).hexdigest()
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
            self._emit(mission=MISSION_BYTES + b"EDITED\n")
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


class RawMboQuestionReachesFrankieTest(StopRuleTests):
    """D68 ordered a report "on the calcs, on the full raw mbo, all of it".

    The calcs half was delivered and the raw-MBO half was never ANSWERED because it was
    never ASKED: the S119 spawn prompt contained `raw mbo`, `retention`, `drop`, `field`,
    `book_full` and `keep` exactly zero times, and mission section 9's nine required outputs
    named none of them. A decision recorded in DECISIONS.md and absent from the mission never
    reaches Frankie. Prose cannot enforce itself, so these are the enforcement.
    """

    @staticmethod
    def _emit_binding_the_mission_on_disk(mission: bytes) -> str:
        """Emit with the run binding the sha of the mission actually written.

        `_emit` deliberately binds MISSION_BYTES whatever it writes, so an altered mission
        trips the HASH check. To reach the 9a gate the mission must be correctly bound and
        merely fail to ask the question - which is the real-world case: nobody edits the
        mission mid-run, it simply never carried the section.
        """
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            root, m_sha, c_sha = _repo_with_docs(root, mission=mission)
            result = root / "calculation_result.json"
            result.write_text(json.dumps(_result(m_sha, c_sha)), encoding="utf-8")
            return emit(result, repo_root=root)

    def test_a_correctly_bound_mission_that_never_asks_refuses_to_spawn(self):
        """The gate's firing branch, executed. A guard whose output was never produced was
        never tested - S113's NC-3, and the reason this assertion exists at all."""
        with self.assertRaises(EmitError) as caught:
            self._emit_binding_the_mission_on_disk(b"a mission that forgot to ask\n")
        self.assertIn("raw-MBO", str(caught.exception))

    def test_the_same_mission_with_9a_added_emits(self):
        """The other half: the gate must PASS on a mission that does carry it, or it is
        refusing everything and proving nothing."""
        text = self._emit_binding_the_mission_on_disk(MISSION_BYTES)
        self.assertIn("raw MBO", text)

    def test_the_question_is_actually_in_the_prompt(self):
        text = self._emit()
        for needle in ("raw MBO", "LOAD_BEARING", "RETAINED_UNREAD",
                       "DEGENERATE_ON_THIS_SLICE", "REDUNDANT", "CANNOT_JUDGE"):
            self.assertIn(needle, text, needle)

    def test_it_says_keep_everything_is_a_first_class_answer(self):
        """D76. A question shaped as "what can we drop" pressures the answer toward a
        casualty, and this programme has already paid for exactly that."""
        text = self._emit()
        self.assertIn("Keep-everything is a first-class answer", text)

    def test_it_refuses_the_calculation_answer_in_advance(self):
        """The calcs have been returned in place of this answer every time it was asked."""
        self.assertIn("not the calculation question", self._emit())

    def test_it_names_what_he_is_NOT_given(self):
        """Asking the question without saying which evidence is absent invites a confident
        judgement on data he never received."""
        def add_retention(body):
            body["ledger_retention"] = {
                "exact_member_ledger": {
                    "row_count": 43569, "bytes": 10630127166,
                    "path": "/opt/frankie-a-arm-run/ledgers/exact_member_rows.jsonl",
                }
            }

        text = self._emit(mutate=add_retention)
        self.assertIn("NOT in this result", text)
        self.assertIn("exact_member_rows.jsonl", text)
        self.assertIn("10,630,127,166", text)

    def test_absent_retention_receipts_are_declared_not_rendered_empty(self):
        """"You were given nothing" and "we did not record what you were given" are
        different facts, and only one of them is an answer."""
        self.assertIn("itself unstated", self._emit())


class EvidenceReadIsAskedForTest(StopRuleTests):
    """F-14 at the ask side: the return shape names `evidence_read` per exact ledger.

    The staging gate refuses an artifact without it; a prompt that never mentioned it would
    make every first spawn fail the gate for a reason the principal was never told.
    """

    def test_the_return_shape_names_every_exact_ledger(self):
        text = self._emit()
        self.assertIn('"evidence_read"', text)
        for ledger in ("exact_member_ledger", "exact_lifecycle_and_runway_ledger",
                       "legacy_observable_rows"):
            self.assertIn(ledger, text, ledger)

    def test_it_says_not_read_is_accepted(self):
        """A prompt that read as 'you must have read them' would push him toward claiming
        reads he did not make - the defect this programme exists to catch."""
        self.assertIn("NOT_READ carries no penalty", self._emit())
