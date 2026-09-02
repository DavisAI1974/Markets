"""The KEEP set reaches the knowledge manifest BY SCRIPT, routed to the one arm that runs.

Greg's rulings (DROP_IN_S121 item zero; D86): no historical number is a spec, so no test here
says 63 or 12 - the KEEP set is derived from `classify_inventory` and the registry at test
time; the sources spec is GENERATED, never hand-typed, and the committed file must be the
generated one; the arm is A_MEMORY and A_CLEAN's profiles stay byte-identical, inert.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark.native_frankie_knowledge_registry import (
    ALLOWED_KINDS,
    load_and_validate_manifest,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import load_registry
from research.kalshi.frankie_raw_mbo_benchmark.native_knowledge_delivery import (
    FEED_INVENTORY_PATH,
    KEEP,
    REPO_ROOT,
    SOURCE_INVENTORY_PATH,
    classify_inventory,
)
from research.kalshi.frankie_raw_mbo_benchmark.refresh_native_frankie_knowledge import (
    load_spec,
    refresh,
)
from research.kalshi.frankie_raw_mbo_benchmark.register_a_memory_knowledge import (
    ARM,
    KEEP_ID_PREFIX,
    SPEC_PATH,
    RegistrationError,
    keep_artifacts,
    kind_for_path,
    main as register_main,
    register,
    render_spec,
)

MANIFEST_PATH = "research/kalshi/agents/frankie_native_raw_mbo_knowledge/KNOWLEDGE_MANIFEST_20260828.json"


def committed_spec() -> dict:
    return json.loads((REPO_ROOT / SPEC_PATH).read_text(encoding="utf-8"))


def keep_paths() -> set[str]:
    return {row.path for row in classify_inventory(REPO_ROOT) if row.classification == KEEP}


def input_bindings(registry: dict) -> dict[str, list[tuple[str, str]]]:
    """path -> [(group_id, authority)] over the pre-call input groups, in registry order."""
    out: dict[str, list[tuple[str, str]]] = {}
    for group in registry["groups"]:
        if group["policy"] not in ("STATIC_REQUIRED_INPUT", "ARM_REQUIRED_INPUT"):
            continue
        for entry in group["entries"]:
            for path in entry["source_paths"]:
                pair = (group["group_id"], group["authority"])
                if pair not in out.setdefault(path, []):
                    out[path].append(pair)
    return out


class KeepArtifactsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry()
        cls.rows = keep_artifacts(cls.registry, REPO_ROOT)
        cls.by_path = {row["path"]: row for row in cls.rows}

    def test_one_artifact_per_keep_path_derived_not_typed(self) -> None:
        self.assertEqual(set(self.by_path), keep_paths())
        self.assertEqual(len(self.rows), len(self.by_path), "paths are unique")

    def test_ids_are_derived_from_the_path_unique_and_prefixed(self) -> None:
        ids = [row["id"] for row in self.rows]
        self.assertEqual(len(ids), len(set(ids)))
        for row in self.rows:
            with self.subTest(path=row["path"]):
                self.assertTrue(row["id"].startswith(KEEP_ID_PREFIX))
                self.assertRegex(row["id"], r"^[a-z0-9_]+$")
                # the extension survives in the id: the D0-D5 contract exists as .md AND .json
                self.assertTrue(row["id"].endswith("_" + row["path"].rsplit(".", 1)[-1]))

    def test_kind_follows_the_extension_and_every_kind_is_allowed(self) -> None:
        for row in self.rows:
            with self.subTest(path=row["path"]):
                self.assertEqual(row["kind"], kind_for_path(row["path"]))
                self.assertIn(row["kind"], ALLOWED_KINDS)
        self.assertEqual(kind_for_path("x/y.py"), "PYTHON_SOURCE")
        self.assertEqual(kind_for_path("x/y.md"), "MARKDOWN")
        self.assertEqual(kind_for_path("x/y.json"), "JSON")
        with self.assertRaises(RegistrationError):
            kind_for_path("x/y.csv")

    def test_routing_is_the_memory_arm_both_roles_retrieval(self) -> None:
        for row in self.rows:
            with self.subTest(path=row["path"]):
                self.assertEqual(row["arms"], [ARM])
                self.assertEqual(row["roles"], ["REAL_TIME_FRANKIE", "FORECASTER_FRANKIE"])
                self.assertEqual(row["load_mode"], "RETRIEVAL")
                self.assertEqual(
                    set(row), {"id", "path", "kind", "authority", "arms", "roles", "load_mode"}
                )

    def test_authority_is_the_binding_registry_groups_authority(self) -> None:
        """Per the registry group that binds the file; a file two groups bind carries both
        authorities joined in registry order (nothing dropped); the two inventories are the
        canonical input list and read BINDING_CURRENT."""
        bindings = input_bindings(self.registry)
        for row in self.rows:
            with self.subTest(path=row["path"]):
                if row["path"] in (FEED_INVENTORY_PATH, SOURCE_INVENTORY_PATH):
                    self.assertEqual(row["authority"], "BINDING_CURRENT")
                    continue
                expected = "+".join(authority for _group, authority in bindings[row["path"]])
                self.assertEqual(row["authority"], expected)

    def test_a_keep_path_no_input_layer_binds_is_refused(self) -> None:
        registry = json.loads(json.dumps(self.registry))
        brain = "research/kalshi/knowledge/ng_brain.json"
        for group in registry["groups"]:
            for entry in group["entries"]:
                # A layer bound ONLY to the brain falls back to the inventory document, so the
                # brain ends up bound by nothing - the case the refusal exists for.
                entry["source_paths"] = [
                    path for path in entry["source_paths"] if path != brain
                ] or [registry["source_authority"]]
        with self.assertRaisesRegex(RegistrationError, "no pre-call input layer binds"):
            keep_artifacts(registry, REPO_ROOT)


class RegisterSpecTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry()
        cls.committed = committed_spec()
        cls.generated = register(cls.committed, cls.registry, REPO_ROOT)
        cls.artifacts = {row["id"]: row for row in cls.generated["artifacts"]}
        cls.profiles = cls.generated["profiles"]

    def _memory_profiles(self) -> list[dict]:
        return [profile for profile in self.profiles.values() if profile["arm"] == ARM]

    def test_every_keep_path_is_a_retrieval_artifact_in_every_memory_profile(self) -> None:
        by_path = {row["path"]: row for row in self.generated["artifacts"]}
        memory_profiles = self._memory_profiles()
        self.assertEqual(len(memory_profiles), 2, "RT and Forecaster profiles for the arm")
        for path in keep_paths():
            with self.subTest(path=path):
                row = by_path[path]
                self.assertEqual(row["load_mode"], "RETRIEVAL")
                for profile in memory_profiles:
                    self.assertIn(row["id"], profile["retrieval_catalog"])

    def test_the_hand_maintained_base_artifacts_are_unchanged(self) -> None:
        base = {row["id"]: row for row in self.committed["artifacts"] if not row["id"].startswith(KEEP_ID_PREFIX)}
        for artifact_id, row in base.items():
            with self.subTest(artifact=artifact_id):
                self.assertEqual(self.artifacts[artifact_id], row)

    def test_the_a_clean_profiles_are_byte_identical_and_inert(self) -> None:
        for profile_id, profile in self.committed["profiles"].items():
            if profile["arm"] != "A_CLEAN":
                continue
            with self.subTest(profile=profile_id):
                self.assertEqual(self.profiles[profile_id], profile)

    def test_the_wrong_data_external_binding_is_retired_from_the_memory_profiles_not_deleted(self) -> None:
        """D86: the 32851909748-1 package is NOT memory and does not go in; the row stays as an
        inert record because removing it breaks nothing and D60 governs its removal."""
        for profile in self._memory_profiles():
            self.assertEqual(profile["external_bindings"], [])
        self.assertEqual(
            [row["id"] for row in self.generated["external_bindings"]],
            [row["id"] for row in self.committed["external_bindings"]],
        )

    def test_registration_is_idempotent(self) -> None:
        self.assertEqual(register(self.generated, self.registry, REPO_ROOT), self.generated)

    def test_the_committed_spec_is_the_generated_one_and_check_passes(self) -> None:
        self.assertEqual(render_spec(self.generated), (REPO_ROOT / SPEC_PATH).read_text(encoding="utf-8"))
        self.assertEqual(register_main(["--check", "--repo-root", str(REPO_ROOT)]), 0)

    def test_check_fails_on_a_stale_copy_and_write_repairs_it(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        target = root / SPEC_PATH
        target.parent.mkdir(parents=True)
        stale = json.loads(json.dumps(self.committed))
        stale["artifacts"] = [row for row in stale["artifacts"] if not row["id"].startswith(KEEP_ID_PREFIX)]
        target.write_text(render_spec(stale), encoding="utf-8")
        # --repo-root is where the inventory and the KEEP files are classified from; --spec is
        # the file being checked or written. They are separate so a copy can be checked.
        args = ["--repo-root", str(REPO_ROOT), "--spec", str(target)]
        self.assertEqual(register_main(["--check", *args]), 1)
        self.assertEqual(register_main(["--write", *args]), 0)
        self.assertEqual(register_main(["--check", *args]), 0)
        self.assertEqual(target.read_text(encoding="utf-8"), (REPO_ROOT / SPEC_PATH).read_text(encoding="utf-8"))


class CommittedManifestTest(unittest.TestCase):
    """The regenerated manifest is CURRENT, validates against every byte on disk, and routes
    the whole KEEP set to the memory arm."""

    def test_refresh_check_is_current(self) -> None:
        result = refresh(REPO_ROOT / SPEC_PATH, REPO_ROOT, write=False)
        self.assertEqual(result["updated_paths"], [])

    def test_manifest_validates_and_carries_every_keep_path_for_the_memory_arm(self) -> None:
        manifest = load_and_validate_manifest(REPO_ROOT / MANIFEST_PATH, REPO_ROOT)
        by_path = {row["path"]: row for row in manifest["artifacts"]}
        for path in keep_paths():
            with self.subTest(path=path):
                self.assertIn(path, by_path)
                self.assertIn(ARM, by_path[path]["arms"])
        spec = load_spec(REPO_ROOT / SPEC_PATH)
        self.assertEqual(
            {row["id"] for row in manifest["artifacts"]}, {row["id"] for row in spec["artifacts"]}
        )


if __name__ == "__main__":
    unittest.main()
