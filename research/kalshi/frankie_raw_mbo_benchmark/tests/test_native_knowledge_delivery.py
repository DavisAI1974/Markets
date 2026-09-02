"""The knowledge Frankie receives is classified from the inventory, bound to real files, receipted.

Greg, 2026-09-02: the proposal lineage goes in whole; every lesson is UNVERIFIED until he
verifies it against the stream; no historical number is a spec; nothing is dropped without
discussion, and every excluded path is listed with its reason. These tests never assert a
count such as 149 or 15 - they derive the expected set from the documents and the registry
the module itself reads, and check the module against that.
"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark.native_knowledge_delivery import (
    ADDENDUM_PATH,
    BRAIN_PATH,
    CLASSIFICATIONS,
    CODE,
    FEED_INVENTORY_PATH,
    KEEP,
    OBSOLETE,
    REPO_ROOT,
    SEALED,
    SOURCE_INVENTORY_PATH,
    SUPERSEDED,
    KnowledgeDeliveryError,
    classify_inventory,
    parse_source_inventory,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (
    ALLOWED_V3_LAYER_IDS,
    ALLOWED_V3_SOURCE_PATHS,
    REGISTRY_PATH,
    IngestionLayerGateError,
    canonical_hash,
    load_registry,
    validate_registry,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_knowledge_delivery import (
    KNOWLEDGE_INPUT_POLICIES,
    KNOWLEDGE_LAYER_SOURCES,
    layers_bound_only_to,
)
from research.kalshi.frankie_raw_mbo_benchmark.rebind_registry_knowledge_layers import (
    main as rebind_main,
    rebind_knowledge_layers,
    render_registry_json,
)
from research.kalshi.frankie_raw_mbo_benchmark.render_source_inventory_addendum import (
    ADDENDUM_DATE,
    main as render_main,
    render_addendum,
)


def independent_bullet_census(text: str) -> list[tuple[str, str | None]]:
    """A second, deliberately naive reading of the inventory: (section, path-or-None) per bullet.

    Written without the module's parser so the test does not merely agree with itself.
    """
    rows: list[tuple[str, str | None]] = []
    section = None
    for line in text.splitlines():
        heading = re.match(r"^## ([A-M])\. ", line)
        if heading:
            section = heading.group(1)
            continue
        if line.startswith("## "):
            section = None
            continue
        if section and line.startswith("- "):
            path = re.match(r"^- `([^`]+)`", line)
            rows.append((section, path.group(1) if path else None))
    return rows


class ParseSourceInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (REPO_ROOT / SOURCE_INVENTORY_PATH).read_text(encoding="utf-8")
        self.bullets = parse_source_inventory(self.text)

    def test_finds_every_bullet_of_sections_a_to_m_in_document_order(self) -> None:
        expected = independent_bullet_census(self.text)
        self.assertEqual([(b.section, b.path) for b in self.bullets], expected)
        self.assertGreater(len(self.bullets), 0)

    def test_records_the_prose_bullet_without_inventing_a_path(self) -> None:
        prose = [b for b in self.bullets if b.path is None]
        self.assertEqual([b.section for b in prose], ["K"])
        self.assertTrue(prose[0].bullet.startswith("Step-1 seconds, populations"))

    def test_every_path_bullet_names_a_file_that_exists_under_the_repo_root(self) -> None:
        missing = [b.path for b in self.bullets if b.path and not (REPO_ROOT / b.path).is_file()]
        self.assertEqual(missing, [])

    def test_no_inventory_path_is_absolute_or_a_desktop_path(self) -> None:
        offenders = [
            b.path for b in self.bullets
            if b.path and (b.path.startswith("/") or re.match(r"^[A-Za-z]:", b.path))
        ]
        self.assertEqual(offenders, [])

    def test_bullet_lines_are_one_based_and_point_at_the_bullet(self) -> None:
        lines = self.text.splitlines()
        for bullet in self.bullets:
            with self.subTest(section=bullet.section, line=bullet.line):
                self.assertTrue(lines[bullet.line - 1].startswith("- "))


class ClassifyInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = classify_inventory(REPO_ROOT)
        cls.by_path = {row.path: row for row in cls.rows if row.path}

    def test_one_row_per_bullet_in_document_order(self) -> None:
        text = (REPO_ROOT / SOURCE_INVENTORY_PATH).read_text(encoding="utf-8")
        self.assertEqual(
            [(r.section, r.path) for r in self.rows],
            independent_bullet_census(text),
        )

    def test_every_row_carries_one_of_the_five_classifications_and_a_reason(self) -> None:
        self.assertEqual(set(CLASSIFICATIONS), {KEEP, CODE, SUPERSEDED, SEALED, OBSOLETE})
        for row in self.rows:
            with self.subTest(path=row.path or row.bullet):
                self.assertIn(row.classification, CLASSIFICATIONS)
                self.assertTrue(row.reason.strip())

    def test_the_knowledge_sections_are_keep(self) -> None:
        for row in self.rows:
            if row.section in ("C", "D", "E", "F"):
                with self.subTest(path=row.path):
                    self.assertEqual(row.classification, KEEP)

    def test_the_brain_is_keep_and_the_rest_of_section_b_is_code(self) -> None:
        self.assertEqual(self.by_path[BRAIN_PATH].classification, KEEP)
        for row in self.rows:
            if row.section == "B" and row.path != BRAIN_PATH:
                with self.subTest(path=row.path):
                    self.assertEqual(row.classification, CODE)

    def test_the_two_inventories_are_keep_and_the_rest_of_section_a_is_superseded(self) -> None:
        self.assertEqual(self.by_path[FEED_INVENTORY_PATH].classification, KEEP)
        self.assertEqual(self.by_path[SOURCE_INVENTORY_PATH].classification, KEEP)
        for row in self.rows:
            if row.section == "A" and row.path not in (FEED_INVENTORY_PATH, SOURCE_INVENTORY_PATH):
                with self.subTest(path=row.path):
                    self.assertEqual(row.classification, SUPERSEDED)

    def test_runtime_receipt_and_shadow_sections_are_code(self) -> None:
        for row in self.rows:
            if row.section in ("G", "H", "I", "J"):
                with self.subTest(path=row.path):
                    self.assertEqual(row.classification, CODE)

    def test_shadow_rows_name_the_provisional_shadow_policy_in_their_reason(self) -> None:
        for row in self.rows:
            if row.section == "J":
                with self.subTest(path=row.path):
                    self.assertIn("PROVISIONAL_SHADOW", row.reason)

    def test_the_sealed_section_is_sealed_including_the_prose_bullet(self) -> None:
        sealed = [row for row in self.rows if row.section == "K"]
        self.assertTrue(sealed)
        for row in sealed:
            with self.subTest(bullet=row.bullet):
                self.assertEqual(row.classification, SEALED)
        self.assertTrue(any(row.path is None for row in sealed))

    def test_obsolete_transport_and_the_forbidden_substitute_are_obsolete(self) -> None:
        for row in self.rows:
            if row.section in ("L", "M"):
                with self.subTest(path=row.path):
                    self.assertEqual(row.classification, OBSOLETE)
        forbidden = [row for row in self.rows if row.section == "M"]
        self.assertTrue(all("FORBIDDEN" in row.reason for row in forbidden))

    def test_every_keep_path_exists_on_disk(self) -> None:
        for row in self.rows:
            if row.classification == KEEP:
                with self.subTest(path=row.path):
                    self.assertIsNotNone(row.path)
                    self.assertTrue((REPO_ROOT / row.path).is_file())


class ClassifyInventoryFailsClosedTests(unittest.TestCase):
    def _root_with_inventory(self, body: str) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        target = root / SOURCE_INVENTORY_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        return root

    def test_a_bullet_in_an_unruled_section_is_refused(self) -> None:
        root = self._root_with_inventory("# x\n\n## N. A section nobody classified\n\n- `research/x.md`\n")
        (root / "research" / "x.md").write_text("x\n", encoding="utf-8")
        with self.assertRaisesRegex(KnowledgeDeliveryError, "no classification rule"):
            classify_inventory(root)

    def test_a_keep_path_missing_on_disk_is_refused(self) -> None:
        root = self._root_with_inventory("# x\n\n## C. Frozen corpus\n\n- `research/MISSING_FREEZE.json`\n")
        with self.assertRaisesRegex(KnowledgeDeliveryError, "KEEP path does not exist"):
            classify_inventory(root)

    def test_a_non_keep_path_missing_on_disk_is_reported_not_hidden(self) -> None:
        root = self._root_with_inventory("# x\n\n## L. Obsolete\n\n- `research/gone.py`\n")
        rows = classify_inventory(root)
        self.assertEqual([(r.classification, r.exists) for r in rows], [(OBSOLETE, False)])


class RenderSourceInventoryAddendumTests(unittest.TestCase):
    """The addendum is a RENDER of the classification, dated, and byte-identical when committed."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.rendered = render_addendum(REPO_ROOT)
        cls.rows = classify_inventory(REPO_ROOT)

    def test_committed_addendum_is_byte_identical_to_the_render(self) -> None:
        committed = (REPO_ROOT / ADDENDUM_PATH).read_bytes()
        self.assertEqual(committed, self.rendered.encode("utf-8"))

    def test_addendum_is_dated_and_never_rewrites_the_inventory(self) -> None:
        self.assertEqual(ADDENDUM_DATE, "2026-09-02")
        self.assertIn(f"Date: {ADDENDUM_DATE}", self.rendered)
        self.assertIn(SOURCE_INVENTORY_PATH, self.rendered)
        self.assertNotIn("| # | path | section | classification | reason |", "")
        # the render names the rule of construction: the 2026-08-24 record stays as written
        self.assertIn("never rewritten", self.rendered)

    def test_table_has_exactly_one_row_per_classified_bullet_in_order(self) -> None:
        table_rows = [
            line for line in self.rendered.splitlines()
            if re.match(r"^\| \d+ \| ", line)
        ]
        self.assertEqual(len(table_rows), len(self.rows))
        for number, (line, row) in enumerate(zip(table_rows, self.rows), start=1):
            with self.subTest(row=number):
                cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
                self.assertEqual(cells[0], str(number))
                if row.path is not None:
                    self.assertEqual(cells[1], f"`{row.path}`")
                else:
                    self.assertIn("no repository path", cells[1])
                    self.assertIn(row.bullet[:40], cells[1])
                self.assertEqual(cells[2], row.section)
                self.assertEqual(cells[3], row.classification)
                self.assertEqual(cells[4], row.reason)

    def test_counts_are_derived_from_the_rows_not_typed(self) -> None:
        for classification in CLASSIFICATIONS:
            expected = sum(1 for row in self.rows if row.classification == classification)
            with self.subTest(classification=classification):
                self.assertIn(f"| {classification} | {expected} |", self.rendered)
        self.assertIn(f"**{len(self.rows)} rows**", self.rendered)

    def test_render_is_deterministic(self) -> None:
        self.assertEqual(render_addendum(REPO_ROOT), self.rendered)

    def test_render_carries_no_emoji_and_no_desktop_or_scratch_path(self) -> None:
        self.assertFalse(re.search(r"[\U0001F300-\U0001FAFF☀-➿]", self.rendered))
        self.assertNotRegex(self.rendered, r"[A-Za-z]:[\\/]")

    def test_check_passes_on_the_committed_tree_and_fails_on_a_stale_addendum(self) -> None:
        self.assertEqual(render_main(["--check", "--repo-root", str(REPO_ROOT)]), 0)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        inventory = root / SOURCE_INVENTORY_PATH
        inventory.parent.mkdir(parents=True)
        inventory.write_text("# x\n\n## L. Obsolete\n\n- `research/old.py`\n", encoding="utf-8")
        (root / ADDENDUM_PATH).write_text("stale\n", encoding="utf-8")
        self.assertEqual(render_main(["--check", "--repo-root", str(root)]), 1)
        self.assertEqual(render_main(["--write", "--repo-root", str(root)]), 0)
        self.assertEqual(render_main(["--check", "--repo-root", str(root)]), 0)
        self.assertIn("`research/old.py`", (root / ADDENDUM_PATH).read_text(encoding="utf-8"))


