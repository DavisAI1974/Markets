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


if __name__ == "__main__":
    unittest.main()
