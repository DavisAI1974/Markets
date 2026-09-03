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
from unittest.mock import patch

from research.kalshi.frankie_raw_mbo_benchmark import emit_frankie_spawn as emitter
from research.kalshi.frankie_raw_mbo_benchmark import native_layer_crosswalk as xw
from research.kalshi.frankie_raw_mbo_benchmark.emit_frankie_spawn import (
    CONTRACT_PATH,
    EmitError,
    MISSION_PATH,
    emit,
)
from research.kalshi.frankie_raw_mbo_benchmark.fetch_frankie_ledgers import (
    LEDGER_FILES,
    RECEIPT_SCHEMA,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import canonical_hash
from research.kalshi.frankie_raw_mbo_benchmark.native_key_alias import (
    apply_aliases,
    build_alias_table,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_staging import EXACT_LEDGERS
from research.kalshi.frankie_raw_mbo_benchmark import native_principal_outputs as outputs


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
            "exact_member_ledger": {
                "exact_member_rows": 57027,
                "field_census": _census(57027),
                "field_census_covers_every_member_row": True,
            },
        },
    }


def _census(rows):
    return {
        "rows_observed": rows,
        "field_count": 3,
        "fields": [],
        "degenerate_fields": [
            {"field": "book_full.top_n", "only_value": 10, "rows_with_field": rows},
        ],
        "always_null_fields": ["structure.gap_ns"],
        "distinct_cap": 64,
        "list_positions_collapsed": True,
        "basis": "measurement only",
    }


#: Plain ledger bytes the fake delivery "delivered". Their sha256 is what a run's own
#: `ledger_retention[*].sha256` must match for the ledger to be bound to the run.
LEDGER_BYTES = {
    "exact_member_ledger": b'{"group_index":0}\n',
    "exact_lifecycle_and_runway_ledger": b'{"emitting_section":"ladder"}\n',
    "legacy_observable_rows": b'{"ts_recv":1.0}\n',
}


def _accounted_prompt_test_crosswalk() -> dict:
    """Computed gate input for tests whose subject is prompt rendering, not delivery.

    This deliberately small registry isolates the older prompt tests from the full delivery
    fixture. The S123 integration tests exercise receipt loading and the production call;
    Task B's fixture is the proof over the full live registry. No computed row is mutated.
    """
    layer_ids = ("controlling_rt_mission", "native_calculation_contract")
    registry = {
        "registry_sha256": "a" * 64,
        "groups": [{
            "group_id": "binding_common_controls",
            "policy": "STATIC_REQUIRED_INPUT",
            "activation_stage": "PRE_CALL",
            "authority": "BINDING_CURRENT",
            "arms": ["A_CLEAN"],
            "principal_route": "DIRECT",
            "proof_mode": "CONTENT_SHA256",
            "entries": [{
                "layer_id": layer_id,
                "description": layer_id,
                "source_paths": [xw.LAYER_PRODUCERS[layer_id]["carrier_paths"][0]],
                "v3_derived": False,
            } for layer_id in layer_ids],
        }],
    }
    knowledge_receipt = {
        "schema": xw.KNOWLEDGE_RECEIPT_SCHEMA,
        "receipt_sha256": "b" * 64,
        "layers": [{
            "layer_id": layer_id,
            "status": "DELIVERED",
            "files": [{
                "path": xw.LAYER_PRODUCERS[layer_id]["carrier_paths"][0],
                "sha256": "c" * 64,
                "bytes": 1,
            }],
        } for layer_id in layer_ids],
    }
    return xw.crosswalk(registry, arm="A_CLEAN", knowledge_receipt=knowledge_receipt)


def _emit_prompt_unit(*args, **kwargs) -> str:
    """Run the real emitter and gate against computed prompt-test rows."""
    with patch.object(emitter, "crosswalk", return_value=_accounted_prompt_test_crosswalk()):
        return emit(*args, **kwargs)


