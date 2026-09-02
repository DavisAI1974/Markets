"""The independent witness for a run's size, because the sink counting its own writes is not one.

**Why this exists.** Four size numbers in one session were present, typed, plausible, and
measuring something other than what their name implied: 24 KB per record (read off an
artifact `upload-artifact` had already compressed), 215 KB per record (CloudWatch bytes over
a record count nobody read), a 9:1 compression ratio (derived from the discrepancy it was
invoked to explain), and "key names are 57.3% of a row" (measured on an invented row). The
figure that replaced them, 246,030 bytes per record, is better evidenced and still
SELF-REPORTED: it comes from `ledger_retention[*].bytes`, which is the sink counting its own
writes.

**The witness.** S3 recorded a size for every object the run copied to it, independently, with
no stake in the answer. If S3's byte count for a ledger equals the receipt's, the receipt is
confirmed by a second party. If it does not, the sink is miscounting and every figure
downstream moves.

**The one discipline this module enforces.** A per-record figure is only ever emitted with
both of the quantities it divides named and sourced. `bytes_per_record` here is S3's bytes
over the traversal's records, and it is REFUSED outright when either side is missing rather
than falling back to the self-reported number - a fallback is how a witnessed figure and an
unwitnessed one end up printed in the same font.

**Three outcomes, not two.** CONFIRMED and CONTRADICTED are the interesting ones;
WITNESS_UNAVAILABLE is the one that matters most in practice, because a packet that was never
uploaded, or was uploaded gzipped, produces a byte count that legitimately does not match and
must never be reported as a contradiction of the sink.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import PurePosixPath
from typing import Any, Mapping, Sequence

CONFIRMED = "CONFIRMED"
CONTRADICTED = "CONTRADICTED"
UNAVAILABLE = "WITNESS_UNAVAILABLE"

# Reasons a ledger has no witness. Each is a different fact and they are never merged: an
# absent object means the packet did not land, a compressed one means it landed in a form
# whose size answers a different question.
ABSENT = "ABSENT_FROM_S3"
COMPRESSED = "PRESENT_ONLY_COMPRESSED"
AMBIGUOUS = "BASENAME_MATCHES_SEVERAL_KEYS"
NO_CLAIMED_BYTES = "RECEIPT_CARRIES_NO_BYTE_COUNT"
NO_CLAIMED_DIGEST = "RECEIPT_CARRIES_NO_SHA256"
NO_RECORD_COUNT = "RECORD_COUNTS_ABSENT"


class WitnessError(ValueError):
    """A run could not be witnessed at all, as distinct from being contradicted."""


def _receipts(result: Mapping[str, Any]) -> Mapping[str, Mapping[str, Any]]:
    receipts = result.get("ledger_retention")
    if not isinstance(receipts, Mapping) or not receipts:
        # Refused rather than witnessed empty. `stream_ledgers=False` writes no receipts, and
        # a run with nothing to witness must not report as a run that was witnessed clean.
        raise WitnessError(
            "result carries no ledger_retention block; there is nothing to witness, which is "
            "not the same as a witness that agreed"
        )
    return receipts


def common_prefix(objects: Mapping[str, int]) -> str:
    """The run this witness actually examined, derived from the keys rather than passed in.

    A caller-supplied label can disagree with the data; a prefix computed from the keys
    cannot. This exists because the first live run witnessed the WRONG RUN and reported
    CONFIRMED: the default lookup takes the newest `calculation_result.json` under the tree,
    and the newest was a push-CI canary rather than the 50,001-record run whose figure was in
    question. Green under a heading that names no run reads as the question being settled.
    """
    keys = sorted(objects)
    if not keys:
        return ""
    first, last = keys[0], keys[-1]
    cut = len(first)
    for index, char in enumerate(first):
        if index >= len(last) or last[index] != char:
            cut = index
            break
    return first[:cut].rsplit("/", 1)[0] if "/" in first[:cut] else first[:cut]


def _index_by_basename(objects: Mapping[str, int]) -> dict[str, tuple[str, int] | None]:
    """Basename -> (key, size), or None when several keys share the basename.

    A dict built by assignment keeps the LAST key silently, so `ledgers/rows.jsonl` and
    `backup/rows.jsonl` under one prefix would witness a ledger against whichever happened to
    sort later. None marks the collision so it is REFUSED rather than answered from a coin
    flip - a wrong witness is worse than no witness.
    """
    index: dict[str, tuple[str, int] | None] = {}
    for key, size in objects.items():
        name = PurePosixPath(key).name
        index[name] = None if name in index else (key, int(size))
    return index


def witness_ledgers(
    result: Mapping[str, Any], objects: Mapping[str, int]
) -> list[dict[str, Any]]:
    """One row per ledger: what the sink said, what S3 says, and whether they agree."""
    rows: list[dict[str, Any]] = []
    index = _index_by_basename(objects)
    for name, receipt in sorted(_receipts(result).items()):
        basename = PurePosixPath(str(receipt.get("path") or "")).name
        raw_claim = receipt.get("bytes")
        claimed = int(raw_claim) if isinstance(raw_claim, int) else 0
        row: dict[str, Any] = {
            "ledger": name,
            "file": basename,
            "claimed_bytes": claimed,
            "witnessed_bytes": None,
            "s3_key": None,
            "status": UNAVAILABLE,
            "reason": ABSENT,
        }
        if not isinstance(raw_claim, int):
            # Nothing to witness AGAINST. Treating a missing count as zero would report the
            # whole object as a discrepancy and convict the sink of an error it never made.
            row["reason"] = NO_CLAIMED_BYTES
            rows.append(row)
            continue
        if index.get(basename) is None and basename in index:
            row["reason"] = AMBIGUOUS
        elif basename in index:
            key, size = index[basename]
            row["s3_key"] = key
            row["witnessed_bytes"] = size
            row["reason"] = None
            row["status"] = CONFIRMED if size == claimed else CONTRADICTED
            row["delta_bytes"] = size - claimed
        elif index.get(f"{basename}.gz") is not None:
            # A gzip's size answers "how well did it compress", never "how many bytes did the
            # sink write". Reporting the difference as a contradiction would convict the sink
            # of an error committed by the upload path.
            key, size = index[f"{basename}.gz"]
            row["s3_key"] = key
            row["compressed_bytes"] = size
            row["reason"] = COMPRESSED
        rows.append(row)
    return rows


def witness_denominator(result: Mapping[str, Any]) -> dict[str, Any]:
    """The denominator nobody checked for the 215 KB figure, checked here.

    Three quantities that must agree, each read from a different place in the result: the
    manifest's declared total, the traversal's own count, and the coverage receipt the
    identity gate is computed against.
    """
    identity = ((result.get("layers") or {}).get("identity_receipt") or {})
    coverage = identity.get("coverage") or {}
    traversal = result.get("traversal") or {}
    values = {
        "manifest_total_mbo_records": identity.get("total_mbo_records"),
        "traversal_records_seen": traversal.get("records_seen"),
        "coverage_records_seen": coverage.get("records_seen"),
    }
    present = [v for v in values.values() if isinstance(v, int) and not isinstance(v, bool)]
    agree = len(present) == len(values) and len(set(present)) == 1
    if agree:
        status = CONFIRMED
    elif len(set(present)) > 1:
        # Two quantities that should be the same number are not. That is a real disagreement.
        status = CONTRADICTED
    else:
        # One or more simply is not there. ABSENT is not DISAGREEING, and the module refuses
        # to accuse the sink of an error on the strength of evidence it does not have.
        status = UNAVAILABLE
    return {
        "values": values,
        "status": status,
        "agree": agree,
        # Only when ALL THREE agree. Taking the value because the PRESENT ones agree is the
        # same defect in miniature: two of three quantities matching says nothing about the
        # one that is missing, and a caller reading `records` would emit a per-record figure
        # off a basis that was never complete. A test drove this out.
        "records": present[0] if agree else None,
    }


def witness_content(
    result: Mapping[str, Any], observed: Mapping[str, str]
) -> list[dict[str, Any]]:
    """A size witness proves length, never content. This compares a downloaded file's digest.

    Only whatever the caller actually downloaded is checked; a ledger nobody fetched is
    reported as unchecked rather than assumed good.
    """
    rows: list[dict[str, Any]] = []
    receipts = _receipts(result)
    for ledger, digest in sorted(observed.items()):
        receipt = receipts.get(ledger)
        if receipt is None:
            raise WitnessError(f"content witness names ledger {ledger!r}, which has no receipt")
        claimed = str(receipt.get("sha256") or "")
        if not claimed:
            # No digest to compare against is not a mismatch.
            rows.append({"ledger": ledger, "claimed_sha256": "", "observed_sha256": digest,
                         "status": UNAVAILABLE, "reason": NO_CLAIMED_DIGEST})
            continue
        rows.append({
            "ledger": ledger,
            "claimed_sha256": claimed,
            "observed_sha256": digest,
            "status": CONFIRMED if digest == claimed else CONTRADICTED,
        })
    return rows


def verdict(
    ledger_rows: Sequence[Mapping[str, Any]],
    denominator: Mapping[str, Any],
    content_rows: Sequence[Mapping[str, Any]] = (),
) -> str:
    statuses = [row["status"] for row in ledger_rows] + [row["status"] for row in content_rows]
    statuses.append(denominator.get("status", UNAVAILABLE))
    if CONTRADICTED in statuses:
        return CONTRADICTED
    if UNAVAILABLE in statuses or not statuses:
        return UNAVAILABLE
    return CONFIRMED


def render(
    result: Mapping[str, Any],
    objects: Mapping[str, int],
    observed: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    """Returns (markdown, verdict)."""
    ledger_rows = witness_ledgers(result, objects)
    denominator = witness_denominator(result)
    content_rows = witness_content(result, observed or {})
    outcome = verdict(ledger_rows, denominator, content_rows)

    claimed_total = sum(row["claimed_bytes"] for row in ledger_rows)
    witnessed = [row for row in ledger_rows if row["witnessed_bytes"] is not None]
    witnessed_total = sum(row["witnessed_bytes"] for row in witnessed)
    fully_witnessed = len(witnessed) == len(ledger_rows) and bool(ledger_rows)

    lines: list[str] = []
    add = lines.append
    traversal = result.get("traversal") or {}
    add("## The independent witness")
    add("")
    add(f"- Verdict: **{outcome}**")
    # THE RUN IS NAMED IN THE HEADING, with its size beside it. Both are here because a
    # verdict with no subject is the failure this module already committed once: it
    # confirmed a run nobody had asked about, and nothing on the page said which run it was.
    add(f"- Run witnessed: `{common_prefix(objects)}`")
    def _count(value: Any) -> str:
        return f"{value:,}" if isinstance(value, int) and not isinstance(value, bool) else "absent"

    add(f"- Records / groups in that run: **{_count(traversal.get('records_seen'))}** / "
        f"{_count(traversal.get('groups_seen'))}")
    add(f"- Objects listed under the run prefix: {len(objects):,}")
    add("")
    add("### Ledger bytes: what the sink counted vs what S3 holds")
    add("")
    add("| ledger | file | sink bytes | S3 bytes | delta | status |")
    add("|---|---|---:|---:|---:|---|")
    for row in ledger_rows:
        s3 = f"{row['witnessed_bytes']:,}" if row["witnessed_bytes"] is not None else "-"
        delta = f"{row['delta_bytes']:+,}" if "delta_bytes" in row else "-"
        status = row["status"] if not row["reason"] else f"{row['status']} ({row['reason']})"
        add(f"| {row['ledger']} | `{row['file']}` | {row['claimed_bytes']:,} | {s3} "
            f"| {delta} | {status} |")
    add("")
    add(f"- Sink total: **{claimed_total:,}**")
    add(f"- S3 total over the ledgers it holds: **{witnessed_total:,}**"
        f" ({len(witnessed)} of {len(ledger_rows)} ledgers)")
    add("")

    add("### The denominator")
    add("")
    add("| quantity | source | value |")
    add("|---|---|---:|")
    sources = {
        "manifest_total_mbo_records": "layers.identity_receipt.total_mbo_records",
        "traversal_records_seen": "traversal.records_seen",
        "coverage_records_seen": "layers.identity_receipt.coverage.records_seen",
    }
    for name, value in denominator["values"].items():
        shown = f"{value:,}" if isinstance(value, int) else "absent"
        add(f"| {name} | `{sources[name]}` | {shown} |")
    add("")
    add(f"- Agree: **{denominator['agree']}** ({denominator['status']})")
    add("")

    if content_rows:
        add("### Content, not just length")
        add("")
        add("| ledger | sink sha256 | downloaded sha256 | status |")
        add("|---|---|---|---|")
        for row in content_rows:
            claimed = f"`{row['claimed_sha256'][:16]}...`" if row["claimed_sha256"] else "absent"
            status = row["status"] + (f" ({row['reason']})" if row.get("reason") else "")
            add(f"| {row['ledger']} | {claimed} "
                f"| `{row['observed_sha256'][:16]}...` | {status} |")
        add("")

    add("### Bytes per record")
    add("")
    records = denominator.get("records")
    if fully_witnessed and isinstance(records, int) and records > 0:
        add(f"- **{witnessed_total / records:,.0f} bytes per record** "
            f"({witnessed_total / records / 1024:.1f} KiB)")
        add("- Numerator: S3 `ContentLength` summed over every ledger object, read from the"
            " object store.")
        add("- Denominator: `traversal.records_seen`, agreeing with the manifest total and"
            " the coverage receipt.")
        add("- Neither quantity is the sink's own tally of its own writes.")
        if any(row["status"] == CONTRADICTED for row in content_rows):
            # LENGTH was witnessed; CONTENT was not. Those are different claims and the
            # stronger-sounding one must not be allowed to carry the weaker.
            add("- **This figure is about LENGTH only.** A content witness above disagreed,"
                " so the bytes are confirmed while the rows in them are not.")
    else:
        # REFUSED, not approximated. Emitting the self-reported figure here is exactly how an
        # unwitnessed number acquires the authority of a witnessed one.
        add("- **REFUSED.** A per-record figure needs two independently sourced quantities and"
            " this run does not supply both.")
        if not fully_witnessed:
            add(f"  - Numerator unavailable: only {len(witnessed)} of {len(ledger_rows)}"
                " ledgers have an uncompressed S3 object.")
        if not isinstance(records, int):
            add(f"  - Denominator unavailable ({denominator['status']}): the three record"
                " counts do not agree, or one is absent.")
    add("")
    return "\n".join(lines), outcome


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", required=True,
                        help="calculation_result.json for the run")
    parser.add_argument("--objects", required=True,
                        help="JSON mapping of S3 key -> size in bytes, from list-objects-v2")
    parser.add_argument("--observed-sha256", action="append", default=[],
                        metavar="LEDGER=HEX",
                        help="digest of a ledger file actually downloaded; repeatable")
    parser.add_argument("--summary", default=None,
                        help="append the report here too, e.g. $GITHUB_STEP_SUMMARY")
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)

    result = json.loads(open(args.result, encoding="utf-8").read())
    objects = json.loads(open(args.objects, encoding="utf-8").read())
    observed: dict[str, str] = {}
    for pair in args.observed_sha256:
        ledger, _, digest = pair.partition("=")
        if not digest:
            raise SystemExit(f"--observed-sha256 wants LEDGER=HEX, got {pair!r}")
        observed[ledger] = digest

    try:
        text, outcome = render(result, objects, observed)
    except (WitnessError, TypeError, ValueError, KeyError) as exc:
        # EXIT 2, NOT 1. A crash is missing evidence, and reporting it as CONTRADICTED would
        # say the sink is wrong on the strength of this module failing to read the result.
        print(f"witness could not be taken: {exc}", file=sys.stderr)
        if args.output:
            open(args.output, "w", encoding="utf-8").write(
                f"## The independent witness\n\n- Verdict: **{UNAVAILABLE}**\n"
                f"- The witness could not be taken: `{exc}`\n")
        return 2
    if args.output:
        open(args.output, "w", encoding="utf-8").write(text)
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as handle:
            handle.write(text)
    if not args.output and not args.summary:
        print(text)
    # CONFIRMED is the only green outcome. WITNESS_UNAVAILABLE is red on purpose: item zero is
    # then still open, and a green run would be read as having settled it.
    return {CONFIRMED: 0, CONTRADICTED: 1, UNAVAILABLE: 2}[outcome]


if __name__ == "__main__":
    sys.exit(main())
