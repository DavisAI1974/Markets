#!/usr/bin/env python3
"""Materialize fixed POX cases from the user-approved frozen marked roster."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

EXPECTED_TOTAL = 3429
EXPECTED_FLIP = 1546
EXPECTED_SAME = 1883
POLICY = "FIXED_3429_DO_NOT_REOPEN"


def _open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("rt", encoding="utf-8")


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with _open_text(path) as handle:
        for lineno, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise RuntimeError(f"roster line {lineno} is not an object")
            yield row


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _case_id(day: str, second_utc: int, polarity: int) -> str:
    return f"{day}-{second_utc:05d}-{polarity:+d}"


def materialize(roster: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for lineno, row in enumerate(_iter_jsonl(roster), 1):
        if row.get("frozen_target_match") is not True:
            continue
        clock = row.get("clock")
        next_target = row.get("next_event_target")
        if not isinstance(clock, dict) or not isinstance(next_target, dict):
            raise RuntimeError(f"marked roster line {lineno} lacks clock/next_event_target")
        polarity = int(row["polarity"])
        same_polarity = next_target.get("same_polarity")
        if polarity not in {-1, 1} or not isinstance(same_polarity, bool):
            raise RuntimeError(f"marked roster line {lineno} has invalid authoritative fields")
        case_id = _case_id(str(clock["day"]), int(clock["second_utc"]), polarity)
        if case_id in seen:
            raise RuntimeError(f"duplicate marked case identity: {case_id}")
        seen.add(case_id)
        cases.append(
            {
                "branch_label": "SAME" if same_polarity else "FLIP",
                "case_id": case_id,
                "clock": clock,
                "frozen_target_family": row.get("frozen_target_family"),
                "frozen_target_split": row.get("frozen_target_split"),
                "next_event_target": next_target,
                "polarity": polarity,
                "population_policy": POLICY,
                "roster_causal_fields": {
                    "chain_membership_state": row.get("chain_membership_state"),
                    "descriptors_posthoc": row.get("descriptors_posthoc"),
                    "endpoint_posthoc": row.get("endpoint_posthoc"),
                },
                "source_roster_identity": {
                    "t_week_second": row.get("t_week_second"),
                    "week_index": row.get("week_index"),
                    "week_sunday": row.get("week_sunday"),
                },
            }
        )
    counts = Counter(case["branch_label"] for case in cases)
    observed = (len(cases), counts["FLIP"], counts["SAME"])
    expected = (EXPECTED_TOTAL, EXPECTED_FLIP, EXPECTED_SAME)
    if observed != expected:
        raise RuntimeError(f"approved fixed-roster gate failed: observed={observed} expected={expected}")
    return sorted(cases, key=lambda case: case["case_id"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roster", required=True)
    parser.add_argument("--out-ledger", required=True)
    parser.add_argument("--provenance-out", required=True)
    args = parser.parse_args()
    roster = Path(args.roster)
    cases = materialize(roster)
    out = Path(args.out_ledger)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wt", encoding="utf-8", newline="\n") as handle:
        for case in cases:
            handle.write(json.dumps(case, sort_keys=True, separators=(",", ":")) + "\n")
    provenance = {
        "authority": "LATEST_EXPLICIT_USER_AUTHORITY_20260819_USE_NEWEST_NUMBERS",
        "ledger": {"path": out.name, "sha256": _sha256(out)},
        "population": {"total": EXPECTED_TOTAL, "flip": EXPECTED_FLIP, "same": EXPECTED_SAME},
        "policy": POLICY,
        "source": {"member_name": roster.name, "member_sha256": _sha256(roster)},
        "status": "AUTHORITATIVE_FIXED_LEDGER_MATERIALIZED",
    }
    provenance_out = Path(args.provenance_out)
    provenance_out.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(provenance, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
