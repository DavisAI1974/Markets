"""The principal's OUTPUT ledgers: the required set is DERIVED, the chain is append-only.

Greg, S120 (DROP_IN_S121 item zero, ruling 4): *"don't take any historical number like that
as a valid number that we should follow"*; *"not 10 as the floor. if it's supposed to have
30, the floor is 28. 10 is how 20 get silently dropped."* So no test here asserts a literal
count. Each derives the expected count independently of the module and compares.

Every refusal below is PRODUCED, not asserted: a guard whose firing branch never executed was
never tested (S113, NC-3).
"""
from __future__ import annotations

import ast
import copy
import inspect
import json
import re
import unittest
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark import native_principal_outputs as outputs
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (
    REGISTRY_PATH,
    load_registry,
)

CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "agents"
    / "frankie_native_raw_mbo_calculation_contract_20260828.md"
)


def registry_today() -> dict:
    return load_registry(REGISTRY_PATH)


def contract_today() -> str:
    return CONTRACT_PATH.read_text(encoding="utf-8")


def independent_output_ids(registry: dict) -> list[str]:
    """Read the registry the long way round, so the test does not trust the module's reader."""
    for group in registry["groups"]:
        if group["group_id"] == "append_only_outputs":
            return [entry["layer_id"] for entry in group["entries"]]
    raise AssertionError("no append_only_outputs group in the registry")


def independent_section_ids(contract_text: str) -> list[str]:
    """Line scan, not the module's regex: every `### 4.` heading, first token after `### `."""
    ids = []
    for line in contract_text.splitlines():
        if line.startswith("### 4."):
            ids.append(line.split()[1])
    return ids


class RequiredSetIsDerivedTest(unittest.TestCase):
    def test_output_layer_ids_are_read_from_the_loaded_registry(self):
        registry = registry_today()
        self.assertEqual(
            list(outputs.registry_output_layer_ids(registry)), independent_output_ids(registry)
        )

    def test_contract_section_ids_include_4_0_and_4_0b_in_document_order(self):
        ids = outputs.contract_section_ids(contract_today())
        self.assertEqual(list(ids), independent_section_ids(contract_today()))
        self.assertIn("4.0", ids)
        self.assertIn("4.0b", ids)
        self.assertLess(ids.index("4.0"), ids.index("4.0b"))
        self.assertLess(ids.index("4.0b"), ids.index("4.1"))

    def test_required_count_on_todays_files_is_outputs_plus_sections_plus_two(self):
        registry, contract = registry_today(), contract_today()
        required = outputs.required_ledger_ids(registry, contract)
        expected = len(independent_output_ids(registry)) + len(independent_section_ids(contract)) + 2
        self.assertEqual(len(required), expected)
        self.assertEqual(len(set(required)), len(required), "no ledger id repeats")
        for section in independent_section_ids(contract):
            self.assertIn(f"contract_section_{section}", required)
        self.assertIn("raw_mbo_classification", required)
        self.assertIn("knowledge_verification", required)

    def test_adding_a_contract_heading_grows_the_set_by_exactly_one(self):
        registry, contract = registry_today(), contract_today()
        before = outputs.required_ledger_ids(registry, contract)
        after = outputs.required_ledger_ids(registry, contract + "\n### 4.17 A new focus\n\nText.\n")
        self.assertEqual(len(after), len(before) + 1)
        self.assertEqual(set(after) - set(before), {"contract_section_4.17"})

    def test_removing_an_output_layer_from_a_registry_copy_shrinks_the_set_by_one(self):
        registry, contract = registry_today(), contract_today()
        before = outputs.required_ledger_ids(registry, contract)
        smaller = copy.deepcopy(registry)
        group = next(g for g in smaller["groups"] if g["group_id"] == "append_only_outputs")
        removed = group["entries"].pop()["layer_id"]
        after = outputs.required_ledger_ids(smaller, contract)
        self.assertEqual(len(after), len(before) - 1)
        self.assertEqual(set(before) - set(after), {removed})

    def test_a_contract_with_no_section_headings_is_refused(self):
        with self.assertRaises(outputs.PrincipalOutputError):
            outputs.contract_section_ids("# Not a calculation contract\n\n## 4. Matrix\n")

    def test_a_registry_without_the_output_group_is_refused(self):
        registry = copy.deepcopy(registry_today())
        registry["groups"] = [g for g in registry["groups"] if g["group_id"] != "append_only_outputs"]
        with self.assertRaises(outputs.PrincipalOutputError):
            outputs.registry_output_layer_ids(registry)

    def test_no_module_level_constant_names_a_count(self):
        # Ruling 4. A count typed into the module is the number that becomes the floor.
        tree = ast.parse(inspect.getsource(outputs))
        offenders = []
        for node in tree.body:
            targets = []
            value = None
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, ast.AnnAssign):
                targets, value = [node.target], node.value
            if value is None:
                continue
            if isinstance(value, ast.UnaryOp):
                value = value.operand
            if isinstance(value, ast.Constant) and isinstance(value.value, int) and not isinstance(value.value, bool):
                offenders.append(ast.unparse(targets[0]))
        self.assertEqual(offenders, [], f"module-level integer constants: {offenders}")


# ----------------------------------------------------------------------------------------
# Slice 2: the append-only ledger, the bundle, its receipt, write and load
# ----------------------------------------------------------------------------------------

import hashlib
import tempfile

