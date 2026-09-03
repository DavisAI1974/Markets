"""Render the principal's report FROM his findings, so the two cannot diverge.

Run 33605852433 produced 44 findings in `frankie_principal_findings.json` and a
hand-authored `frankie_calculation_assessment.md` beside it. Because the report was written
separately from the findings, the 44 never reached Greg: what he was shown was a verdict on
whether each section earned its place, while chain depths, family crosswalks, exhaustion
runways, prebirth recognition and the dipole decoupling sat unread in the JSON. A report
authored apart from its evidence can omit the evidence and still look complete.

So the findings artifact is the STORE and this is the RENDER, exactly as `DECISIONS.md`,
`OPEN_ITEMS.md` and `RUN_SOP.md` already are in this tree. Edit the store and re-render;
never edit the render.

**It writes a NEW file and never touches `frankie_calculation_assessment.md`.** That document
is a hand-authored record of what a principal said, and D60 does not permit destroying a
record to make room for a generated one.

The load-bearing property is that EVERY finding reaches the page, with its claim, evidence,
falsifier and confidence basis, and with the count stated so a dropped one is visible. A
renderer that silently omitted a finding would be the exact defect this module exists to
close.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

REPORT_FILENAME = "frankie_findings_report.md"

#: Every field a finding must carry. `attach_principal_findings` already refuses a finding
#: with no falsifier; this refuses one that cannot be rendered honestly.
REQUIRED_FIELDS = ("id", "section", "claim", "falsifier")


class ReportError(RuntimeError):
    """Raised when the artifact cannot be rendered without inventing or omitting content."""


def _identity_rows(body: Mapping[str, Any]) -> list[tuple[str, str]]:
    """Which run this describes. A verdict with no subject was read against the wrong run
    once already in this tree, and every step passed while it happened."""
    names = (
        "run_id", "principal", "arm", "role", "source_day", "causal_clock",
        "continuity_segment", "evidence_result_hash",
    )
    return [(n, str(body.get(n))) for n in names if body.get(n) is not None]


def _render_evidence(evidence: Any) -> str:
    if evidence is None:
        return "_no evidence block on this finding_"
    if isinstance(evidence, str):
        return evidence
    return "```json\n" + json.dumps(evidence, indent=2, sort_keys=True) + "\n```"


def render_report(
    body: Mapping[str, Any],
    *,
    crosswalk: Mapping[str, Any] | None = None,
    crosswalk_note: str | None = None,
) -> str:
    """Return the markdown report for one principal artifact.

    `crosswalk` is a `native_layer_crosswalk.crosswalk` body; when given, its table is
    appended after the findings (S121 slice 3) - this report is the one file every artifact
    produces, so what reached the principal is stated where it cannot be missed.
    `crosswalk_note` states, in the report, why no crosswalk could be computed; a failure
    recorded only on stderr expires with the terminal. Neither given: the report is unchanged.
    """
    findings = body.get("findings")
    if not isinstance(findings, Sequence) or isinstance(findings, (str, bytes)):
        raise ReportError("the artifact findings must be a list")
    for row in findings:
        if not isinstance(row, Mapping):
            raise ReportError("a finding is not an object")
        missing = [f for f in REQUIRED_FIELDS if not str(row.get(f, "")).strip()]
        if missing:
            raise ReportError(
                f"finding {row.get('id', '<unnamed>')!r} is missing {missing}; it cannot be "
                "rendered without inventing content"
            )

    lines: list[str] = []
    add = lines.append
    add(f"# Frankie findings — {body.get('run_id', 'unknown run')}")
    add("")
    add("**This file is a RENDER of `frankie_principal_findings.json`. Do not edit it.**")
    add("Edit the findings artifact and re-render. The report is generated from the findings")
    add("so the two cannot diverge: a report authored separately from its evidence can omit")
    add("the evidence and still look complete, which is how 44 findings went unread once.")
    add("")
    add("| | |")
    add("|---|---|")
    for name, value in _identity_rows(body):
        add(f"| {name} | `{value}` |")
    add("")
    # F-10 / F-14: the report states IN WORDS which exact ledgers the principal read, so a
    # reader can tell a claim resting on rows from one resting on counters. The staging gate
    # refuses an artifact without the declaration; a render of one says so rather than
    # quietly omitting the table.
    add("## What the principal read")
    add("")
    evidence_read = body.get("evidence_read")
    if isinstance(evidence_read, Mapping) and evidence_read:
        add("| exact ledger | read status |")
        add("|---|---|")
        for ledger in sorted(evidence_read):
            add(f"| `{ledger}` | **{evidence_read[ledger]}** |")
        add("")
        unread = [k for k, v in sorted(evidence_read.items()) if v != "READ"]
        if unread:
            add("A claim about exact members on a ledger marked PARTIAL or NOT_READ rests on the")
            add("runner's counters and per-stratum summaries, not on rows the principal read.")
        else:
            add("Every exact ledger was declared READ.")
    else:
        add("_`evidence_read` is not declared on this artifact. The staging gate refuses such an_")
        add("_artifact, so this render came from one that predates the gate; treat every_")
        add("_exact-member claim in it as resting on counters._")
    add("")
    add(f"**{len(findings)} findings.** The count is stated because a reader cannot notice an")
    add("absent finding without a denominator to check it against.")
    add("")
    add("## Day-over-day memory carry")
    add("")
    if not findings:
        add("**No new findings.** This is a legitimate completed day: the committed artifact")
        add("proves the principal ran, while the empty list adds no entry to served memory.")
        add("")
    else:
        add("These are the new findings this artifact asks the automatic A-memory carry to retain.")
        add("Their own evidence, falsifier, and confidence basis explain why each is carried;")
        add("only later stream evidence may change UNVERIFIED to VERIFIED.")
        add("")
        for row in findings:
            add(f"#### Carry {row['id']}")
            add("")
            add(f"**Claim.** {row['claim']}")
            add("")
            add("**Evidence.**")
            add(_render_evidence(row.get("evidence")))
            add("")
            add(f"**Falsifier.** {row['falsifier']}")
            add("")
            basis = row.get("confidence_basis")
            add(f"**Confidence basis.** {basis}" if basis
                else "**Confidence basis.** _not stated on this finding_")
            add("")

    by_section: dict[str, list[Mapping[str, Any]]] = {}
    for row in findings:
        by_section.setdefault(str(row["section"]), []).append(row)

    add("## Findings by section")
    add("")
    add("| section | findings |")
    add("|---|---:|")
    for section in sorted(by_section):
        add(f"| {section} | {len(by_section[section])} |")
    add("")
    add("A section heading here is whatever the finding named, including a multi-section")
    add("label such as `4.3 / 4.14`. Nothing is re-filed into a tidier key, because a")
    add("finding that spans sections is evidence about the join between them.")
    add("")

    for section in sorted(by_section):
        add(f"## {section}")
        add("")
        for row in by_section[section]:
            add(f"#### {row['id']}")
            if row.get("category"):
                add(f"*{row['category']}*")
                add("")
            add(f"**Claim.** {row['claim']}")
            add("")
            add("**Evidence.**")
            add(_render_evidence(row.get("evidence")))
            add("")
            add(f"**Falsifier.** {row['falsifier']}")
            add("")
            basis = row.get("confidence_basis")
            add(f"**Confidence basis.** {basis}" if basis
                else "**Confidence basis.** _not stated on this finding_")
            add("")

    if crosswalk is not None or crosswalk_note is not None:
        add("## Layer crosswalk")
        add("")
        if crosswalk is not None:
            add("What reached the principal, one row per registry layer, COMPUTED from this run's")
            add("receipts and its own field census - never read off a policy")
            add("(`native_layer_crosswalk.crosswalk`). Appended here because this report is the one")
            add("file every artifact produces, so the delivery record cannot be lost beside it.")
            add("")
            # Imported here, not at module level: the crosswalk module imports the ledger fetcher,
            # which imports staging, which renders this report - a top-level import would cycle.
            from research.kalshi.frankie_raw_mbo_benchmark.native_layer_crosswalk import (
                render_crosswalk_table,
            )

            add(render_crosswalk_table(crosswalk))
        else:
            add(f"_{crosswalk_note}_")
            add("")
    return "\n".join(lines) + "\n"


def write_report(
    artifact_path: Path | str,
    *,
    out_dir: Path | None = None,
    crosswalk: Mapping[str, Any] | None = None,
    crosswalk_note: str | None = None,
) -> Path:
    """Render `artifact_path` and write the report beside it. Returns the written path.

    Writes `frankie_findings_report.md`. It never writes
    `frankie_calculation_assessment.md`: that is a hand-authored record and a generated file
    does not get to overwrite one. `crosswalk` / `crosswalk_note` are passed to `render_report`.
    """
    artifact_path = Path(artifact_path)
    try:
        body = json.loads(artifact_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReportError(f"no principal artifact at {artifact_path}") from exc
    except json.JSONDecodeError as exc:
        raise ReportError(f"principal artifact at {artifact_path} is not valid JSON: {exc}") from exc
    target = (out_dir or artifact_path.parent) / REPORT_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        render_report(body, crosswalk=crosswalk, crosswalk_note=crosswalk_note), encoding="utf-8"
    )
    return target


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    written = write_report(args.artifact, out_dir=args.out_dir)
    body = json.loads(Path(args.artifact).read_text(encoding="utf-8"))
    print(json.dumps({
        "report": str(written),
        "findings_rendered": len(body.get("findings") or []),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
