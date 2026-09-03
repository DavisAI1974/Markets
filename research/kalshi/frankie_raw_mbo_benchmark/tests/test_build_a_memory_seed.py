"""The A-memory seed: every committed output of the past runs, hashed, provenance-labelled, UNVERIFIED.

Greg's rulings (D86, D88): one arm, A_MEMORY; day one is SEEDED with every committed output of
the past runs; the wrong-data run 32851909748-1 is in the seed AS the wrong-data run, never
filtered (D76); *"if you can't find the canary just use something from the last run"* - no
canary output is committed, so the last run seeds it. No number here is a spec: the entry set
is DERIVED from the committed tree at test time and compared against the seed file.
"""
from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark.build_a_memory_seed import (
    CORRECTIONS,
    SEED_PATH,
    SEED_SCHEMA,
    SeedBuildError,
    build_seed,
    main as seed_main,
    mission_seed_sha256,
    pin_mission,
    render_seed,
    seed_entry_paths,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_frankie_knowledge_registry import (
    load_and_validate_manifest,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import load_registry
from research.kalshi.frankie_raw_mbo_benchmark.native_knowledge_delivery import (
    A_MEMORY_SEED_LAYER_SOURCES,
    KNOWLEDGE_INPUT_POLICIES,
    REPO_ROOT,
)
from research.kalshi.frankie_raw_mbo_benchmark.register_a_memory_knowledge import (
    SEED_ARTIFACT_ID,
    SPEC_PATH,
)

PKG = "research/kalshi/frankie_raw_mbo_benchmark/"
MISSION_PATH = "research/kalshi/agents/frankie_native_raw_mbo_oct45_realtime_mission_20260828.md"
MANIFEST_PATH = "research/kalshi/agents/frankie_native_raw_mbo_knowledge/KNOWLEDGE_MANIFEST_20260828.json"
KNOWLEDGE_DIR = "research/kalshi/agents/frankie_native_raw_mbo_knowledge/"
WRONG_DATA_DIR = PKG + "prior_memory/workmode-32851909748-1/"
LAST_RUN_DIR = PKG + "principal_runs/33605852433/"
WRONG_DATA_HASHES = (
    "b487acfbbea8ac8a82f42ceb555e8334057e4004740af91b9127cd2ba71e1cf8",
    "d54c61915c0d85c8b2630eb79d5e1b8911481c80883c56d75ba815fcfab20c05",
)
OVERLAY_LAYERS = ("a_memory_prior_lessons_package", "a_memory_prior_package_proof")


def committed_seed() -> dict:
    return json.loads((REPO_ROOT / SEED_PATH).read_text(encoding="utf-8"))


def files_under(relative_dir: str) -> set[str]:
    root = REPO_ROOT / relative_dir
    return {path.relative_to(REPO_ROOT).as_posix() for path in root.rglob("*") if path.is_file()}


def sha256_of(relative: str) -> str:
    return hashlib.sha256((REPO_ROOT / relative).read_bytes()).hexdigest()


class SeedContentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.seed = build_seed(REPO_ROOT)
        cls.by_path = {entry["path"]: entry for entry in cls.seed["entries"]}

    def test_the_seed_is_reproducible_byte_for_byte_and_the_committed_file_is_it(self) -> None:
        first = render_seed(build_seed(REPO_ROOT))
        second = render_seed(build_seed(REPO_ROOT))
        self.assertEqual(first, second)
        self.assertEqual(first, (REPO_ROOT / SEED_PATH).read_text(encoding="utf-8"))
        self.assertEqual(self.seed["schema"], SEED_SCHEMA)

    def test_every_entry_path_exists_and_hashes_as_listed(self) -> None:
        self.assertTrue(self.seed["entries"])
        for entry in self.seed["entries"]:
            with self.subTest(path=entry["path"]):
                target = REPO_ROOT / entry["path"]
                self.assertTrue(target.is_file(), entry["path"])
                self.assertEqual(entry["sha256"], sha256_of(entry["path"]))
                self.assertEqual(entry["bytes"], target.stat().st_size)

    def test_entry_paths_are_unique_repo_relative_and_never_local(self) -> None:
        paths = [entry["path"] for entry in self.seed["entries"]]
        self.assertEqual(len(paths), len(set(paths)))
        blob = render_seed(self.seed)
        self.assertNotIn("/tmp/", blob)
        self.assertNotIn("scratchpad", blob)
        self.assertNotRegex(blob, r"[A-Za-z]:[\\/]")
        for path in paths:
            self.assertFalse(path.startswith("/"), path)

    def test_the_last_runs_committed_outputs_are_the_seed_because_no_canary_is_committed(self) -> None:
        """D88: 'if you can't find the canary just use something from the last run'."""
        expected = files_under(LAST_RUN_DIR)
        self.assertTrue(expected, "the last run's outputs must be committed for the seed to exist")
        self.assertTrue(expected <= set(self.by_path), sorted(expected - set(self.by_path)))
        header = self.seed["header"].lower()
        self.assertIn("no canary output is committed", header)
        self.assertIn("last run", header)
        self.assertIn("D88", self.seed["header"])
        for path in expected:
            with self.subTest(path=path):
                self.assertEqual(self.by_path[path]["provenance"]["run_id"], "frankie-a-clean-rt-33605852433-1")

    def test_the_wrong_data_run_is_present_whole_and_labelled_as_the_wrong_data_run(self) -> None:
        """D86 / D76: included AS the wrong-data run, labelled, never filtered."""
        expected = files_under(WRONG_DATA_DIR)
        self.assertTrue(expected)
        self.assertTrue(expected <= set(self.by_path), sorted(expected - set(self.by_path)))
        for path in expected:
            with self.subTest(path=path):
                provenance = self.by_path[path]["provenance"]
                self.assertEqual(provenance["included_as"], "THE_WRONG_DATA_RUN")
                self.assertEqual(provenance["run_id"], "32851909748-1")
                self.assertIn("wrong-data", provenance["label"].lower())
                self.assertEqual(provenance["correction"], "PRE_CORRECTION")

    def test_the_capsules_and_their_source_reports_are_present(self) -> None:
        package = REPO_ROOT / PKG
        sources = {
            path.relative_to(REPO_ROOT).as_posix()
            for prefix in ("ACLEAN_", "AMEMORY_")
            for path in package.glob(prefix + "*")
            if path.is_file() and path.suffix in {".md", ".json"}
        }
        capsules = {
            KNOWLEDGE_DIR + "A_CLEAN_POSITIVE_KNOWLEDGE_20260828.md",
            KNOWLEDGE_DIR + "A_MEMORY_POSITIVE_KNOWLEDGE_20260828.md",
        }
        self.assertTrue(sources)
        self.assertIn(PKG + "ACLEAN_S119_MEASURED_KNOWLEDGE_SOURCE_20260902.md", sources)
        for path in sorted(sources | capsules):
            with self.subTest(path=path):
                self.assertIn(path, self.by_path)

    def test_the_entry_set_is_exactly_the_derived_set(self) -> None:
        self.assertEqual(set(self.by_path), set(seed_entry_paths(REPO_ROOT)))

    def test_every_entry_is_unverified_and_carries_a_full_provenance_label(self) -> None:
        for entry in self.seed["entries"]:
            with self.subTest(path=entry["path"]):
                self.assertEqual(entry["status"], "UNVERIFIED")
                provenance = entry["provenance"]
                for key in ("run_id", "data_surface", "correction", "label", "included_as", "group_id"):
                    self.assertIn(key, provenance)
                    self.assertTrue(str(provenance[key]).strip(), key)
                self.assertIn(provenance["correction"], CORRECTIONS)

    def test_the_seed_never_lists_the_mission_the_manifest_the_spec_or_itself(self) -> None:
        """No circularity: the mission pins the seed's hash and the manifest pins both."""
        for forbidden in (
            MISSION_PATH, MANIFEST_PATH, SPEC_PATH, SEED_PATH,
            "research/kalshi/agents/frankie_native_raw_mbo_ingestion_layer_registry_20260828.json",
        ):
            with self.subTest(path=forbidden):
                self.assertNotIn(forbidden, self.by_path)

    def test_totals_are_derived_from_the_entries(self) -> None:
        totals = self.seed["totals"]
        self.assertEqual(totals["entries"], len(self.seed["entries"]))
        self.assertEqual(totals["bytes"], sum(entry["bytes"] for entry in self.seed["entries"]))
        by_group = {}
        for entry in self.seed["entries"]:
            by_group[entry["provenance"]["group_id"]] = by_group.get(entry["provenance"]["group_id"], 0) + 1
        self.assertEqual(totals["by_group"], by_group)
        self.assertEqual({group["group_id"] for group in self.seed["groups"]}, set(by_group))

    def test_a_file_no_provenance_rule_covers_is_refused_not_labelled_by_default(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for relative in seed_entry_paths(REPO_ROOT):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((REPO_ROOT / relative).read_bytes())
        stray = root / PKG / "ACLEAN_SOMETHING_NEW_20261231.md"
        stray.write_text("# a new report nobody labelled\n", encoding="utf-8")
        with self.assertRaisesRegex(SeedBuildError, "no provenance rule"):
            build_seed(root)


class MissionPinTest(unittest.TestCase):
    def test_the_mission_names_the_seed_and_its_current_sha256_as_memory(self) -> None:
        text = (REPO_ROOT / MISSION_PATH).read_text(encoding="utf-8")
        self.assertIn(SEED_PATH, text)
        self.assertEqual(mission_seed_sha256(text), sha256_of(SEED_PATH))
        lowered = " ".join(text.lower().split())  # the mission wraps at 80 columns
        self.assertIn("32851909748-1", text)
        self.assertIn("unverified", lowered)
        self.assertIn("day two", lowered)
        self.assertIn("a-clean", lowered)

    def test_the_mission_no_longer_pins_the_wrong_data_hashes_as_memory(self) -> None:
        text = (REPO_ROOT / MISSION_PATH).read_text(encoding="utf-8")
        for digest in WRONG_DATA_HASHES:
            self.assertNotIn(digest, text)
        self.assertNotIn("receives only the verified prior lessons", text)

    def test_pin_mission_replaces_exactly_the_seed_hash_and_refuses_a_mission_without_the_slot(self) -> None:
        text = (REPO_ROOT / MISSION_PATH).read_text(encoding="utf-8")
        pinned = pin_mission(text, "f" * 64)
        self.assertEqual(mission_seed_sha256(pinned), "f" * 64)
        self.assertEqual(pin_mission(pinned, mission_seed_sha256(text)), text)
        with self.assertRaisesRegex(SeedBuildError, "seed"):
            pin_mission("# a mission with no seed paragraph\n", "f" * 64)

    def test_the_mission_is_pinned_in_the_manifest_at_its_current_bytes(self) -> None:
        manifest = load_and_validate_manifest(REPO_ROOT / MANIFEST_PATH, REPO_ROOT)
        by_path = {row["path"]: row for row in manifest["artifacts"]}
        self.assertEqual(by_path[MISSION_PATH]["sha256"], sha256_of(MISSION_PATH))


class OverlayRebindTest(unittest.TestCase):
    """The a_memory_overlay layers bind to the seed FILE through the existing rebind."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry()
        cls.entries = {
            entry["layer_id"]: (group, entry)
            for group in cls.registry["groups"]
            for entry in group["entries"]
        }

    def test_the_two_overlay_layers_bind_to_the_seed_file(self) -> None:
        for layer_id in OVERLAY_LAYERS:
            with self.subTest(layer=layer_id):
                group, entry = self.entries[layer_id]
                self.assertEqual(group["group_id"], "a_memory_overlay")
                self.assertEqual(entry["source_paths"], [SEED_PATH])
                # "UNVERIFIED" is the point; a bare "verified" of a wrong-data package is the defect.
                self.assertIsNone(re.search(r"(?<!un)verified", entry["description"], re.IGNORECASE))

    def test_the_seed_bindings_are_declared_beside_the_keep_bindings_with_reasons(self) -> None:
        self.assertEqual({b.layer_id for b in A_MEMORY_SEED_LAYER_SOURCES}, set(OVERLAY_LAYERS))
        seed_text = (REPO_ROOT / SEED_PATH).read_text(encoding="utf-8")
        for binding in A_MEMORY_SEED_LAYER_SOURCES:
            with self.subTest(layer=binding.layer_id):
                self.assertEqual(binding.paths, (SEED_PATH,))
                self.assertTrue(binding.why.strip())
                self.assertIsNotNone(re.compile(binding.content_terms, re.IGNORECASE).search(seed_text))
                self.assertTrue(binding.description)

    def test_no_pre_call_input_layer_binds_an_external_path_any_more(self) -> None:
        """Reported to the coordinator: native_a_arm_launch.EXTERNAL_SOURCE_IDENTITIES is retired
        by them once nothing binds to it. This is the measurement."""
        external = [
            (entry["layer_id"], path)
            for group in self.registry["groups"]
            if group["policy"] in KNOWLEDGE_INPUT_POLICIES
            for entry in group["entries"]
            for path in entry["source_paths"]
            if path.startswith("external:")
        ]
        self.assertEqual(external, [])
        for group in self.registry["groups"]:
            for entry in group["entries"]:
                for path in entry["source_paths"]:
                    with self.subTest(layer=entry["layer_id"], path=path):
                        self.assertFalse(path.startswith("external:"))
                        self.assertTrue((REPO_ROOT / path).is_file(), path)


class ManifestRoutingTest(unittest.TestCase):
    def test_the_seed_is_a_json_artifact_always_loaded_by_both_memory_profiles_and_no_clean_one(self) -> None:
        manifest = load_and_validate_manifest(REPO_ROOT / MANIFEST_PATH, REPO_ROOT)
        by_id = {row["id"]: row for row in manifest["artifacts"]}
        self.assertIn(SEED_ARTIFACT_ID, by_id)
        row = by_id[SEED_ARTIFACT_ID]
        self.assertEqual(row["path"], SEED_PATH)
        self.assertEqual(row["kind"], "JSON")
        self.assertEqual(row["load_mode"], "ALWAYS_LOAD")
        self.assertEqual(row["arms"], ["A_MEMORY"])
        self.assertEqual(row["sha256"], sha256_of(SEED_PATH))
        memory = [p for p in manifest["profiles"].values() if p["arm"] == "A_MEMORY"]
        clean = [p for p in manifest["profiles"].values() if p["arm"] == "A_CLEAN"]
        self.assertEqual(len(memory), 2)
        for profile in memory:
            self.assertIn(SEED_ARTIFACT_ID, profile["always_load"])
        for profile in clean:
            self.assertNotIn(SEED_ARTIFACT_ID, profile["always_load"] + profile["retrieval_catalog"])

    def test_the_seed_artifacts_authority_is_the_binding_registry_groups(self) -> None:
        manifest = load_and_validate_manifest(REPO_ROOT / MANIFEST_PATH, REPO_ROOT)
        row = next(r for r in manifest["artifacts"] if r["id"] == SEED_ARTIFACT_ID)
        overlay = next(g for g in load_registry()["groups"] if g["group_id"] == "a_memory_overlay")
        self.assertEqual(row["authority"], overlay["authority"])


class CommandLineTest(unittest.TestCase):
    def test_check_passes_on_the_committed_tree(self) -> None:
        self.assertEqual(seed_main(["--check", "--repo-root", str(REPO_ROOT)]), 0)

    def test_check_fails_on_a_stale_copy_and_write_repairs_seed_and_mission_pin(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        stale_seed = root / "seed.json"
        stale_seed.write_text("{}\n", encoding="utf-8")
        stale_mission = root / "mission.md"
        stale_mission.write_text(
            pin_mission((REPO_ROOT / MISSION_PATH).read_text(encoding="utf-8"), "0" * 64), encoding="utf-8"
        )
        args = ["--repo-root", str(REPO_ROOT), "--seed", str(stale_seed), "--mission", str(stale_mission)]
        self.assertEqual(seed_main(["--check", *args]), 1)
        self.assertEqual(seed_main(["--write", *args]), 0)
        self.assertEqual(seed_main(["--check", *args]), 0)
        self.assertEqual(stale_seed.read_text(encoding="utf-8"), (REPO_ROOT / SEED_PATH).read_text(encoding="utf-8"))
        self.assertEqual(mission_seed_sha256(stale_mission.read_text(encoding="utf-8")), sha256_of(SEED_PATH))

    def test_a_stale_mission_pin_alone_fails_check(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        seed = root / "seed.json"
        seed.write_text((REPO_ROOT / SEED_PATH).read_text(encoding="utf-8"), encoding="utf-8")
        mission = root / "mission.md"
        mission.write_text(
            pin_mission((REPO_ROOT / MISSION_PATH).read_text(encoding="utf-8"), "0" * 64), encoding="utf-8"
        )
        self.assertEqual(
            seed_main(["--check", "--repo-root", str(REPO_ROOT), "--seed", str(seed), "--mission", str(mission)]), 1
        )


if __name__ == "__main__":
    unittest.main()
