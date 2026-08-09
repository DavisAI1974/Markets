from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import databento_backfill_s115 as m16  # noqa: E402


class M16Tests(unittest.TestCase):
    def test_default_destinations_are_absolute_repo_root_paths(self):
        self.assertTrue(m16.absolute_destination(None, "trades").is_absolute())
        self.assertTrue(m16.absolute_destination(None, "mbp-10").is_absolute())
        self.assertTrue(m16.absolute_destination(None, "mbp-1").is_absolute())
        self.assertEqual(m16.absolute_destination(None, "trades").name, "nymex_cont_n0")

    def test_relative_override_is_root_relative_not_cwd_relative(self):
        got = m16.absolute_destination("data/custom", "trades")
        self.assertEqual(got, (m16.ROOT / "data/custom").resolve())

    def test_reported_rows_require_byte_growth(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            p = dest / "NG_20260801.jsonl"
            p.write_text("x\n", encoding="utf-8")
            before = {str(p.resolve()): p.stat().st_size}
            with self.assertRaises(m16.LandingError):
                m16.assert_size_growth(before, dict(before), 10, dest)
            p.write_text("x\ny\n", encoding="utf-8")
            after = {str(p.resolve()): p.stat().st_size}
            m16.assert_size_growth(before, after, 10, dest)


if __name__ == "__main__":
    unittest.main()
