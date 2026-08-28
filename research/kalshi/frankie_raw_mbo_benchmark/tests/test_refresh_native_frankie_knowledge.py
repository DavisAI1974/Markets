from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from research.kalshi.frankie_raw_mbo_benchmark.refresh_native_frankie_knowledge import (
    KnowledgeRefreshError,
    verify_managed_knowledge_inventory,
)


class NativeFrankieKnowledgeRefreshTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "source.md").write_text("source\n", encoding="utf-8")
        (self.root / "capsule.md").write_text("capsule\n", encoding="utf-8")
        self.spec = {
            "managed_globs": ["*.md"],
            "capsules": [
                {
                    "output_path": "capsule.md",
                    "sources": [{"path": "source.md"}],
                }
            ],
            "artifacts": [{"path": "source.md"}, {"path": "capsule.md"}],
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_accepts_fully_registered_managed_inventory(self) -> None:
        verify_managed_knowledge_inventory(self.spec, self.root)

    def test_rejects_random_unregistered_managed_file(self) -> None:
        (self.root / "forgotten.md").write_text("forgotten\n", encoding="utf-8")
        with self.assertRaisesRegex(
            KnowledgeRefreshError, "unregistered managed knowledge files"
        ):
            verify_managed_knowledge_inventory(self.spec, self.root)


if __name__ == "__main__":
    unittest.main()
