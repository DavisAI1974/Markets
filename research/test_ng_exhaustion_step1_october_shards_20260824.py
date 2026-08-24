#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from pathlib import Path

import ng_exhaustion_mbo_5y_step1_census_20260822 as census
from ng_exhaustion_step1_october_shards_20260824 import (
    BOUNDARY_METHOD,
    F_LAST,
    F_SNAPSHOT,
    FROZEN_CANDIDATE_COMMIT,
    OctoberShardError,
    canonical_science_row,
    merge_shard_bundles,
    october_shard_plan,
    prove_transition_records,
    trim_seconds,
    validate_boundary_gate,
    verify_monolithic_equivalence,
)


RESEARCH = Path(__file__).resolve().parent
MANIFEST = RESEARCH / "kalshi" / "NG_EXHAUSTION_MBO_5Y_CANONICAL_OBJECT_MANIFEST_20260822.json"


def mbo(
    iid: int,
    action: str,
    *,
    side: str = "N",
    order_id: int = 0,
    price: int = 0,
    size: int = 0,
    flags: int = F_LAST,
    seq: int = 1,
    ts_ns: int = 1_000_000_000,
) -> dict[str, object]:
    return {
        "instrument_id": iid,
        "publisher_id": 1,
        "channel_id": 1,
        "order_id": order_id,
        "action": action,
        "side": side,
        "price": price,
        "size": size,
        "flags": flags,
        "sequence": seq,
        "ts_event": ts_ns,
        "ts_recv": ts_ns,
        "ts_in_delta": 0,
    }


