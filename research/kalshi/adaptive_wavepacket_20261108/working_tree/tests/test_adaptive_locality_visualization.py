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


class ReviewFixVisualizationTests(unittest.TestCase):
    """Findings E-3, E-7, E-14."""

    def setUp(self):
        self.metric = MetricContract(("spread", "pressure"), (1, 1), (1, 1), "v1")
        self.events = [
            Observation("p1", "P", {"spread": 0, "pressure": 0}, 1, "test"),
            Observation("p2", "P", {"spread": 0.1, "pressure": 0.2}, 2, "test"),
            Observation("p3", "P", {"spread": 0.2, "pressure": 0.3}, 3, "test"),
            Observation("x1", "X", {"spread": 5, "pressure": 5}, 4, "test"),
            Observation("x2", "X", {"spread": 5.1, "pressure": 5.1}, 5, "test"),
        ]
        self.manifest = EvidenceManifest("demo", "20231018", "fake-test-hash", ("test-plane",))

    def test_e7_abstain_reason_survives_export_and_frame(self):
        # bandwidth tiny relative to distance -> gaussian kernel underflows to 0 -> ABSTAIN
        engine = LocalityEngine(self.metric, LocalityConfig(1000.0, 1e-3))
        far = [Observation("a", "P", {"spread": 0, "pressure": 0}, 1, "test"),
               Observation("b", "P", {"spread": 500, "pressure": 0}, 2, "test")]
        raw = shadow_batch(far, engine, DecisionLedger(), self.manifest)
        statuses = {d["event_id"]: d for d in raw["decisions"]}
        self.assertEqual(statuses["b"]["status"], "ABSTAIN")
        self.assertEqual(statuses["b"]["reason"], "kernel underflow")
        self.assertEqual(statuses["a"]["reason"], "no eligible center")
        exported = buildmap_evidence(raw)
        self.assertEqual({d["event_id"]: d["reason"] for d in exported["decisions"]},
                         {"a": "no eligible center", "b": "kernel underflow"})
        frame = scientific_frame(far, exported, self.metric, "spread", "pressure")
        reasons = {p["id"]: p["reason"] for p in frame["points"]}
        self.assertEqual(reasons, {"a": "no eligible center", "b": "kernel underflow"})
        self.assertIn("kernel underflow", render_html(frame))

    def test_e7_cli_export_carries_decision_reason(self):
        import json
        from unittest import mock
        from adaptive_locality import cli
        payload = {
            "manifest": {"run_id": "demo", "day": "20231018",
                         "source_identity": "fake-test-hash", "planes": ["test-plane"]},
            "metric": {"features": ["spread", "pressure"], "scales": [1, 1],
                       "weights": [1, 1], "version": "v1"},
            "config": {"radius": 1000, "bandwidth": 0.001},
            "events": [dict(e.__dict__, features=dict(e.features)) for e in (
                Observation("a", "P", {"spread": 0, "pressure": 0}, 1, "test"),
                Observation("b", "P", {"spread": 500, "pressure": 0}, 2, "test"))],
        }
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "in.json"
            source.write_text(json.dumps(payload), encoding="utf-8")
            out = Path(temporary) / "out.json"
            with mock.patch("sys.argv", ["cli", str(source), "--output", str(out)]):
                cli.main()
            exported = json.loads(out.read_text(encoding="utf-8"))
            reasons = {d["event_id"]: (d["status"], d["reason"]) for d in exported["decisions"]}
            self.assertEqual(reasons["b"], ("ABSTAIN", "kernel underflow"))
            self.assertEqual(reasons["a"], ("NEW_CENTER", "no eligible center"))

    def test_e14_omitted_event_ids_listed_when_display_sampled(self):
        engine = LocalityEngine(self.metric, LocalityConfig(1, 0.5))
        shadow = buildmap_evidence(shadow_batch(self.events, engine, DecisionLedger(), self.manifest))
        frame = scientific_frame(self.events, shadow, self.metric, "spread", "pressure", limit=2)
        shown = {p["id"] for p in frame["points"]}
        self.assertEqual(sorted(shown | set(frame["omitted_event_ids"])), sorted(e.event_id for e in self.events))
        self.assertEqual(len(frame["omitted_event_ids"]), 3)
        self.assertEqual(frame["omitted_event_ids"], sorted(frame["omitted_event_ids"]))
        full = scientific_frame(self.events, shadow, self.metric, "spread", "pressure")
        self.assertEqual(full["omitted_event_ids"], [])
        self.assertEqual(full["source_event_set_sha256"], frame["source_event_set_sha256"])
        verify_frame(frame)

    def test_e3_probe_collision_leaves_no_html_behind(self):
        import json
        from unittest import mock
        from adaptive_locality import review_cli
        payload = {
            "manifest": {"run_id": "demo", "day": "20231018",
                         "source_identity": "fake-test-hash", "planes": ["test-plane"]},
            "metric": {"features": ["spread", "pressure"], "scales": [1, 1],
                       "weights": [1, 1], "version": "v1"},
            "config": {"radius": 1, "bandwidth": 0.5},
            "events": [dict(event.__dict__, features=dict(event.features)) for event in self.events],
        }
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = folder / "input.json"
            source.write_text(json.dumps(payload), encoding="utf-8")
            html = folder / "out.html"
            probes = folder / "probes.json"
            probes.write_text("{}", encoding="utf-8")
            argv = ["review", str(source), "--output", str(html), "--x", "spread", "--y", "pressure",
                    "--probes", str(probes)]
            with mock.patch("sys.argv", argv):
                with self.assertRaises((LocalityError, FileExistsError)):
                    review_cli.main()
            self.assertFalse(html.exists())
            self.assertEqual(probes.read_text(encoding="utf-8"), "{}")
            # and the mirrored case: HTML present, probes absent -> probes must not be created
            html.write_text("existing", encoding="utf-8")
            probes.unlink()
            with mock.patch("sys.argv", argv):
                with self.assertRaises((LocalityError, FileExistsError)):
                    review_cli.main()
            self.assertFalse(probes.exists())
            self.assertEqual(html.read_text(encoding="utf-8"), "existing")
            # happy path still writes both
            html.unlink()
            with mock.patch("sys.argv", argv):
                review_cli.main()
            self.assertIn("Locality Lab", html.read_text(encoding="utf-8"))
            self.assertIn("probes", json.loads(probes.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
