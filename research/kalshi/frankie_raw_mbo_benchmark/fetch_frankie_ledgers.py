"""Bring the exact ledgers into a session and PROVE they are the box's ledgers. D81.

**The route, and why it has this shape.** AWS credentials exist only as GitHub secrets; an
interactive session resolves none. So a session cannot read S3, and a workflow cannot run the
principal. Delivery is therefore two-legged: the workflow
(`.github/workflows/frankie_ledger_delivery_20260902.yml`) presigns each object of a pinned
run and publishes a `FRANKIE_LEDGER_DELIVERY_MANIFEST_V1` as a run artifact; the session
downloads the manifest and runs `fetch` here, which pulls each presigned URL and verifies it.

**Every verification is against an independent witness.** The gzip's byte length is checked
against S3's own `ContentLength`, recorded at PUT time with no stake in the answer. The plain
bytes after gunzip are checked against the box's `wc -c` (`PLAIN_SIZES`) and `sha256sum`
(`PLAIN_SHA256SUMS`), written over the PLAIN files at the moment the traversal finished and
carried in `small_artifacts.tar.gz` (launch workflow, "THE RECEIPT IS WRITTEN BEFORE THE
COMPRESSION"). A sha256 of a gzip proves the gzip arrived and says nothing about the rows;
this checks the rows.

**Any mismatch is a refusal, never a warning.** Status per ledger is exactly one of
`VERIFIED | LENGTH_MISMATCH | SHA_MISMATCH | MISSING`, the receipt is written whatever the
outcome so the failure is evidence, and `fetch` then RAISES. The emitter refuses to spawn on
anything but VERIFIED for every exact ledger, so a partial delivery cannot be reasoned over
as a complete one.

**Presigned URLs are secrets for seven days.** They live in the manifest file and nowhere
else: the receipt does not repeat them, and the CLI summary prints keys and sizes only.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import gzip
import hashlib
import json
import shutil
import sys
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping

from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import canonical_hash
from research.kalshi.frankie_raw_mbo_benchmark.native_staging import EXACT_LEDGERS

MANIFEST_SCHEMA = "FRANKIE_LEDGER_DELIVERY_MANIFEST_V1"
RECEIPT_SCHEMA = "FRANKIE_LEDGER_DELIVERY_RECEIPT_V1"

LEDGER_FILES: dict[str, str] = {
    "exact_member_ledger": "exact_member_rows.jsonl",
    "exact_lifecycle_and_runway_ledger": "exact_lifecycle_rows.jsonl",
    "legacy_observable_rows": "legacy_observable_rows.jsonl",
}
"""Ledger name (native_staging.EXACT_LEDGERS) -> the file `LedgerSinks` writes it to."""
assert tuple(LEDGER_FILES) == EXACT_LEDGERS

OTHER_OBJECTS = ("calculation_result.json", "small_artifacts.tar.gz")
"""The runner's result and the box's receipts. Delivered for the gates, not as his evidence."""

VERIFIED = "VERIFIED"
LENGTH_MISMATCH = "LENGTH_MISMATCH"
SHA_MISMATCH = "SHA_MISMATCH"
MISSING = "MISSING"

CHUNK = 8 * 1024 * 1024

Downloader = Callable[[str, Path], None]


class DeliveryError(ValueError):
    """A manifest could not be built, or a delivered object failed its witness."""


# --- the box's receipts -------------------------------------------------------


def parse_plain_sizes(text: str) -> dict[str, int]:
    """`wc -c` output: `<bytes> <path>` per file plus a `<total> total` line that names no file."""
    sizes: dict[str, int] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 2 or parts[1] == "total" or not parts[0].isdigit():
            continue
        sizes[PurePosixPath(parts[1]).name] = int(parts[0])
    return sizes


def parse_plain_sha256sums(text: str) -> dict[str, str]:
    """`sha256sum` output: `<sha>  <path>` per file, keyed by basename."""
    shas: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 2 or len(parts[0]) != 64:
            continue
        shas[PurePosixPath(parts[1]).name] = parts[0].lower()
    return shas


# --- the manifest ---------------------------------------------------------------


def _expected_objects(listing_names: Mapping[str, Any]) -> dict[str, str | None]:
    """Object basename -> ledger name (None for the two non-ledger objects).

    A ledger is expected gzipped (a box run) and accepted plain (a canary), whichever the
    listing holds; both present is refused because two objects cannot both be the ledger.
    """
    expected: dict[str, str | None] = {}
    for ledger, plain in LEDGER_FILES.items():
        gz, have_gz, have_plain = plain + ".gz", plain + ".gz" in listing_names, plain in listing_names
        if have_gz and have_plain:
            raise DeliveryError(f"the run holds both {gz} and {plain}; two objects cannot both be the ledger")
        expected[gz if have_gz or not have_plain else plain] = ledger
    for name in OTHER_OBJECTS:
        expected[name] = None
    return expected


def build_manifest(
    *,
    run_id: str,
    run_prefix: str,
    bucket: str,
    listing: list[Mapping[str, Any]],
    presigned: Mapping[str, str],
    plain_sizes: Mapping[str, int],
    plain_sha256: Mapping[str, str],
    expires_at: str,
    presign_seconds: int,
) -> dict[str, Any]:
    """Assemble the manifest from S3's listing, the presigned URLs and the box's receipts.

    Refuses on any absence: an object missing from the listing, a URL not presigned, a ledger
    without a plain size or sha. A manifest with a hole would be discovered at fetch time as a
    MISSING that reads like a network fault.
    """
    by_name: dict[str, Mapping[str, Any]] = {}
    for row in listing:
        key = str(row["Key"])
        by_name[PurePosixPath(key).name] = {"key": key, "content_length": int(row["Size"])}
    expected = _expected_objects(by_name)
    objects: dict[str, dict[str, Any]] = {}
    for name in expected:
        if name not in by_name:
            raise DeliveryError(f"the run at {run_prefix} holds no object named {name}")
        if name not in presigned or not str(presigned[name]).startswith("https://"):
            raise DeliveryError(f"no presigned https URL for {name}")
        objects[name] = {**by_name[name], "url": str(presigned[name])}
    sizes: dict[str, int] = {}
    shas: dict[str, str] = {}
    for ledger, plain in LEDGER_FILES.items():
        if plain not in plain_sizes:
            raise DeliveryError(f"PLAIN_SIZES carries no length for {plain} ({ledger})")
        if plain not in plain_sha256:
            raise DeliveryError(f"PLAIN_SHA256SUMS carries no sha256 for {plain} ({ledger})")
        sizes[plain] = int(plain_sizes[plain])
        shas[plain] = str(plain_sha256[plain]).lower()
    # F-feed-1: the box's sha256sum also covers the non-ledger objects it witnessed (the
    # result file, and source_manifest.json on a box run). Every such digest is carried so the
    # fetch verifies the object's bytes, not only S3's length; an object the box did not
    # witness is verified by length alone and the receipt says so.
    object_sha256: dict[str, str] = {
        name: str(plain_sha256[name]).lower() for name in OTHER_OBJECTS if name in plain_sha256
    }
    manifest: dict[str, Any] = {
        "schema": MANIFEST_SCHEMA,
        "run_id": str(run_id),
        "run_prefix": run_prefix,
        "bucket": bucket,
        "expires_at": expires_at,
        "presign_seconds": int(presign_seconds),
        "objects": objects,
        "plain_sizes": sizes,
        "plain_sha256": shas,
        "object_sha256": object_sha256,
        "ledger_files": dict(LEDGER_FILES),
        "manifest_sha256": "",
    }
    manifest["manifest_sha256"] = canonical_hash(manifest, omit="manifest_sha256")
    return manifest


def load_manifest(path: Path | str) -> dict[str, Any]:
    body = json.loads(Path(path).read_text(encoding="utf-8"))
    if body.get("schema") != MANIFEST_SCHEMA:
        raise DeliveryError(f"{path} is not a {MANIFEST_SCHEMA}")
    for key in ("run_id", "run_prefix", "bucket", "expires_at", "objects", "plain_sizes", "plain_sha256"):
        if key not in body:
            raise DeliveryError(f"manifest lacks {key}")
    return body


def redacted_summary(manifest: Mapping[str, Any]) -> str:
    """Keys and sizes for the log. Never the URLs, which are credentials for seven days."""
    lines = [f"run {manifest['run_id']} at s3://{manifest['bucket']}/{manifest['run_prefix']}",
             f"presigned until {manifest['expires_at']}"]
    for name, obj in sorted(manifest["objects"].items()):
        lines.append(f"  {name:36s} {obj['content_length']:>15,d} bytes  key={obj['key']}")
    for plain, size in sorted(manifest["plain_sizes"].items()):
        lines.append(f"  plain {plain:30s} {size:>15,d} bytes  sha256={manifest['plain_sha256'][plain]}")
    return "\n".join(lines)


# --- the fetch --------------------------------------------------------------------


def _urllib_download(url: str, dest: Path) -> None:
    with urllib.request.urlopen(url) as response, dest.open("wb") as handle:  # noqa: S310 - presigned https
        shutil.copyfileobj(response, handle, CHUNK)


def _gunzip_verified(src: Path, dest: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    total = 0
    with gzip.open(src, "rb") as reader, dest.open("wb") as writer:
        while True:
            chunk = reader.read(CHUNK)
            if not chunk:
                break
            writer.write(chunk)
            digest.update(chunk)
            total += len(chunk)
    return total, digest.hexdigest()


def _hash_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(CHUNK)
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
    return total, digest.hexdigest()


def fetch(
    manifest: Mapping[str, Any],
    out_dir: Path | str,
    *,
    downloader: Downloader | None = None,
    receipt_path: Path | str | None = None,
) -> dict[str, Any]:
    """Download every object, verify, gunzip the ledgers, write the receipt, refuse on any miss."""
    download = downloader or _urllib_download
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    receipt_file = Path(receipt_path) if receipt_path else out / "FRANKIE_LEDGER_DELIVERY_RECEIPT.json"
    objects: dict[str, dict[str, Any]] = {}
    ledgers: dict[str, dict[str, Any]] = {}
    object_for_ledger = {v: k for k, v in _expected_objects(manifest["objects"]).items() if v is not None}

    for name, obj in manifest["objects"].items():
        dest = out / name
        entry: dict[str, Any] = {
            "key": obj["key"], "content_length_expected": int(obj["content_length"]),
            "bytes_observed": None, "local_path": str(dest), "status": MISSING, "error": None,
        }
        try:
            download(obj["url"], dest)
        except Exception as exc:  # noqa: BLE001 - the reason travels in the receipt
            entry["error"] = f"{type(exc).__name__}: {exc}"
            objects[name] = entry
            continue
        observed = dest.stat().st_size
        entry["bytes_observed"] = observed
        entry["status"] = VERIFIED if observed == entry["content_length_expected"] else LENGTH_MISMATCH
        # The digest the box witnessed for a non-ledger object (F-feed-1), when it carried one.
        # Older manifests carry no object_sha256 block; they verify by length alone, as before.
        expected_sha = (manifest.get("object_sha256") or {}).get(name)
        entry["sha256_expected"] = str(expected_sha).lower() if expected_sha else None
        entry["sha256_observed"] = None
        if entry["status"] == VERIFIED and entry["sha256_expected"] is not None:
            _, entry["sha256_observed"] = _hash_file(dest)
            if entry["sha256_observed"] != entry["sha256_expected"]:
                entry["status"] = SHA_MISMATCH
        objects[name] = entry

    for ledger, plain in LEDGER_FILES.items():
        name = object_for_ledger.get(ledger)
        obj = objects.get(name) if name else None
        entry: dict[str, Any] = {
            "file": plain, "object": name, "status": MISSING, "local_path": None,
            "gz_bytes_expected": None, "gz_bytes_observed": None,
            "plain_bytes_expected": int(manifest["plain_sizes"][plain]),
            "plain_bytes_observed": None,
            "plain_sha256_expected": str(manifest["plain_sha256"][plain]).lower(),
            "plain_sha256_observed": None,
        }
        if obj is None or obj["status"] == MISSING:
            ledgers[ledger] = entry
            continue
        src = Path(obj["local_path"])
        if name.endswith(".gz"):
            entry["gz_bytes_expected"] = obj["content_length_expected"]
            entry["gz_bytes_observed"] = obj["bytes_observed"]
            if obj["status"] != VERIFIED:
                entry["status"] = LENGTH_MISMATCH
                ledgers[ledger] = entry
                continue
            dest = out / plain
            try:
                observed_bytes, observed_sha = _gunzip_verified(src, dest)
            except (OSError, EOFError, gzip.BadGzipFile) as exc:
                entry["status"] = LENGTH_MISMATCH
                entry["error"] = f"{type(exc).__name__}: {exc}"
                ledgers[ledger] = entry
                continue
        else:
            dest = src
            if obj["status"] != VERIFIED:
                entry["status"] = LENGTH_MISMATCH
                ledgers[ledger] = entry
                continue
            observed_bytes, observed_sha = _hash_file(dest)
        entry["local_path"] = str(dest)
        entry["plain_bytes_observed"] = observed_bytes
        entry["plain_sha256_observed"] = observed_sha
        if observed_bytes != entry["plain_bytes_expected"]:
            entry["status"] = LENGTH_MISMATCH
        elif observed_sha != entry["plain_sha256_expected"]:
            entry["status"] = SHA_MISMATCH
        else:
            entry["status"] = VERIFIED
        ledgers[ledger] = entry

    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "run_id": str(manifest["run_id"]),
        "run_prefix": manifest["run_prefix"],
        "bucket": manifest["bucket"],
        "manifest_sha256": manifest.get("manifest_sha256"),
        "fetched_at": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "out_dir": str(out),
        "ledgers": ledgers,
        "objects": objects,
        "all_ledgers_verified": all(ledgers[l]["status"] == VERIFIED for l in EXACT_LEDGERS),
        "receipt_sha256": "",
    }
    receipt["receipt_sha256"] = canonical_hash(receipt, omit="receipt_sha256")
    receipt_file.parent.mkdir(parents=True, exist_ok=True)
    receipt_file.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures = {l: ledgers[l]["status"] for l in EXACT_LEDGERS if ledgers[l]["status"] != VERIFIED}
    failures.update({n: o["status"] for n, o in objects.items() if o["status"] != VERIFIED})
    if failures:
        raise DeliveryError(f"delivery refused; receipt at {receipt_file}: {failures}")
    return receipt


# --- CLI ------------------------------------------------------------------------


def _expires_at(seconds: int) -> str:
    when = _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(seconds=seconds)
    return when.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main(argv: list[str] | None = None, *, downloader: Downloader | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build-manifest", help="workflow side: assemble the manifest from S3's listing and the box's receipts")
    build.add_argument("--run-id", required=True)
    build.add_argument("--run-prefix", required=True)
    build.add_argument("--bucket", required=True)
    build.add_argument("--listing", required=True, help="JSON list of {Key, Size} from list-objects-v2")
    build.add_argument("--presigned", required=True, help="TSV of <basename>\\t<url>")
    build.add_argument("--plain-sizes", required=True, help="the box's PLAIN_SIZES")
    build.add_argument("--plain-sha256sums", required=True, help="the box's PLAIN_SHA256SUMS")
    build.add_argument("--presign-seconds", type=int, required=True)
    build.add_argument("--output", required=True)
    get = sub.add_parser("fetch", help="session side: download, verify, gunzip, receipt")
    get.add_argument("--manifest", required=True)
    get.add_argument("--out-dir", required=True)
    get.add_argument("--receipt", default=None)
    args = parser.parse_args(argv)
    try:
        if args.command == "build-manifest":
            listing = json.loads(Path(args.listing).read_text(encoding="utf-8")) or []
            presigned: dict[str, str] = {}
            for line in Path(args.presigned).read_text(encoding="utf-8").splitlines():
                if "\t" in line:
                    name, url = line.split("\t", 1)
                    presigned[name.strip()] = url.strip()
            manifest = build_manifest(
                run_id=args.run_id, run_prefix=args.run_prefix, bucket=args.bucket, listing=listing,
                presigned=presigned,
                plain_sizes=parse_plain_sizes(Path(args.plain_sizes).read_text(encoding="utf-8")),
                plain_sha256=parse_plain_sha256sums(Path(args.plain_sha256sums).read_text(encoding="utf-8")),
                expires_at=_expires_at(args.presign_seconds), presign_seconds=args.presign_seconds,
            )
            Path(args.output).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(redacted_summary(manifest))
            return 0
        manifest = load_manifest(args.manifest)
        receipt = fetch(manifest, args.out_dir, downloader=downloader, receipt_path=args.receipt)
    except DeliveryError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    for ledger, entry in receipt["ledgers"].items():
        print(f"{entry['status']:16s} {ledger:36s} {entry['plain_bytes_observed']:>15,d} bytes  {entry['local_path']}")
    print(f"receipt sha256 {receipt['receipt_sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
