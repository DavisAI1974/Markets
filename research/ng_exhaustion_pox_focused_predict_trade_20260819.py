#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

EXPECTED_TOTAL = 3429
EXPECTED_FLIP = 1444
EXPECTED_SAME = 1985
POLICY = "FIXED_3429_DO_NOT_REOPEN"

CASE_ID_KEYS = ("case_id", "id", "pox_case_id", "event_id")
BRANCH_KEYS = ("branch_label", "branch", "later_branch", "successor_branch")


def _open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("rt", encoding="utf-8")


def _iter_rows(path: Path) -> Iterable[dict[str, Any]]:
    """Load a ledger without deriving population membership from canonical data."""
    with _open_text(path) as f:
        first = f.read(1)
        f.seek(0)
        if first in ("[", "{"):
            data = json.load(f)
            if isinstance(data, list):
                rows = data
            elif isinstance(data, dict):
                rows = data.get("rows") or data.get("cases") or data.get("ledger")
                if rows is None:
                    raise RuntimeError("JSON ledger object must contain rows/cases/ledger")
            else:
                raise RuntimeError("unsupported ledger JSON container")
            for row in rows:
                if not isinstance(row, dict):
                    raise RuntimeError("ledger rows must be JSON objects")
                yield row
            return

        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise RuntimeError(f"ledger line {lineno} is not a JSON object")
            yield row


def _pick(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def normalize(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, row in enumerate(rows):
        case_id = _pick(row, CASE_ID_KEYS)
        if case_id is None:
            raise RuntimeError(f"row {i} missing stable case id; accepted keys={CASE_ID_KEYS}")
        case_id = str(case_id)
        if case_id in seen:
            raise RuntimeError(f"duplicate case id: {case_id}")
        seen.add(case_id)

        branch = _pick(row, BRANCH_KEYS)
        if branch is None:
            raise RuntimeError(f"row {i} case {case_id} missing authoritative branch label")
        branch = str(branch).upper().strip()
        if branch not in {"FLIP", "SAME"}:
            raise RuntimeError(f"row {i} case {case_id} invalid branch label {branch!r}")

        out.append({
            "case_id": case_id,
            "branch_label": branch,
            "source_row": row,
        })
    return out


def validate_fixed_population(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(r["branch_label"] for r in rows)
    observed = (len(rows), counts["FLIP"], counts["SAME"])
    expected = (EXPECTED_TOTAL, EXPECTED_FLIP, EXPECTED_SAME)
    if observed != expected:
        raise RuntimeError(
            "authoritative fixed-ledger invariant failed: "
            f"observed total/flip/same={observed} expected={expected}. "
            "Do not attempt canonical adjacency or any other population rediscovery; repair/provide the correct ledger."
        )
    return {
        "policy": POLICY,
        "total": EXPECTED_TOTAL,
        "flip": EXPECTED_FLIP,
        "same": EXPECTED_SAME,
        "preserved_all": True,
        "population_rediscovery_performed": False,
        "canonical_adjacency_enumeration_performed": False,
    }


def write_normalized(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if path.suffix == ".gz" else open
    mode = "wt"
    kwargs = {"encoding": "utf-8"}
    with opener(path, mode, **kwargs) as f:
        for r in rows:
            src = dict(r["source_row"])
            src["case_id"] = r["case_id"]
            src["branch_label"] = r["branch_label"]
            src["population_policy"] = POLICY
            f.write(json.dumps(src, sort_keys=True) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Focused POX fixed-ledger gate. This program intentionally does NOT derive the 3,429 population "
            "from canonical adjacency. Canonical/raw inputs belong to later enrichment and modeling stages."
        )
    )
    ap.add_argument("--ledger", required=True, help="authoritative 3,429-case JSON/JSONL ledger (.gz accepted)")
    ap.add_argument("--out", required=True, help="validation/status JSON")
    ap.add_argument("--normalized-ledger", help="optional normalized preserve-all JSONL(.gz) output")
    args = ap.parse_args()

    ledger = Path(args.ledger)
    if not ledger.is_file():
        raise RuntimeError(f"ledger not found: {ledger}")

    rows = normalize(_iter_rows(ledger))
    population = validate_fixed_population(rows)

    if args.normalized_ledger:
        write_normalized(Path(args.normalized_ledger), rows)

    result = {
        "status": "POX_FIXED_LEDGER_VALIDATED",
        "population": population,
        "initial_sign_persistence_through_plus60_approx": 0.944,
        "next_stages": {
            "target_A_pox_identity": "REQUIRES_SEPARATE_CAUSAL_CANDIDATE_CONTROL_UNIVERSE_IF_BINARY_MEMBERSHIP_MODEL_IS_RUN",
            "target_B_initial_continuation": "READY_AFTER_LEDGER_JOIN_TO_RAW_TAPE_AND_SIGNAL_TIMESTAMPS",
            "target_C_flip_same": "READY_AFTER_LEDGER_JOIN_TO_CAUSAL_FEATURE_PREFIXES",
            "target_D_branch_knowability": "READY_AFTER_LEDGER_JOIN_TO_FROZEN_CAUSAL_TIMESTAMPS",
            "target_E_management": "READY_AFTER_TARGET_B_C_D_OUTPUTS",
        },
        "D0_D5_incremental_crosswalk": "DEFERRED_UNTIL_POX_AND_D0_D5_ARE_INDEPENDENTLY_FROZEN",
        "protected_mutations": {
            "detector": False,
            "canonical_evidence": False,
            "phase1_lineage_scores": False,
            "phase2_findings": False,
            "runway_clock": False,
            "permanent_frankie": False,
            "frankie1": False,
            "spawn_py": False,
            "ssos_play": False,
        },
        "promotion_performed": False,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
