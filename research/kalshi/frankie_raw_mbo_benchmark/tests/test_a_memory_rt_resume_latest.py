from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark.a_memory_rt_resume_latest_20260828 import (
    checkpoint_source,
    source_position,
)


class AMemoryLatestResumeCursorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = {
            "sources": [
                {"name": "20211001", "mbo_records": 1_504_374},
                {"name": "20211003", "mbo_records": 57_027},
                {"name": "20211004", "mbo_records": 1_994_358},
                {"name": "20211005", "mbo_records": 2_111_930},
            ],
            "total_mbo_records": 5_667_689,
        }

    def test_sequence_seven_global_cursor_maps_into_october_four(self) -> None:
        self.assertEqual(source_position(self.manifest, 2_500_000), (2, 938_599, False))

    def test_raw_file_boundary_is_bound_to_the_source_that_just_closed(self) -> None:
        source, local_cursor = checkpoint_source(self.manifest, 1_561_401)
        self.assertEqual(source["name"], "20211003")
        self.assertEqual(local_cursor, 57_027)

    def test_final_cursor_maps_to_the_last_closed_source(self) -> None:
        self.assertEqual(
            source_position(self.manifest, 5_667_689),
            (3, 2_111_930, True),
        )

    def test_cursor_beyond_manifest_fails_closed(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "outside source manifest"):
            source_position(self.manifest, 5_667_690)


if __name__ == "__main__":
    unittest.main()
