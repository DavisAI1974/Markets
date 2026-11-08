"""Account for pinned ROOT inputs without treating historical extraction as verification."""

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re


BRIDGE = Path(__file__).resolve().parent
FAMILIES = BRIDGE.parents[3] / "artifacts/sqlite-triage/20261022/families"
SESSIONS = ("20231002", "20231003", "20231017", "20231018")
PINS = {
    BRIDGE / "tasks/root-ledger-headings.md":
        "fd4a106872946e83385a8e60c7500d150c45930ddf28385c4f7be359307d741e",
    FAMILIES / "joint-inputs-v4/root_full_feature_registry.csv":
        "b596ce2597299f7fe86b2750e27e856a6ad39017d6372aafc6af050b4c7163eb",
    FAMILIES / "descriptive-v1/plane_registry.csv":
        "e8ab4bed007970dccb6ae7c242a8b590c2d7cda6a625b1c4988d98593a28bf3c",
    FAMILIES / "full-context-audit/canonical-99-registry.json":
        "7ee754f1f9b080cdc5b7b68cf75829897d6216a1fadbb4b8a5ecd7b4f2133e06",
    FAMILIES / "completed-run-source-list.json":
        "98494b0ac784ac01e7322dff285278b32ed4861f9d08f32ac6b6566dedd0b842",
    FAMILIES / "dipole-audit-v1/complete_component_input_receipt.json":
        "58c7cebc1b0b9fe4534b44c02d5e16f184d171884b3a342bcf614803a6a2b676",
    FAMILIES / "full-context-audit/external_history_recovery.json":
        "b113ad07ca21f9f294b9bebcb8115237742fbbf6992a8a5623a638012e0c3a9f",
    FAMILIES / "external-history-v4/source_record_counts.csv":
        "ae905902e5b59c59cf0d7a9932217316dc4f2d5794e8f8df727b7c1a4eee2255",
    FAMILIES / "full-context-audit/native_entries.json":
        "b0d28751dff2a5d1bc7d39c8d4a4d198d6f70a29bc6e2be32dbbdea3b5d49b83",
}

PATH_ROLES = {
    "Identity or ordering": ("context", "identity_order", "Retain for joins, ordering and lineage"),
    "Clock or delivery timing": ("context", "timing", "Retain for alignment, availability and derived durations"),
    "Encoding, provenance, or control": ("context", "encoding_provenance_control", "Retain for decoding, scope and provenance"),
    "Source quality": ("context", "integrity", "Retain for validity and diagnosis"),
    "Review definition and units": ("held", "derived_activity", "Recompute over independently verified ordered market events and window boundaries"),
    "Market measurement or derived book statistic": ("held", "market_candidate", "Verify full-session values, units, aliases and availability against source"),
    "Action, side, or book definition": ("held", "market_category_candidate", "Verify source semantics, membership and availability"),
}

PLANE_ROLES = {
    "raw": ("held", "Split measurements from decoding, bootstrap, linkage and provenance"),
    "calculation": ("held", "Resolve actual carrier and consumer and independently check each eligible component"),
    "clock": ("context", "As-of ordering and alignment"),
    "control": ("context", "Definitions, scope and configuration"),
    "arm": ("context", "Arm scope and version"),
    "knowledge": ("context", "Traceable definitions, hypotheses and reference checks"),
    "sealed_answer": ("context", "Sealed until authorized outcome evaluation"),
    "shadow": ("context", "Separate provisional research"),
    "output": ("context", "Append-only output and audit evidence"),
}
PLANE_OVERRIDES = {
    "raw_source_identity_provenance_clocks_integrity": "Decode, align and check the raw feed",
    "order_identity_transitions": "Link original order observations and validate lineage",
    "contract_session_roll_state": "Apply contract and continuity scope",
    "complete_state_reset_bootstrap_receipts": "Apply resets and audit the opening book",
    "missingness_and_integrity_flags": "Validate and diagnose source gaps",
    "derived_feature_availability_timestamps": "Apply as-of availability",
    "prebirth_stopped_chain_false_context_controls": "Run the specified matched control checks",
}


def pinned_text(path):
    content = path.read_bytes().replace(b"\r\n", b"\n")
    if hashlib.sha256(content).hexdigest() != PINS[path]:
        raise ValueError(f"Unreviewed inventory revision: {path.name}")
    return content.decode("utf-8")


