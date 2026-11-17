"""Independent offline-view checks; all synthetic, never a scientific receipt."""
import copy
import tempfile
import unittest
from pathlib import Path

from adaptive_locality.core import Observation, MetricContract, LocalityConfig, LocalityEngine, LocalityError
from adaptive_locality.adapters import EvidenceManifest, shadow_batch, buildmap_evidence
from adaptive_locality.ledger import DecisionLedger
from adaptive_locality.visualization import scientific_frame, render_html, verify_frame, replay_probes, write_html
from adaptive_locality.review_cli import build_review


class OfflineVisualizationTests(unittest.TestCase):
    def setUp(self):
        self.metric = MetricContract(("spread", "pressure"), (1, 1), (1, 1), "v1")
        self.events = [
            Observation("p1", "P", {"spread": 0, "pressure": 0}, 1, "test"),
            Observation("p2", "P", {"spread": 0.1, "pressure": 0.2}, 2, "test"),
            Observation("p3", "P", {"spread": 0.2, "pressure": 0.3}, 3, "test"),
            Observation("x1", "X", {"spread": 5, "pressure": 5}, 4, "test"),
            Observation("x2", "X", {"spread": 5.1, "pressure": 5.1}, 5, "test"),
        ]
        manifest = EvidenceManifest("demo", "20231018", "fake-test-hash", ("test-plane",))
        engine = LocalityEngine(self.metric, LocalityConfig(1, 0.5))
        self.shadow = buildmap_evidence(shadow_batch(self.events, engine, DecisionLedger(), manifest))

    def frame(self, events=None, **kw):
        return scientific_frame(events if events is not None else self.events,
                                self.shadow, self.metric, "spread", "pressure", **kw)

    def test_frame_is_order_independent_with_same_verified_decisions(self):
        a = self.frame()
        b = self.frame(list(reversed(self.events)))
        self.assertEqual(a, b)
        self.assertEqual(a["scientific_jobs_eliminated"], 0)
        self.assertEqual(a["all_center_count"], 2)
        self.assertEqual(a["source_count"], 5)
        self.assertEqual(a["shown_count"], 5)
        self.assertEqual(a["trust"], "UNSIGNED_SHADOW_NOT_PRODUCTION_EVIDENCE")
        self.assertEqual(len(a["finite_convergence"]), 2)
        verify_frame(a)

    def test_visible_subset_never_drops_source(self):
        a = self.frame(limit=2)
        self.assertEqual(a["shown_count"], 2)
        self.assertTrue(a["sampled_for_display_only"])
        self.assertEqual(a["source_count"], 5)
        self.assertEqual(a["all_center_count"], 2)
        self.assertEqual(set(p["status"] for p in a["points"]), {"NEW_CENTER"})

    def test_replay_probes_stable(self):
        a = self.frame()
        self.assertEqual(replay_probes(a), replay_probes(self.frame()))
        self.assertEqual(len(replay_probes(a, 2)), 2)
        with self.assertRaises(LocalityError):
            replay_probes(a, 0)

    def test_modified_evidence_rejected(self):
        fake = copy.deepcopy(self.shadow)
        fake["decisions"][0]["event_identity"] = "wrong"
        with self.assertRaises(LocalityError):
            scientific_frame(self.events, fake, self.metric, "spread", "pressure")
        original = self.frame()
        original["points"][0]["x"] = 100
        with self.assertRaises(LocalityError):
            verify_frame(original)

    def test_unsafe_markup_is_escaped(self):
        malicious = '</script><script>window.bad=1</script>'
        injected = [Observation(malicious, "P", {"spread": 0, "pressure": 0}, 1, "test")]
        engine = LocalityEngine(self.metric, LocalityConfig(1, 0.5))
        shadow = buildmap_evidence(shadow_batch(
            injected, engine, DecisionLedger(),
            EvidenceManifest("demo", "day", "test", ("plane",))
        ))
        frame = scientific_frame(injected, shadow, self.metric, "spread", "pressure")
        html = render_html(frame)
        self.assertNotIn(malicious, html)
        self.assertIn("\\u003c/script>", html)
        self.assertNotIn('src="http', html)

    def test_output_is_offline_and_no_clobber(self):
        frame = self.frame()
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "report.html"
            write_html(frame, target)
            html = target.read_text(encoding="utf-8")
            self.assertIn("Locality Lab", html)
            self.assertIn(frame["frame_sha256"], html)
            self.assertIn("default-src 'none'", html)
            with self.assertRaises(FileExistsError):
                write_html(frame, target)

    def test_cli_build_uses_same_contract(self):
        payload = {
            "manifest": {"run_id": "demo", "day": "20231018",
                         "source_identity": "fake-test-hash", "planes": ["test-plane"]},
            "metric": {"features": ["spread", "pressure"], "scales": [1, 1],
                       "weights": [1, 1], "version": "v1"},
            "config": {"radius": 1, "bandwidth": 0.5},
            "events": [dict(event.__dict__, features=dict(event.features)) for event in self.events],
        }
        result = build_review(payload, "spread", "pressure", limit=2, window=2, tolerance=0.2)
        self.assertEqual(result["source_count"], 5)
        self.assertEqual(result["shown_count"], 2)
        self.assertEqual(result["scientific_jobs_eliminated"], 0)
        verify_frame(result)


if __name__ == "__main__":
    unittest.main()
