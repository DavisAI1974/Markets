#!/usr/bin/env python3
"""Fail-closed receipt artifact verification for the two-day transfer recovery."""

from __future__ import annotations

import gzip
import hashlib
from pathlib import Path, PurePosixPath
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_path(root: Path, value: Any) -> tuple[str, Path]:
    relative = PurePosixPath(str(value))
    if relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 1:
        raise ValueError("RECEIPT_ARTIFACT_PATH_ESCAPE")
    name = relative.as_posix()
    path = root / name
    if not path.is_file():
        raise ValueError("RECEIPT_ARTIFACT_MISSING=" + name)
    return name, path


def verify_receipt_artifacts(
    root: Path,
    receipt: dict[str, Any],
    *,
    max_uncompressed_bytes: int = 4 * 1024**3,
) -> dict[str, str]:
    """Verify both JSON and deterministic-gzip artifact descriptor schemas."""

    verified: dict[str, str] = {}
    uncompressed_bytes = 0

    def record(name: str, digest: str) -> None:
        prior = verified.get(name)
        if prior is not None and prior != digest:
            raise ValueError("RECEIPT_ARTIFACT_DUPLICATE_DRIFT=" + name)
        verified[name] = digest

    def visit(value: Any) -> None:
        nonlocal uncompressed_bytes
        if isinstance(value, dict):
            if "relative_path" in value:
                name, path = _artifact_path(root, value["relative_path"])
                json_keys = {"relative_path", "bytes", "sha256"}
                gzip_keys = {
                    "relative_path",
                    "rows",
                    "uncompressed_jsonl_sha256",
                    "gzip_sha256",
                }
                if json_keys.issubset(value):
                    digest = sha256_file(path)
                    if path.stat().st_size != int(value["bytes"]):
                        raise ValueError("RECEIPT_ARTIFACT_BYTE_DRIFT=" + name)
                    if digest != str(value["sha256"]):
                        raise ValueError("RECEIPT_ARTIFACT_HASH_DRIFT=" + name)
                    record(name, digest)
                elif gzip_keys.issubset(value):
                    gzip_digest = sha256_file(path)
                    if gzip_digest != str(value["gzip_sha256"]):
                        raise ValueError("RECEIPT_ARTIFACT_GZIP_HASH_DRIFT=" + name)
                    raw_digest = hashlib.sha256()
                    rows = 0
                    with gzip.open(path, "rb") as handle:
                        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                            uncompressed_bytes += len(chunk)
                            if uncompressed_bytes > max_uncompressed_bytes:
                                raise ValueError("RECEIPT_ARTIFACT_JSONL_SIZE_CAP_EXCEEDED")
                            raw_digest.update(chunk)
                            rows += chunk.count(b"\n")
                    if raw_digest.hexdigest() != str(value["uncompressed_jsonl_sha256"]):
                        raise ValueError("RECEIPT_ARTIFACT_JSONL_HASH_DRIFT=" + name)
                    if rows != int(value["rows"]):
                        raise ValueError("RECEIPT_ARTIFACT_ROW_COUNT_DRIFT=" + name)
                    record(name, gzip_digest)
                else:
                    raise ValueError("RECEIPT_ARTIFACT_DESCRIPTOR_SCHEMA_DRIFT=" + name)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(receipt)
    return verified