def write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as handle:
            for row in rows:
                handle.write((json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode())


class OctoberPlanTests(unittest.TestCase):
    def test_four_weekly_shards_bind_exact_ordered_objects(self) -> None:
        manifest = json.loads(MANIFEST.read_text())
        plan = october_shard_plan(manifest)
        self.assertEqual([x["start_boundary_date"] for x in plan["shards"]], [None, "20211010", "20211017", "20211024"])
        self.assertEqual([x["end_boundary_date"] for x in plan["shards"]], ["20211010", "20211017", "20211024", None])
        self.assertEqual([len(x["source_objects"]) for x in plan["shards"]], [8, 7, 7, 7])
        keys = set()
        for shard in plan["shards"]:
            for obj in shard["source_objects"]:
                self.assertEqual(set(obj), {"date", "key", "bytes", "sha256", "native_segment_job_id"})
                keys.add(obj["key"])
        expected = {x["key"] for x in manifest["canonical_dbn_objects"] if x["segment"] == "20211001_20211101"}
        self.assertEqual(keys, expected)


class BoundaryDifferentialTests(unittest.TestCase):
    def test_clean_snapshot_reaches_exact_future_state(self) -> None:
        prior = [mbo(1, "A", side="B", order_id=8, price=3_000_000_000, size=2, ts_ns=1)]
        boundary = [
            mbo(1, "R", flags=F_SNAPSHOT, ts_ns=700_000_000_000),
            mbo(1, "A", side="B", order_id=9, price=3_100_000_000, size=3, flags=F_SNAPSHOT | F_LAST, seq=2, ts_ns=700_000_000_001),
            mbo(1, "T", side="B", price=3_100_000_000, size=1, seq=3, ts_ns=1_001_000_000_000),
        ]
        proof = prove_transition_records(prior, boundary, warmup_seconds=300)
        self.assertEqual(proof["status"], "PASS")
        self.assertEqual(proof["continued_state_sha256"], proof["fresh_state_sha256"])
        self.assertGreater(proof["cut_epoch_second"], 1001)

    def test_prior_integrity_divergence_fails_closed(self) -> None:
        prior = [mbo(1, "C", side="B", order_id=999, size=1, ts_ns=1)]
        boundary = [
            mbo(1, "R", flags=F_SNAPSHOT, ts_ns=700_000_000_000),
            mbo(1, "A", side="B", order_id=9, price=3_100_000_000, size=3, flags=F_SNAPSHOT | F_LAST, seq=2, ts_ns=700_000_000_001),
            mbo(1, "T", side="B", price=3_100_000_000, size=1, seq=3, ts_ns=1_001_000_000_000),
        ]
        proof = prove_transition_records(prior, boundary, warmup_seconds=300)
        self.assertEqual(proof["status"], "FAIL_CLOSED")
        self.assertIn("state_mismatch", proof["reasons"])

    def test_omitted_instrument_fails_closed(self) -> None:
        prior = [mbo(2, "A", side="A", order_id=3, price=4_000_000_000, size=2, ts_ns=1)]
        boundary = [
            mbo(1, "R", flags=F_SNAPSHOT, ts_ns=700_000_000_000),
            mbo(1, "A", side="B", order_id=9, price=3_100_000_000, size=3, flags=F_SNAPSHOT | F_LAST, seq=2, ts_ns=700_000_000_001),
            mbo(1, "T", side="B", price=3_100_000_000, size=1, seq=3, ts_ns=1_001_000_000_000),
        ]
        proof = prove_transition_records(prior, boundary, warmup_seconds=300)
        self.assertEqual(proof["status"], "FAIL_CLOSED")
        self.assertEqual(proof["continued_instrument_ids"], [1, 2])
        self.assertEqual(proof["fresh_instrument_ids"], [1])

    def test_gate_rejects_wrong_induction_chain(self) -> None:
        plan = {"plan_sha256": "p", "boundary_transitions": [
            {"predecessor_date": "20211001", "boundary_date": "20211010", "boundary_object_sha256": "a"},
            {"predecessor_date": "20211010", "boundary_date": "20211017", "boundary_object_sha256": "b"},
            {"predecessor_date": "20211017", "boundary_date": "20211024", "boundary_object_sha256": "c"},
        ]}
        proofs = [
            {"status": "PASS", "predecessor_date": "20211001", "boundary_date": "20211010", "boundary_object_sha256": "a", "cut_epoch_second": 10},
            {"status": "PASS", "predecessor_date": "20211009", "boundary_date": "20211017", "boundary_object_sha256": "b", "cut_epoch_second": 20},
            {"status": "PASS", "predecessor_date": "20211017", "boundary_date": "20211024", "boundary_object_sha256": "c", "cut_epoch_second": 30},
        ]
        with self.assertRaises(OctoberShardError):
            validate_boundary_gate({"schema": "NG_EXHAUSTION_STEP1_OCTOBER_BOUNDARY_GATE_V2_20260824", "status": "PASS", "plan_sha256": "p", "boundary_proofs": proofs}, plan)

    def test_gate_accepts_exact_self_hashed_induction_chain(self) -> None:
        plan = october_shard_plan(json.loads(MANIFEST.read_text()))
        cuts = [1_633_824_061, 1_634_428_861, 1_635_033_661]
        proofs = []
        for transition, cut in zip(plan["boundary_transitions"], cuts):
            proof = {
                "schema": "NG_EXHAUSTION_STEP1_OCTOBER_BOUNDARY_PROOF_V2_20260824",
                "status": "PASS",
                "method": BOUNDARY_METHOD,
                "plan_sha256": plan["plan_sha256"],
                "source_manifest_sha256": plan["source_manifest_sha256"],
                "frozen_candidate_commit": FROZEN_CANDIDATE_COMMIT,
                "engine_hashes": census.material_hashes(),
                "ruleset_sha256": census.ruleset_sha256(),
                "predecessor_date": transition["predecessor_date"],
                "boundary_date": transition["boundary_date"],
                "boundary_object_sha256": transition["boundary_object_sha256"],
                "source_objects": transition["source_objects"],
                "warmup_seconds": 300,
                "reorder_tolerance_seconds": 60,
                "reasons": [],
                "scientific_engine_changed": False,
                "cut_epoch_second": cut,
                "continued_state_sha256": "same",
                "fresh_state_sha256": "same",
            }
            proof["receipt_sha256"] = _json_sha(proof)
            proofs.append(proof)
        gate = {
            "schema": "NG_EXHAUSTION_STEP1_OCTOBER_BOUNDARY_GATE_V2_20260824",
            "status": "PASS",
            "plan_sha256": plan["plan_sha256"],
            "source_manifest_sha256": plan["source_manifest_sha256"],
            "frozen_candidate_commit": FROZEN_CANDIDATE_COMMIT,
            "engine_hashes": census.material_hashes(),
            "ruleset_sha256": census.ruleset_sha256(),
            "boundary_proofs": proofs,
            "scientific_engine_changed": False,
        }
        gate["receipt_sha256"] = _json_sha(gate)
        self.assertEqual(validate_boundary_gate(gate, plan)["status"], "PASS")


class TrimAndMergeTests(unittest.TestCase):
    def test_trim_is_half_open_and_canonicalizes_validated_source(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "native" / "20211001_20211101" / "glbx-mdp3-20211010.mbo.dbn.zst"
            input_path, output_path = root / "in.gz", root / "out.gz"
            objects = [{"date": "20211010", "key": "nymex/ng_mbo_5y_v0/native/20211001_20211101/glbx-mdp3-20211010.mbo.dbn.zst", "bytes": 1, "sha256": "abc", "native_segment_job_id": "job"}]
            write_rows(input_path, [
                {"epoch_second": 9, "source_dbn_object": str(source), "source_dbn_key": objects[0]["key"], "source_dbn_sha256": "abc"},
                {"epoch_second": 10, "source_dbn_object": str(source), "source_dbn_key": objects[0]["key"], "source_dbn_sha256": "abc"},
                {"epoch_second": 11, "source_dbn_object": str(source), "source_dbn_key": objects[0]["key"], "source_dbn_sha256": "abc"},
                {"epoch_second": 12, "source_dbn_object": str(source), "source_dbn_key": objects[0]["key"], "source_dbn_sha256": "abc"},
            ])
            receipt = trim_seconds(input_path, output_path, 10, 12, objects, "bucket")
            self.assertEqual(receipt["rows"], 2)
            rows = [row for _, row in _read_rows(output_path)]
            self.assertEqual([row["epoch_second"] for row in rows], [10, 11])
            self.assertEqual(rows[0]["source_dbn_object"], "s3://bucket/nymex/ng_mbo_5y_v0/native/20211001_20211101/glbx-mdp3-20211010.mbo.dbn.zst")

    def test_merge_rejects_swapped_output(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plan = {"plan_sha256": "p", "shards": []}
            bundles = []
            for i in range(4):
                sid = f"october-cpu-{i + 1}"
                source_objects = [{"date": f"202110{i + 1:02d}", "key": f"k{i}", "bytes": 1, "sha256": "s", "native_segment_job_id": "job"}]
                path = root / f"{sid}.gz"
                write_rows(path, [{"epoch_second": i, "source_dbn_object": "s3://b/k", "source_dbn_key": "k", "source_dbn_sha256": "s"}])
                output = {"path": str(path), "rows": 1, "gzip_sha256": _sha(path), "uncompressed_jsonl_sha256": _raw_sha(path)}
                child_sources = [{k: x[k] for k in ("key", "bytes", "sha256", "native_segment_job_id")} for x in source_objects]
                child = {"schema": "NG_EXHAUSTION_MBO_5Y_STEP1_SEGMENT_RECEIPT_V1", "status": "SEGMENT_COMPLETE", "source_objects": child_sources, "source_object_count": 1, "engine_hashes": {"engine": "hash"}, "ruleset_sha256": "rules"}
                child["receipt_sha256"] = _json_sha(child)
                wrapper = {"schema": "NG_EXHAUSTION_STEP1_OCTOBER_SHARD_RECEIPT_V2_20260824", "status": "SHARD_COMPLETE_UNACCEPTED_PENDING_MONOLITHIC_EQUIVALENCE", "shard_id": sid, "plan_sha256": "p", "boundary_gate_receipt_sha256": "gate", "source_objects": source_objects, "target_start_epoch_second": i, "target_end_epoch_second": i + 1, "child_receipt_sha256": child["receipt_sha256"], "child_engine_hashes": child["engine_hashes"], "child_ruleset_sha256": child["ruleset_sha256"], "trimmed_seconds_output": output}
                wrapper["receipt_sha256"] = _json_sha(wrapper)
                plan["shards"].append({"shard_id": sid, "source_objects": source_objects})
                bundles.append((wrapper, path, child))
            bundles[1] = (bundles[1][0], bundles[2][1], bundles[1][2])
            with self.assertRaises(OctoberShardError):
                merge_shard_bundles(plan, bundles, root / "merged.gz")


class EquivalenceTests(unittest.TestCase):
    def test_only_validated_local_source_path_is_ignored(self) -> None:
        objects = [{"date": "20211010", "key": "nymex/ng_mbo_5y_v0/native/20211001_20211101/glbx-mdp3-20211010.mbo.dbn.zst", "bytes": 1, "sha256": "abc", "native_segment_job_id": "job"}]
        row = {"source_dbn_object": "/tmp/stage/native/20211001_20211101/glbx-mdp3-20211010.mbo.dbn.zst", "source_dbn_key": objects[0]["key"], "source_dbn_sha256": "abc", "x": 1}
        self.assertEqual(canonical_science_row(row, objects, "bucket")["source_dbn_object"], "s3://bucket/nymex/ng_mbo_5y_v0/native/20211001_20211101/glbx-mdp3-20211010.mbo.dbn.zst")
        row["source_dbn_object"] = "/tmp/stage/wrong.dbn.zst"
        with self.assertRaises(OctoberShardError):
            canonical_science_row(row, objects, "bucket")

    def test_monolithic_equivalence_is_exact_after_path_canonicalization(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            objects = [{"date": "20211010", "key": "nymex/ng_mbo_5y_v0/native/20211001_20211101/glbx-mdp3-20211010.mbo.dbn.zst", "bytes": 1, "sha256": "abc", "native_segment_job_id": "job"}]
            left, right = root / "left.gz", root / "right.gz"
            base = {"epoch_second": 1, "source_dbn_key": objects[0]["key"], "source_dbn_sha256": "abc", "x": 4}
            write_rows(left, [{**base, "source_dbn_object": "/tmp/a/native/20211001_20211101/glbx-mdp3-20211010.mbo.dbn.zst"}])
            write_rows(right, [{**base, "source_dbn_object": "s3://bucket/nymex/ng_mbo_5y_v0/native/20211001_20211101/glbx-mdp3-20211010.mbo.dbn.zst"}])
            self.assertEqual(verify_monolithic_equivalence(left, right, objects, "bucket")["status"], "PASS")
            write_rows(right, [{**base, "x": 5, "source_dbn_object": "s3://bucket/nymex/ng_mbo_5y_v0/native/20211001_20211101/glbx-mdp3-20211010.mbo.dbn.zst"}])
            with self.assertRaises(OctoberShardError):
                verify_monolithic_equivalence(left, right, objects, "bucket")


def _read_rows(path: Path):
    with gzip.open(path, "rb") as handle:
        for raw in handle:
            yield raw, json.loads(raw)


def _sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _raw_sha(path: Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    with gzip.open(path, "rb") as handle:
        for raw in handle:
            digest.update(raw)
    return digest.hexdigest()


def _json_sha(value: dict[str, object]) -> str:
    import hashlib
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


if __name__ == "__main__":
    unittest.main()
