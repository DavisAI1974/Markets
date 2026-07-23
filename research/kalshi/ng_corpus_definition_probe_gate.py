#!/usr/bin/env python3
"""Bind quarantined NG identity probes to an observed-definition catalog.

The lower-level identity probe accepts a collection of individually fingerprinted
instrument definitions.  This gate is the production path: it requires the complete
``ng_definition_observation_catalog.v1`` artifact, verifies the original definition
source bytes, runs the quarantine probe, and binds the resulting review proposal to
that exact catalog.  A loose definition list, stale catalog, altered source file, or
refingerprinted nested artifact fails closed.

The output remains REVIEW_REQUIRED.  It cannot infer identity from object names,
approve a session-day assignment, read outcomes, mutate either blind forecast or the
posterior, update ``knowledge/ng_brain.json``, authorize execution, or start options.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

import ng_corpus_coverage_audit as coverage
import ng_corpus_identity_probe as identity_probe
import ng_corpus_materialization as materialization
import ng_definition_observation as definition_observation
from ng_corpus_quarantine_storage import (
    CorpusQuarantineError,
    _authority,
    _fp,
    _validate_authority,
    _verify,
    quarantine_download,
    validate_quarantine,
)
from ng_definition_observation_support import DefinitionObservationError

SCHEMA = "ng_corpus_definition_probe_gate.v1"
STATUS = "PROVENANCE_LOCKED_REVIEW_REQUIRED"


def _validated_catalog(value: Mapping[str, Any], *, verify_files: bool) -> dict[str, Any]:
    if not isinstance(value, Mapping) or value.get("schema") != definition_observation.CATALOG_SCHEMA:
        raise CorpusQuarantineError(
            "identity probing requires the fingerprinted observed-definition catalog; "
            "a raw definition list is not permitted"
        )
    try:
        return definition_observation.validate_catalog(value, verify_files=verify_files)
    except DefinitionObservationError as error:
        raise CorpusQuarantineError(f"definition catalog validation failed: {error}") from error


def _definition_map(catalog: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row["definition_fingerprint"]): copy.deepcopy(dict(row))
        for row in catalog["definitions"]
    }


def probe_with_catalog(
    *,
    snapshot: Mapping[str, Any],
    quarantine: Mapping[str, Any],
    definition_catalog: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Run a REVIEW_REQUIRED identity probe tied to verified definition-source bytes."""
    snap = materialization.validate_snapshot(snapshot)
    quarantined = validate_quarantine(quarantine, snapshot=snap, verify_files=True)
    catalog = _validated_catalog(definition_catalog, verify_files=True)

    probed, bindings = identity_probe.probe_quarantine(
        snapshot=snap,
        quarantine=quarantined,
        definitions=catalog,
    )
    identity_probe.validate_probe(
        probed,
        snapshot=snap,
        quarantine=quarantined,
        proposed_bindings=bindings,
    )

    status_counts = {
        status: sum(1 for row in probed["objects"] if row["status"] == status)
        for status in sorted(identity_probe.PROBE_STATUSES)
    }
    artifact = {
        "schema": SCHEMA,
        "status": STATUS,
        "snapshot_fingerprint": snap["snapshot_fingerprint"],
        "quarantine_fingerprint": quarantined["quarantine_fingerprint"],
        "definition_catalog_schema": catalog["schema"],
        "definition_catalog_fingerprint": catalog["catalog_fingerprint"],
        "definition_catalog_observed_at": catalog["observed_at"],
        "definition_source_fingerprints": list(catalog["source_fingerprints"]),
        "definition_fingerprints": list(catalog["definition_fingerprints"]),
        "definition_source_files_verified": True,
        "raw_definition_list_permitted": False,
        "probe_fingerprint": probed["probe_fingerprint"],
        "proposed_binding_manifest_fingerprint": bindings["binding_manifest_fingerprint"],
        "probed_object_count": probed["probed_object_count"],
        "probe_status_counts": status_counts,
        "automatic_approval_permitted": False,
        "session_day_assignment_status": "REVIEW_REQUIRED",
        "identity_inferred_from_object_name": False,
        "session_day_inferred_from_object_name": False,
        **_authority(),
    }
    artifact["gate_fingerprint"] = _fp(artifact)
    validate_gate(
        artifact,
        snapshot=snap,
        quarantine=quarantined,
        definition_catalog=catalog,
        probe=probed,
        proposed_bindings=bindings,
        verify_definition_files=True,
    )
    return artifact, probed, bindings