def read_rows(relative_path):
    return list(csv.DictReader(io.StringIO(pinned_text(FAMILIES / relative_path))))


def ledger_paths():
    document = pinned_text(BRIDGE / "tasks/root-ledger-headings.md")
    heading_line = document.split("Top-level headings in source order\n\n", 1)[1].splitlines()[0]
    headings = re.findall(r"`([^`]+)`", heading_line)
    paths = {}
    for path, stored_type, review_role in re.findall(
        r"^\| `([^`]+)` \| ([^|]+?) \| ([^|]+?) \|", document, re.MULTILINE
    ):
        disposition, role, reason = PATH_ROLES[review_role]
        if path == "transition":
            disposition, role, reason = "held", "book_transition_candidate", "Recompute directional book changes at consecutive lawful group closes"
        if path == "input_records[].price" or path.endswith(".price_raw"):
            disposition, role, reason = "context", "price_encoding", "Retain exact price encoding for decoding and alias reconciliation"
        paths[path] = dict(path=path, stored_type=stored_type, disposition=disposition, role=role, reason=reason)
    if len(headings) != 23 or len(paths) != 324:
        raise ValueError("Incomplete ROOT heading inventory")
    return headings, paths


def column_role(row, paths):
    source, feature = row["source_path"], row["feature"]
    if source.startswith("activity.") and source in paths and feature == f"root_full.{source}":
        original = paths[source]
        return original["disposition"], original["role"], original["reason"]
    if source == "input_records[].rtype":
        return "context", "wire_encoding", "DBN record type identifies the encoded message layout"
    if source == "observation.orders[].last_update_recv_ns":
        return "context", "clock_validity", "Clock validity category stays with source diagnostics"
    if source == "observation.orders[].last_update_recv_ns linked by order_id to book FIFO position":
        return "held", "elapsed_age_candidate", "Replay the linked order update and verify nonnegative elapsed ns at the lawful cutoff"
    if source == "transition":
        original = paths[source]
        return original["disposition"], original["role"], original["reason"]
    if source in {"mirror.orientation", "mirror.mirror_side_string", "mirror.side_string"}:
        return "context", "adapter_or_group_representation", "Retain source transition and mirror representation for controls and reconciliation"
    if source == "fill_disposition_signature.unresolved_fill_id_count":
        return "context", "integrity", "Retain unresolved native fill linkage for diagnostics"
    return "held", "structure_candidate", "Verify original ROOT structure definition, units, alias mapping and lawful group-close membership"


def source_planes(original):
    canonical = json.loads(pinned_text(FAMILIES / "full-context-audit/canonical-99-registry.json"))
    entries = {
        item["layer_id"]: (group, item)
        for group in canonical["groups"]
        for item in group["entries"]
    }
    crosswalk = json.loads(pinned_text(FAMILIES / "full-context-audit/native_entries.json"))["entries"]
    rows = read_rows("descriptive-v1/plane_registry.csv")
    if len(rows) != 99 or len(entries) != 99 or {row["entry_id"] for row in rows} != entries.keys():
        raise ValueError("Incomplete or inconsistent plane inventory")
    historic_pins = {row["entry_id"]: row for row in original["original_99_plane_records"]}
    if len(historic_pins) != 99 or historic_pins.keys() != entries.keys():
        raise ValueError("Original run does not match the canonical plane identities")
    planes = []
    for row in rows:
        name = row["entry_id"]
        group, item = entries[name]
        historical = json.loads(row["body"])
        pinned = historic_pins[name]
        if int(row["ordinal"]) != pinned["ordinal"] or historical != pinned["original_run_record"]:
            raise ValueError(f"Historical plane record disagrees for {name}")
        role = historical["role"]
        disposition, reason = PLANE_ROLES[role]
        if name in PLANE_OVERRIDES:
            disposition, reason = "context", PLANE_OVERRIDES[name]
        planes.append(dict(
            entry_id=name, group=group["group_id"], role=role, disposition=disposition,
            reason=reason, declared_sources=item["source_paths"],
            october18_native_crosswalk=crosswalk.get(name),
            historical_consumer=historical["consumer"], new_consumer=None,
            session_coverage={session: "UNRESOLVED" for session in SESSIONS},
        ))
    return planes


