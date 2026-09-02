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


if __name__ == "__main__":
    unittest.main()