def _delivery_receipt(root: Path, *, statuses=None, mutate=None) -> Path:
    """A FRANKIE_LEDGER_DELIVERY_RECEIPT_V1 as `fetch_frankie_ledgers.fetch` writes it, with
    the ledger files actually present on disk so the paths it names resolve."""
    statuses = statuses or {}
    ledgers = {}
    for name in EXACT_LEDGERS:
        path = root / "delivered" / LEDGER_FILES[name]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(LEDGER_BYTES[name])
        ledgers[name] = {
            "file": LEDGER_FILES[name], "object": LEDGER_FILES[name] + ".gz",
            "status": statuses.get(name, "VERIFIED"), "local_path": str(path),
            "plain_bytes_expected": len(LEDGER_BYTES[name]),
            "plain_bytes_observed": len(LEDGER_BYTES[name]),
            "plain_sha256_expected": hashlib.sha256(LEDGER_BYTES[name]).hexdigest(),
            "plain_sha256_observed": hashlib.sha256(LEDGER_BYTES[name]).hexdigest(),
        }
    body = {
        "schema": RECEIPT_SCHEMA, "run_id": "33630348943",
        "run_prefix": "nymex/ng_mbo_5y_v0/frankie/raw_mbo_benchmark/a-clean/full/7638659/33630348943-1",
        "bucket": "bento-568968024170-us-east-2-an", "manifest_sha256": "f" * 64,
        "fetched_at": "2026-09-02T20:00:00Z", "out_dir": str(root / "delivered"),
        "ledgers": ledgers, "objects": {},
        "all_ledgers_verified": all(v["status"] == "VERIFIED" for v in ledgers.values()),
        "receipt_sha256": "",
    }
    body["receipt_sha256"] = canonical_hash(body, omit="receipt_sha256")
    if mutate:
        mutate(body)
    path = root / "FRANKIE_LEDGER_DELIVERY_RECEIPT.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