from research.kalshi.frankie_raw_mbo_benchmark.native_causal_stream import (
    GENESIS_PREVIOUS_RECEIPT_SHA256,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (
    canonical_hash,
)

C1 = 1_633_298_413_318_097_271
C2 = 1_633_298_414_318_097_271
C3 = 1_633_298_415_318_097_271


def canon(value) -> bytes:
    """The package's canonical form, restated here so the test does not trust the module's."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def independent_entry_hash(prev_hash: str, entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "entry_hash"}
    return hashlib.sha256(prev_hash.encode("ascii") + canon(body)).hexdigest()


def rechained(entries: list[dict]) -> list[dict]:
    """Recompute prev/entry hashes over an edited entry list, so a structural defect (a gap, a
    regression) can be tested on its own rather than hidden behind a broken hash."""
    prev = outputs.GENESIS_PREV_HASH
    out = []
    for entry in entries:
        entry = dict(entry, prev_hash=prev)
        entry["entry_hash"] = independent_entry_hash(prev, entry)
        prev = entry["entry_hash"]
        out.append(entry)
    return out


def bundle_fixture(**overrides) -> "outputs.OutputBundle":
    kwargs = dict(
        run_id="run-fixture-0001",
        arm="A_CLEAN",
        role="REAL_TIME_FRANKIE",
        registry=registry_today(),
        contract_text=contract_today(),
    )
    kwargs.update(overrides)
    return outputs.OutputBundle(**kwargs)


class AppendOnlyLedgerTest(unittest.TestCase):
    def test_the_genesis_is_the_causal_stream_convention_sha256_of_nothing(self):
        self.assertEqual(outputs.GENESIS_PREV_HASH, GENESIS_PREVIOUS_RECEIPT_SHA256)
        self.assertEqual(outputs.GENESIS_PREV_HASH, hashlib.sha256(b"").hexdigest())

    def test_entries_chain_from_genesis_with_monotone_sequence_and_recomputable_hashes(self):
        ledger = outputs.AppendOnlyLedger("output_frankie_reasoning_movie")
        first = ledger.append(C1, {"note": "first"})
        second = ledger.append(C2, {"note": "second"})
        self.assertEqual([first["sequence"], second["sequence"]], [0, 1])
        self.assertEqual(first["prev_hash"], outputs.GENESIS_PREV_HASH)
        self.assertEqual(second["prev_hash"], first["entry_hash"])
        self.assertEqual(first["entry_hash"], independent_entry_hash(outputs.GENESIS_PREV_HASH, first))
        self.assertEqual(second["entry_hash"], independent_entry_hash(first["entry_hash"], second))
        self.assertEqual(ledger.head_hash, second["entry_hash"])
        self.assertEqual(
            set(first), {"ledger_id", "sequence", "cutoff_recv_ns", "body", "prev_hash", "entry_hash"}
        )

    def test_an_empty_ledger_has_the_genesis_as_its_head(self):
        self.assertEqual(outputs.AppendOnlyLedger("x").head_hash, outputs.GENESIS_PREV_HASH)

    def test_a_cutoff_may_repeat_but_never_regress_at_write_time(self):
        ledger = outputs.AppendOnlyLedger("x")
        ledger.append(C2, {"a": 1})
        ledger.append(C2, {"a": 2})
        with self.assertRaises(outputs.PrincipalOutputError) as ctx:
            ledger.append(C1, {"a": 3})
        self.assertIn("earlier", str(ctx.exception))

    def test_a_cutoff_must_be_an_integer_nanosecond_reading(self):
        ledger = outputs.AppendOnlyLedger("x")
        for bad in (True, 1.5, "1633298413318097271", None):
            with self.subTest(bad=bad), self.assertRaises(outputs.PrincipalOutputError):
                ledger.append(bad, {"a": 1})

    def test_a_body_must_be_a_mapping(self):
        with self.assertRaises(outputs.PrincipalOutputError):
            outputs.AppendOnlyLedger("x").append(C1, ["not", "a", "mapping"])


class VerifyChainTest(unittest.TestCase):
    def ledger_dict(self) -> dict:
        ledger = outputs.AppendOnlyLedger("x")
        ledger.append(C1, {"a": 1})
        ledger.append(C2, {"a": 2})
        ledger.append(C3, {"a": 3})
        return ledger.to_dict()

    def test_an_untouched_ledger_verifies_and_returns_its_entries(self):
        entries = outputs.verify_chain("x", self.ledger_dict())
        self.assertEqual([e["body"] for e in entries], [{"a": 1}, {"a": 2}, {"a": 3}])

    def test_an_edited_entry_is_refused(self):
        ledger = self.ledger_dict()
        ledger["entries"][1]["body"]["a"] = 99
        with self.assertRaises(outputs.PrincipalOutputError) as ctx:
            outputs.verify_chain("x", ledger)
        self.assertIn("rewritten", str(ctx.exception))

    def test_a_reordered_entry_is_refused(self):
        ledger = self.ledger_dict()
        ledger["entries"][1], ledger["entries"][2] = ledger["entries"][2], ledger["entries"][1]
        with self.assertRaises(outputs.PrincipalOutputError):
            outputs.verify_chain("x", ledger)

    def test_a_cutoff_regression_is_refused_even_with_a_consistent_chain(self):
        ledger = self.ledger_dict()
        entries = ledger["entries"]
        entries[2] = dict(entries[2], cutoff_recv_ns=C1)
        ledger["entries"] = rechained(entries)
        ledger["head_hash"] = ledger["entries"][-1]["entry_hash"]
        with self.assertRaises(outputs.PrincipalOutputError) as ctx:
            outputs.verify_chain("x", ledger)
        self.assertIn("causal order", str(ctx.exception))

    def test_a_sequence_gap_is_refused_even_with_a_consistent_chain(self):
        ledger = self.ledger_dict()
        entries = [ledger["entries"][0], ledger["entries"][2]]
        ledger["entries"] = rechained(entries)
        ledger["head_hash"] = ledger["entries"][-1]["entry_hash"]
        with self.assertRaises(outputs.PrincipalOutputError) as ctx:
            outputs.verify_chain("x", ledger)
        self.assertIn("sequence", str(ctx.exception))

    def test_a_head_hash_that_disagrees_with_the_last_entry_is_refused(self):
        ledger = self.ledger_dict()
        ledger["head_hash"] = "0" * 64
        with self.assertRaises(outputs.PrincipalOutputError):
            outputs.verify_chain("x", ledger)

    def test_a_ledger_filed_under_another_id_is_refused(self):
        with self.assertRaises(outputs.PrincipalOutputError):
            outputs.verify_chain("y", self.ledger_dict())


class OutputBundleTest(unittest.TestCase):
    def test_the_bundle_binds_run_arm_role_registry_and_contract(self):
        registry, contract = registry_today(), contract_today()
        bundle = bundle_fixture()
        body = bundle.to_dict()
        self.assertEqual(body["schema"], "FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_OUTPUTS_V1")
        self.assertEqual((body["run_id"], body["arm"], body["role"]), ("run-fixture-0001", "A_CLEAN", "REAL_TIME_FRANKIE"))
        self.assertEqual(body["registry_sha256"], registry["registry_sha256"])
        self.assertEqual(body["contract_sha256"], hashlib.sha256(contract.encode("utf-8")).hexdigest())
        self.assertEqual(body["ledgers"], {})
        self.assertEqual(list(bundle.required_ledger_ids), list(outputs.required_ledger_ids(registry, contract)))

    def test_the_role_set_is_the_one_staging_allows(self):
        # Declared in both modules so staging can import this one without a cycle; pinned equal.
        from research.kalshi.frankie_raw_mbo_benchmark import native_staging

        self.assertEqual(outputs.ALLOWED_ROLES, native_staging.ALLOWED_ROLES)
        self.assertEqual(outputs.ALLOWED_ARMS, native_staging.ALLOWED_ARMS)

    def test_an_unknown_arm_or_role_is_refused(self):
        with self.assertRaises(outputs.PrincipalOutputError):
            bundle_fixture(arm="B_SOMETHING")
        with self.assertRaises(outputs.PrincipalOutputError):
            bundle_fixture(role="HELPER_LANE")

    def test_ledger_returns_the_same_ledger_on_repeat_and_serialises_it(self):
        bundle = bundle_fixture()
        ledger = bundle.ledger("output_frankie_reasoning_movie")
        ledger.append(C1, {"note": "x"})
        self.assertIs(bundle.ledger("output_frankie_reasoning_movie"), ledger)
        body = bundle.to_dict()["ledgers"]["output_frankie_reasoning_movie"]
        self.assertEqual(body["ledger_id"], "output_frankie_reasoning_movie")
        self.assertEqual(len(body["entries"]), 1)
        self.assertEqual(body["head_hash"], ledger.head_hash)
        self.assertIsNone(body["empty_reason"])

    def test_the_receipt_names_every_missing_required_ledger_and_hashes_itself(self):
        bundle = bundle_fixture()
        bundle.ledger("output_frankie_reasoning_movie").append(C1, {"note": "x"})
        bundle.ledger("output_answer_wall_access_receipts", empty_reason="blind by construction")
        receipt = outputs.bundle_receipt(bundle)
        self.assertEqual(receipt["schema"], "FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_OUTPUTS_RECEIPT_V1")
        self.assertEqual((receipt["run_id"], receipt["arm"]), ("run-fixture-0001", "A_CLEAN"))
        self.assertEqual(
            receipt["ledgers"]["output_frankie_reasoning_movie"],
            {"entry_count": 1, "head_hash": bundle.ledger("output_frankie_reasoning_movie").head_hash},
        )
        self.assertEqual(receipt["ledgers"]["output_answer_wall_access_receipts"]["entry_count"], 0)
        self.assertEqual(list(receipt["required_ledger_ids"]), list(bundle.required_ledger_ids))
        expected_missing = [lid for lid in bundle.required_ledger_ids if lid not in bundle.ledgers]
        self.assertEqual(receipt["missing_ledger_ids"], expected_missing)
        self.assertEqual(len(expected_missing), len(bundle.required_ledger_ids) - 2)
        self.assertEqual(receipt["receipt_sha256"], canonical_hash(receipt, omit="receipt_sha256"))

    def test_a_receipt_over_a_plain_mapping_needs_the_required_set_stated(self):
        bundle = bundle_fixture()
        with self.assertRaises(outputs.PrincipalOutputError):
            outputs.bundle_receipt(bundle.to_dict())
        receipt = outputs.bundle_receipt(bundle.to_dict(), required_ledger_ids=bundle.required_ledger_ids)
        self.assertEqual(receipt["missing_ledger_ids"], list(bundle.required_ledger_ids))


class WriteAndLoadBundleTest(unittest.TestCase):
    def written(self) -> tuple["outputs.OutputBundle", Path, dict]:
        bundle = bundle_fixture()
        bundle.ledger("output_frankie_reasoning_movie").append(C1, {"note": "x"})
        bundle.ledger("output_frankie_reasoning_movie").append(C2, {"note": "y"})
        bundle.ledger("output_answer_wall_access_receipts", empty_reason="blind by construction")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name) / "outputs"
        receipt = outputs.write_bundle(bundle, root)
        return bundle, root, receipt

    def test_one_json_per_ledger_plus_the_receipt_round_trips(self):
        bundle, root, receipt = self.written()
        self.assertTrue((root / "RECEIPT.json").exists())
        self.assertEqual(
            sorted(p.name for p in (root / "ledgers").iterdir()),
            ["output_answer_wall_access_receipts.json", "output_frankie_reasoning_movie.json"],
        )
        self.assertEqual(json.loads((root / "RECEIPT.json").read_text())["receipt_sha256"], receipt["receipt_sha256"])
        self.assertEqual(outputs.load_bundle(root), bundle.to_dict())

    def test_an_entry_edited_on_disk_refuses_to_load(self):
        _bundle, root, _receipt = self.written()
        path = root / "ledgers" / "output_frankie_reasoning_movie.json"
        ledger = json.loads(path.read_text())
        ledger["entries"][0]["body"]["note"] = "edited"
        path.write_text(json.dumps(ledger))
        with self.assertRaises(outputs.PrincipalOutputError):
            outputs.load_bundle(root)

    def test_a_ledger_file_the_receipt_does_not_vouch_for_refuses_to_load(self):
        _bundle, root, _receipt = self.written()
        other = outputs.AppendOnlyLedger("output_frankie_reasoning_movie")
        other.append(C1, {"note": "substituted"})
        (root / "ledgers" / "output_frankie_reasoning_movie.json").write_text(json.dumps(other.to_dict()))
        with self.assertRaises(outputs.PrincipalOutputError) as ctx:
            outputs.load_bundle(root)
        self.assertIn("head_hash", str(ctx.exception))

    def test_a_ledger_file_absent_from_the_receipt_refuses_to_load(self):
        _bundle, root, _receipt = self.written()
        stray = outputs.AppendOnlyLedger("output_probability_movie")
        stray.append(C1, {"p": 1})
        (root / "ledgers" / "output_probability_movie.json").write_text(json.dumps(stray.to_dict()))
        with self.assertRaises(outputs.PrincipalOutputError):
            outputs.load_bundle(root)

    def test_a_tampered_receipt_hash_refuses_to_load(self):
        _bundle, root, _receipt = self.written()
        receipt = json.loads((root / "RECEIPT.json").read_text())
        receipt["arm"] = "A_MEMORY"
        (root / "RECEIPT.json").write_text(json.dumps(receipt))
        with self.assertRaises(outputs.PrincipalOutputError):
            outputs.load_bundle(root)

    def test_a_rewrite_may_only_extend_what_is_already_on_disk(self):
        bundle, root, _receipt = self.written()
        bundle.ledger("output_frankie_reasoning_movie").append(C3, {"note": "z"})
        outputs.write_bundle(bundle, root)
        self.assertEqual(len(outputs.load_bundle(root)["ledgers"]["output_frankie_reasoning_movie"]["entries"]), 3)
        shorter = bundle_fixture()
        shorter.ledger("output_frankie_reasoning_movie").append(C1, {"note": "different history"})
        with self.assertRaises(outputs.PrincipalOutputError) as ctx:
            outputs.write_bundle(shorter, root)
        self.assertIn("never rewritten", str(ctx.exception))


# ----------------------------------------------------------------------------------------
# Slice 3a: the timing rule (one helper, reused) and the state movie
# ----------------------------------------------------------------------------------------

from research.kalshi.frankie_raw_mbo_benchmark.native_full_capture_adapter import (
    FullCaptureAdapter,
)
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import F_LAST

RECV = "clock_receive_time"


def rec(*, seq, order_id, action="A", side="B", size=5, price=3_500_000_000, ts=1_000_000_000):
    """One F_LAST-closed native record, the shape `test_native_full_capture_adapter` drives."""
    return {
        "instrument_id": 42,
        "publisher_id": 1,
        "channel_id": 0,
        "order_id": order_id,
        "action": action,
        "side": side,
        "price": price,
        "size": size,
        "flags": F_LAST,
        "sequence": seq,
        "ts_event": ts,
        "ts_recv": ts + 150_000,
        "ts_in_delta": 0,
        "source_dbn_object": "20211003.dbn",
        "source_dbn_sha256": "0" * 64,
    }


def real_frames() -> list[dict]:
    """Member frames from the REAL adapter: `book` and `book_full` exactly as a member row has them."""
    adapter = FullCaptureAdapter()
    frames = []
    records = [
        rec(seq=1, order_id=11, side="B", price=3_500_000_000, ts=1_000_000_000),
        rec(seq=2, order_id=12, side="A", price=3_501_000_000, ts=2_000_000_000),
        rec(seq=3, order_id=13, side="B", price=3_500_000_000, size=7, ts=3_000_000_000),
    ]
    for record in records:
        frame, _legacy = adapter.apply(
            record, raw_symbol="NGX1", source_dbn_object=record["source_dbn_object"],
            source_dbn_sha256=record["source_dbn_sha256"],
        )
        if frame is not None:
            frames.append(frame)
    return frames


def reading(observed_ns: int, clock: str = RECV) -> dict:
    return {"clock": clock, "observed_ns": observed_ns}


def state_frame(frame: dict, *, cutoff: int, previous_cutoff: int | None, channels: dict | None = None) -> dict:
    """A lawful state-movie body over a real member frame."""
    if channels is None:
        channels = {
            "spread": {"status": "OBSERVED", "value": frame["book"]["spread"]},
            "dipole": {"status": "MISSING"},
            "roll20": {"status": "STRUCTURALLY_NOT_YET_KNOWN"},
            "signed_flow": {"status": "TRUE_ZERO", "value": 0},
        }
    missing = sorted(
        name for name, chan in channels.items() if isinstance(chan, dict) and chan.get("status") == "MISSING"
    )
    return {
        "channels": channels,
        "missing_channels": missing,
        # Deep-copied so a subtest that pops a book field does not leak into the next subtest.
        "book": copy.deepcopy(frame["book"]),
        "fifo_state": outputs.fifo_state_from_book_full(frame["book_full"]),
        "delta": {"previous_cutoff_recv_ns": previous_cutoff, "channels": {}, "book": {}},
    }


class TimingRuleTest(unittest.TestCase):
    def setUp(self):
        self.registry = registry_today()
        self.clocks = outputs.registry_clock_ids(self.registry)

    def test_clock_ids_are_the_registry_causal_clocks_layer_ids(self):
        expected = [
            e["layer_id"] for g in self.registry["groups"] if g["group_id"] == "causal_clocks"
            for e in g["entries"]
        ]
        self.assertEqual(list(self.clocks), expected)
        self.assertIn(outputs.RECEIVE_CLOCK_ID, self.clocks)

    def test_a_reading_names_a_registry_clock_and_an_integer_observation(self):
        self.assertEqual(
            outputs.clock_reading(reading(1500), clock_ids=self.clocks, where="x.lead"), (RECV, 1500)
        )
        self.assertEqual(
            outputs.clock_reading(reading(-7, "clock_event_time"), clock_ids=self.clocks, where="x"),
            ("clock_event_time", -7),
        )

    def test_a_fixed_ladder_label_or_a_clockless_number_is_refused_naming_the_rule(self):
        for bad in ("H+60", "300s", 300, 12.5, {"observed_ns": 5}, {"clock": RECV}, {"clock": "wall", "observed_ns": 1}, {"clock": RECV, "observed_ns": 1.5}, {"clock": RECV, "observed_ns": True}):
            with self.subTest(bad=bad), self.assertRaises(outputs.PrincipalOutputError) as ctx:
                outputs.clock_reading(bad, clock_ids=self.clocks, where="entry.horizon")
            self.assertIn("TIMING RULE", str(ctx.exception))
            self.assertIn("entry.horizon", str(ctx.exception))

    def test_the_scan_refuses_a_clockless_timing_anywhere_in_a_body(self):
        for body in (
            {"lead_ns": 300},
            {"recognition": {"label": "H+N", "horizon": "H+60"}},
            {"runways": [{"runway": "300s"}]},
            {"carried": {"age": 12}},
            {"elapsed": {"observed_ns": 5}},
        ):
            with self.subTest(body=body), self.assertRaises(outputs.PrincipalOutputError) as ctx:
                outputs.refuse_clockless_timings(body, clock_ids=self.clocks, where="entry")
            self.assertIn("TIMING RULE", str(ctx.exception))

    def test_the_scan_accepts_readings_absent_timings_and_non_timing_keys(self):
        outputs.refuse_clockless_timings(
            {
                "lead": reading(300),
                "horizons": [reading(1), reading(2)],
                "recognition": {"lead": None},
                "runway_stages": [{"stage": 1, "signed_flow": -12}],
                "coverage": 0.5,
                "message": "ages ago",
                "stage_duration_ns": 42,
            },
            clock_ids=self.clocks,
            where="entry",
        )

    def test_the_scan_leaves_verbatim_member_row_material_alone(self):
        # `front_order_age_s` and `priority_age_s` are the hash-locked adapter's own names on
        # every level of `book` / `book_full` (D61: wrap, never edit). Copied verbatim into a
        # frame they are on the frame's own receive-clock cutoff, and are not the principal's
        # timings; the scan skips the two verbatim subtrees and nothing else.
        frame = real_frames()[-1]
        body = {"book": frame["book"], "fifo_state": outputs.fifo_state_from_book_full(frame["book_full"])}
        self.assertIn("front_order_age_s", frame["book"]["bid_levels"][0])
        outputs.refuse_clockless_timings(body, clock_ids=self.clocks, where="frame")
        with self.assertRaises(outputs.PrincipalOutputError):
            outputs.refuse_clockless_timings({"elsewhere": {"front_order_age_s": 1.5}}, clock_ids=self.clocks, where="frame")


class FifoStateBuilderTest(unittest.TestCase):
    def test_it_carries_touch_identities_and_the_full_book_hash_and_says_why(self):
        frame = real_frames()[-1]
        state = outputs.fifo_state_from_book_full(frame["book_full"])
        self.assertEqual(state["book_full_sha256"], hashlib.sha256(canon(frame["book_full"])).hexdigest())
        self.assertEqual(state["level_count"], len(frame["book_full"]["bid_levels_full"]) + len(frame["book_full"]["ask_levels_full"]))
        self.assertEqual(state["order_count"], 3)
        bid = state["touch"]["bid"]
        self.assertEqual(bid["price_raw"], 3_500_000_000)
        self.assertEqual([q["order_id"] for q in bid["fifo_queue"]], [11, 13])
        self.assertEqual(bid["fifo_queue"][1]["volume_ahead"], 5)
        for key in ("order_id", "priority_recv_ns", "priority_sequence", "size", "volume_ahead"):
            self.assertIn(key, bid["fifo_queue"][0])
        self.assertEqual(state["touch"]["ask"]["price_raw"], 3_501_000_000)
        self.assertTrue(state["basis"].strip())

    def test_an_empty_side_is_a_stated_absence(self):
        frame = real_frames()[0]
        state = outputs.fifo_state_from_book_full(frame["book_full"])
        self.assertIsNone(state["touch"]["ask"])
        self.assertEqual(state["order_count"], 1)


class StateMovieTest(unittest.TestCase):
    def setUp(self):
        self.frames = real_frames()
        self.registry = registry_today()
        self.bundle = bundle_fixture()
        self.ledger = self.bundle.ledger("output_state_and_state_delta_movie")
        self.cutoffs = [f["ts_recv_ns"] for f in self.frames]

    def validate(self, ledger=None):
        ledger = ledger or self.ledger
        ctx = outputs.ValidationContext(registry=self.registry, bundle=self.bundle.to_dict())
        outputs.validate_ledger_entries(ledger.ledger_id, ledger.to_dict()["entries"], ctx)
        return ctx

    def test_a_lawful_movie_over_real_member_frames_passes(self):
        previous = None
        for frame, cutoff in zip(self.frames, self.cutoffs):
            self.ledger.append(cutoff, state_frame(frame, cutoff=cutoff, previous_cutoff=previous))
            previous = cutoff
        self.validate()

    def test_a_carried_channel_keeps_its_source_timestamp_and_age_on_a_clock(self):
        c0, c1 = self.cutoffs[0], self.cutoffs[1]
        carried = {
            "spread": {"status": "PAST_CARRY", "value": 1_000_000, "source_recv_ns": c0, "age": reading(c1 - c0)},
        }
        self.ledger.append(c1, state_frame(self.frames[1], cutoff=c1, previous_cutoff=None, channels=carried))
        self.validate()
        for broken in (
            {"status": "PAST_CARRY", "value": 1, "age": reading(c1 - c0)},
            {"status": "STALE", "value": 1, "source_recv_ns": c0},
            {"status": "STALE", "value": 1, "source_recv_ns": c0, "age": reading(c1 - c0 + 1)},
            {"status": "PAST_CARRY", "value": 1, "source_recv_ns": c1 + 1, "age": reading(-1)},
            {"status": "PAST_CARRY", "value": 1, "source_recv_ns": c0, "age": "1s"},
        ):
            with self.subTest(broken=broken):
                ledger = outputs.AppendOnlyLedger("output_state_and_state_delta_movie")
                ledger.append(c1, state_frame(self.frames[1], cutoff=c1, previous_cutoff=None, channels={"spread": broken}))
                with self.assertRaises(outputs.PrincipalOutputError):
                    self.validate(ledger)

    def test_missing_channels_are_named_on_every_frame(self):
        c0 = self.cutoffs[0]
        body = state_frame(self.frames[0], cutoff=c0, previous_cutoff=None)
        body["missing_channels"] = []
        self.ledger.append(c0, body)
        with self.assertRaises(outputs.PrincipalOutputError) as ctx:
            self.validate()
        self.assertIn("MISSING", str(ctx.exception))

    def test_every_channel_status_is_one_of_the_seven_and_true_zero_is_zero(self):
        c0 = self.cutoffs[0]
        for channels in (
            {"x": {"status": "UNKNOWN", "value": 1}},
            {"x": {"status": "OBSERVED"}},
            {"x": {"status": "TRUE_ZERO", "value": 3}},
            {"x": "OBSERVED"},
            {},
        ):
            with self.subTest(channels=channels):
                ledger = outputs.AppendOnlyLedger("output_state_and_state_delta_movie")
                body = state_frame(self.frames[0], cutoff=c0, previous_cutoff=None, channels=channels) if channels else None
                if body is None:
                    body = state_frame(self.frames[0], cutoff=c0, previous_cutoff=None)
                    body["channels"] = {}
                ledger.append(c0, body)
                with self.assertRaises(outputs.PrincipalOutputError):
                    self.validate(ledger)

    def test_the_frame_carries_the_book_as_on_the_member_row(self):
        c0 = self.cutoffs[0]
        for mutate in (
            lambda b: b.pop("book"),
            lambda b: b["book"].pop("bid_levels"),
            lambda b: b["book"].pop("best_ask"),
            lambda b: b["book"]["bid_levels"][0].pop("price_raw"),
            lambda b: b["book"].pop("bid_depth_full"),
        ):
            with self.subTest():
                ledger = outputs.AppendOnlyLedger("output_state_and_state_delta_movie")
                body = state_frame(self.frames[0], cutoff=c0, previous_cutoff=None)
                mutate(body)
                ledger.append(c0, body)
                with self.assertRaises(outputs.PrincipalOutputError) as ctx:
                    self.validate(ledger)
                self.assertIn("book", str(ctx.exception))

    def test_the_frame_carries_the_fifo_state_with_touch_identities_and_the_full_book_hash(self):
        c0 = self.cutoffs[0]
        for mutate in (
            lambda b: b.pop("fifo_state"),
            lambda b: b["fifo_state"].pop("touch"),
            lambda b: b["fifo_state"].pop("book_full_sha256"),
            lambda b: b["fifo_state"].pop("basis"),
            lambda b: b["fifo_state"]["touch"]["bid"]["fifo_queue"][0].pop("priority_sequence"),
            lambda b: b["fifo_state"].pop("order_count"),
        ):
            with self.subTest():
                ledger = outputs.AppendOnlyLedger("output_state_and_state_delta_movie")
                body = state_frame(self.frames[0], cutoff=c0, previous_cutoff=None)
                mutate(body)
                ledger.append(c0, body)
                with self.assertRaises(outputs.PrincipalOutputError) as ctx:
                    self.validate(ledger)
                self.assertIn("fifo", str(ctx.exception).lower())

    def test_the_delta_points_at_the_previous_frame(self):
        c0, c1 = self.cutoffs[0], self.cutoffs[1]
        self.ledger.append(c0, state_frame(self.frames[0], cutoff=c0, previous_cutoff=None))
        self.ledger.append(c1, state_frame(self.frames[1], cutoff=c1, previous_cutoff=c0 - 1))
        with self.assertRaises(outputs.PrincipalOutputError) as ctx:
            self.validate()
        self.assertIn("delta", str(ctx.exception))
        for mutate in (lambda b: b.pop("delta"), lambda b: b["delta"].pop("book"), lambda b: b["delta"].pop("channels")):
            with self.subTest():
                ledger = outputs.AppendOnlyLedger("output_state_and_state_delta_movie")
                body = state_frame(self.frames[0], cutoff=c0, previous_cutoff=None)
                mutate(body)
                ledger.append(c0, body)
                with self.assertRaises(outputs.PrincipalOutputError):
                    self.validate(ledger)

    def test_a_first_frame_claiming_a_predecessor_is_refused(self):
        c0 = self.cutoffs[0]
        self.ledger.append(c0, state_frame(self.frames[0], cutoff=c0, previous_cutoff=c0 - 5))
        with self.assertRaises(outputs.PrincipalOutputError):
            self.validate()


# ----------------------------------------------------------------------------------------
# Slice 3b: reasoning movie, probability movie, candidate discoveries, first locks
# ----------------------------------------------------------------------------------------


def sha_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class LedgerRuleCase(unittest.TestCase):
    """Shared plumbing: a context over today's registry and a bundle, and a one-ledger check."""

    def setUp(self):
        self.registry = registry_today()
        self.bundle = bundle_fixture()
        self.ctx = outputs.ValidationContext(registry=self.registry, bundle=self.bundle.to_dict())

    def check(self, ledger_id: str, bodies: list[tuple[int, dict]], ctx=None):
        ledger = outputs.AppendOnlyLedger(ledger_id)
        for cutoff, body in bodies:
            ledger.append(cutoff, body)
        outputs.validate_ledger_entries(ledger_id, ledger.to_dict()["entries"], ctx or self.ctx)
        return ledger

    def refused(self, ledger_id: str, bodies: list[tuple[int, dict]], needle: str | None = None, ctx=None):
        with self.assertRaises(outputs.PrincipalOutputError) as caught:
            self.check(ledger_id, bodies, ctx)
        if needle is not None:
            self.assertIn(needle, str(caught.exception))
        return caught.exception


def reasoning_body(**overrides) -> dict:
    body = {
        "role": "REAL_TIME_FRANKIE",
        "reasoning": "persistence read off the bid ladder; queue at the touch unchanged",
        "helper_invocations": [],
        "knowledge_retrievals": [],
    }
    body.update(overrides)
    return body


def helper(**overrides) -> dict:
    record = {
        "persona": "queue-survival-reviewer",
        "question": "does the at-risk count support the persistence read?",
        "answer_sha256": sha_of("answer"),
    }
    record.update(overrides)
    return record


class ReasoningMovieTest(LedgerRuleCase):
    LEDGER = "output_frankie_reasoning_movie"

    def test_a_plain_reasoning_entry_and_a_helper_invocation_pass(self):
        self.check(self.LEDGER, [(C1, reasoning_body()), (C2, reasoning_body(helper_invocations=[helper()]))])

    def test_a_helper_invocation_carries_persona_question_and_answer_hash(self):
        for broken in (helper(persona=""), helper(question=None), helper(answer_sha256="not-a-sha"), "queue-survival-reviewer"):
            with self.subTest(broken=broken):
                self.refused(self.LEDGER, [(C1, reasoning_body(helper_invocations=[broken]))])

    def test_a_helper_that_looks_like_a_parallel_lane_is_refused(self):
        for key in ("lane", "cpu", "cpu_affinity", "parallel", "output_artifact"):
            with self.subTest(key=key):
                exc = self.refused(self.LEDGER, [(C1, reasoning_body(helper_invocations=[helper(**{key: 1})]))])
                self.assertIn("D63", str(exc))
                self.assertIn("D64", str(exc))

    def test_the_role_is_the_bundle_role_and_the_reasoning_is_stated(self):
        self.refused(self.LEDGER, [(C1, reasoning_body(role="FORECASTER_FRANKIE"))], "role")
        self.refused(self.LEDGER, [(C1, reasoning_body(reasoning=""))], "reasoning")

    def test_a_knowledge_retrieval_cites_a_receipt_that_exists_at_or_before_the_cutoff(self):
        self.ctx.receipt_cutoffs["kr-0001"] = C2
        self.check(self.LEDGER, [(C2, reasoning_body(knowledge_retrievals=["kr-0001"]))])
        self.refused(self.LEDGER, [(C1, reasoning_body(knowledge_retrievals=["kr-0001"]))], "after")
        self.refused(self.LEDGER, [(C2, reasoning_body(knowledge_retrievals=["kr-9999"]))], "no receipt")


def probability_body(**overrides) -> dict:
    body = {
        "instance_id": "cand-0001",
        "snapshot_id": "snap-0",
        "head": "exhaustion_persistence_vs_collapse",
        "view": "rt-frankie/persistence/v1",
        "probabilities": {"PERSIST": 0.4, "COLLAPSE": 0.6},
        "evaluation": reading(C1),
        "lock_rule_revision": "lock-rule-r1",
        "lock_state": "NO_LOCK",
    }
    body.update(overrides)
    return body


class ProbabilityMovieTest(LedgerRuleCase):
    LEDGER = "output_probability_movie"

    def test_a_partition_head_passes_and_is_remembered_for_the_lock_ledger(self):
        ledger = self.check(self.LEDGER, [(C1, probability_body())])
        self.assertEqual(self.ctx.probability_entry_cutoffs, {ledger.head_hash: C1})

    def test_probabilities_are_in_unit_range_and_sum_to_one_where_they_partition(self):
        self.refused(self.LEDGER, [(C1, probability_body(probabilities={"PERSIST": 0.7, "COLLAPSE": 0.6}))], "sum")
        self.refused(self.LEDGER, [(C1, probability_body(probabilities={"PERSIST": 1.2, "COLLAPSE": -0.2}))])
        self.refused(self.LEDGER, [(C1, probability_body(probabilities={}))])
        self.refused(self.LEDGER, [(C1, probability_body(probabilities={"PERSIST": "0.4", "COLLAPSE": 0.6}))])

    def test_a_non_partition_head_says_so_with_a_reason(self):
        survival = {"survives_past_first_reading": 0.9, "survives_past_second_reading": 0.7}
        self.check(self.LEDGER, [(C1, probability_body(probabilities=survival, partition=False, not_a_partition_reason="survival curve: P(runway survives past each observed reading), not exclusive outcomes"))])
        self.refused(self.LEDGER, [(C1, probability_body(probabilities=survival, partition=False))], "not_a_partition_reason")
        self.refused(self.LEDGER, [(C1, probability_body(probabilities=survival))], "sum")

    def test_the_evaluation_is_a_clock_reading_at_or_before_the_cutoff(self):
        self.refused(self.LEDGER, [(C1, probability_body(evaluation=C1))], "TIMING RULE")
        self.refused(self.LEDGER, [(C1, probability_body(evaluation=reading(C1 + 1)))], "after")
        self.check(self.LEDGER, [(C1, probability_body(evaluation=reading(C1 - 400, "clock_model_evaluation")))])

    def test_identity_head_view_lock_rule_and_lock_state_are_required(self):
        for broken in (
            dict(instance_id=""), dict(snapshot_id=None), dict(head=""), dict(view=""),
            dict(lock_rule_revision=""), dict(lock_state="LOCKED"),
        ):
            with self.subTest(broken=broken):
                self.refused(self.LEDGER, [(C1, probability_body(**broken))])
        for state in ("FIRST_LOCK", "NO_RELIABLE_LOCK", "NO_LOCK", "WRONG_LOCK", "LATE", "CENSORED"):
            with self.subTest(state=state):
                self.check(self.LEDGER, [(C1, probability_body(lock_state=state))])


def candidate_body(**overrides) -> dict:
    body = {
        "candidate_id": "cand-0001",
        "family_id": "fam-000001",
        "member_group_indices": [4562, 4563],
        "falsifier": "a member F_LAST after the lawful cutoff, or a second instrument among the members",
        "first_lawful_availability_ns": C2 - 500,
        "recognition": {"label": "PRIOR", "lead": reading(1_500_000_000)},
    }
    body.update(overrides)
    return body


class CandidateDiscoveriesTest(LedgerRuleCase):
    LEDGER = "output_candidate_discoveries"

    def test_a_discovery_names_its_members_its_falsifier_and_its_recognition_on_a_clock(self):
        self.check(self.LEDGER, [(C2, candidate_body())])

    def test_member_groups_and_falsifier_are_required(self):
        self.refused(self.LEDGER, [(C2, candidate_body(member_group_indices=[]))], "member")
        self.refused(self.LEDGER, [(C2, candidate_body(member_group_indices=[1, "2"]))], "member")
        self.refused(self.LEDGER, [(C2, candidate_body(falsifier=""))], "falsifier")
        self.refused(self.LEDGER, [(C2, candidate_body(candidate_id=""))])
        self.refused(self.LEDGER, [(C2, candidate_body(family_id=""))])

    def test_a_discovery_is_not_lawful_before_its_first_availability(self):
        self.refused(self.LEDGER, [(C2, candidate_body(first_lawful_availability_ns=C2 + 1))], "availability")

    def test_the_recognition_label_and_its_lead_agree_in_sign(self):
        self.check(self.LEDGER, [(C2, candidate_body(recognition={"label": "T0", "lead": reading(0)}))])
        self.check(self.LEDGER, [(C2, candidate_body(recognition={"label": "H+N", "lead": reading(-2_000_000_000)}))])
        for recognition in (
            {"label": "PRIOR", "lead": reading(0)},
            {"label": "T0", "lead": reading(5)},
            {"label": "H+N", "lead": reading(5)},
            {"label": "H+60", "lead": reading(-60_000_000_000)},
            {"label": "PRIOR", "lead": "300s"},
            {"label": "PRIOR"},
        ):
            with self.subTest(recognition=recognition):
                self.refused(self.LEDGER, [(C2, candidate_body(recognition=recognition))])


def lock_body(**overrides) -> dict:
    body = {"candidate_id": "cand-0001", "lock_rule_revision": "lock-rule-r1", "lock_state": "NO_LOCK", "reason": "persistence 0.5 does not clear the r1 bar"}
    body.update(overrides)
    return body


class FirstLocksTest(LedgerRuleCase):
    LEDGER = "output_first_locks_and_no_locks"

    def setUp(self):
        super().setUp()
        probability = self.check("output_probability_movie", [(C2, probability_body()), (C3, probability_body(snapshot_id="snap-1", lock_state="FIRST_LOCK"))])
        self.p2, self.p3 = [e["entry_hash"] for e in probability.entries]

    def first_lock(self, cutoff, **overrides):
        body = lock_body(lock_state="FIRST_LOCK", probability_entry_hash=self.p3, lock_at=reading(cutoff))
        body.pop("reason")
        body.update(overrides)
        return body

    def test_a_no_lock_then_a_first_lock_referencing_the_probability_entry_passes(self):
        self.check(self.LEDGER, [(C2, lock_body()), (C3, self.first_lock(C3))])
        self.assertEqual((self.ctx.locks, self.ctx.no_locks), (1, 1))
        self.assertEqual(self.ctx.first_locks, {"cand-0001": C3})

    def test_a_first_lock_is_stamped_at_its_cutoff_and_never_moved_earlier(self):
        self.refused(self.LEDGER, [(C3, self.first_lock(C3, lock_at=reading(C2)))], "never moved")
        self.refused(self.LEDGER, [(C3, self.first_lock(C3, lock_at=C3))], "TIMING RULE")
        self.refused(self.LEDGER, [(C3, self.first_lock(C3, lock_at=None))])

    def test_a_first_lock_references_a_probability_entry_written_at_or_before_it(self):
        self.refused(self.LEDGER, [(C3, self.first_lock(C3, probability_entry_hash="0" * 64))], "probability")
        self.refused(self.LEDGER, [(C2, self.first_lock(C2, probability_entry_hash=self.p3))], "probability")
        self.check(self.LEDGER, [(C2, self.first_lock(C2, probability_entry_hash=self.p2))])

    def test_a_second_first_lock_on_the_same_candidate_is_refused(self):
        self.refused(self.LEDGER, [(C2, self.first_lock(C2, probability_entry_hash=self.p2)), (C3, self.first_lock(C3))], "already")

    def test_no_lock_and_no_reliable_lock_carry_a_reason(self):
        self.check(self.LEDGER, [(C2, lock_body(lock_state="NO_RELIABLE_LOCK"))])
        self.refused(self.LEDGER, [(C2, lock_body(reason=""))], "reason")
        self.refused(self.LEDGER, [(C2, lock_body(lock_state="WRONG_LOCK"))])

    def test_a_lock_is_never_withdrawn(self):
        self.refused(self.LEDGER, [(C2, self.first_lock(C2, probability_entry_hash=self.p2)), (C3, lock_body())], "withdrawn")


# ----------------------------------------------------------------------------------------
# Slice 3c: negative ledger, knowledge receipts, invocation receipts, answer wall, run hashes
# ----------------------------------------------------------------------------------------


def negative_body(**overrides) -> dict:
    body = {
        "kind": "SPARSE",
        "section": "4.5",
        "stratum": {"family": "fam-000001", "side": "ASK", "phase": "PRE_SETTLEMENT"},
        "numerator": 0,
        "denominator": 3,
        "statement": "no ASK-side group in fam-000001 closed before the cutoff; absence recorded, not inferred",
    }
    body.update(overrides)
    return body


class NegativeLedgerTest(LedgerRuleCase):
    LEDGER = "output_negative_sparse_inconclusive_ledger"

    def test_every_kind_passes_with_its_numerator_and_denominator(self):
        for kind in ("ABSTENTION", "WEAK", "NEGATIVE", "SPARSE", "INCONCLUSIVE"):
            with self.subTest(kind=kind):
                self.check(self.LEDGER, [(C1, negative_body(kind=kind))])

    def test_numerator_and_denominator_are_population_counts_on_every_entry(self):
        for broken in (dict(numerator=None), dict(denominator="3"), dict(numerator=4, denominator=3), dict(numerator=-1), dict(denominator=-1)):
            with self.subTest(broken=broken):
                self.refused(self.LEDGER, [(C1, negative_body(**broken))])

    def test_kind_statement_and_stratum_are_required(self):
        self.refused(self.LEDGER, [(C1, negative_body(kind="MAYBE"))], "kind")
        self.refused(self.LEDGER, [(C1, negative_body(statement=""))], "statement")
        self.refused(self.LEDGER, [(C1, negative_body(stratum="fam-000001"))], "stratum")


def knowledge_receipt_body(**overrides) -> dict:
    body = {
        "receipt_id": "kr-0001",
        "layer_id": "controlling_rt_mission",
        "sha256": sha_of("mission"),
        "disposition": "INSPECTED",
    }
    body.update(overrides)
    return body


class KnowledgeRetrievalReceiptsTest(LedgerRuleCase):
    LEDGER = "output_knowledge_retrieval_receipts"

    def test_receipts_are_remembered_by_id_at_their_cutoff(self):
        self.check(self.LEDGER, [(C1, knowledge_receipt_body()), (C2, knowledge_receipt_body(receipt_id="kr-0002", disposition="UNINSPECTED"))])
        self.assertEqual(self.ctx.receipt_cutoffs, {"kr-0001": C1, "kr-0002": C2})

    def test_layer_hash_and_disposition_are_required_and_ids_do_not_repeat(self):
        for broken in (dict(layer_id=""), dict(sha256="abc"), dict(disposition="READ"), dict(receipt_id="")):
            with self.subTest(broken=broken):
                self.refused(self.LEDGER, [(C1, knowledge_receipt_body(**broken))])
        self.refused(self.LEDGER, [(C1, knowledge_receipt_body()), (C2, knowledge_receipt_body())], "repeats")


def invocation_body(turn: int = 0, **overrides) -> dict:
    body = {
        "mechanism": "AGENT_SESSION",
        "session_id": "session_fixture_0001",
        "model_identity_as_reported_by_session": "the-model-the-session-reported",
        "request_sha256": sha_of(f"request-{turn}"),
        "response_sha256": sha_of(f"response-{turn}"),
    }
    body.update(overrides)
    return body


class InvocationReceiptsTest(LedgerRuleCase):
    LEDGER = "output_provider_invocation_response_receipts"

    def test_an_agent_session_receipt_per_cutoff_passes(self):
        self.check(self.LEDGER, [(C1, invocation_body(0)), (C2, invocation_body(1))])

    def test_an_api_shaped_receipt_is_refused_because_a_correct_session_run_could_not_supply_it(self):
        for key in ("provider", "requested_model", "served_model", "principal_invocation_id", "usage", "input_tokens", "output_tokens"):
            with self.subTest(key=key):
                exc = self.refused(self.LEDGER, [(C1, invocation_body(0, **{key: "x"}))])
                self.assertIn("AGENT SESSION", str(exc))
                self.assertIn("D70", str(exc))

    def test_mechanism_session_and_model_identity_are_required(self):
        self.refused(self.LEDGER, [(C1, invocation_body(0, mechanism="API"))], "mechanism")
        self.refused(self.LEDGER, [(C1, invocation_body(0, session_id=""))], "session_id")
        self.refused(self.LEDGER, [(C1, invocation_body(0, model_identity_as_reported_by_session=""))], "model_identity")

    def test_request_and_response_hashes_must_differ(self):
        same = sha_of("same")
        self.refused(self.LEDGER, [(C1, invocation_body(0, request_sha256=same, response_sha256=same))], "own input")
        self.refused(self.LEDGER, [(C1, invocation_body(0, response_sha256="nope"))])


class AnswerWallReceiptsTest(LedgerRuleCase):
    LEDGER = "output_answer_wall_access_receipts"

    def test_an_empty_ledger_passes_and_any_entry_invalidates_the_run(self):
        self.check(self.LEDGER, [])
        exc = self.refused(self.LEDGER, [(C1, {"accessed": "later_outcome_reveal"})])
        self.assertIn("invalidates", str(exc))


def run_hash_body(phase: str, state: str = "state-0", **overrides) -> dict:
    body = {
        "phase": phase,
        "run_id": "run-fixture-0001",
        "mission_sha256": sha_of("mission"),
        "contract_sha256": hashlib.sha256(contract_today().encode("utf-8")).hexdigest(),
        "knowledge_manifest_sha256": sha_of("manifest"),
        "source_manifest_sha256": sha_of("source"),
        "code_sha256": sha_of("code"),
        "state_sha256": sha_of(state),
    }
    body.update(overrides)
    return body


class RunHashesTest(LedgerRuleCase):
    LEDGER = "output_source_state_manifest_code_model_run_hashes"

    def test_start_and_end_with_equal_invariants_and_a_moved_state_pass(self):
        self.check(self.LEDGER, [(C1, run_hash_body("START")), (C3, run_hash_body("END", state="state-3"))])

    def test_exactly_two_entries_start_then_end(self):
        self.refused(self.LEDGER, [(C1, run_hash_body("START"))], "START")
        self.refused(self.LEDGER, [(C1, run_hash_body("END")), (C3, run_hash_body("START"))], "START")
        self.refused(self.LEDGER, [(C1, run_hash_body("START")), (C2, run_hash_body("END")), (C3, run_hash_body("END"))])

    def test_every_hash_but_the_state_is_invariant_across_the_run(self):
        for key in ("mission_sha256", "contract_sha256", "knowledge_manifest_sha256", "source_manifest_sha256", "code_sha256"):
            with self.subTest(key=key):
                end = run_hash_body("END", state="state-3", **{key: sha_of("changed")})
                # A moved contract hash is caught first as "not the contract this bundle is bound
                # to"; every other invariant is caught as a START/END disagreement.
                needle = "contract" if key == "contract_sha256" else "only the state"
                self.refused(self.LEDGER, [(C1, run_hash_body("START")), (C3, end)], needle)

    def test_the_contract_hash_is_the_bundles_and_the_run_id_is_the_bundles(self):
        self.refused(self.LEDGER, [(C1, run_hash_body("START", contract_sha256=sha_of("other"))), (C3, run_hash_body("END", contract_sha256=sha_of("other")))], "contract")
        self.refused(self.LEDGER, [(C1, run_hash_body("START", run_id="other")), (C3, run_hash_body("END", run_id="other"))], "run_id")

    def test_an_optional_model_identity_is_invariant_too(self):
        self.check(self.LEDGER, [(C1, run_hash_body("START", model_identity="m")), (C3, run_hash_body("END", state="s", model_identity="m"))])
        self.refused(self.LEDGER, [(C1, run_hash_body("START", model_identity="m")), (C3, run_hash_body("END", state="s", model_identity="n"))])


if __name__ == "__main__":
    unittest.main()
