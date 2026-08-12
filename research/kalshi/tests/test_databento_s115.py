from __future__ import annotations

import argparse
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def test_mbp10_dispatch_tracks_uncompressed_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            real = dest / "NG_20260801.jsonl"
            wrong = dest / "NG_20260801.jsonl.gz"
            real.write_text("depth\n", encoding="utf-8")
            wrong.write_text("l1\n", encoding="utf-8")
            self.assertEqual(m16._files_for(dest, "NG", "mbp-10"), [real])
            self.assertEqual(m16._files_for(dest, "NG", "mbp-1"), [wrong])

    @staticmethod
    def _args(tmp: str, *, mode: str, schema: str) -> argparse.Namespace:
        return argparse.Namespace(
            mode=mode,
            symbol="NG",
            start="2026-08-01",
            end="2026-08-02",
            schema=schema,
            roll="n",
            max_cost=1.0,
            out_dir=tmp,
            job_id=None,
            flush_dir=None,
        )

    def test_mbp10_run_pull_accepts_real_writer_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            def fake_batch(*call_args):
                dest = Path(call_args[-1])
                (dest / "NG_20260801.jsonl").write_text("depth\n", encoding="utf-8")
                return 10

            with mock.patch.object(m16.legacy, "_client", return_value=object()), \
                 mock.patch.object(m16.legacy, "batch_pull", side_effect=fake_batch):
                reported = m16.run_pull(self._args(tmp, mode="pull", schema="mbp-10"))
            self.assertEqual(reported, 10)

    def test_range_none_return_without_landing_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(m16.legacy, "_client", return_value=object()), \
                 mock.patch.object(m16.legacy, "range_pull", return_value=None):
                with self.assertRaises(m16.LandingError):
                    m16.run_pull(self._args(tmp, mode="range", schema="trades"))


if __name__ == "__main__":
    unittest.main()