class StopRuleTests(unittest.TestCase):
    def _emit(self, mutate=None, mission=MISSION_BYTES, receipt_statuses=None,
              receipt_mutate=None, without_receipt=False):
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
            receipt = None if without_receipt else _delivery_receipt(
                root, statuses=receipt_statuses, mutate=receipt_mutate
            )
            return _emit_prompt_unit(result, repo_root=root, delivery_receipt=receipt)

    def test_a_complete_run_emits_every_required_slot(self):
        text = self._emit()
        for needle in ("REAL_TIME_FRANKIE", "A_CLEAN", "cb685e0e",
                       "you compute the sixteen sections yourself",
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
            return _emit_prompt_unit(result, repo_root=root, delivery_receipt=_delivery_receipt(root))

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
            return _emit_prompt_unit(result, repo_root=root, delivery_receipt=_delivery_receipt(root))

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
            return _emit_prompt_unit(result, repo_root=root, delivery_receipt=_delivery_receipt(root))

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

    def test_it_names_what_the_run_retained_beside_what_was_delivered(self):
        """The run's own sink receipt is rendered beside the delivered file, so a reader can
        see the box's count and bytes next to the local path, and a delivered ledger whose
        sha256 matches the sink's is stated as BOUND to the run."""
        def add_retention(body):
            body["ledger_retention"] = {
                "exact_member_ledger": {
                    "row_count": 43569, "bytes": 10630127166,
                    "path": "/opt/frankie-a-arm-run/ledgers/exact_member_rows.jsonl",
                    "sha256": hashlib.sha256(LEDGER_BYTES["exact_member_ledger"]).hexdigest(),
                }
            }

        text = self._emit(mutate=add_retention)
        self.assertIn("exact_member_rows.jsonl", text)
        self.assertIn("10,630,127,166", text)
        self.assertIn("43,569 rows", text)
        self.assertIn("BOUND to this run", text)
        self.assertNotIn("NOT in this result", text)

    def test_a_delivered_ledger_that_is_not_the_runs_ledger_halts(self):
        """The binding that makes 'this ledger is this run's' true, executed on its firing
        branch: the sink hashed one file, the delivery verified another."""
        def add_retention(body):
            body["ledger_retention"] = {
                "exact_member_ledger": {"row_count": 1, "bytes": 18, "path": "/x", "sha256": "0" * 64}
            }
        with self.assertRaisesRegex(EmitError, "exact_member_ledger.*not the ledger this run retained"):
            self._emit(mutate=add_retention)

    def test_absent_retention_receipts_are_declared_not_rendered_empty(self):
        """"You were given nothing" and "we did not record what you were given" are
        different facts, and only one of them is an answer."""
        self.assertIn("itself unstated", self._emit())


class FieldCensusReachesFrankieTest(StopRuleTests):
    """F-10: the measurement behind 9a is rendered, and a spawn without it HALTS.

    Asking for a per-field classification while withholding the per-field census is asking
    for a guess. A census that saw fewer rows than were written is partial, and a partial
    census rendered as complete is the S119 shape - present, typed, plausible, wrong.
    """

    def test_the_degenerate_fields_are_rendered_with_their_value_and_row_count(self):
        text = self._emit()
        self.assertIn("The field census, measured on every retained member row", text)
        self.assertIn("57,027 rows censused", text)
        self.assertIn("| `book_full.top_n` | `10` | 57,027 |", text)
        self.assertIn("1 fields carried exactly one value throughout", text)

    def test_the_always_null_fields_are_rendered(self):
        self.assertIn("- `structure.gap_ns`", self._emit())

    def test_it_says_measurement_not_recommendation(self):
        text = self._emit()
        self.assertIn("It is a measurement, not a recommendation", text)
        self.assertIn("say CANNOT_JUDGE", text)

    def test_a_result_without_the_census_halts(self):
        def drop(body):
            del body["layers"]["exact_member_ledger"]["field_census"]
        with self.assertRaises(EmitError):
            self._emit(mutate=drop)

    def test_a_census_that_saw_fewer_rows_than_were_written_halts(self):
        def partial(body):
            body["layers"]["exact_member_ledger"]["field_census"] = _census(57026)
        with self.assertRaisesRegex(EmitError, "does not cover every member row"):
            self._emit(mutate=partial)

    def test_the_run_reporting_its_own_census_partial_halts(self):
        def flag(body):
            body["layers"]["exact_member_ledger"]["field_census_covers_every_member_row"] = False
        with self.assertRaisesRegex(EmitError, "partial"):
            self._emit(mutate=flag)


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

    def test_it_says_not_read_is_now_refused_because_the_ledgers_are_delivered(self):
        """NOT_READ was the honest answer while delivery was unsolved. Delivered and
        verified, a ledger he did not read is a failed spawn, and the prompt says so."""
        text = self._emit()
        self.assertNotIn("NOT_READ carries no penalty", text)
        self.assertIn("NOT_READ is refused", text)
        self.assertIn('"exact_member_ledger": "READ"', text)
        self.assertIn('"exact_lifecycle_and_runway_ledger": "READ"', text)
        self.assertIn('"legacy_observable_rows": "READ"', text)


class DeliveryReceiptGateTest(StopRuleTests):
    """D81: the raw MBO is his evidence, and the spawn is refused until it is in his hands.

    Every session built to mission section 5's "the runner calculates; you interpret" while
    section 3 and 55 registry layers said the principal receives the group stream at every
    F_LAST cutoff. The emitter now REQUIRES a delivery receipt with every exact ledger
    VERIFIED, names the local ledger paths and the stream tool as THE evidence, and says the
    runner's result is not.
    """

    def test_no_receipt_no_spawn(self):
        with self.assertRaisesRegex(EmitError, "delivery receipt"):
            self._emit(without_receipt=True)

    def test_a_ledger_that_is_not_verified_halts_by_name(self):
        for status in ("LENGTH_MISMATCH", "SHA_MISMATCH", "MISSING"):
            with self.subTest(status=status):
                with self.assertRaisesRegex(EmitError, f"exact_lifecycle_and_runway_ledger.*{status}"):
                    self._emit(receipt_statuses={"exact_lifecycle_and_runway_ledger": status})

    def test_a_receipt_whose_own_hash_does_not_verify_halts(self):
        def tamper(body):
            body["ledgers"]["exact_member_ledger"]["status"] = "VERIFIED"
            body["receipt_sha256"] = "0" * 64
        with self.assertRaisesRegex(EmitError, "receipt_sha256"):
            self._emit(receipt_mutate=tamper)

    def test_a_receipt_of_another_schema_halts(self):
        def wrong(body):
            body["schema"] = "SOMETHING_ELSE_V1"
            body["receipt_sha256"] = canonical_hash(body, omit="receipt_sha256")
        with self.assertRaisesRegex(EmitError, "FRANKIE_LEDGER_DELIVERY_RECEIPT_V1"):
            self._emit(receipt_mutate=wrong)

    def test_the_prompt_names_every_local_ledger_path_as_the_evidence(self):
        text = self._emit()
        head = text.index("## The evidence")
        evidence = text[head:text.index("## ", head + 4)]
        for name in EXACT_LEDGERS:
            self.assertIn(f"delivered/{LEDGER_FILES[name]}", evidence, name)
        self.assertIn("native_causal_stream", evidence)
        self.assertIn("CausalGroupStream", evidence)

    def test_it_says_he_computes_the_sixteen_sections_himself(self):
        text = self._emit()
        self.assertIn("you compute the sixteen sections yourself", text)
        self.assertIn("causal order", text)
        self.assertIn("no random access", text)
        self.assertNotIn("the runner calculates, you interpret", text)
        self.assertNotIn("Do not recompute them", text)

    def test_the_runners_result_is_not_listed_as_his_evidence(self):
        text = self._emit()
        head = text.index("## The evidence")
        evidence = text[head:text.index("## ", head + 4)]
        self.assertNotIn("calculation_result.json", evidence)
        self.assertIn("calculation_result.json", text)          # named, as NOT his evidence
        self.assertIn("NOT your evidence", text)
        self.assertIn("compared AFTER you file", text)

    def test_the_twenty_megabyte_skeleton_wording_is_gone(self):
        text = self._emit()
        self.assertNotIn("It is about 20 MB", text)
        self.assertNotIn("read the\nskeleton", text)
        self.assertNotIn("skeleton", text)

    def test_the_return_shape_carries_both_receipt_hashes(self):
        text = self._emit()
        self.assertIn('"delivery_receipt_sha256"', text)
        self.assertIn('"stream_receipt_sha256"', text)
        # The delivery hash is KNOWN and filled in; the stream hash is his to produce.
        block = text[text.index("```json"):text.index("```", text.index("```json") + 7)]
        shape = json.loads(block.replace("```json", "").strip())
        self.assertRegex(shape["delivery_receipt_sha256"], r"^[0-9a-f]{64}$")
        self.assertIn("stream receipt", shape["stream_receipt_sha256"])
        self.assertEqual(shape["evidence_read"], {name: "READ" for name in EXACT_LEDGERS})

    def test_the_return_shape_carries_the_outputs_receipt_and_describes_the_bundle(self):
        """F-25 at the ask side. `native_staging.load_principal_artifact` REFUSES a delivered
        artifact that cites no `outputs_receipt_sha256` (OutputsBundleGateTest pins the
        refusal against the emitter's previous text), so the return shape must ask for it
        and the prompt must say what the bundle is - the schema, the directory, the receipt
        file, the derived required set - from `native_principal_outputs`, the file that
        carries it (D82), not from a description of it."""
        text = self._emit()
        block = text[text.index("```json"):text.index("```", text.index("```json") + 7)]
        shape = json.loads(block.replace("```json", "").strip())
        self.assertIn("outputs_receipt_sha256", shape)
        self.assertIn(outputs.RECEIPT_FILENAME, shape["outputs_receipt_sha256"])
        self.assertIn("## Your output bundle", text)
        bundle = text[text.index("## Your output bundle"):]
        for needle in (
            outputs.OUTPUT_BUNDLE_SCHEMA, outputs.OUTPUT_RECEIPT_SCHEMA,
            outputs.RECEIPT_FILENAME, outputs.LEDGERS_DIRNAME,
            outputs.APPEND_ONLY_OUTPUTS_GROUP, outputs.SECTION_LEDGER_PREFIX,
            outputs.RAW_MBO_CLASSIFICATION_LEDGER, outputs.KNOWLEDGE_VERIFICATION_LEDGER,
            "append-only", "hash chain", "no count", "outputs_receipt_sha256",
            "native_principal_outputs validate",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, bundle)
        # The refusal is stated where he reads the shape, beside the other refusals.
        self.assertIn("cites a delivery receipt but no `outputs_receipt_sha256`", text)

    def test_the_9a_block_and_the_field_census_survive(self):
        text = self._emit()
        self.assertIn("### 9a", text.replace("section 9a", "### 9a"))
        self.assertIn("Keep-everything is a first-class answer", text)
        self.assertIn("The field census, measured on every retained member row", text)
