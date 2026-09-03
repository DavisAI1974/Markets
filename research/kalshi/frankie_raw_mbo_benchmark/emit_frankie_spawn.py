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

from research.kalshi.frankie_raw_mbo_benchmark.fetch_frankie_ledgers import (
    RECEIPT_SCHEMA as DELIVERY_RECEIPT_SCHEMA,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (
    SHA256_RE,
    canonical_hash,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_key_alias import read_averaged_rows
from research.kalshi.frankie_raw_mbo_benchmark.native_knowledge_delivery import (
    KnowledgeDeliveryError,
    render_knowledge_block,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_layer_crosswalk import (
    CrosswalkError,
    CrosswalkGateError,
    crosswalk,
    gate_applicable_inputs,
)
from research.kalshi.frankie_raw_mbo_benchmark import native_principal_outputs as outputs
from research.kalshi.frankie_raw_mbo_benchmark.native_staging import EXACT_LEDGERS

REPO_ROOT = Path(__file__).resolve().parents[3]
STREAM_MODULE = "research.kalshi.frankie_raw_mbo_benchmark.native_causal_stream"
MISSION_PATH = "research/kalshi/agents/frankie_native_raw_mbo_oct45_realtime_mission_20260828.md"
CONTRACT_PATH = "research/kalshi/agents/frankie_native_raw_mbo_calculation_contract_20260828.md"

#: The mission must ASK the raw-MBO retention question or the spawn is refused. D68 ordered
#: a report "on the calcs, on the full raw mbo, all of it"; the calcs half was delivered and
#: the raw-MBO half was never asked, so it was never answered - the spawn prompt contained
#: `raw mbo`, `retention`, `drop`, `field`, `book_full` and `keep` exactly zero times. A
#: decision recorded in DECISIONS.md and absent from the mission never reaches Frankie, and
#: prose cannot enforce itself. This is the enforcement.
RAW_MBO_SECTION_MARKER = "### 9a. The raw MBO"
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


def _load_json_object(path: Path | str | None, label: str) -> dict[str, Any] | None:
    """Load one optional receipt/proof object without interpreting its schema."""
    if path is None:
        return None
    path = Path(path)
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EmitError(f"cannot read the {label} at {path}: {exc}") from exc
    if not isinstance(body, Mapping):
        raise EmitError(f"the {label} at {path} is not a JSON object")
    return dict(body)


def _load_delivery_receipt(path: Path | str | None) -> dict[str, Any]:
    """The D81 gate: no spawn until every exact ledger is in his hands and VERIFIED.

    The receipt is `fetch_frankie_ledgers`' FRANKIE_LEDGER_DELIVERY_RECEIPT_V1. Its own hash
    must verify, its schema must be that one, and every ledger in `EXACT_LEDGERS` must read
    VERIFIED with a local path that exists. A partial delivery reasoned over as a complete
    one is the S120 finding wearing a receipt.
    """
    if path is None:
        raise EmitError(
            "no delivery receipt: the raw MBO is the principal's evidence (D81) and the spawn "
            "is refused until fetch_frankie_ledgers has delivered and VERIFIED every exact "
            f"ledger in {list(EXACT_LEDGERS)}; pass --delivery-receipt"
        )
    path = Path(path)
    body = _load_json_object(path, "delivery receipt")
    assert body is not None
    if body.get("schema") != DELIVERY_RECEIPT_SCHEMA:
        raise EmitError(f"{path} is not a {DELIVERY_RECEIPT_SCHEMA}")
    if body.get("receipt_sha256") != canonical_hash(body, omit="receipt_sha256"):
        raise EmitError(f"delivery receipt at {path} fails its own receipt_sha256")
    ledgers = body.get("ledgers")
    if not isinstance(ledgers, Mapping):
        raise EmitError("delivery receipt carries no `ledgers`")
    for name in EXACT_LEDGERS:
        entry = ledgers.get(name)
        status = entry.get("status") if isinstance(entry, Mapping) else None
        if status != "VERIFIED":
            raise EmitError(
                f"delivery receipt: {name} is {status!r}, not VERIFIED; a ledger that did not "
                "arrive whole and matching the box's PLAIN_SHA256SUMS is not evidence"
            )
        local = entry.get("local_path")
        if not isinstance(local, str) or not Path(local).exists():
            raise EmitError(f"delivery receipt: {name} names no local_path that exists ({local!r})")
        if not isinstance(entry.get("plain_sha256_observed"), str) or SHA256_RE.fullmatch(entry["plain_sha256_observed"]) is None:
            raise EmitError(f"delivery receipt: {name} carries no observed plain sha256")
    return dict(body)


def emit(
    result_path: Path | str, *, delivery_receipt: Path | str | None = None,
    stream_receipt: Path | str | None = None,
    knowledge_receipt: Path | str | None = None,
    outputs_receipt: Path | str | None = None,
    sealed_proof: Path | str | None = None,
    ledger_dir: Path | str | None = None,
    repo_root: Path | None = None, evidence_uri: str | None = None,
) -> str:
    """Render the prompt for one Frankie run. Returns text; raises EmitError on any gap.

    `delivery_receipt` is REQUIRED in the only sense that matters: absent, the emission is
    refused. It is a keyword with a None default so the refusal is an EmitError naming the
    rule rather than a TypeError naming a parameter.
    """
    repo_root = Path(repo_root or REPO_ROOT)
    result_path = Path(result_path)
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EmitError(f"cannot read the evidence at {result_path}: {exc}") from exc
    receipt = _load_delivery_receipt(delivery_receipt)
    stream_receipt_body = _load_json_object(stream_receipt, "stream receipt")
    knowledge_receipt_body = _load_json_object(knowledge_receipt, "knowledge receipt")
    outputs_receipt_body = _load_json_object(outputs_receipt, "outputs receipt")
    sealed_proof_body = _load_json_object(sealed_proof, "sealed-absence proof")
    delivered = {name: receipt["ledgers"][name] for name in EXACT_LEDGERS}

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
    # THE GATE THAT MAKES THE RAW-MBO QUESTION UNSKIPPABLE. The hash check above proves the
    # mission was not edited between traversal and spawn; it says nothing about what the
    # mission ASKS. A mission missing section 9a produces a report that answers the
    # calculations and silently omits the half Greg has asked for repeatedly.
    if RAW_MBO_SECTION_MARKER not in mission_file.read_text(encoding="utf-8"):
        raise EmitError(
            f"the mission at {MISSION_PATH} does not carry {RAW_MBO_SECTION_MARKER!r}, so it "
            "never asks the raw-MBO retention question and a spawn against it cannot answer "
            "it. D68 requires the report to cover the calcs AND the full raw MBO. Restore "
            "section 9a rather than spawning against a mission that omits it."
        )

    contract_file = repo_root / CONTRACT_PATH
    contract_now = _file_sha256(contract_file)
    contract_bound = _lookup(identity, "calculation_contract_sha256")
    if contract_now != contract_bound:
        raise EmitError(
            f"the calculation contract on disk hashes to {contract_now} but the run bound "
            f"{contract_bound}"
        )

    try:
        crosswalk_body = crosswalk(
            None,
            arm=arm,
            result=result,
            delivery_receipt=receipt,
            stream_receipt=stream_receipt_body,
            knowledge_receipt=knowledge_receipt_body,
            outputs_receipt=outputs_receipt_body,
            sealed_proof=sealed_proof_body,
            ledger_dir=None if ledger_dir is None else Path(ledger_dir),
        )
        gate_applicable_inputs(crosswalk_body)
    except CrosswalkGateError as exc:
        raise EmitError(str(exc)) from exc
    except CrosswalkError as exc:
        raise EmitError(f"cannot compute the input-layer crosswalk: {exc}") from exc
    if knowledge_receipt_body is None:
        raise EmitError("the accounted input gate returned without a knowledge receipt")
    try:
        # One object, one authority: this is the exact receipt instance crosswalk() gated.
        # Re-loading here would allow the prompt to name knowledge other than the knowledge
        # whose delivery status authorized emission.
        knowledge_block = render_knowledge_block(knowledge_receipt_body)
    except KnowledgeDeliveryError as exc:
        raise EmitError(f"cannot render the gated knowledge receipt: {exc}") from exc

    cutoffs = _lookup(traversal, "invocation_cutoffs")
    if not isinstance(cutoffs, list) or not cutoffs:
        raise EmitError(
            "the run staged no invocation cutoffs; there is no lawful decision point to "
            "spawn against, which is a cadence defect and not an empty day"
        )
    days = sorted({str(cut["source_day"]) for cut in cutoffs})
    if len(days) != 1:
        raise EmitError(
            "each Frankie run must cover exactly one source day; the four-day roster is "
            "four sequential daily runs with frozen A_MEMORY carried into the next day"
        )
    sections_fed = _lookup(traversal, "sections_fed")
    # BY LOOKUP, like every other slot. Absent, the evidence block says the run's own
    # retention receipts are unstated rather than silently rendering an empty list, because
    # "you were given nothing" and "we did not record what you were given" are different facts.
    retention = result.get("ledger_retention") or {}

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
    add("**you compute every current `### 4.x` contract section yourself**, from the complete")
    add("causal stream, per")
    add("the calculation contract. Greg, 2026-09-02: *\"he gets every record of every field for")
    add("Sunday, the date and time we are running\"* and *\"this has to exactly mimic how it's")
    add("going to come in rt.\"* The runner captured, retained and proved that nothing was")
    add("dropped; it did not do your work, and its calculations are not your evidence.")
    add("**No calculation section may be silently omitted.** Every contract section gets its")
    add("own computed result; an empty lawful population is an explicit `NULL_RESULT`, not a")
    add("missing calculation. The output-bundle gate refuses the whole spawn if any required")
    add("section ledger is absent. The current eighteen section identities are the minimum")
    add("baseline, and every later contract heading grows the required set automatically.")
    add("These calculations are **not a set of math exercises**. Use them to uncover causal market mechanics,")
    add("relationships, falsifiers and possible signals, including where")
    add("non-exhaustion behavior does or does not connect to exhaustion. The job is to explain")
    add("what the market is doing and what the evidence rules out, not merely to fill ledgers.")
    add("")
    add(knowledge_block)
    add("")
    add("## INITIAL FOUR-DAY INPUT ISOLATION")
    add("")
    add("Reliable day-aligned October 2021 values are not currently available for these")
    add("contemporaneous non-MBO context families: weather, storage, COT/positioning, pipeline/LNG,")
    add("production/demand, grid/nuclear/solar, STEO, options, cash basis, macro, and equivalent")
    add("fundamental or external feeds. For these initial four one-day runs, classify those inputs")
    add("as `IGNORE_AS_EVIDENCE`: do not infer, fabricate, backfill, retrieve, or use them in a")
    add("calculation, finding, causal explanation, hypothesis, falsifier, or elimination recommendation.")
    add("Their input identities are preserved for later phases and later source days where reliable")
    add("aligned values are available; this is temporary isolation, not deletion and not a zero-value")
    add("judgment. Native raw MBO, lawful raw/derived MBO transformations, the binding mission and")
    add("calculation contract, and the 44 A_MEMORY seed findings remain in scope. Historical mentions")
    add("of an external input within those findings are provenance, not permission to substitute")
    add("contemporaneous external data that is unavailable for these dates.")
    add("")
    add("## The evidence")
    add("")
    crosswalk_totals = crosswalk_body["totals"]
    add(f"Computed layer crosswalk `{crosswalk_body['crosswalk_sha256']}`: ")
    add(
        f"{crosswalk_totals['inputs_accounted']:,} of "
        f"{crosswalk_totals['inputs_applicable']:,} applicable input layers accounted "
        f"({crosswalk_totals['inputs_delivered']:,} delivered; "
        f"{crosswalk_totals['principal_stamped']:,} principal-stamped)."
    )
    add("")
    add("Every record of every field for the day being run, delivered at each F_LAST cutoff in")
    add("causal order, never ahead. Three exact ledgers, each downloaded, gunzipped and verified")
    add("byte-for-byte against the box's own `PLAIN_SHA256SUMS` and `PLAIN_SIZES`:")
    add("")
    for name in EXACT_LEDGERS:
        entry = delivered[name]
        bound = ""
        sink = retention.get(name) if isinstance(retention, Mapping) else None
        if isinstance(sink, Mapping) and isinstance(sink.get("sha256"), str):
            # THE BINDING THAT MAKES "THIS LEDGER IS THIS RUN'S" TRUE. The sink hashed the
            # file as it wrote it; the delivery hashed the file as it arrived. Different
            # programs, different machines, one number - or a refusal.
            if sink["sha256"] != entry["plain_sha256_observed"]:
                raise EmitError(
                    f"{name}: the delivered file hashes to {entry['plain_sha256_observed']} "
                    f"but the run's sink wrote {sink['sha256']}; this is not the ledger this "
                    "run retained, and a spawn against it would bind him to another run's rows"
                )
            bound = (f" - BOUND to this run: sha256 equals the sink's, "
                     f"{int(sink.get('row_count', 0)):,} rows, {int(sink.get('bytes', 0)):,} bytes as written")
        add(f"- `{name}`: `{entry['local_path']}` ({int(entry['plain_bytes_observed']):,} bytes, "
            f"sha256 `{entry['plain_sha256_observed']}`){bound}")
    add("")
    add(f"Consume them through `{STREAM_MODULE}` - `CausalGroupStream(member, lifecycle, legacy,")
    add(f"run_id=..., arm={arm!r})` and `iterate()`. It hands you one F_LAST-closed group at a")
    add("time in `ts_recv_ns` order, byte-identical to the ledger, with the lifecycle and legacy")
    add("rows whose own clocks are at or before that group's cutoff. There is no random access:")
    add("peek, seek, rewind and indexing raise. Its closing `stream_receipt()` is the proof of")
    add("what you consumed; write it beside your artifact and cite its sha256 below.")
    add("")
    add(f"Delivery receipt `{receipt['receipt_sha256']}` (run {receipt['run_id']} at")
    add(f"`s3://{receipt['bucket']}/{receipt['run_prefix']}`).")
    add("")
    add("### What the runner produced, and what it is for")
    add("")
    add(f"- `calculation_result.json` at `{result_path}` (`evidence_result_hash` `{result_hash}`)")
    if evidence_uri:
        add(f"  durable copy `{evidence_uri}`")
    add("  is **NOT your evidence**. It is the runner's own pass over the same stream, retained")
    add("  for the section 6 gates; it may be compared AFTER you file against what you computed,")
    add("  never read first, never adopted. A finding that agrees with it is not thereby")
    add("  confirmed and one that disagrees is not thereby wrong; the stream decides.")
    add(f"- Verdict `{verdict}`, failed gates {_lookup(result, 'failed_gates') or 'none'}, "
        f"completion `{_lookup(result, 'completion_status')}`")
    add(f"- Source traversed: `{Path(str(_lookup(result, 'slice.sources')[0])).name}`")
    add(f"- Coverage: {coverage['records_seen']:,} records, {coverage['groups_seen']:,} groups, "
        f"{coverage['groups_f_last_closed']:,} F_LAST-closed")
    add(f"- Integrity: {coverage['cursor_discontinuities']} cursor discontinuities, "
        f"{coverage['duplicate_group_indices']} duplicate group indices, "
        f"{coverage['fifo_reconstruction_failures']} FIFO reconstruction failures")
    add("")
    add("Do not guess at what you have not streamed, and say what you did not read.")
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
    # THE RAW-MBO HALF, RENDERED WITH WHAT HE CAN AND CANNOT SEE STATED. Asking the question
    # without saying which evidence is absent invites a confident judgement on data he never
    # received, which is the defect this programme exists to catch.
    add("## The raw MBO, which is section 9a and is REQUIRED")
    add("")
    add("**This is not the calculation question.** Every current contract calculation is")
    add("settled and kept - the previously measured outputs were about 1.78% of the bytes,")
    add("and none can be argued")
    add("away on cost. Do not answer this with a verdict on the calculations; that has")
    add("happened every time it was asked and it is not an answer.")
    add("")
    add("Judge the RAW MBO: the retained per-record fields, the reconstructed book including")
    add("`book_full`, the ladder, the legacy observable rows and the per-second substrate.")
    add("Classify each field or field group as LOAD_BEARING, RETAINED_UNREAD,")
    add("DEGENERATE_ON_THIS_SLICE, REDUNDANT or CANNOT_JUDGE, with evidence, per section 9a.")
    add("")
    add("**Keep-everything is a first-class answer and carries no penalty.** If every field")
    add("earns its retention, say so and say why. You ADVISE; nothing is removed on your")
    add("say-so, and any removal is Greg's decision after discussion.")
    add("After inspecting the full raw MBO, assess whether any raw-data layer or field group")
    add("makes **exactly zero useful contribution**—its ongoing ingestion provides no value to your")
    add("calculations, causal interpretation, discovery, falsification or hypotheses. If the")
    add("evidence supports that conclusion, recommend it for elimination and show why; Greg")
    add("decides whether it is eliminated. You are under no obligation to identify one, and")
    add("must not manufacture a casualty because the question was asked.")
    add("**Zero value is the bar.** Low value, infrequent value or poor value per byte does not")
    add("qualify. If it has even a little credible present or future informational value, KEEP")
    add("it. Size matters only after zero value is established; it never makes useful data expendable.")
    add("That applies explicitly to `book_full` and FIFO identities/queues, to the whole surface and every constituent part:")
    add("each field, depth level, order identity, queue, queue-position fact and derived component.")
    add("No surface or constituent part may be recommended unless it independently meets the")
    add("same zero-value bar. Their size is not evidence that they are expendable.")
    add("For any elimination recommendation, quantify the practical case as far as the run")
    add("allows: retained bytes per record and per day, downstream duplicate/derived storage,")
    add("avoidable ingestion or calculation work, and every dependent calculation or future")
    add("question that would lose evidence. The point is meaningful space and work saved only")
    add("when information is genuinely valueless, not a smaller schema for its own sake.")
    add("")
    causal_layers = [
        row for row in crosswalk_body["layers"]
        if row.get("policy") == "CAUSAL_STREAM_REQUIRED"
    ]
    raw_layers = [row for row in causal_layers if row.get("group_id") != "derived_geometry"]
    geometry_layers = [row for row in causal_layers if row.get("group_id") == "derived_geometry"]
    add("Review both the per-field census and **every individual causal registry layer**.")
    add(f"The current gated roster is {len(causal_layers)} layers: {len(raw_layers)} raw/non-geometry")
    add(f"MBO identities plus {len(geometry_layers)} derived-geometry identities. Derived surfaces")
    add("such as dipole are included, but distinguish dropping a transform from dropping its raw")
    add("inputs. The registry is authoritative; later additions grow this review automatically.")
    add("Do not let a group-level judgement hide an individual layer. The roster you must cover is:")
    add("")
    causal_group_order: list[str] = []
    for row in causal_layers:
        group_id = str(row["group_id"])
        if group_id not in causal_group_order:
            causal_group_order.append(group_id)
    for group_id in causal_group_order:
        group_rows = [row for row in causal_layers if row["group_id"] == group_id]
        identities = ", ".join(f"`{row['layer_id']}`" for row in group_rows)
        add(f"- `{group_id}` ({len(group_rows)}): {identities}")
    add("")
    add("### What you are actually given, so `CANNOT_JUDGE` is used honestly")
    add("")
    add("The three exact ledgers above, whole and verified, streamed to you group by group. What")
    add("the runner's sink recorded as it wrote them, for comparison with what arrived:")
    add("")
    for name, sink in sorted(retention.items()):
        add(f"- `{name}`: {int(sink.get('row_count', 0)):,} rows, "
            f"{int(sink.get('bytes', 0)):,} bytes written on the box at "
            f"`{sink.get('path', 'unknown')}`; delivered to you at "
            f"`{delivered[name]['local_path'] if name in delivered else 'no exact ledger of that name'}`")
    if not retention:
        add("- the run recorded no ledger retention receipts, so what the sink wrote is")
        add("  itself unstated; the binding of the delivered files to this run then rests on the")
        add("  box's `PLAIN_SHA256SUMS` alone, which the delivery receipt verified against")
    add("")
    # THE MEASUREMENT BEHIND 9a. Every retained member row was censused per field path; a
    # result without the census, or with a census that saw fewer rows than were written,
    # cannot support the classification and the spawn HALTS rather than asking anyway.
    census = _lookup(result, "layers.exact_member_ledger.field_census")
    member_rows = _lookup(result, "layers.exact_member_ledger.exact_member_rows")
    if not isinstance(census, Mapping) or census.get("rows_observed") != member_rows:
        raise EmitError(
            "field census does not cover every member row: "
            f"rows_observed={census.get('rows_observed') if isinstance(census, Mapping) else None} "
            f"exact_member_rows={member_rows}"
        )
    if _lookup(result, "layers.exact_member_ledger.field_census_covers_every_member_row") is not True:
        raise EmitError("the run itself reports the field census as partial")
    degenerate = list(census.get("degenerate_fields") or [])
    always_null = list(census.get("always_null_fields") or [])
    add("### The field census, measured on every retained member row")
    add("")
    add(f"`layers.exact_member_ledger.field_census`: {census['rows_observed']:,} rows censused, "
        f"{census['field_count']:,} field paths. Per path it carries observations, rows-with-field,")
    add("nulls, distinct values (capped at "
        f"{census['distinct_cap']}), types and numeric range. `[]` marks a list whose every")
    add("element is counted under one path, because a position in a ladder is not a field.")
    add("**It is a measurement, not a recommendation.** A field degenerate on this slice may")
    add("vary on another day; where one slice cannot settle it, say CANNOT_JUDGE.")
    add("")
    add(f"**{len(degenerate)} fields carried exactly one value throughout:**")
    add("")
    add("| field | only value | rows with field |")
    add("|---|---|---:|")
    for row in degenerate:
        add(f"| `{row['field']}` | `{row['only_value']!r}` | {row['rows_with_field']:,} |")
    add("")
    add(f"**{len(always_null)} fields were present and null on every observation:**")
    add("")
    for name in always_null:
        add(f"- `{name}`")
    if not always_null:
        add("- none")
    add("")
    add("Your exact-member claims rest on rows you streamed, not on the runner's counters.")
    add("**Say which fields you could not assess and why.** An honest CANNOT_JUDGE is worth")
    add("more than a guess.")
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
        # D81: the ledgers were delivered and verified, so READ is the only honest answer
        # for each; the staging gate refuses NOT_READ when a delivery receipt is cited.
        "evidence_read": {name: "READ" for name in EXACT_LEDGERS},
        "delivery_receipt_sha256": receipt["receipt_sha256"],
        "stream_receipt_sha256": (
            "<sha256 of the stream receipt your CausalGroupStream run wrote: "
            "canonical_hash(stream_receipt(), omit='receipt_sha256')>"
        ),
        # F-25: the staging gate validates the output bundle he wrote and refuses an
        # artifact whose citation does not equal the validator's computed receipt.
        "outputs_receipt_sha256": (
            f"<receipt_sha256 of the {outputs.RECEIPT_FILENAME} in the output bundle you "
            "wrote; see 'Your output bundle' below>"
        ),
        "run_id": run_id,
        "source_day": "<the one manifest-roster source day this artifact covers>",
        "findings": [
            "<new findings only; [] is valid; every finding carries a persistent global id, "
            "claim, evidence, falsifier, confidence_basis, and exact exemplars>"
        ],
    }, indent=2))
    add("```")
    add("")
    add("`load_principal_artifact` refuses a missing artifact, a different")
    add("`evidence_result_hash`, `controller_only` true, an artifact that does not attest an")
    add("actual invocation, a findings value that is not a list, an artifact that does not declare")
    add("`evidence_read` for every exact ledger, and an artifact that")
    add("cites a delivery receipt but no `outputs_receipt_sha256` (or one whose bundle does")
    add("not validate to that receipt). A committed artifact with `findings: []` is a legitimate")
    add("completed day with no novelty: it adds no memory entry. A missing artifact still means")
    add("the spawn did not happen and is refused.")
    add("")
    add("**Return only findings that are new to the memory you were served.** Finding `id` is")
    add("global and persistent across days: reuse an existing id only for the identical finding;")
    add("the carry deduplicates an identical id and refuses the same id with changed content.")
    add("Do not restart a local `F-01` counter each day. The automatic carry is triggered only")
    add("after this artifact is committed under `principal_runs/<run_id>/`; an empty JSON remains")
    add("a run receipt and is not copied into served memory.")
    add("")
    add("**`evidence_read` must be READ for every ledger, and NOT_READ is refused.** The")
    add("ledgers were delivered to you whole and verified, so a ledger you did not read is a")
    add("failed spawn, not a caveat. Cite `delivery_receipt_sha256` exactly as above and")
    add("`stream_receipt_sha256` from the receipt your own stream wrote; the staging gate")
    add("refuses NOT_READ on any artifact that cites a delivery receipt.")
    add("")
    add("## Your output bundle")
    add("")
    add("Everything you produce as the stream advances is written to an output bundle -")
    add(f"schema `{outputs.OUTPUT_BUNDLE_SCHEMA}` - in a directory beside your artifact")
    add(f"(`principal_outputs/`): one JSON per ledger under `{outputs.LEDGERS_DIRNAME}/` and")
    add(f"a `{outputs.RECEIPT_FILENAME}` (schema `{outputs.OUTPUT_RECEIPT_SCHEMA}`) whose")
    add("`receipt_sha256` is the `outputs_receipt_sha256` you cite above. The staging gate")
    add("validates the bundle against the registry, the calculation contract, the delivery")
    add("receipt and the knowledge receipt, and refuses your artifact if its citation does")
    add("not equal the receipt the validator computes.")
    add("")
    add("**The ledgers are append-only and chain-hashed.** Every entry carries a monotone")
    add("`sequence`, a nondecreasing `cutoff_recv_ns` (the F_LAST `ts_recv_ns` after which")
    add("you wrote it - contract section 2), a `body`, and `entry_hash = sha256(prev_hash +")
    add("canonical(entry))` from `sha256(b\"\")`. An edited entry breaks its own hash chain, a")
    add("reordered one breaks its sequence, a moved one breaks the cutoff order. Nothing is")
    add("rewritten; a re-write that is not a pure extension is refused.")
    add("")
    add("**The required set is derived at validation time, and there is no count** - no")
    add("historical number is a spec (DROP_IN_S121 item zero, D60). The bundle must carry:")
    add("")
    add(f"- every layer id of the registry's `{outputs.APPEND_ONLY_OUTPUTS_GROUP}` group;")
    add(f"- one ledger per `### 4.x` heading of the calculation contract, named")
    add(f"  `{outputs.SECTION_LEDGER_PREFIX}<id>` (4.0 and 4.0b included);")
    add(f"- `{outputs.RAW_MBO_CLASSIFICATION_LEDGER}` - the mission's section 9a")
    add("  classification, which advises and never drops (D60, D76);")
    add(f"- `{outputs.KNOWLEDGE_VERIFICATION_LEDGER}` - one verdict per delivered lesson")
    add("  (VERIFIED / UNVERIFIED / REFUTED against the stream), citing the knowledge")
    add("  receipt.")
    add("")
    add("Every timing is written on a named causal clock as `{clock, observed_ns}`; a fixed")
    add("ladder label names no clock and is refused (D83). A helper is a tool invocation")
    add("inside your role, never a lane (D63/D64). Invocation receipts attest an AGENT")
    add("SESSION, never an API call (D70). No body names a desktop or session-local path")
    add("(D34). Check your own bundle before you file:")
    add("")
    add("```")
    add("python3 -m research.kalshi.frankie_raw_mbo_benchmark.native_principal_outputs validate \\")
    add(f"    --dir <your principal_outputs dir> --arm {arm}")
    add("```")
    add("")
    add("It prints the receipt or `REFUSED: <why>`; a refused bundle is a failed spawn.")
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

    # THE SOURCE DAY STATED TO THE PRINCIPAL, not left for him to infer from the cutoff
    # table. A bounded canary uses fewer than the source object's full MBO, so "one day"
    # alone would overclaim its coverage. Production is four sequential complete-day runs;
    # canaries remain honest partial slices of exactly one of those source days.
    add(f"**This run is ONE SOURCE DAY: {days[0]}.** The mission is executed as four")
    add("sequential daily runs for October 1, 3, 4 and 5, with each finished day's frozen")
    add("A_MEMORY carried into the next. Never combine their evidence in one run.")
    if bool(_lookup(result, "slice.is_complete_source_day")):
        add("**This is the complete raw-MBO traversal for that one source day.**")
    else:
        add("**This is a bounded/reduced-MBO slice, not proof of a complete day.**")
    add("Any question needing a cross-day comparison can only be answered WITHIN this day.")
    add("Say which those are and mark them unanswerable on this slice. Do not report a")
    add("single-day reading as if it settled a question the mission asks across days.")
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
    parser.add_argument(
        "--delivery-receipt", required=True,
        help="FRANKIE_LEDGER_DELIVERY_RECEIPT_V1 written by fetch_frankie_ledgers; every "
             "exact ledger must be VERIFIED or the spawn is refused (D81)",
    )
    parser.add_argument("--stream-receipt", default=None)
    parser.add_argument("--knowledge-receipt", default=None)
    parser.add_argument("--outputs-receipt", default=None)
    parser.add_argument("--sealed-proof", default=None)
    parser.add_argument("--ledger-dir", default=None)
    parser.add_argument("--evidence-uri", default=None, help="durable S3 URI, for the record")
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)
    try:
        text = emit(
            args.result,
            delivery_receipt=args.delivery_receipt,
            stream_receipt=args.stream_receipt,
            knowledge_receipt=args.knowledge_receipt,
            outputs_receipt=args.outputs_receipt,
            sealed_proof=args.sealed_proof,
            ledger_dir=args.ledger_dir,
            evidence_uri=args.evidence_uri,
        )
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
