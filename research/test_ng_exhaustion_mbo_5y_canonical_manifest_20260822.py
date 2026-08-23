from __future__ import annotations

import datetime as dt
import json
import unittest

from ng_exhaustion_mbo_5y_canonical_manifest_20260822 import (
    DATASET,
    SCHEMA,
    STYPE_IN,
    SYMBOL,
    ManifestFreezeError,
    expected_intervals,
    freeze_manifest,
    payload_sha256,
    segment_id,
)


BUCKET = "bucket"
PREFIX = "science/"


def fixtures(intervals):
    blobs = {}
    heads = {}
    for start, end in intervals:
        seg = segment_id(start, end)
        jid = "JOB-" + seg
        key = f"{PREFIX}native/{seg}/{seg}.dbn.zst"
        sha = ("a" if start.day == 20 else "b") * 64
        job = {"job_id": jid, "start": start.isoformat(), "end": end.isoformat()}
        manifest = {
            "segment": seg,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "job_id": jid,
            "dataset": DATASET,
            "symbol": SYMBOL,
            "stype_in": STYPE_IN,
            "data_schema": SCHEMA,
            "files": [{"s3_key": key, "bytes": 7, "sha256": sha}],
        }
        blobs[f"{PREFIX}_jobs/{seg}.json"] = json.dumps(job).encode()
        blobs[f"{PREFIX}manifests/{seg}.json"] = json.dumps(manifest).encode()
        heads[key] = {
            "ContentLength": 7,
            "ETag": '"etag"',
            "Metadata": {
                "sha256": sha,
                "dataset": DATASET,
                "schema": SCHEMA,
                "symbol": SYMBOL,
                "stype": STYPE_IN,
                "job_id": jid,
                "segment": seg,
            },
        }
    return blobs, heads


class CanonicalManifestTests(unittest.TestCase):
    def test_expected_grid_is_exactly_61_intervals(self):
        rows = expected_intervals()
        self.assertEqual(len(rows), 61)
        self.assertEqual(rows[0], (dt.date(2021, 8, 20), dt.date(2021, 9, 1)))
        self.assertEqual(rows[-1], (dt.date(2026, 8, 1), dt.date(2026, 8, 20)))

    def test_freezes_exact_receipts_and_retains_exclusions(self):
        intervals = [
            (dt.date(2021, 8, 20), dt.date(2021, 9, 1)),
            (dt.date(2021, 9, 1), dt.date(2021, 10, 1)),
        ]
        blobs, heads = fixtures(intervals)
        legacy = {
            "job_id": "DUPLICATE-JOB",
            "start": "2021-08-20",
            "end": "2021-09-01",
        }
        blobs[f"{PREFIX}_jobs/2021-08.json"] = json.dumps(legacy).encode()

        result = freeze_manifest(
            bucket=BUCKET,
            prefix=PREFIX,
            get_json_bytes=lambda key: blobs[key],
            get_json_optional=lambda key: None if key not in blobs else (blobs[key], json.loads(blobs[key])),
            head_object=lambda key: heads[key],
            archive_audit={
                "unexpected_intervals": [{
                    "start": "2022-08-20", "end": "2022-09-01", "job_ids": ["PARTIAL-JOB"]
                }]
            },
            intervals=intervals,
        )
        self.assertEqual(result["selected_interval_count"], 2)
        self.assertEqual(result["canonical_object_count"], 2)
        self.assertFalse(result["prefix_wide_enumeration_used"])
        self.assertEqual({x["kind"] for x in result["exclusions"]}, {
            "DUPLICATE_EXPECTED_INTERVAL_JOB", "UNEXPECTED_PARTIAL_OVERLAP_JOB"
        })
        self.assertEqual(result["manifest_sha256"], payload_sha256(result))

    def test_fails_on_s3_hash_drift(self):
        intervals = [(dt.date(2021, 8, 20), dt.date(2021, 9, 1))]
        blobs, heads = fixtures(intervals)
        only_key = next(iter(heads))
        heads[only_key]["Metadata"]["sha256"] = "0" * 64
        with self.assertRaises(ManifestFreezeError):
            freeze_manifest(
                bucket=BUCKET,
                prefix=PREFIX,
                get_json_bytes=lambda key: blobs[key],
                get_json_optional=lambda _key: None,
                head_object=lambda key: heads[key],
                archive_audit={"unexpected_intervals": []},
                intervals=intervals,
            )

    def test_missing_exact_manifest_fails_closed(self):
        intervals = [(dt.date(2021, 8, 20), dt.date(2021, 9, 1))]
        blobs, heads = fixtures(intervals)
        del blobs[f"{PREFIX}manifests/20210820_20210901.json"]
        with self.assertRaises(ManifestFreezeError):
            freeze_manifest(
                bucket=BUCKET,
                prefix=PREFIX,
                get_json_bytes=lambda key: blobs[key],
                get_json_optional=lambda _key: None,
                head_object=lambda key: heads[key],
                archive_audit={"unexpected_intervals": []},
                intervals=intervals,
            )


if __name__ == "__main__":
    unittest.main()