class KnowledgeLayerBindingTests(unittest.TestCase):
    """The mapping from KEEP files to registry knowledge layers is by content, and it is complete."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry()
        cls.rows = classify_inventory(REPO_ROOT)
        cls.keep_paths = {row.path for row in cls.rows if row.classification == KEEP}
        cls.mapped_paths = {path for binding in KNOWLEDGE_LAYER_SOURCES for path in binding.paths}
        cls.input_layers = {
            entry["layer_id"]: group
            for group in cls.registry["groups"]
            if group["policy"] in KNOWLEDGE_INPUT_POLICIES
            for entry in group["entries"]
        }

    def test_every_mapped_layer_is_a_required_input_layer_of_the_registry(self) -> None:
        for binding in KNOWLEDGE_LAYER_SOURCES:
            with self.subTest(layer=binding.layer_id):
                self.assertIn(binding.layer_id, self.input_layers)

    def test_mapping_layer_ids_are_unique(self) -> None:
        ids = [binding.layer_id for binding in KNOWLEDGE_LAYER_SOURCES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_mapped_path_is_keep_and_exists(self) -> None:
        for binding in KNOWLEDGE_LAYER_SOURCES:
            for path in binding.paths:
                with self.subTest(layer=binding.layer_id, path=path):
                    self.assertIn(path, self.keep_paths)
                    self.assertTrue((REPO_ROOT / path).is_file())

    def test_every_keep_path_lands_in_a_mapped_layer_or_an_already_bound_input_layer(self) -> None:
        already_bound = {
            path
            for group in self.registry["groups"]
            if group["policy"] in KNOWLEDGE_INPUT_POLICIES
            for entry in group["entries"]
            if entry["layer_id"] not in {b.layer_id for b in KNOWLEDGE_LAYER_SOURCES}
            for path in entry["source_paths"]
        }
        unbound = sorted(self.keep_paths - self.mapped_paths - already_bound)
        self.assertEqual(unbound, [])

    def test_every_bound_file_matches_its_layers_content_terms(self) -> None:
        for binding in KNOWLEDGE_LAYER_SOURCES:
            pattern = re.compile(binding.content_terms, re.IGNORECASE)
            for path in binding.paths:
                with self.subTest(layer=binding.layer_id, path=path):
                    text = (REPO_ROOT / path).read_text(encoding="utf-8", errors="replace")
                    self.assertIsNotNone(pattern.search(text))

    def test_no_mapped_layer_is_bound_only_to_the_feed_inventory_document(self) -> None:
        for binding in KNOWLEDGE_LAYER_SOURCES:
            with self.subTest(layer=binding.layer_id):
                self.assertNotEqual(set(binding.paths), {FEED_INVENTORY_PATH})

    def test_the_brain_is_the_file_every_current_brain_layer_binds(self) -> None:
        brain_group = next(
            group for group in self.registry["groups"] if group["group_id"] == "current_brain_runtime"
        )
        by_id = {binding.layer_id: binding for binding in KNOWLEDGE_LAYER_SOURCES}
        for entry in brain_group["entries"]:
            with self.subTest(layer=entry["layer_id"]):
                self.assertIn(BRAIN_PATH, by_id[entry["layer_id"]].paths)

    def test_every_binding_carries_a_reason(self) -> None:
        for binding in KNOWLEDGE_LAYER_SOURCES:
            with self.subTest(layer=binding.layer_id):
                self.assertTrue(binding.why.strip())
                self.assertTrue(binding.paths)


class RegistryRebindTests(unittest.TestCase):
    """The registry is rebound BY SCRIPT: layout preserved, hash recomputed, validator satisfied."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.committed_bytes = REGISTRY_PATH.read_bytes()
        cls.registry = load_registry()
        cls.rebound = rebind_knowledge_layers(cls.registry)

    def test_render_reproduces_the_committed_registry_byte_for_byte(self) -> None:
        self.assertEqual(render_registry_json(self.registry).encode("utf-8"), self.committed_bytes)

    def test_committed_registry_is_already_rebound_and_check_passes(self) -> None:
        self.assertEqual(self.rebound, self.registry)
        self.assertEqual(rebind_main(["--check"]), 0)

    def test_rebind_is_idempotent(self) -> None:
        self.assertEqual(rebind_knowledge_layers(self.rebound), self.rebound)

    def test_rebound_registry_validates_with_the_identity_set_and_counts_unchanged(self) -> None:
        before = validate_registry(self.registry)
        after = validate_registry(self.rebound)
        for key in (
            "exact_layer_id_set_sha256",
            "concrete_layer_count",
            "a_clean_applicable_layer_count",
            "a_memory_applicable_layer_count",
            "sealed_layer_ids",
        ):
            with self.subTest(key=key):
                self.assertEqual(after[key], before[key])

    def test_each_mapped_layer_binds_exactly_its_mapping_and_flags_v3_by_rule(self) -> None:
        entries = {
            entry["layer_id"]: entry
            for group in self.rebound["groups"]
            for entry in group["entries"]
        }
        for binding in KNOWLEDGE_LAYER_SOURCES:
            with self.subTest(layer=binding.layer_id):
                entry = entries[binding.layer_id]
                self.assertEqual(entry["source_paths"], list(binding.paths))
                self.assertEqual(entry["v3_derived"], any("_V3_" in p for p in binding.paths))

    def test_no_required_input_layer_is_bound_only_to_the_inventory_after_rebind(self) -> None:
        self.assertEqual(
            layers_bound_only_to(
                self.rebound, self.rebound["source_authority"], policies=KNOWLEDGE_INPUT_POLICIES
            ),
            [],
        )

    def test_v3_allowlists_are_exactly_what_the_rebound_registry_uses(self) -> None:
        v3_layers = {
            entry["layer_id"]
            for group in self.rebound["groups"]
            for entry in group["entries"]
            if entry["v3_derived"]
        }
        v3_paths = {
            path
            for group in self.rebound["groups"]
            for entry in group["entries"]
            for path in entry["source_paths"]
            if "_V3_" in path
        }
        self.assertEqual(v3_layers, set(ALLOWED_V3_LAYER_IDS))
        self.assertEqual(v3_paths, set(ALLOWED_V3_SOURCE_PATHS))
        self.assertEqual(set(self.rebound["permitted_v3_source_paths"]), set(ALLOWED_V3_SOURCE_PATHS))

    def test_registry_hash_is_recomputed_never_hand_edited(self) -> None:
        self.assertEqual(
            self.rebound["registry_sha256"], canonical_hash(self.rebound, omit="registry_sha256")
        )

    def test_rebind_refuses_when_a_knowledge_layer_would_stay_bound_to_the_inventory(self) -> None:
        stale = load_registry()
        for group in stale["groups"]:
            for entry in group["entries"]:
                if entry["layer_id"] == "complete_s105_9_brain":
                    entry["source_paths"] = [stale["source_authority"]]
        partial = tuple(b for b in KNOWLEDGE_LAYER_SOURCES if b.layer_id != "complete_s105_9_brain")
        with self.assertRaisesRegex(KnowledgeDeliveryError, "bound only to the inventory document"):
            rebind_knowledge_layers(stale, bindings=partial)

    def test_check_fails_on_a_stale_registry_copy_and_write_repairs_it(self) -> None:
        stale = load_registry()
        for group in stale["groups"]:
            for entry in group["entries"]:
                if entry["layer_id"] == "complete_s105_9_brain":
                    entry["source_paths"] = [stale["source_authority"]]
        stale["registry_sha256"] = canonical_hash(stale, omit="registry_sha256")
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        target = Path(temporary.name) / "registry.json"
        target.write_text(render_registry_json(stale), encoding="utf-8")
        self.assertEqual(rebind_main(["--check", "--registry", str(target)]), 1)
        self.assertEqual(rebind_main(["--write", "--registry", str(target)]), 0)
        self.assertEqual(rebind_main(["--check", "--registry", str(target)]), 0)
        self.assertEqual(target.read_bytes(), self.committed_bytes)

    def test_a_rebound_registry_with_a_wrong_hash_is_refused_by_the_validator(self) -> None:
        broken = dict(self.rebound)
        broken["registry_sha256"] = "0" * 64
        with self.assertRaisesRegex(IngestionLayerGateError, "hash mismatch"):
            validate_registry(broken)


if __name__ == "__main__":
    unittest.main()