def dependencies(original):
    external = original["original_13_point_binding"]["points"]
    components = json.loads(pinned_text(FAMILIES / "dipole-audit-v1/complete_component_input_receipt.json"))
    if len(external) != 13 or len(set(components["names"])) != 19:
        raise ValueError("Incomplete external or second-set inventory")

    recovery = json.loads(pinned_text(FAMILIES / "full-context-audit/external_history_recovery.json"))
    rows = read_rows("external-history-v4/source_record_counts.csv")
    counts = {}
    for row in rows:
        counts.setdefault(row["source_id"], {})[row["point"]] = int(row["source_records"])
    attachments = {day: {"status": "NO_MATCHING_ATTACHMENT_IN_PINNED_INVENTORY"} for day in SESSIONS}
    for item in recovery["files"]:
        day = item["day"]
        if day not in attachments:
            continue
        digest = item["declared_sha256"]
        tables = counts[f"manifest:{digest}"]
        if item["status"] != "complete_manifest_hash_verified" or sum(tables.values()) != item["rows"]:
            raise ValueError(f"Attachment receipt disagrees with normalized counts for {day}")
        attachments[day] = dict(
            status="HISTORICAL_HASH_RECEIPT_AND_NORMALIZED_COUNTS_AGREE",
            sha256=digest, source_rows=item["rows"], source_bytes=item["bytes"], tables=tables,
            availability="HELD_FOR_SCOPE_UNITS_AND_PUBLICATION_CHECK",
        )

    return {
        "historic_native_root_carriers": original["original_source_registry"],
        "historic_october18_external_primary": original["original_external_file"],
        "historic_external_13_bindings": external,
        "external_attachment_inventory": attachments,
        "second_set_component_names": components["names"],
        "second_set_clock_fields": components["clock_names"],
        "second_set_states": components["component_state_names"],
        "second_set_original_binding": original["original_second_set_binding"],
        "knowledge_evidence": original["knowledge_evidence_paths"],
        "disposition": "PRESERVE_SOURCE_ROLES_AND_HOLD_UNVERIFIED_VALUES",
    }


def audit_inputs():
    headings, paths = ledger_paths()
    columns = read_rows("joint-inputs-v4/root_full_feature_registry.csv")
    if len(columns) != 10286 or len({row["feature"] for row in columns}) != len(columns):
        raise ValueError("Incomplete or duplicate ROOT fitted column inventory")
    for row in columns:
        row["disposition"], row["role"], row["reason"] = column_role(row, paths)
    original = json.loads(pinned_text(FAMILIES / "completed-run-source-list.json"))
    return {
        "scope": "Pinned retained ROOT paths, historical ROOT fitted columns and 99 canonical plane entries",
        "sessions": list(SESSIONS),
        "session_role": "Equal discovery data for all four trade dates",
        "coverage_gate": "NOT_PASSED",
        "admitted_by_session": {session: [] for session in SESSIONS},
        "headings": headings,
        "paths": list(paths.values()),
        "columns": columns,
        "planes": source_planes(original),
        "dependencies": dependencies(original),
    }


def require_market_fields(session, features):
    """Preflight for the future complete replay; require reviewed coverage for the available span."""
    if session not in SESSIONS:
        raise ValueError(f"No pinned session: {session!r}")
    audit = audit_inputs()
    requested = set(features)
    denied = requested.difference(audit["admitted_by_session"][session])
    if denied:
        raise ValueError(f"Unadmitted {session} inputs: {', '.join(sorted(denied))}")
    if audit["coverage_gate"] != "PASSED":
        raise ValueError(f"Full semantic coverage has not passed for {session}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--section", choices=("summary", "paths", "columns", "planes", "dependencies", "all"), default="summary")
    args = parser.parse_args()
    audit = audit_inputs()
    if args.section == "summary":
        result = {
            "coverage_gate": audit["coverage_gate"],
            "session_role": audit["session_role"],
            "admitted_by_session": audit["admitted_by_session"],
            "headings": audit["headings"],
            **{key: dict(Counter(row["disposition"] for row in audit[key]))
               for key in ("paths", "columns", "planes")},
        }
    elif args.section == "all":
        result = audit
    else:
        result = audit[args.section]
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
