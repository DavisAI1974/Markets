"""The ledgers reach the session and are proven to be the ledgers the box reconciled.

A session holds no AWS credential, so delivery is: workflow presigns -> manifest artifact ->
session downloads -> this module verifies. Every check is against an INDEPENDENT witness -
S3's ContentLength for the gzip, the box's `wc -c` (PLAIN_SIZES) and `sha256sum`
(PLAIN_SHA256SUMS) for the plain bytes - and any mismatch is a refusal, never a warning: a
ledger of the wrong length is not "mostly" the evidence.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark.fetch_frankie_ledgers import (
    LEDGER_FILES,
    MANIFEST_SCHEMA,
    RECEIPT_SCHEMA,
    DeliveryError,
    build_manifest,
    fetch,
    main,
    parse_plain_sha256sums,
    parse_plain_sizes,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_staging import EXACT_LEDGERS

PREFIX = "nymex/ng_mbo_5y_v0/frankie/raw_mbo_benchmark/a-clean/full/7638659/33630348943-1"
BUCKET = "bento-568968024170-us-east-2-an"

PLAIN = {
    "exact_member_rows.jsonl": b'{"group_index":0,"ts_recv_ns":1}\n{"group_index":1,"ts_recv_ns":2}\n',
    "exact_lifecycle_rows.jsonl": b'{"emitting_section":"ladder","recv_ns":1}\n',
    "legacy_observable_rows.jsonl": b'{"ts_recv":0.000000001,"action":"A"}\n',
}
GZ = {name + ".gz": gzip.compress(body, compresslevel=1) for name, body in PLAIN.items()}
OTHER = {
    "calculation_result.json": b'{"verdict":"ACCEPTED"}\n',
    "small_artifacts.tar.gz": b"not really a tarball but bytes with a length\n",
}
OBJECTS = {**GZ, **OTHER}


def listing() -> list[dict]:
    return [{"Key": f"{PREFIX}/{name}", "Size": len(body)} for name, body in OBJECTS.items()]


def ledger_key(name: str) -> str:
    return f"{PREFIX}/ledgers/{name}" if name.endswith(".jsonl.gz") else f"{PREFIX}/{name}"


def listing_with_ledger_dir() -> list[dict]:
    return [{"Key": ledger_key(name), "Size": len(body)} for name, body in OBJECTS.items()]


def presigned() -> dict[str, str]:
    return {name: f"https://s3.example/{name}?X-Amz-Signature=SECRET{i}" for i, name in enumerate(OBJECTS)}


def plain_sizes_text() -> str:
    lines = [f"{len(body)} ledgers/{name}" for name, body in PLAIN.items()]
    lines.append(f"{sum(len(b) for b in PLAIN.values())} total")
    return "\n".join(lines) + "\n"


def plain_sha_text() -> str:
    lines = [f"{hashlib.sha256(body).hexdigest()}  ledgers/{name}" for name, body in PLAIN.items()]
    lines.append(f"{hashlib.sha256(OTHER['calculation_result.json']).hexdigest()}  calculation_result.json")
    return "\n".join(lines) + "\n"


def manifest() -> dict:
    return build_manifest(
        run_id="33630348943", run_prefix=PREFIX, bucket=BUCKET, listing=listing_with_ledger_dir(),
        presigned=presigned(), plain_sizes=parse_plain_sizes(plain_sizes_text()),
        plain_sha256=parse_plain_sha256sums(plain_sha_text()),
        expires_at="2026-09-09T12:00:00Z", presign_seconds=604800,
    )


def stub_downloader(objects: dict[str, bytes] | None = None, *, fail: set[str] = frozenset()):
    store = OBJECTS if objects is None else objects

    def download(url: str, dest: Path) -> None:
        name = url.split("/")[-1].split("?")[0]
        if name in fail:
            raise OSError(f"stub: {name} unreachable")
        dest.write_bytes(store[name])

    return download


class ParsersTest(unittest.TestCase):
    def test_plain_sizes_reads_wc_c_and_ignores_the_total_line(self):
        sizes = parse_plain_sizes(plain_sizes_text())
        self.assertEqual(sizes["exact_member_rows.jsonl"], len(PLAIN["exact_member_rows.jsonl"]))
        self.assertNotIn("total", sizes)

    def test_plain_sha256sums_reads_the_sha256sum_format_by_basename(self):
        shas = parse_plain_sha256sums(plain_sha_text())
        self.assertEqual(shas["legacy_observable_rows.jsonl"], hashlib.sha256(PLAIN["legacy_observable_rows.jsonl"]).hexdigest())
        self.assertIn("calculation_result.json", shas)


class BuildManifestTest(unittest.TestCase):
    def test_the_manifest_carries_every_object_with_its_s3_length_and_the_plain_witnesses(self):
        m = manifest()
        self.assertEqual(m["schema"], MANIFEST_SCHEMA)
        self.assertEqual(set(m["objects"]), set(OBJECTS))
        self.assertEqual(m["objects"]["exact_member_rows.jsonl.gz"]["content_length"], len(GZ["exact_member_rows.jsonl.gz"]))
        self.assertEqual(m["objects"]["exact_member_rows.jsonl.gz"]["key"], f"{PREFIX}/ledgers/exact_member_rows.jsonl.gz")
        self.assertTrue(m["objects"]["exact_member_rows.jsonl.gz"]["url"].startswith("https://"))
        self.assertEqual(m["plain_sizes"]["exact_member_rows.jsonl"], len(PLAIN["exact_member_rows.jsonl"]))
        self.assertEqual(m["plain_sha256"]["exact_member_rows.jsonl"], hashlib.sha256(PLAIN["exact_member_rows.jsonl"]).hexdigest())
        self.assertEqual(m["expires_at"], "2026-09-09T12:00:00Z")
        self.assertEqual(m["run_id"], "33630348943")
        self.assertEqual(m["bucket"], BUCKET)

    def test_a_missing_object_is_refused_not_omitted(self):
        rows = [r for r in listing_with_ledger_dir() if not r["Key"].endswith("exact_lifecycle_rows.jsonl.gz")]
        with self.assertRaisesRegex(DeliveryError, "exact_lifecycle_rows.jsonl.gz"):
            build_manifest(
                run_id="1", run_prefix=PREFIX, bucket=BUCKET, listing=rows, presigned=presigned(),
                plain_sizes=parse_plain_sizes(plain_sizes_text()), plain_sha256=parse_plain_sha256sums(plain_sha_text()),
                expires_at="x", presign_seconds=1,
            )

    def test_a_ledger_without_a_plain_witness_is_refused(self):
        shas = parse_plain_sha256sums(plain_sha_text())
        del shas["legacy_observable_rows.jsonl"]
        with self.assertRaisesRegex(DeliveryError, "PLAIN_SHA256SUMS.*legacy_observable_rows.jsonl"):
            build_manifest(
                run_id="1", run_prefix=PREFIX, bucket=BUCKET, listing=listing_with_ledger_dir(), presigned=presigned(),
                plain_sizes=parse_plain_sizes(plain_sizes_text()), plain_sha256=shas, expires_at="x", presign_seconds=1,
            )

    def test_an_object_without_a_presigned_url_is_refused(self):
        urls = presigned()
        del urls["calculation_result.json"]
        with self.assertRaisesRegex(DeliveryError, "presign.*calculation_result.json"):
            build_manifest(
                run_id="1", run_prefix=PREFIX, bucket=BUCKET, listing=listing_with_ledger_dir(), presigned=urls,
                plain_sizes=parse_plain_sizes(plain_sizes_text()), plain_sha256=parse_plain_sha256sums(plain_sha_text()),
                expires_at="x", presign_seconds=1,
            )


class FetchTest(unittest.TestCase):
    def _fetch(self, m=None, downloader=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "delivered"
        receipt_path = Path(tmp.name) / "receipt.json"
        try:
            receipt = fetch(m or manifest(), out, downloader=downloader or stub_downloader(), receipt_path=receipt_path)
            error = None
        except DeliveryError as exc:
            error = exc
            receipt = json.loads(receipt_path.read_text())
        return receipt, error, out, receipt_path

    def test_verified_ledgers_are_gunzipped_and_byte_identical_and_the_receipt_says_so(self):
        receipt, error, out, receipt_path = self._fetch()
        self.assertIsNone(error)
        self.assertEqual(receipt["schema"], RECEIPT_SCHEMA)
        self.assertTrue(receipt["all_ledgers_verified"])
        for ledger in EXACT_LEDGERS:
            entry = receipt["ledgers"][ledger]
            self.assertEqual(entry["status"], "VERIFIED", ledger)
            self.assertEqual(Path(entry["local_path"]).read_bytes(), PLAIN[LEDGER_FILES[ledger]])
            self.assertEqual(entry["plain_sha256_observed"], entry["plain_sha256_expected"])
        self.assertEqual(receipt["objects"]["calculation_result.json"]["status"], "VERIFIED")
        self.assertEqual(json.loads(receipt_path.read_text())["receipt_sha256"], receipt["receipt_sha256"])
        self.assertNotIn("X-Amz-Signature", receipt_path.read_text())

    def test_a_short_gzip_is_a_length_mismatch_and_a_refusal(self):
        objects = dict(OBJECTS)
        objects["exact_member_rows.jsonl.gz"] = OBJECTS["exact_member_rows.jsonl.gz"][:-3]
        receipt, error, _, _ = self._fetch(downloader=stub_downloader(objects))
        self.assertIsNotNone(error)
        self.assertEqual(receipt["ledgers"]["exact_member_ledger"]["status"], "LENGTH_MISMATCH")
        self.assertFalse(receipt["all_ledgers_verified"])
        self.assertIn("exact_member_ledger", str(error))

    def test_a_wrong_plain_sha_is_a_sha_mismatch_and_a_refusal(self):
        m = manifest()
        m["plain_sha256"]["exact_lifecycle_rows.jsonl"] = "0" * 64
        receipt, error, _, _ = self._fetch(m=m)
        self.assertIsNotNone(error)
        self.assertEqual(receipt["ledgers"]["exact_lifecycle_and_runway_ledger"]["status"], "SHA_MISMATCH")
        self.assertEqual(receipt["ledgers"]["exact_member_ledger"]["status"], "VERIFIED")

    def test_a_wrong_plain_length_is_a_length_mismatch_even_when_the_gzip_arrived_whole(self):
        m = manifest()
        m["plain_sizes"]["legacy_observable_rows.jsonl"] += 1
        receipt, error, _, _ = self._fetch(m=m)
        self.assertIsNotNone(error)
        self.assertEqual(receipt["ledgers"]["legacy_observable_rows"]["status"], "LENGTH_MISMATCH")

    def test_an_unreachable_object_is_missing_and_a_refusal(self):
        receipt, error, _, _ = self._fetch(downloader=stub_downloader(fail={"exact_member_rows.jsonl.gz"}))
        self.assertIsNotNone(error)
        self.assertEqual(receipt["ledgers"]["exact_member_ledger"]["status"], "MISSING")
        self.assertEqual(receipt["ledgers"]["legacy_observable_rows"]["status"], "VERIFIED")

    def test_an_uncompressed_ledger_object_is_verified_directly(self):
        """A canary uploads its ledgers plain; the plain witness is then S3's own length."""
        objects = {"exact_member_rows.jsonl": PLAIN["exact_member_rows.jsonl"], **{k: v for k, v in OBJECTS.items() if k != "exact_member_rows.jsonl.gz"}}
        rows = [{"Key": ledger_key(n) if n.endswith(".gz") else (f"{PREFIX}/ledgers/{n}" if n.endswith(".jsonl") else f"{PREFIX}/{n}"), "Size": len(b)} for n, b in objects.items()]
        urls = {n: f"https://s3.example/{n}?sig" for n in objects}
        m = build_manifest(
            run_id="1", run_prefix=PREFIX, bucket=BUCKET, listing=rows, presigned=urls,
            plain_sizes=parse_plain_sizes(plain_sizes_text()), plain_sha256=parse_plain_sha256sums(plain_sha_text()),
            expires_at="x", presign_seconds=1,
        )
        receipt, error, _, _ = self._fetch(m=m, downloader=stub_downloader(objects))
        self.assertIsNone(error)
        self.assertEqual(receipt["ledgers"]["exact_member_ledger"]["status"], "VERIFIED")
        self.assertEqual(receipt["ledgers"]["exact_member_ledger"]["object"], "exact_member_rows.jsonl")


