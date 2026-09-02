"""What a witness must refuse to say.

The failure this guards is not a wrong table, it is a confident one. Four size numbers were
produced in a session and every one of them was present, typed and plausible while measuring
something else. So the cases that matter here are the ones where the witness is ABSENT or
answers a different question - an object that never landed, an object that landed gzipped -
because those are the two states that produce a legitimate mismatch which must never be
reported as the sink being wrong, and must never be quietly filled in from the sink's own
figure either.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark.verify_ledger_size_witness import (
    ABSENT,
    COMPRESSED,
    CONFIRMED,
    CONTRADICTED,
    UNAVAILABLE,
    WitnessError,
    main,
    render,
    witness_content,
    witness_denominator,
    witness_ledgers,
)

PREFIX = "nymex/ng_mbo_5y_v0/frankie/raw_mbo_benchmark/a-clean/abc/1-1"


def _result(*, member=12_113_675_715, lifecycle=169_866_829, legacy=18_194_001,
            records=50_001, total=None):
    total = records if total is None else total
    return {
        "traversal": {"records_seen": records, "groups_seen": 40_242},
        "layers": {
            "identity_receipt": {
                "total_mbo_records": total,
                "coverage": {"records_seen": records},
            }
        },
        "ledger_retention": {
            "exact_member_ledger": {
                "path": "/opt/frankie-a-arm-run/ledgers/exact_member_rows.jsonl",
                "bytes": member,
                "row_count": 40_242,
                "sha256": "a" * 64,
            },
            "exact_lifecycle_and_runway_ledger": {
                "path": "/opt/frankie-a-arm-run/ledgers/exact_lifecycle_rows.jsonl",
                "bytes": lifecycle,
                "row_count": 226_411,
                "sha256": "b" * 64,
            },
            "legacy_observable_rows": {
                "path": "/opt/frankie-a-arm-run/ledgers/legacy_observable_rows.jsonl",
                "bytes": legacy,
                "row_count": 13_855,
                "sha256": "c" * 64,
            },
        },
    }


def _objects(*, member=12_113_675_715, lifecycle=169_866_829, legacy=18_194_001):
    return {
        f"{PREFIX}/calculation_result.json": 4_096,
        f"{PREFIX}/ledgers/exact_member_rows.jsonl": member,
        f"{PREFIX}/ledgers/exact_lifecycle_rows.jsonl": lifecycle,
        f"{PREFIX}/ledgers/legacy_observable_rows.jsonl": legacy,
    }


class WitnessTests(unittest.TestCase):
    def test_matching_sizes_confirm_the_sink(self):
        text, outcome = render(_result(), _objects())
        self.assertEqual(outcome, CONFIRMED)
        # The exact figure the S118 table reports, reproduced from the three real ledger
        # sizes: 12,301,736,545 over 50,001 records. If the witness ever renders a different
        # number from the same inputs, this fails before a run is read off it.
        self.assertIn("246,030 bytes per record", text)

    def test_a_differing_size_contradicts_and_never_averages_the_two(self):
        rows = witness_ledgers(_result(), _objects(member=12_113_675_000))
        member = next(r for r in rows if r["ledger"] == "exact_member_ledger")
        self.assertEqual(member["status"], CONTRADICTED)
        self.assertEqual(member["delta_bytes"], -715)
        _, outcome = render(_result(), _objects(member=12_113_675_000))
        self.assertEqual(outcome, CONTRADICTED)

    def test_an_absent_object_is_unavailable_not_a_contradiction(self):
        objects = _objects()
        del objects[f"{PREFIX}/ledgers/exact_member_rows.jsonl"]
        rows = witness_ledgers(_result(), objects)
        member = next(r for r in rows if r["ledger"] == "exact_member_ledger")
        self.assertEqual(member["status"], UNAVAILABLE)
        self.assertEqual(member["reason"], ABSENT)
        text, outcome = render(_result(), objects)
        self.assertEqual(outcome, UNAVAILABLE)
        self.assertIn("REFUSED", text)
        self.assertNotIn("bytes per record**", text.split("### Bytes per record")[1])

    def test_a_gzipped_object_answers_a_different_question(self):
        objects = _objects()
        size = objects.pop(f"{PREFIX}/ledgers/exact_member_rows.jsonl")
        objects[f"{PREFIX}/ledgers/exact_member_rows.jsonl.gz"] = size // 9
        rows = witness_ledgers(_result(), objects)
        member = next(r for r in rows if r["ledger"] == "exact_member_ledger")
        self.assertEqual(member["status"], UNAVAILABLE)
        self.assertEqual(member["reason"], COMPRESSED)
        self.assertEqual(member["compressed_bytes"], size // 9)
        self.assertNotIn("delta_bytes", member)

    def test_the_denominator_is_read_from_three_places_and_must_agree(self):
        agreeing = witness_denominator(_result())
        self.assertTrue(agreeing["agree"])
        self.assertEqual(agreeing["records"], 50_001)
        disagreeing = witness_denominator(_result(total=50_002))
        self.assertFalse(disagreeing["agree"])
        self.assertIsNone(disagreeing["records"])

    def test_a_disagreeing_denominator_contradicts_even_with_matching_bytes(self):
        text, outcome = render(_result(total=50_002), _objects())
        self.assertEqual(outcome, CONTRADICTED)
        self.assertIn("REFUSED", text)

    def test_an_absent_denominator_refuses_the_per_record_figure(self):
        # The bug this drove out: with one of the three counts ABSENT and the other two
        # agreeing, the report still emitted a per-record figure. Two of three agreeing says
        # nothing about the third, and the whole point of the module is that a figure is not
        # emitted off an incomplete basis.
        result = _result()
        del result["layers"]["identity_receipt"]["total_mbo_records"]
        text, outcome = render(result, _objects())
        # UNAVAILABLE, not CONTRADICTED: absent is not disagreeing, and accusing the sink of
        # an error on evidence we do not have is the same failure in the other direction.
        self.assertEqual(outcome, UNAVAILABLE)
        self.assertIn("Denominator unavailable", text)
        self.assertNotIn("bytes per record**", text.split("### Bytes per record")[1])

    def test_content_witness_compares_the_digest_not_the_length(self):
        text, outcome = render(_result(), _objects(), {"exact_member_ledger": "a" * 64})
        self.assertEqual(outcome, CONFIRMED)
        self.assertIn("Content, not just length", text)
        _, wrong = render(_result(), _objects(), {"exact_member_ledger": "c" * 64})
        self.assertEqual(wrong, CONTRADICTED)

    def test_a_content_witness_for_an_unknown_ledger_raises(self):
        with self.assertRaises(WitnessError):
            render(_result(), _objects(), {"no_such_ledger": "a" * 64})

    def test_a_result_with_no_receipts_is_refused_not_witnessed_clean(self):
        with self.assertRaises(WitnessError):
            render({"traversal": {"records_seen": 1}}, _objects())

    def test_exit_codes_separate_the_three_outcomes(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            result = directory / "result.json"
            objects = directory / "objects.json"
            out = directory / "witness.md"
            result.write_text(json.dumps(_result()), encoding="utf-8")

            objects.write_text(json.dumps(_objects()), encoding="utf-8")
            self.assertEqual(main(["--result", str(result), "--objects", str(objects),
                                   "--output", str(out)]), 0)

            objects.write_text(json.dumps(_objects(member=1)), encoding="utf-8")
            self.assertEqual(main(["--result", str(result), "--objects", str(objects),
                                   "--output", str(out)]), 1)

            objects.write_text(json.dumps({}), encoding="utf-8")
            self.assertEqual(main(["--result", str(result), "--objects", str(objects),
                                   "--output", str(out)]), 2)


if __name__ == "__main__":
    unittest.main()


class LengthIsNotContentTests(unittest.TestCase):
    """A confirmed length must not be allowed to vouch for unconfirmed content."""

    def test_a_contradicted_digest_qualifies_the_per_record_figure(self):
        text, outcome = render(_result(), _objects(), {"exact_member_ledger": "d" * 64})
        self.assertEqual(outcome, CONTRADICTED)
        self.assertIn("246,030 bytes per record", text)
        self.assertIn("about LENGTH only", text)

    def test_a_clean_run_carries_no_such_qualifier(self):
        text, _ = render(_result(), _objects(), {"exact_member_ledger": "a" * 64})
        self.assertNotIn("about LENGTH only", text)


class NamesTheRunItExaminedTests(unittest.TestCase):
    """The first live run witnessed the wrong run and reported CONFIRMED without saying so."""

    def test_the_heading_carries_the_prefix_and_the_record_count(self):
        text, outcome = render(_result(), _objects())
        self.assertEqual(outcome, CONFIRMED)
        self.assertIn(PREFIX, text)
        self.assertIn("**50,001**", text)

    def test_the_prefix_is_derived_from_the_keys_not_supplied(self):
        from research.kalshi.frankie_raw_mbo_benchmark.verify_ledger_size_witness import (
            common_prefix,
        )
        self.assertEqual(common_prefix(_objects()), PREFIX)
        self.assertEqual(common_prefix({}), "")
        self.assertEqual(common_prefix({"a/b/one.json": 1, "a/b/two.json": 2}), "a/b")

    def test_a_different_run_shows_a_different_heading(self):
        other = {k.replace("/1-1/", "/9-9/"): v for k, v in _objects().items()}
        text, _ = render(_result(), other)
        self.assertIn("/9-9", text)
        self.assertNotIn(PREFIX, text)


class AbsenceIsNotDisagreementTests(unittest.TestCase):
    """Every way the evidence can be MISSING, kept distinct from the evidence DISAGREEING.

    A review found the module preaching this distinction for objects while collapsing it
    everywhere else: a receipt with no byte count, a receipt with no digest, and record
    counts that were simply absent all came out CONTRADICTED - which says the sink is wrong,
    on the strength of evidence nobody has.
    """

    def test_a_receipt_with_no_byte_count_has_nothing_to_witness_against(self):
        from research.kalshi.frankie_raw_mbo_benchmark.verify_ledger_size_witness import (
            NO_CLAIMED_BYTES,
        )
        result = _result()
        del result["ledger_retention"]["exact_member_ledger"]["bytes"]
        rows = witness_ledgers(result, _objects())
        member = next(r for r in rows if r["ledger"] == "exact_member_ledger")
        self.assertEqual(member["status"], UNAVAILABLE)
        self.assertEqual(member["reason"], NO_CLAIMED_BYTES)
        text, outcome = render(result, _objects())
        self.assertEqual(outcome, UNAVAILABLE)
        # and the sink total must not silently include a zero it never claimed
        self.assertNotIn("12,301,736,545", text.split("- Sink total:")[1].split("\n")[0])

    def test_a_receipt_with_no_digest_is_unavailable_not_a_mismatch(self):
        from research.kalshi.frankie_raw_mbo_benchmark.verify_ledger_size_witness import (
            NO_CLAIMED_DIGEST,
        )
        result = _result()
        del result["ledger_retention"]["exact_member_ledger"]["sha256"]
        rows = witness_content(result, {"exact_member_ledger": "a" * 64})
        self.assertEqual(rows[0]["status"], UNAVAILABLE)
        self.assertEqual(rows[0]["reason"], NO_CLAIMED_DIGEST)

    def test_every_record_count_absent_is_unavailable_not_contradicted(self):
        result = _result()
        del result["layers"]
        del result["traversal"]["records_seen"]
        self.assertEqual(witness_denominator(result)["status"], UNAVAILABLE)
        _, outcome = render(result, _objects())
        self.assertEqual(outcome, UNAVAILABLE)

    def test_counts_that_disagree_are_still_contradicted(self):
        self.assertEqual(witness_denominator(_result(total=50_002))["status"], CONTRADICTED)

    def test_a_boolean_is_not_a_record_count(self):
        result = _result()
        result["traversal"]["records_seen"] = True
        self.assertNotEqual(witness_denominator(result)["status"], CONFIRMED)


class WrongObjectTests(unittest.TestCase):
    """Two keys sharing a basename must refuse, not pick one."""

    def test_a_basename_collision_refuses_rather_than_guessing(self):
        from research.kalshi.frankie_raw_mbo_benchmark.verify_ledger_size_witness import (
            AMBIGUOUS,
        )
        objects = _objects()
        objects[f"{PREFIX}/backup/exact_member_rows.jsonl"] = 999_999
        rows = witness_ledgers(_result(), objects)
        member = next(r for r in rows if r["ledger"] == "exact_member_ledger")
        self.assertEqual(member["status"], UNAVAILABLE)
        self.assertEqual(member["reason"], AMBIGUOUS)
        _, outcome = render(_result(), objects)
        self.assertEqual(outcome, UNAVAILABLE)


class CrashIsMissingEvidenceTests(unittest.TestCase):
    """A result this module cannot read is UNAVAILABLE, never CONTRADICTED."""

    def test_a_result_without_groups_seen_still_renders(self):
        result = _result()
        del result["traversal"]["groups_seen"]
        text, outcome = render(result, _objects())
        self.assertEqual(outcome, CONFIRMED)
        self.assertIn("**50,001** / absent", text)

    def test_an_unreadable_result_exits_two_not_one(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            result = directory / "result.json"
            objects = directory / "objects.json"
            out = directory / "witness.md"
            result.write_text(json.dumps({"traversal": {"records_seen": 1}}), encoding="utf-8")
            objects.write_text(json.dumps(_objects()), encoding="utf-8")
            self.assertEqual(main(["--result", str(result), "--objects", str(objects),
                                   "--output", str(out)]), 2)
            self.assertIn("WITNESS_UNAVAILABLE", out.read_text(encoding="utf-8"))
