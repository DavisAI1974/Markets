from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import frankie_bounded_3mo_parallel as bounded  # noqa: E402


class FrankieBoundedThreeMonthParallelTests(unittest.TestCase):
    def test_contract_is_exact_three_month_four_worker_run(self):
        self.assertEqual(bounded.SOURCE_WINDOW_START, "2021-09-01")
        self.assertEqual(bounded.SOURCE_WINDOW_END_EXCLUSIVE, "2021-12-01")
        self.assertEqual(bounded.DEFAULT_WORKERS, 4)

    def test_cpu_list_parser(self):
        self.assertEqual(bounded.parse_cpu_list("0-3"), {0, 1, 2, 3})
        self.assertEqual(bounded.parse_cpu_list("0,2-3,7"), {0, 2, 3, 7})

    def test_effective_capacity_honors_systemd_cgroup_quota(self):
        self.assertEqual(
            bounded.effective_cpu_capacity(
                nproc=4,
                affinity_count=4,
                cgroup={"quota_cores": 4.0, "cpuset_count": 4},
            ),
            4.0,
        )
        self.assertEqual(
            bounded.effective_cpu_capacity(
                nproc=4,
                affinity_count=4,
                cgroup={"quota_cores": 1.5, "cpuset_count": 4},
            ),
            1.5,
        )

    def test_environment_rejects_serial_or_reduced_mode(self):
        good = {
            "FRANKIE_QUEUE_URL": "https://example.invalid/frankie-bounded",
            "FRANKIE_DETERMINISTIC_ONLY": "0",
            "FRANKIE_BOUNDED_QUEUE_EXCLUSIVE": "1",
        }
        self.assertEqual(bounded.environment_checks(good, workers=4)["errors"], [])
        deterministic = dict(good)
        deterministic["FRANKIE_DETERMINISTIC_ONLY"] = "1"
        self.assertTrue(bounded.environment_checks(deterministic, workers=4)["errors"])
        self.assertTrue(bounded.environment_checks(good, workers=1)["errors"])

    def test_canonical_delivery_recomputes_envelope_and_event_hashes(self):
        event = {
            "event_id": "event-a",
            "candidate_id": "candidate",
            "knowable_at": "2021-09-01T00:00:00Z",
            "observed_at": "2021-09-01T00:00:01Z",
        }
        event_hash = bounded.sha256_json(event)
        decision = {
            "event_id": "event-a",
            "candidate_id": "candidate",
            "decision_hash": "decision-a",
            "qualification": {"event_hash": event_hash},
        }
        envelope = {"decision": decision, "event": event}
        envelope["envelope_hash"] = bounded.sha256_json(envelope)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evidence.json"
            path.write_text(json.dumps(envelope), encoding="utf-8")
            result = {
                "received": True,
                "processed": True,
                "decision": decision,
                "evidence": {
                    "local_path": str(path),
                    "envelope_hash": envelope["envelope_hash"],
                    "deduplicated": False,
                },
            }
            canonical = bounded.canonical_delivery(result)
            self.assertEqual(canonical["event_hash"], event_hash)

            tampered = dict(envelope)
            tampered["event"] = {**event, "observed_at": "2021-09-01T00:00:02Z"}
            path.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaises(bounded.BoundedParallelError):
                bounded.canonical_delivery(result)

    def test_canonical_reassembly_is_completion_order_independent(self):
        a = {
            "event_hash": "aaa",
            "event_id": "event-a",
            "candidate_id": "candidate",
            "knowable_at": "2021-09-01T00:00:00Z",
            "observed_at": "2021-09-01T00:00:01Z",
            "decision_hash": "decision-a",
            "local_path": "/tmp/a",
            "envelope_hash": "envelope-a",
            "s3_uri": None,
            "deduplicated": False,
            "receive_count": "1",
        }
        b = {
            "event_hash": "bbb",
            "event_id": "event-b",
            "candidate_id": "candidate",
            "knowable_at": "2021-09-02T00:00:00Z",
            "observed_at": "2021-09-02T00:00:01Z",
            "decision_hash": "decision-b",
            "local_path": "/tmp/b",
            "envelope_hash": "envelope-b",
            "s3_uri": None,
            "deduplicated": False,
            "receive_count": "1",
        }
        first = bounded.canonical_unique_events([b, a])
        second = bounded.canonical_unique_events([a, b])
        self.assertEqual(first, second)
        self.assertEqual([item["event_hash"] for item in first], ["aaa", "bbb"])

    def test_transport_redelivery_does_not_duplicate_scientific_event(self):
        event = {
            "event_hash": "aaa",
            "event_id": "event-a",
            "candidate_id": "candidate",
            "knowable_at": "2021-09-01T00:00:00Z",
            "observed_at": "2021-09-01T00:00:01Z",
            "decision_hash": "decision-a",
            "local_path": "/tmp/a",
            "envelope_hash": "envelope-a",
            "s3_uri": None,
            "deduplicated": False,
            "receive_count": "1",
        }
        out = bounded.canonical_unique_events([event, {**event, "deduplicated": True}])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["transport_delivery_count"], 2)

    def test_first_lock_drift_fails_closed(self):
        event = {
            "event_hash": "aaa",
            "event_id": "event-a",
            "candidate_id": "candidate",
            "knowable_at": "2021-09-01T00:00:00Z",
            "observed_at": "2021-09-01T00:00:01Z",
            "decision_hash": "decision-a",
            "local_path": "/tmp/a",
            "envelope_hash": "envelope-a",
            "s3_uri": None,
            "deduplicated": False,
            "receive_count": "1",
        }
        with self.assertRaises(bounded.BoundedParallelError):
            bounded.canonical_unique_events([event, {**event, "decision_hash": "different"}])


if __name__ == "__main__":
    unittest.main()
