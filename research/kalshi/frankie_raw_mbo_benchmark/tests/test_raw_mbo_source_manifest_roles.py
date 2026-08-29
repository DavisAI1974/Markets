"""Tests for the single-role roster and the identity/manifest hash split."""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark.raw_mbo_source_manifest import (
    DEFAULT_SOURCE_URI_PREFIX,
    EXPECTED_ROSTER,
    SCORED_FINDINGS_DAY,
    ManifestError,
    _validate_manifest,
    manifest_hash,
    source_identity_hash,
)
from research.kalshi.frankie_raw_mbo_benchmark.tests.manifest_fixture import manifest_fixture

REAL_COUNTS = (1_504_374, 57_027, 1_994_358, 2_111_930)
PINNED_IDENTITY = "4d02dae63163a43fe0dc093ad0bda9a6d055a455cbc946a59d5b9008dad190ac"

REAL = {
    "20211001": (25_628_861, "e6b4ec01bd9b34d57cb22c770b5d49c756e7f41a658f081823d923004a0121b2"),
    "20211003": (973_355, "4380bd9ba83a5badc4839e12785aa464817b87e3fac11176b951e7b474446d88"),
    "20211004": (34_300_424, "8ed47cc0a68cf40cae9fde45e158142978076e60d3f9fc7cf940196babfddc0a"),
    "20211005": (36_192_430, "a4a12f9578da762412884e7f559a123361eaa3a153bec0db59dfb3ba6224a874"),
}


def real_manifest() -> dict:
    """The actual roster, with the byte lengths and digests pinned in both workflows."""
    m = manifest_fixture(REAL_COUNTS)
    for row in m["sources"]:
        nbytes, digest = REAL[row["date"]]
        row["bytes"], row["sha256"] = nbytes, digest
    m["source_identity_hash"] = source_identity_hash(m)
    m["manifest_hash"] = manifest_hash(m)
    return m


class RosterRoleTest(unittest.TestCase):
    def test_all_four_days_share_one_role(self) -> None:
        """Every day is scored and every day produces findings, so no role divides them."""
        roles = {role for _, role in EXPECTED_ROSTER}
        self.assertEqual(roles, {SCORED_FINDINGS_DAY})

    def test_the_old_split_roles_are_gone(self) -> None:
        roles = {role for _, role in EXPECTED_ROSTER}
        self.assertNotIn("WARMUP_DEVELOPMENT", roles)
        self.assertNotIn("HELD_OUT_BLIND", roles)

    def test_roster_position_records_stream_order(self) -> None:
        """What the old split carried is position, not role."""
        m = manifest_fixture(REAL_COUNTS)
        self.assertEqual([r["roster_position"] for r in m["sources"]], [0, 1, 2, 3])
        self.assertEqual([r["date"] for r in m["sources"]], ["20211001", "20211003", "20211004", "20211005"])

    def test_a_position_out_of_stream_order_is_refused(self) -> None:
        m = manifest_fixture(REAL_COUNTS)
        m["sources"][0]["roster_position"] = 3
        m["manifest_hash"] = manifest_hash(m)
        m["source_identity_hash"] = source_identity_hash(m)
        m["manifest_hash"] = manifest_hash(m)
        with self.assertRaises(ManifestError):
            _validate_manifest(m)


class HashSplitTest(unittest.TestCase):
    def test_identity_is_stable_across_staging_but_the_manifest_hash_is_not(self) -> None:
        """The reason there are two hashes: staging is per-run, identity is not."""
        base = manifest_fixture(REAL_COUNTS)
        staged = manifest_fixture(REAL_COUNTS)
        for row in staged["sources"]:
            row["staged_path"] = "/somewhere/else/" + row["name"]
            row["staged_sha256"] = "a" * 64
            row["download_receipt"] = "receipt-123"
        staged["source_identity_hash"] = source_identity_hash(staged)
        staged["manifest_hash"] = manifest_hash(staged)

        self.assertEqual(staged["source_identity_hash"], base["source_identity_hash"])
        self.assertNotEqual(staged["manifest_hash"], base["manifest_hash"])
        _validate_manifest(staged)

    def test_identity_moves_when_a_real_identity_field_changes(self) -> None:
        base = manifest_fixture(REAL_COUNTS)
        for field, value in (("bytes", 999), ("sha256", "b" * 64), ("mbo_records", 7), ("uri", "s3://x/y")):
            with self.subTest(field=field):
                other = manifest_fixture(REAL_COUNTS)
                other["sources"][0][field] = value
                self.assertNotEqual(source_identity_hash(other), base["source_identity_hash"])

    def test_the_pinned_identity_hash_reproduces_from_the_real_roster(self) -> None:
        """This is the value pinned in a_memory_prepare and the A-memory workflow."""
        self.assertEqual(real_manifest()["source_identity_hash"], PINNED_IDENTITY)

    def test_the_real_roster_reconciles_to_the_declared_total(self) -> None:
        m = real_manifest()
        self.assertEqual(m["total_mbo_records"], 5_667_689)
        _validate_manifest(m)


class ValidationTest(unittest.TestCase):
    def test_the_old_schema_is_refused(self) -> None:
        m = manifest_fixture(REAL_COUNTS)
        m["warmup_mbo_records"] = 1
        with self.assertRaises(ManifestError):
            _validate_manifest(m)

    def test_a_missing_uri_is_refused(self) -> None:
        m = manifest_fixture(REAL_COUNTS)
        m["sources"][0]["uri"] = ""
        m["source_identity_hash"] = source_identity_hash(m)
        m["manifest_hash"] = manifest_hash(m)
        with self.assertRaises(ManifestError):
            _validate_manifest(m)

    def test_every_source_carries_the_external_uri(self) -> None:
        for row in manifest_fixture(REAL_COUNTS)["sources"]:
            self.assertTrue(row["uri"].startswith(DEFAULT_SOURCE_URI_PREFIX))
            self.assertTrue(row["uri"].endswith(row["name"]))

    def test_an_unstaged_source_is_valid_but_a_bad_staged_digest_is_not(self) -> None:
        """Not yet staged is a lawful state; a malformed digest is not."""
        m = manifest_fixture(REAL_COUNTS)
        _validate_manifest(m)
        m["sources"][0]["staged_sha256"] = "not-a-digest"
        m["source_identity_hash"] = source_identity_hash(m)
        m["manifest_hash"] = manifest_hash(m)
        with self.assertRaises(ManifestError):
            _validate_manifest(m)

    def test_a_tampered_identity_hash_is_refused(self) -> None:
        m = manifest_fixture(REAL_COUNTS)
        m["source_identity_hash"] = "c" * 64
        m["manifest_hash"] = manifest_hash(m)
        with self.assertRaises(ManifestError):
            _validate_manifest(m)


if __name__ == "__main__":
    unittest.main()