def validate_gate(
    value: Mapping[str, Any],
    *,
    snapshot: Mapping[str, Any],
    quarantine: Mapping[str, Any],
    definition_catalog: Mapping[str, Any],
    probe: Mapping[str, Any],
    proposed_bindings: Mapping[str, Any],
    verify_definition_files: bool = True,
) -> dict[str, Any]:
    checked = _verify(value, "gate_fingerprint", label="definition probe gate")
    if checked.get("schema") != SCHEMA or checked.get("status") != STATUS:
        raise CorpusQuarantineError("definition probe gate schema/status mismatch")
    _validate_authority(checked, label="definition probe gate")
    if checked.get("raw_definition_list_permitted") is not False:
        raise CorpusQuarantineError("definition probe gate may not accept raw definition lists")
    if checked.get("definition_source_files_verified") is not True:
        raise CorpusQuarantineError("definition probe gate must verify definition source files")
    if checked.get("automatic_approval_permitted") is not False:
        raise CorpusQuarantineError("definition probe gate may not approve objects")
    if checked.get("session_day_assignment_status") != "REVIEW_REQUIRED":
        raise CorpusQuarantineError("definition probe gate may not approve a session day")
    if checked.get("identity_inferred_from_object_name") is not False:
        raise CorpusQuarantineError("definition probe gate inferred identity from an object name")
    if checked.get("session_day_inferred_from_object_name") is not False:
        raise CorpusQuarantineError("definition probe gate inferred a session day from an object name")

    snap = materialization.validate_snapshot(snapshot)
    quarantined = validate_quarantine(quarantine, snapshot=snap, verify_files=True)
    catalog = _validated_catalog(definition_catalog, verify_files=verify_definition_files)
    probed = identity_probe.validate_probe(
        probe,
        snapshot=snap,
        quarantine=quarantined,
        proposed_bindings=proposed_bindings,
    )
    bindings = materialization.validate_bindings(
        proposed_bindings,
        snapshot=snap,
        require_approved=False,
    )

    expected_links = {
        "snapshot_fingerprint": snap["snapshot_fingerprint"],
        "quarantine_fingerprint": quarantined["quarantine_fingerprint"],
        "definition_catalog_schema": catalog["schema"],
        "definition_catalog_fingerprint": catalog["catalog_fingerprint"],
        "definition_catalog_observed_at": catalog["observed_at"],
        "definition_source_fingerprints": list(catalog["source_fingerprints"]),
        "definition_fingerprints": list(catalog["definition_fingerprints"]),
        "probe_fingerprint": probed["probe_fingerprint"],
        "proposed_binding_manifest_fingerprint": bindings["binding_manifest_fingerprint"],
        "probed_object_count": probed["probed_object_count"],
    }
    for field, expected in expected_links.items():
        if checked.get(field) != expected:
            raise CorpusQuarantineError(f"definition probe gate {field} mismatch")

    expected_counts = {
        status: sum(1 for row in probed["objects"] if row["status"] == status)
        for status in sorted(identity_probe.PROBE_STATUSES)
    }
    if checked.get("probe_status_counts") != expected_counts:
        raise CorpusQuarantineError("definition probe gate status counts mismatch")

    definitions_by_fp = _definition_map(catalog)
    probe_by_id = {str(row["object_id"]): row for row in probed["objects"]}
    binding_by_id = {str(row["object_id"]): row for row in bindings["bindings"]}
    if not set(probe_by_id).issubset(binding_by_id):
        raise CorpusQuarantineError("definition probe gate is missing proposed bindings")

    for object_id, evidence in probe_by_id.items():
        binding = binding_by_id[object_id]
        if binding.get("review_status") != "REVIEW_REQUIRED":
            raise CorpusQuarantineError("definition probe gate proposal must remain REVIEW_REQUIRED")
        if binding.get("probe_status") != evidence.get("status"):
            raise CorpusQuarantineError("definition probe gate probe status mismatch")
        if binding.get("probe_evidence_fingerprint") != evidence.get("evidence_fingerprint"):
            raise CorpusQuarantineError("definition probe gate evidence provenance mismatch")

        unique = evidence.get("unique_definition")
        proposed = binding.get("definition")
        if evidence.get("status") == "UNIQUE_DEFINITION_MATCH":
            if not isinstance(unique, Mapping) or not isinstance(proposed, Mapping):
                raise CorpusQuarantineError("unique definition match is missing its reviewed proposal")
            fingerprint = str(unique.get("definition_fingerprint") or "")
            if fingerprint not in definitions_by_fp:
                raise CorpusQuarantineError("identity probe selected a definition outside the catalog")
            if proposed != definitions_by_fp[fingerprint] or unique != definitions_by_fp[fingerprint]:
                raise CorpusQuarantineError("proposed definition differs from catalog evidence")
        elif proposed is not None or unique is not None:
            raise CorpusQuarantineError("non-unique identity evidence may not propose a definition")

    return copy.deepcopy(dict(value))


