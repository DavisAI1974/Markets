#!/usr/bin/env python3
"""Identity-neutral quarantine storage and reviewed-byte promotion for NG corpus objects."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any, Mapping, Sequence

import ng_corpus_materialization as materialization

QUARANTINE_SCHEMA = "ng_corpus_quarantine_receipt.v1"


class CorpusQuarantineError(ValueError):
    """Raised when quarantine, identity probing, or promotion is unsafe."""


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise CorpusQuarantineError(f"{label} must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CorpusQuarantineError(f"{label} must be a positive integer") from error
    if number <= 0:
        raise CorpusQuarantineError(f"{label} must be a positive integer")
    return number


def _verify(value: Mapping[str, Any], field: str, *, label: str) -> dict[str, Any]:
    payload = copy.deepcopy(dict(value))
    observed = payload.pop(field, None)
    if not isinstance(observed, str) or observed != _fp(payload):
        raise CorpusQuarantineError(f"{label}: {field} mismatch")
    return copy.deepcopy(dict(value))


def _authority() -> dict[str, Any]:
    return {
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "remote_presence_inferred": False,
        "identity_inferred_from_object_name": False,
        "may_update_ng_brain": False,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
    }


def _validate_authority(value: Mapping[str, Any], *, label: str) -> None:
    for field in (
        "actual_outcomes_used",
        "paid_live_data_assumed",
        "remote_presence_inferred",
        "identity_inferred_from_object_name",
        "may_update_ng_brain",
        "may_change_blind_forecast",
        "may_change_posterior",
        "execution_authority",
        "options_lane_started",
    ):
        if value.get(field) is not False:
            raise CorpusQuarantineError(f"{label}: {field} must remain false")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise CorpusQuarantineError(f"{label}: CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise CorpusQuarantineError(f"{label}: brokerage must remain tastytrade_not_ibkr")


def _suffix(key: str) -> str:
    path = Path(key)
    suffixes = path.suffixes
    if len(suffixes) >= 2 and suffixes[-2:] == [".dbn", ".zst"]:
        return ".dbn.zst"
    return path.suffix or ".bin"


def _download_one(s3: Any, *, bucket: str, key: str, target: Path) -> None:
    if hasattr(s3, "download_file"):
        s3.download_file(bucket, key, str(target))
        return
    response = s3.get_object(Bucket=bucket, Key=key)
    body = response["Body"]
    with target.open("wb") as handle:
        while True:
            chunk = body.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)


def quarantine_download(
    s3: Any,
    *,
    snapshot: Mapping[str, Any],
    object_ids: Sequence[str],
    output_root: Path,
    confirm_download: bool,
    max_total_bytes: int,
) -> dict[str, Any]:
    """Download explicitly selected UNOBSERVED objects into identity-neutral quarantine."""
    if confirm_download is not True:
        raise CorpusQuarantineError("quarantine download requires explicit confirmation")
    snap = materialization.validate_snapshot(snapshot)
    selected_ids = [str(value) for value in object_ids]
    if not selected_ids or len(selected_ids) != len(set(selected_ids)):
        raise CorpusQuarantineError("object_ids must be a nonempty unique list")
    objects = {row["object_id"]: row for row in snap["objects"]}
    unknown = [object_id for object_id in selected_ids if object_id not in objects]
    if unknown:
        raise CorpusQuarantineError(f"unknown object_ids: {', '.join(sorted(unknown))}")
    selected = [objects[object_id] for object_id in selected_ids]
    total = sum(int(row["size_bytes"]) for row in selected)
    limit = _positive_int(max_total_bytes, label="max_total_bytes")
    if total > limit:
        raise CorpusQuarantineError(
            f"selected quarantine size {total} exceeds max_total_bytes {limit}"
        )
    root = output_root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    receipts: list[dict[str, Any]] = []
    for row in selected:
        target = root / f"{row['object_id']}{_suffix(str(row['key']))}"
        if target.exists():
            raise CorpusQuarantineError(f"refusing to overwrite quarantine file {target}")
        temp = target.with_suffix(target.suffix + ".partial")
        temp.unlink(missing_ok=True)
        try:
            _download_one(s3, bucket=row["bucket"], key=row["key"], target=temp)
            size = temp.stat().st_size
            if size != int(row["size_bytes"]):
                raise CorpusQuarantineError(
                    f"downloaded size mismatch for {row['location']}: {size} != {row['size_bytes']}"
                )
            sha = _sha256(temp)
            os.replace(temp, target)
        except Exception:
            temp.unlink(missing_ok=True)
            raise
        receipt = {
            "object_id": row["object_id"],
            "location": row["location"],
            "quarantine_path": str(target),
            "size_bytes": size,
            "sha256": sha,
            "snapshot_object_fingerprint": row["object_fingerprint"],
            "contract_identity_status": "UNOBSERVED",
            "raw_input_untouched": True,
            "identity_inferred_from_object_name": False,
        }
        receipt["quarantine_object_fingerprint"] = _fp(receipt)
        receipts.append(receipt)
    receipts.sort(key=lambda row: row["object_id"])
    value = {
        "schema": QUARANTINE_SCHEMA,
        "status": "IDENTITY_UNOBSERVED_QUARANTINE",
        "snapshot_fingerprint": snap["snapshot_fingerprint"],
        "output_root": str(root),
        "selected_object_count": len(selected),
        "quarantined_object_count": len(receipts),
        "total_size_bytes": total,
        "objects": receipts,
        **_authority(),
    }
    value["quarantine_fingerprint"] = _fp(value)
    validate_quarantine(value, snapshot=snap, verify_files=True)
    return value


def validate_quarantine(
    value: Mapping[str, Any],
    *,
    snapshot: Mapping[str, Any],
    verify_files: bool,
) -> dict[str, Any]:
    checked = _verify(value, "quarantine_fingerprint", label="quarantine receipt")
    if checked.get("schema") != QUARANTINE_SCHEMA:
        raise CorpusQuarantineError("quarantine schema mismatch")
    if checked.get("status") != "IDENTITY_UNOBSERVED_QUARANTINE":
        raise CorpusQuarantineError("quarantine status mismatch")
    _validate_authority(checked, label="quarantine receipt")
    snap = materialization.validate_snapshot(snapshot)
    if checked.get("snapshot_fingerprint") != snap["snapshot_fingerprint"]:
        raise CorpusQuarantineError("quarantine snapshot mismatch")
    objects = {row["object_id"]: row for row in snap["objects"]}
    rows = list(checked.get("objects") or [])
    if checked.get("selected_object_count") != len(rows):
        raise CorpusQuarantineError("quarantine selected count mismatch")
    if checked.get("quarantined_object_count") != len(rows):
        raise CorpusQuarantineError("quarantine object count mismatch")
    seen: set[str] = set()
    total = 0
    for raw in rows:
        row = copy.deepcopy(dict(raw))
        observed = row.pop("quarantine_object_fingerprint", None)
        if observed != _fp(row):
            raise CorpusQuarantineError("quarantine object fingerprint mismatch")
        object_id = str(raw.get("object_id") or "")
        if object_id not in objects or object_id in seen:
            raise CorpusQuarantineError("unknown or duplicate quarantined object")
        seen.add(object_id)
        obj = objects[object_id]
        if raw.get("location") != obj["location"]:
            raise CorpusQuarantineError("quarantine location mismatch")
        if raw.get("snapshot_object_fingerprint") != obj["object_fingerprint"]:
            raise CorpusQuarantineError("quarantine snapshot-object mismatch")
        size = _positive_int(raw.get("size_bytes"), label="quarantine size")
        if size != int(obj["size_bytes"]):
            raise CorpusQuarantineError("quarantine size differs from snapshot")
        sha = str(raw.get("sha256") or "").lower()
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise CorpusQuarantineError("quarantine sha256 must be 64 hex characters")
        if raw.get("contract_identity_status") != "UNOBSERVED":
            raise CorpusQuarantineError("quarantine may not assert contract identity")
        if raw.get("raw_input_untouched") is not True:
            raise CorpusQuarantineError("quarantine raw input must remain untouched")
        if raw.get("identity_inferred_from_object_name") is not False:
            raise CorpusQuarantineError("quarantine may not infer identity from object name")
        if verify_files:
            path = Path(str(raw.get("quarantine_path") or "")).expanduser().resolve()
            if not path.is_file() or path.stat().st_size != size or _sha256(path) != sha:
                raise CorpusQuarantineError(f"quarantine file verification failed: {path}")
        total += size
    if checked.get("total_size_bytes") != total:
        raise CorpusQuarantineError("quarantine total size mismatch")
    return checked


def promote_quarantine(
    *,
    snapshot: Mapping[str, Any],
    bindings: Mapping[str, Any],
    quarantine: Mapping[str, Any],
    output_root: Path,
    confirm_promote: bool,
) -> dict[str, Any]:
    """Promote operator-approved quarantine bytes into the canonical receipt contract."""
    if confirm_promote is not True:
        raise CorpusQuarantineError("quarantine promotion requires explicit confirmation")
    snap = materialization.validate_snapshot(snapshot)
    bound = materialization.validate_bindings(bindings, snapshot=snap, require_approved=True)
    quarantined = validate_quarantine(quarantine, snapshot=snap, verify_files=True)
    approved = [row for row in bound["bindings"] if row["review_status"] == "APPROVED"]
    by_quarantine = {row["object_id"]: row for row in quarantined["objects"]}
    missing = [row["object_id"] for row in approved if row["object_id"] not in by_quarantine]
    if missing:
        raise CorpusQuarantineError(
            "approved objects missing from quarantine: " + ", ".join(sorted(missing))
        )
    root = output_root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    objects = {row["object_id"]: row for row in snap["objects"]}
    receipts: list[dict[str, Any]] = []
    total = 0
    for binding in approved:
        object_id = binding["object_id"]
        source_row = by_quarantine[object_id]
        source = Path(source_row["quarantine_path"]).expanduser().resolve()
        target = root / f"{object_id}{_suffix(str(objects[object_id]['key']))}"
        if target.exists():
            raise CorpusQuarantineError(f"refusing to overwrite promoted file {target}")
        temp = target.with_suffix(target.suffix + ".partial")
        temp.unlink(missing_ok=True)
        try:
            with source.open("rb") as src, temp.open("wb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
                dst.flush()
                os.fsync(dst.fileno())
            size = temp.stat().st_size
            sha = _sha256(temp)
            if size != int(source_row["size_bytes"]) or sha != source_row["sha256"]:
                raise CorpusQuarantineError(f"quarantine bytes changed before promotion: {source}")
            os.replace(temp, target)
        except Exception:
            temp.unlink(missing_ok=True)
            raise
        row = {
            "object_id": object_id,
            "location": objects[object_id]["location"],
            "materialized_path": str(target),
            "size_bytes": size,
            "sha256": sha,
            "snapshot_object_fingerprint": objects[object_id]["object_fingerprint"],
            "raw_input_untouched": True,
            "identity_inferred_from_object_name": False,
        }
        row["materialization_fingerprint"] = _fp(row)
        receipts.append(row)
        total += size
    receipts.sort(key=lambda row: row["object_id"])
    value = {
        "schema": materialization.MATERIALIZATION_SCHEMA,
        "snapshot_fingerprint": snap["snapshot_fingerprint"],
        "binding_manifest_fingerprint": bound["binding_manifest_fingerprint"],
        "output_root": str(root),
        "approved_object_count": len(approved),
        "materialized_object_count": len(receipts),
        "total_size_bytes": total,
        "objects": receipts,
        **_authority(),
    }
    value["receipt_fingerprint"] = _fp(value)
    materialization.validate_materialization(
        value, snapshot=snap, bindings=bound, verify_files=True
    )
    return value
