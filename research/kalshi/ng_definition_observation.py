#!/usr/bin/env python3
"""Extract exact NG definition observations for corpus identity matching.

Reads definition-schema DBN or decoded JSONL, never filenames or S3 keys. Repeated
identical definitions are deduplicated; distinct overlapping periods remain visible.
The artifact is outcome-blind, SHADOW-only, tastytrade-scoped, and cannot update
blind forecasts, posterior state, ng_brain.json, execution, or the options lane.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import ng_corpus_inspection as inspection
from ng_definition_observation_support import (
    EXACT_NG_RE, SOURCE_SCHEMA, DefinitionObservationError, authority,
    extract_candidate, fp, identity_key, iter_records, sha256, transport_metadata,
    validate_authority, validate_observed_at, verify,
)

CATALOG_SCHEMA = "ng_definition_observation_catalog.v1"
_fp = fp


def build_catalog(sources: Sequence[Path], *, observed_at: str, raw_symbols: Sequence[str] | None = None) -> dict[str, Any]:
    observed_at = validate_observed_at(observed_at)
    selected = {str(symbol).upper() for symbol in (raw_symbols or ())}
    invalid = sorted(symbol for symbol in selected if not EXACT_NG_RE.fullmatch(symbol))
    if invalid:
        raise DefinitionObservationError("raw-symbol filter contains non-exact contracts: " + ", ".join(invalid))
    paths = [Path(path).expanduser().resolve() for path in sources]
    if not paths:
        raise DefinitionObservationError("at least one definition source is required")
    if len(paths) != len(set(paths)):
        raise DefinitionObservationError("definition source paths must be unique")

    receipts, candidates = [], []
    for path in sorted(paths, key=str):
        if not path.is_file():
            raise DefinitionObservationError(f"definition source does not exist: {path}")
        before, size = sha256(path), path.stat().st_size
        if size <= 0:
            raise DefinitionObservationError(f"definition source is empty: {path}")
        transport = transport_metadata(path)
        input_count = exact_count = filtered_count = ignored_count = 0
        chosen = []
        for input_count, record in enumerate(iter_records(path), 1):
            candidate = extract_candidate(record, transport=transport, path=path, observed_at=observed_at, source_sha=before, source_size=size)
            if candidate is None:
                ignored_count += 1
                continue
            exact_count += 1
            if selected and candidate["definition"]["raw_symbol"] not in selected:
                filtered_count += 1
                continue
            chosen.append(candidate)
            candidates.append(candidate)
        after = sha256(path)
        if after != before or path.stat().st_size != size:
            raise DefinitionObservationError(f"definition source changed during inspection: {path}")
        if input_count == 0:
            raise DefinitionObservationError(f"definition source contained zero records: {path}")
        receipt = {
            "schema": SOURCE_SCHEMA,
            "path": str(path),
            "size_bytes": size,
            "sha256_before": before,
            "sha256_after": after,
            "transport_metadata": transport,
            "input_record_count": input_count,
            "exact_ng_record_count": exact_count,
            "selected_record_count": len(chosen),
            "filtered_exact_record_count": filtered_count,
            "ignored_non_exact_record_count": ignored_count,
            **authority(),
        }
        receipt["source_fingerprint"] = fp(receipt)
        receipts.append(receipt)
    if not candidates:
        target = ", ".join(sorted(selected)) if selected else "exact NG contracts"
        raise DefinitionObservationError(f"no observed definitions matched {target}")

    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for candidate in candidates:
        grouped.setdefault(identity_key(candidate["definition"]), []).append(candidate)
    definitions, evidence_groups = [], []
    for key in sorted(grouped, key=lambda row: tuple(str(part) for part in row)):
        rows = sorted(
            grouped[key],
            key=lambda row: (
                row["definition"]["definition_date"],
                row["definition"]["source_sha256"],
                row["definition"]["observed_from"],
                row["definition"]["definition_fingerprint"],
            ),
        )
        canonical = rows[0]["definition"]
        definitions.append(canonical)
        group = {
            "identity_period": {
                "dataset": key[0],
                "publisher_id": key[1],
                "instrument_id": key[2],
                "raw_symbol": key[3],
                "definition_start_s": key[4],
                "definition_end_s": key[5],
            },
            "canonical_definition_fingerprint": canonical["definition_fingerprint"],
            "duplicate_observation_count": len(rows),
            "observations": [
                {
                    "definition_fingerprint": row["definition"]["definition_fingerprint"],
                    "definition_date": row["definition"]["definition_date"],
                    "definition_event_s": row["definition_event_s"],
                    "observed_from": row["definition"]["observed_from"],
                    "source_sha256": row["definition"]["source_sha256"],
                    "source_schema": row["source_schema"],
                }
                for row in rows
            ],
        }
        group["evidence_group_fingerprint"] = fp(group)
        evidence_groups.append(group)
    definitions.sort(
        key=lambda row: (
            row["raw_symbol"],
            int(row["instrument_id"]),
            float(row["definition_start_s"]),
            float(row["definition_end_s"]),
            row["definition_fingerprint"],
        )
    )
    artifact = {
        "schema": CATALOG_SCHEMA,
        "status": "OBSERVED_DEFINITIONS_READY",
        "observed_at": observed_at,
        "raw_symbol_filter": sorted(selected),
        "source_count": len(receipts),
        "definition_count": len(definitions),
        "source_fingerprints": [row["source_fingerprint"] for row in receipts],
        "definition_fingerprints": [row["definition_fingerprint"] for row in definitions],
        "sources": receipts,
        "definitions": definitions,
        "evidence_groups": evidence_groups,
        "deduplication_rule": "exact dataset/publisher/instrument/raw-symbol/definition-period; deterministic first evidence",
        "overlapping_distinct_periods_preserved": True,
        "definitions_compatible_with_identity_probe": True,
        "automatic_identity_approval_permitted": False,
        **authority(),
    }
    artifact["catalog_fingerprint"] = fp(artifact)
    validate_catalog(artifact, verify_files=True)
    return artifact


def validate_catalog(item: Mapping[str, Any], *, verify_files: bool = False) -> dict[str, Any]:
    checked = verify(item, "catalog_fingerprint", "definition catalog")
    if checked.get("schema") != CATALOG_SCHEMA or checked.get("status") != "OBSERVED_DEFINITIONS_READY":
        raise DefinitionObservationError("definition catalog schema/status mismatch")
    validate_authority(checked, "definition catalog")
    validate_observed_at(str(checked.get("observed_at") or ""))
    if checked.get("overlapping_distinct_periods_preserved") is not True or checked.get("definitions_compatible_with_identity_probe") is not True:
        raise DefinitionObservationError("definition catalog compatibility flags are invalid")
    if checked.get("automatic_identity_approval_permitted") is not False:
        raise DefinitionObservationError("definition catalog may not auto-approve identity")
    selected = checked.get("raw_symbol_filter")
    sources = checked.get("sources")
    definitions = checked.get("definitions")
    groups = checked.get("evidence_groups")
    if not isinstance(selected, list) or selected != sorted(set(selected)) or any(not EXACT_NG_RE.fullmatch(str(symbol)) for symbol in selected):
        raise DefinitionObservationError("definition raw-symbol filter is malformed")
    if not all(isinstance(rows, list) for rows in (sources, definitions, groups)):
        raise DefinitionObservationError("definition catalog lists are malformed")
    if checked.get("source_count") != len(sources) or checked.get("definition_count") != len(definitions):
        raise DefinitionObservationError("definition catalog counts mismatch")

    source_fps, source_by_path = [], {}
    for row in sources:
        source = verify(row, "source_fingerprint", "definition source receipt")
        if source.get("schema") != SOURCE_SCHEMA:
            raise DefinitionObservationError("definition source schema mismatch")
        validate_authority(source, "definition source receipt")
        path_text = str(source.get("path") or "")
        if not path_text or path_text in source_by_path or source.get("sha256_before") != source.get("sha256_after"):
            raise DefinitionObservationError("definition source provenance is invalid")
        try:
            counts = [
                int(source[name])
                for name in (
                    "input_record_count",
                    "exact_ng_record_count",
                    "selected_record_count",
                    "filtered_exact_record_count",
                    "ignored_non_exact_record_count",
                )
            ]
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            raise DefinitionObservationError("definition source counts are malformed") from error
        total, exact, chosen, filtered, ignored = counts
        if total <= 0 or min(exact, chosen, filtered, ignored) < 0 or exact != chosen + filtered or total != exact + ignored:
            raise DefinitionObservationError("definition source counts do not reconcile")
        path = Path(path_text)
        if verify_files and (
            not path.is_file()
            or path.stat().st_size != int(source.get("size_bytes", -1))
            or sha256(path) != source.get("sha256_before")
        ):
            raise DefinitionObservationError(f"definition source verification failed: {path}")
        source_by_path[path_text] = source
        source_fps.append(row["source_fingerprint"])
    if checked.get("source_fingerprints") != source_fps:
        raise DefinitionObservationError("definition source fingerprint list mismatch")

    validated = [inspection.validate_definition(row) for row in definitions]
    if not validated:
        raise DefinitionObservationError("definition catalog must contain at least one definition")
    definition_fps = [row["definition_fingerprint"] for row in validated]
    if len(definition_fps) != len(set(definition_fps)) or checked.get("definition_fingerprints") != definition_fps:
        raise DefinitionObservationError("definition fingerprint list mismatch")
    if len({identity_key(row) for row in validated}) != len(validated):
        raise DefinitionObservationError("definition catalog contains duplicate identity periods")
    if selected and any(row["raw_symbol"] not in selected for row in validated):
        raise DefinitionObservationError("definition catalog contains a symbol outside its filter")

    by_fp, canonical_refs = {row["definition_fingerprint"]: row for row in validated}, []
    for row in groups:
        group = verify(row, "evidence_group_fingerprint", "definition evidence group")
        canonical = str(group.get("canonical_definition_fingerprint") or "")
        if canonical not in by_fp:
            raise DefinitionObservationError("definition evidence references an unknown canonical definition")
        definition = by_fp[canonical]
        expected = {
            "dataset": definition["dataset"],
            "publisher_id": int(definition["publisher_id"]),
            "instrument_id": int(definition["instrument_id"]),
            "raw_symbol": definition["raw_symbol"],
            "definition_start_s": float(definition["definition_start_s"]),
            "definition_end_s": float(definition["definition_end_s"]),
        }
        observations = group.get("observations")
        if group.get("identity_period") != expected:
            raise DefinitionObservationError("definition evidence identity-period mismatch")
        if not isinstance(observations, list) or not observations or group.get("duplicate_observation_count") != len(observations):
            raise DefinitionObservationError("definition evidence observations are malformed")
        observed_fps = []
        for observation in observations:
            source = source_by_path.get(str(observation.get("observed_from") or ""))
            if source is None or observation.get("source_sha256") != source.get("sha256_before"):
                raise DefinitionObservationError("definition evidence source provenance mismatch")
            observed_fps.append(str(observation.get("definition_fingerprint") or ""))
        if canonical not in observed_fps:
            raise DefinitionObservationError("canonical definition is absent from its evidence group")
        canonical_refs.append(canonical)
    if sorted(canonical_refs) != sorted(definition_fps):
        raise DefinitionObservationError("definition evidence groups do not cover canonical definitions")
    return copy.deepcopy(dict(item))


def _load(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write(path: Path, item: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(item, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def _selftest() -> None:
    rows = [
        {
            "event_type": "definition",
            "dataset": inspection.DATASET,
            "publisher_id": 1,
            "instrument_id": 1008,
            "raw_symbol": "NGJ26",
            "ts_event_s": 1773500000.0,
            "activation": 1773000000.0,
            "expiration": 1775000000.0,
        },
        {
            "event_type": "definition",
            "dataset": inspection.DATASET,
            "publisher_id": 1,
            "instrument_id": 996,
            "raw_symbol": "NGK26",
            "ts_event_s": 1773500001.0,
            "activation": 1773000000.0,
            "expiration": 1778000000.0,
        },
    ]
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "opaque.jsonl"
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
        catalog = build_catalog(
            [path],
            observed_at="2026-07-22T00:00:00Z",
            raw_symbols=["NGJ26", "NGK26"],
        )
        assert [row["raw_symbol"] for row in catalog["definitions"]] == ["NGJ26", "NGK26"]
        validate_catalog(catalog, verify_files=True)


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    sub = parser.add_subparsers(dest="command")
    build = sub.add_parser("build")
    build.add_argument("--source", action="append", type=Path, required=True)
    build.add_argument("--observed-at", required=True)
    build.add_argument("--raw-symbol", action="append")
    build.add_argument("--out", type=Path, required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--catalog", type=Path, required=True)
    validate.add_argument("--verify-files", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        _selftest()
        print("ng_definition_observation selftest: PASS")
        return 0
    if not args.command:
        parser.error("a command or --selftest is required")
    if args.command == "build":
        _write(args.out, build_catalog(args.source, observed_at=args.observed_at, raw_symbols=args.raw_symbol))
    else:
        validate_catalog(_load(args.catalog), verify_files=args.verify_files)
        print("ng_definition_observation catalog: VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