def _load(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def _selftest() -> None:
    class _Lister:
        def __init__(self, key: str, size: int) -> None:
            self.key = key
            self.size = size

        def list_objects_v2(self, **_: Any) -> dict[str, Any]:
            return {
                "Contents": [{"Key": self.key, "Size": self.size, "ETag": "selftest"}],
                "IsTruncated": False,
            }

    class _Downloader:
        def __init__(self, bucket: str, key: str, payload: bytes) -> None:
            self.bucket = bucket
            self.key = key
            self.payload = payload

        def download_file(self, bucket: str, key: str, target: str) -> None:
            assert (bucket, key) == (self.bucket, self.key)
            Path(target).write_bytes(self.payload)

    trade_rows = [
        {
            "event_type": "trade",
            "source_schema": "trades",
            "dataset": coverage.DATASET,
            "publisher_id": 1,
            "instrument_id": 1008,
            "raw_symbol": "NGJ26",
            "ts_event_s": 1773579600.0,
            "sequence": 1,
        },
        {
            "event_type": "trade",
            "source_schema": "trades",
            "dataset": coverage.DATASET,
            "publisher_id": 1,
            "instrument_id": 1008,
            "raw_symbol": "NGJ26",
            "ts_event_s": 1773579700.0,
            "sequence": 2,
        },
    ]
    payload = ("\n".join(json.dumps(row) for row in trade_rows) + "\n").encode("utf-8")
    bucket, key = "selftest", "opaque/object.jsonl"

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        definition_path = root / "definition.jsonl"
        definition_path.write_text(
            json.dumps(
                {
                    "event_type": "definition",
                    "dataset": coverage.DATASET,
                    "publisher_id": 1,
                    "instrument_id": 1008,
                    "raw_symbol": "NGJ26",
                    "ts_event_s": 1773500000.0,
                    "activation": 1773500000.0,
                    "expiration": 1773700000.0,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        catalog = definition_observation.build_catalog(
            [definition_path],
            observed_at="2026-07-22T00:00:00Z",
            raw_symbols=["NGJ26"],
        )
        snapshot = materialization.snapshot_s3(
            _Lister(key, len(payload)),
            bucket=bucket,
            prefixes=["opaque/"],
            observed_at="2026-07-22T00:00:00Z",
        )
        object_id = snapshot["objects"][0]["object_id"]
        quarantined = quarantine_download(
            _Downloader(bucket, key, payload),
            snapshot=snapshot,
            object_ids=[object_id],
            output_root=root / "quarantine",
            confirm_download=True,
            max_total_bytes=len(payload),
        )
        gate, probed, bindings = probe_with_catalog(
            snapshot=snapshot,
            quarantine=quarantined,
            definition_catalog=catalog,
        )
        assert gate["status"] == STATUS
        assert gate["definition_catalog_fingerprint"] == catalog["catalog_fingerprint"]
        assert probed["objects"][0]["status"] == "UNIQUE_DEFINITION_MATCH"
        assert bindings["bindings"][0]["review_status"] == "REVIEW_REQUIRED"


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--quarantine", type=Path)
    parser.add_argument("--definition-catalog", type=Path)
    parser.add_argument("--gate-out", type=Path)
    parser.add_argument("--probe-out", type=Path)
    parser.add_argument("--bindings-out", type=Path)
    args = parser.parse_args()
    if args.selftest:
        _selftest()
        print("ng_corpus_definition_probe_gate selftest: PASS")
        return 0
    required = {
        "--snapshot": args.snapshot,
        "--quarantine": args.quarantine,
        "--definition-catalog": args.definition_catalog,
        "--gate-out": args.gate_out,
        "--probe-out": args.probe_out,
        "--bindings-out": args.bindings_out,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        parser.error("required arguments: " + ", ".join(missing))
    gate, probed, bindings = probe_with_catalog(
        snapshot=_load(args.snapshot),
        quarantine=_load(args.quarantine),
        definition_catalog=_load(args.definition_catalog),
    )
    _write(args.gate_out, gate)
    _write(args.probe_out, probed)
    _write(args.bindings_out, bindings)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
