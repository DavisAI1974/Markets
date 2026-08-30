"""Contract 4.4 mandates ONE mechanically defined mirror key.

These tests keep the count at one, and keep it from swallowing section 4.12's
orientation, which is a different axis under a different contract clause.
"""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark import native_dipole, native_mirror
from research.kalshi.frankie_raw_mbo_benchmark.a_memory_member_first_recalculation_20260828 import (
    discovery_contract,
    mirror_identity as a_memory_mirror_identity,
)

SIDE_STRINGS = (
    "A", "B", "N", "AB", "BA", "ABBN", "BAAN", "AAAA", "BBBB", "NNN", "", "ABNBAN",
)


class MirrorIdentityTest(unittest.TestCase):
    def test_the_mirror_is_the_side_swapped_side_string(self) -> None:
        self.assertEqual(native_mirror.mirror_identity("ABBN")["mirror_side_string"], "BAAN")

    def test_a_pair_resolves_to_one_key_from_either_end(self) -> None:
        """What makes it a pair KEY rather than two labels for two structures."""
        left = native_mirror.mirror_identity("ABBN")
        right = native_mirror.mirror_identity("BAAN")
        self.assertEqual(left["mirror_pair_key"], right["mirror_pair_key"])
        self.assertEqual(left["mirror_pair_key"], "ABBN|BAAN")
        self.assertNotEqual(left["orientation"], right["orientation"])

    def test_orientation_is_canonical_for_the_lexicographically_first_member(self) -> None:
        self.assertEqual(native_mirror.mirror_identity("ABBN")["orientation"], native_mirror.CANONICAL)
        self.assertEqual(native_mirror.mirror_identity("BAAN")["orientation"], native_mirror.MIRROR)

    def test_unsided_characters_pass_through_rather_than_raising(self) -> None:
        """D60: an unsided or novel row is characterized, never dropped."""
        self.assertEqual(native_mirror.mirror_identity("NNN")["mirror_side_string"], "NNN")
        self.assertEqual(native_mirror.mirror_identity("NNN")["orientation"], native_mirror.CANONICAL)

    def test_swapping_twice_returns_the_original(self) -> None:
        for sides in SIDE_STRINGS:
            with self.subTest(sides=sides):
                once = native_mirror.mirror_identity(sides)["mirror_side_string"]
                twice = native_mirror.mirror_identity(once)["mirror_side_string"]
                self.assertEqual(twice, sides)


class OneDefinitionTest(unittest.TestCase):
    def test_the_a_memory_recalculation_delegates_rather_than_reimplementing(self) -> None:
        for sides in SIDE_STRINGS:
            with self.subTest(sides=sides):
                self.assertEqual(
                    a_memory_mirror_identity(sides), native_mirror.mirror_identity(sides)
                )


class SeparateFromSection412Test(unittest.TestCase):
    """4.4's pair key and 4.12's orientation are different axes. Both are required."""

    def test_section_4_12_keeps_its_contract_orientation(self) -> None:
        """Contract 4.12: "`SAME` and `FLIP` orientations never pool"."""
        self.assertEqual(native_dipole.VALID_ORIENTATIONS, frozenset({"SAME", "FLIP"}))

    def test_the_frozen_transition_orientation_uses_the_same_words(self) -> None:
        self.assertEqual(discovery_contract()["transition_orientation_seeds"], ["SAME", "FLIP"])

    def test_the_mirror_key_does_not_borrow_them(self) -> None:
        self.assertNotIn("SAME", native_mirror.VALID_ORIENTATIONS)
        self.assertNotIn("FLIP", native_mirror.VALID_ORIENTATIONS)


if __name__ == "__main__":
    unittest.main()
