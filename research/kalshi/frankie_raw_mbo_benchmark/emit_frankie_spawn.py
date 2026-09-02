"""Fill every Frankie spawn slot BY LOOKUP and emit the exact prompt. The A-arm `spawn.py`.

**Why this exists, and why it is the reason Frankie had never been run.** The A-arm had both
ends of the spawn contract and nothing in between: `native_staging.stage_spawn_request`
writes a request at each lawful cutoff, and `load_principal_artifact` /
`attach_principal_findings` validate and bind what comes back. Nothing turned a staged
request plus the mission plus the evidence into the text a principal is actually run
against. So the traversal produced evidence, the run completed `EVIDENCE_ONLY`, and the
second half of D68 never happened - not because it was refused, because nobody had written
the renderer.

**The contract is `spawn.py`'s, deliberately.** Every slot below is a LOOKUP from a
committed artifact, never a judgement call, and a slot that cannot be resolved HALTS the
emission naming the failed lookup rather than producing a prompt with a hole in it. That
rule is NC-1's: a refine directive once asserted "first post-roll session" when
`flow_calendar` said BCOM roll day 5 of 5, and the false premise propagated into the blind
posterior. Greg's framing was that running off-SOP should become impossible rather than
forbidden. A premise that cannot be typed cannot be wrong.

**The hash check is section 10 made mechanical.** The mission's own execution-proof gate
requires that "this complete mission's exact bytes and SHA-256 were loaded into Frankie".
The run froze a `mission_sha256` at launch; this refuses to emit if the mission on disk no
longer hashes to it. Without that, editing the mission between the traversal and the spawn
would hand Frankie bytes that do not match the run he is reporting on, and every downstream
receipt would still look clean.

**No API call anywhere.** Greg, 2026-08-29: *"on invoke runs chatgpt 5.6 sol just like you
used to run the blind/reveal for the group runs, no api call."* This emits text for a
session over committed files. It calls no model and knows about no provider.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

from research.kalshi.frankie_raw_mbo_benchmark.native_key_alias import read_averaged_rows

REPO_ROOT = Path(__file__).resolve().parents[3]
MISSION_PATH = "research/kalshi/agents/frankie_native_raw_mbo_oct45_realtime_mission_20260828.md"
CONTRACT_PATH = "research/kalshi/agents/frankie_native_raw_mbo_calculation_contract_20260828.md"
FINDINGS_SCHEMA = "FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_FINDINGS_V1"


class EmitError(ValueError):
    """A slot could not be resolved, so no prompt is emitted. The stop rule."""


def _lookup(body: Mapping[str, Any], path: str) -> Any:
    """Read a dotted path, or HALT naming the exact lookup that failed.

    Never returns a default. A slot filled with a default is a slot nobody checked, which
    is the failure mode this module exists to make impossible.
    """
    node: Any = body
    for part in path.split("."):
        if not isinstance(node, Mapping) or part not in node:
            raise EmitError(f"lookup failed: {path!r} (stopped at {part!r})")
        node = node[part]
    if node is None or node == "":
        raise EmitError(f"lookup resolved empty: {path!r}")
    return node


def _file_sha256(path: Path) -> str:
    if not path.exists():
        raise EmitError(f"lookup failed: {path} does not exist")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def emit(result_path: Path | str, *, repo_root: Path | None = None,
         evidence_uri: str | None = None) -> str:
    """Render the prompt for one Frankie run. Returns text; raises EmitError on any gap."""
    repo_root = Path(repo_root or REPO_ROOT)
    result_path = Path(result_path)
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EmitError(f"cannot read the evidence at {result_path}: {exc}") from exc

    verdict = _lookup(result, "verdict")
    if verdict != "ACCEPTED":
        # A refused calculation is not evidence. Section 6 rejects the whole result rather
        # than partially promoting it, so a principal run against one would be interpreting
        # something the runner already declined to stand behind.
        raise EmitError(f"the run's verdict is {verdict!r}, not ACCEPTED; nothing to spawn against")

    identity = _lookup(result, "layers.identity_receipt")
    coverage = _lookup(identity, "coverage")
    traversal = _lookup(result, "traversal")
    result_hash = _lookup(result, "result_hash")
    arm = _lookup(identity, "arm")
    run_id = _lookup(identity, "run_id")

    # THE HASH CHECK THAT MAKES THE MISSION UNEDITABLE BETWEEN TRAVERSAL AND SPAWN.
    mission_file = repo_root / MISSION_PATH
    mission_now = _file_sha256(mission_file)
    mission_bound = _lookup(identity, "mission_sha256")
    if mission_now != mission_bound:
        raise EmitError(
            f"the mission on disk hashes to {mission_now} but the run bound "
            f"{mission_bound}. Section 10 requires this mission's exact bytes and SHA-256 to "
            "be the ones loaded into Frankie, so emitting would bind him to a document the "
            "run never saw. Restore the bound bytes, or re-run the traversal."
        )
    contract_file = repo_root / CONTRACT_PATH
    contract_now = _file_sha256(contract_file)
    contract_bound = _lookup(identity, "calculation_contract_sha256")
    if contract_now != contract_bound:
        raise EmitError(
            f"the calculation contract on disk hashes to {contract_now} but the run bound "
            f"{contract_bound}"
        )

    cutoffs = _lookup(traversal, "invocation_cutoffs")
    if not isinstance(cutoffs, list) or not cutoffs:
        raise EmitError(
            "the run staged no invocation cutoffs; there is no lawful decision point to "
            "spawn against, which is a cadence defect and not an empty day"
        )
    sections_fed = _lookup(traversal, "sections_fed")

    # NOT `_lookup(..., "layers.averaged_companions.rows")`. When the rows are aliased
    # that lookup still succeeds, still returns the right count, and `row.get("section")`
    # then returns None on every one - so the per-section table would report every row
    # under `None` and the prompt would go out looking complete.
    rows = read_averaged_rows(result)
    per_section: dict[str, int] = {}
    for row in rows:
        per_section[str(row.get("section"))] = per_section.get(str(row.get("section")), 0) + 1

    lines: list[str] = []
    add = lines.append
    add(f"You are `REAL_TIME_FRANKIE`, the principal for arm `{arm}`, run `{run_id}`.")
    add("")
    add("## Read these first, in full")
    add("")
    add(f"1. `{MISSION_PATH}`")
    add(f"   sha256 `{mission_bound}` - verified to match the bytes this run was launched")
    add("   against. It is your mission; every question you answer is one of its questions.")
    add(f"2. `{CONTRACT_PATH}`")
    add(f"   sha256 `{contract_bound}` - what the runner computed and how.")
    add("")
    add("Section 5 of the mission governs the division of labour and is not negotiable:")
    add("**the runner calculates, you interpret.** The sixteen sections were computed")
    add("deterministically before you saw them. Do not recompute them differently, and do")
    add("not treat a mechanical summary as a finding.")
    add("")
    add("## The evidence")
    add("")
    add(f"- Local file: `{result_path}`")
    if evidence_uri:
        add(f"- Durable copy: `{evidence_uri}`")
    add(f"- `evidence_result_hash`: `{result_hash}`")
    add(f"- Verdict `{verdict}`, failed gates {_lookup(result, 'failed_gates') or 'none'}, "
        f"completion `{_lookup(result, 'completion_status')}`")
    add(f"- Source traversed: `{Path(str(_lookup(result, 'slice.sources')[0])).name}`")
    add(f"- Coverage: {coverage['records_seen']:,} records, {coverage['groups_seen']:,} groups, "
        f"{coverage['groups_f_last_closed']:,} F_LAST-closed")
    add(f"- Integrity: {coverage['cursor_discontinuities']} cursor discontinuities, "
        f"{coverage['duplicate_group_indices']} duplicate group indices, "
        f"{coverage['fifo_reconstruction_failures']} FIFO reconstruction failures")
    add("")
    add("It is about 20 MB. `layers.averaged_companions.rows` is 99% of it, so read the")
    add("skeleton whole and the averaged rows section by section with tools. Do not guess at")
    add("what you have not read, and say what you did not read.")
    add("")
    add("### What each section actually received")
    add("")
    add("| section | ingest |")
    add("|---|---:|")
    for name, count in sections_fed.items():
        add(f"| {name} | {count:,} |")
    add("")
    add("An ingest count is not a result. A section reporting strata off an empty ingest is")
    add("indistinguishable from one reporting a real absence, which is why these are here.")
    add("")
    add("### Averaged companion rows, by section")
    add("")
    add("| section | rows |")
    add("|---|---:|")
    for name in sorted(per_section, key=lambda k: -per_section[k]):
        add(f"| {name} | {per_section[name]:,} |")
    add(f"\nTotal {len(rows):,} rows. Each carries `measure`, `stratum`, `kind`, `value`,")
    add("`declaration` and `excluded_missing_members`. Mission section 7 forbids quoting any")
    add("of them without their strata, and section 5 says a summary that cannot be traced to")
    add("members is not evidence.")
    add("")
    add(f"### The {len(cutoffs)} lawful cutoffs you are reporting across")
    add("")
    add("| # | group_index | source_day | session_phase | recv_ns | first_lawful_availability_ns |")
    add("|---:|---:|---|---|---:|---:|")
    for index, cut in enumerate(cutoffs, start=1):
        add(f"| {index} | {cut['group_index']:,} | {cut['source_day']} | {cut['session_phase']} "
            f"| {cut['recv_ns']} | {cut['first_lawful_availability_ns']} |")
    add("")
    add("## What you return")
    add("")
    add("One committed artifact, JSON, exactly this shape:")
    add("")
    add("```json")
    add(json.dumps({
        "schema": FINDINGS_SCHEMA,
        "principal": "<the model that actually ran>",
        "arm": arm,
        "role": "REAL_TIME_FRANKIE",
        "evidence_result_hash": result_hash,
        "controller_only": False,
        "actual_principal_invocation": True,
        "findings": ["<at least one; see the mission's section 9 for what a finding must carry>"],
    }, indent=2))
    add("```")
    add("")
    add("`load_principal_artifact` refuses a missing artifact, a different")
    add("`evidence_result_hash`, `controller_only` true, an artifact that does not attest an")
    add("actual invocation, and an empty findings list. An empty artifact is a failed spawn,")
    add("not an empty success.")
    add("")
    add("Mission section 9 says what the output must contain: searched coverage and current")
    add("causal state; candidate families and complete causal runways; pre-birth and")
    add("early-recognition timing; duration, recurrence, extension, chain and completion")
    add("behaviour; direction/dipole states and transitions; exact and averaged views with")
    add("reconciliation labels; novel correlations and positive hypotheses; provisional")
    add("strategy hypotheses; and exact evidence and clock references.")
    add("")
    # THE SPAN, NOT JUST THE DATE. On an 88-minute window "Oct 1" reads as a day and is an
    # hour and a half, and a finding scoped to the wrong unit is wrong in the way this
    # project keeps catching: present, typed, plausible, measuring something other than what
    # its name implies. Stated as the CUTOFF span rather than the session's, because the
    # traversal may begin before the first lawful cutoff and end after the last.
    span_ns = int(cutoffs[-1]["recv_ns"]) - int(cutoffs[0]["recv_ns"])
    phases = sorted({str(cut["session_phase"]) for cut in cutoffs})
    add(f"**Cutoff span: {span_ns / 1e9:,.0f} seconds ({span_ns / 6e10:,.1f} minutes)** from the")
    add("first lawful cutoff to the last - which is not the session's length, since the")
    add("traversal may begin before the first cutoff and end after the last.")
    add(f"**Session phases covered: {', '.join(phases)}.** Any phase not in that list was not")
    add("observed at all on this slice, which is a different fact from observing it empty.")
    add("Scope every finding to this span and these phases.")
    add("")

    days = sorted({str(cut["source_day"]) for cut in cutoffs})
    if len(days) == 1:
        # THE SLICE STATED TO THE PRINCIPAL, not left for him to infer from the cutoff table.
        # The mission is written for October 1, 3, 4 and 5; this run traversed one of them.
        # Anything needing a cross-day comparison is UNANSWERABLE here rather than absent,
        # and those are different facts - the mission's own "censored is not negative" rule
        # applied to the shape of the run instead of to a stratum.
        add(f"**This run is ONE DAY: {days[0]}.** The mission is written across October 1, 3,")
        add("4 and 5, and every question in it applies here - but any of them needing a")
        add("cross-day comparison can only be answered WITHIN this day. Say which those are")
        add("and mark them unanswerable on this slice. Do not report a single-day reading as")
        add("if it settled a question the mission asks across days.")
        add("")
    add("Three of its rules are the ones most often broken. **Absence is a result** - a")
    add("section that produced nothing on a stratum has told you something; say so rather")
    add("than omitting it. **Censored is not negative** - never-restored, never-recognized")
    add("and still-open are distinct from not-yet-observed. **Most sections are not")
    add("exhaustion** - 4.5 through 4.9 and 4.12 through 4.14 are market mechanics in their")
    add("own right, and several have never been studied on native MBO at all.")
    add("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", required=True, help="calculation_result.json for the run")
    parser.add_argument("--evidence-uri", default=None, help="durable S3 URI, for the record")
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)
    try:
        text = emit(args.result, evidence_uri=args.evidence_uri)
    except EmitError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