class CommandLineTest(unittest.TestCase):
    def test_build_manifest_prints_keys_and_sizes_and_never_a_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "listing.json").write_text(json.dumps(listing_with_ledger_dir()))
            (root / "presigned.tsv").write_text("".join(f"{n}\t{u}\n" for n, u in presigned().items()))
            (root / "PLAIN_SIZES").write_text(plain_sizes_text())
            (root / "PLAIN_SHA256SUMS").write_text(plain_sha_text())
            out = io.StringIO()
            with redirect_stdout(out):
                code = main([
                    "build-manifest", "--run-id", "33630348943", "--run-prefix", PREFIX, "--bucket", BUCKET,
                    "--listing", str(root / "listing.json"), "--presigned", str(root / "presigned.tsv"),
                    "--plain-sizes", str(root / "PLAIN_SIZES"), "--plain-sha256sums", str(root / "PLAIN_SHA256SUMS"),
                    "--presign-seconds", "604800", "--output", str(root / "delivery_manifest.json"),
                ])
            self.assertEqual(code, 0)
            text = out.getvalue()
            self.assertNotIn("X-Amz-Signature", text)
            self.assertNotIn("https://", text)
            self.assertIn("exact_member_rows.jsonl.gz", text)
            written = json.loads((root / "delivery_manifest.json").read_text())
            self.assertEqual(written["schema"], MANIFEST_SCHEMA)
            self.assertRegex(written["expires_at"], r"^\d{4}-\d{2}-\d{2}T")

    def test_fetch_exits_nonzero_on_any_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            m = manifest()
            m["plain_sha256"]["exact_member_rows.jsonl"] = "0" * 64
            (root / "m.json").write_text(json.dumps(m))
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["fetch", "--manifest", str(root / "m.json"), "--out-dir", str(root / "d"),
                             "--receipt", str(root / "r.json")], downloader=stub_downloader())
            self.assertEqual(code, 1)
            self.assertEqual(json.loads((root / "r.json").read_text())["ledgers"]["exact_member_ledger"]["status"], "SHA_MISMATCH")


if __name__ == "__main__":
    unittest.main()
