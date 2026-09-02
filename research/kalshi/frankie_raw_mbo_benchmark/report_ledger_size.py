"""Which calculation is the size. The table that replaces an opinion.

**Why this exists.** A run filled a 300 GB volume in 2h35m and the only thing it left behind
was a total. A total says the run is too big; it says nothing about what to do next. Greg's
question - of the sixteen calculations, which are the size, and does any of it carry no
value - needs bytes attributed to sections and to fields, which is what `native_row_sink`
now records and what this renders.

**Why it is repo code rather than a shell block.** The results land on S3 and an interactive
session resolves no AWS credentials, so only a workflow can read them. Code a workflow calls
can be tested; a heredoc that runs once cannot. The rendering is also the place where a
sampled number is most likely to be quietly presented as an exact one, which is a good
reason for it to have tests.

**The two properties that matter more than the layout.** Section bytes are EXACT and are
merged ACROSS ledgers - reported per ledger, a section spread over three files ranks below a
smaller section concentrated in one, and the widest-spread section is exactly the one a
reader would then leave alone. Field bytes are SAMPLED, and every heading and row carrying
them says so, because a drop decision taken off an unmarked estimate is the failure D60
exists to prevent.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


class ReportError(ValueError):
    """A result could not be rendered into a size table."""


def _merge(receipts: Mapping[str, Mapping[str, Any]], key: str) -> dict[str, int]:
    merged: dict[str, int] = {}
    for receipt in receipts.values():
        for name, value in (receipt.get(key) or {}).items():
            merged[name] = merged.get(name, 0) + int(value)
    return merged


def _merge_fields(receipts: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, int], int, int]:
    merged: dict[str, int] = {}
    sampled = 0
    rates = set()
    for receipt in receipts.values():
        estimate = receipt.get("field_bytes_estimated") or {}
        sampled += int(estimate.get("rows_sampled") or 0)
        if estimate.get("sample_every_nth_row"):
            rates.add(int(estimate["sample_every_nth_row"]))
        for name, value in (estimate.get("bytes_by_field") or {}).items():
            merged[name] = merged.get(name, 0) + int(value)
    if len(rates) > 1:
        # Two ledgers sampled at different rates cannot be summed into one estimate without
        # weighting, and silently summing them would understate whichever sampled less.
        raise ReportError(f"ledgers sampled at different rates {sorted(rates)}; cannot merge")
    return merged, sampled, (rates.pop() if rates else 0)


def _share(value: int, total: int) -> str:
    return f"{100.0 * value / total:.1f}%" if total else "n/a"


def render_report(result_path: Path | str) -> str:
    """Render the size table for one finished run. Returns markdown."""
    result_path = Path(result_path)
    try:
        body = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReportError(f"cannot read {result_path}: {exc}") from exc

    receipts = body.get("ledger_retention")
    if not isinstance(receipts, Mapping) or not receipts:
        # REFUSED, not rendered empty. `stream_ledgers=False` keeps the ledgers in RAM and
        # writes no receipts, so an absent block is reachable by configuration - which is
        # precisely when a table of zeroes would be believed rather than questioned.
        raise ReportError(
            f"{result_path} carries no ledger_retention block; a run that retained nothing "
            "in receipts cannot be reported as a run that cost nothing"
        )

    traversal = body.get("traversal") or {}
    records = int(traversal.get("records_seen") or 0)
    total_bytes = sum(int(r.get("bytes") or 0) for r in receipts.values())
    total_rows = sum(int(r.get("row_count") or 0) for r in receipts.values())

    lines: list[str] = []
    add = lines.append
    add("## Where the bytes went")
    add("")
    add(f"- Verdict: **{body.get('verdict')}** "
        f"(failed gates: {', '.join(body.get('failed_gates') or []) or 'none'})")
    add(f"- Completion: {body.get('completion_status')}")
    add(f"- Groups / records: {traversal.get('groups_seen'):,} / {records:,}"
        if isinstance(traversal.get("groups_seen"), int)
        else f"- Groups / records: {traversal.get('groups_seen')} / {records:,}")
    add(f"- Save points: {traversal.get('save_points')}")
    for source in (body.get("slice") or {}).get("sources") or []:
        add(f"- Source traversed: `{Path(source).name}`")
    add("")
    add(f"- Exact ledger rows: **{total_rows:,}**")
    add(f"- Exact ledger bytes: **{total_bytes:,}**")
    if records:
        add(f"- Bytes **per record**: **{total_bytes / records:,.0f}** "
            f"({total_bytes / records / 1024:.1f} KiB)")
        add("")
        add("  This is the figure that was wrong by 9x and cost a run: it was taken from a"
            " COMPRESSED artifact and called a disk requirement.")
    add("")

    add("### By ledger (exact)")
    add("")
    add("| ledger | rows | bytes | share |")
    add("|---|---:|---:|---:|")
    for name, receipt in sorted(receipts.items(), key=lambda kv: -int(kv[1].get("bytes") or 0)):
        size = int(receipt.get("bytes") or 0)
        add(f"| {name} | {int(receipt.get('row_count') or 0):,} | {size:,} "
            f"| {_share(size, total_bytes)} |")
    add("")

    by_section = _merge(receipts, "bytes_by_section")
    rows_by_section = _merge(receipts, "rows_by_section")
    add("### By emitting section (exact, merged across ledgers)")
    add("")
    add("Merged across ledgers on purpose: reported per file, a section spread over three"
        " ledgers ranks below a smaller one concentrated in a single ledger.")
    add("")
    add("| section | rows | bytes | share | bytes/record |")
    add("|---|---:|---:|---:|---:|")
    for name, size in sorted(by_section.items(), key=lambda kv: -kv[1]):
        per_record = f"{size / records:,.0f}" if records else "n/a"
        add(f"| {name} | {rows_by_section.get(name, 0):,} | {size:,} "
            f"| {_share(size, total_bytes)} | {per_record} |")
    add("")

    by_field, sampled_rows, rate = _merge_fields(receipts)
    add(f"### By field (SAMPLED, 1 row in {rate}) - these are ESTIMATES")
    add("")
    add(f"Scaled from {sampled_rows:,} sampled rows. Exact section totals are above; these"
        " are not exact and must not be quoted as if they were. They exist because the"
        " expensive thing is usually one field rather than one section.")
    add("")
    add("| field | bytes (estimated) | share of ledger bytes (estimated) |")
    add("|---|---:|---:|")
    for name, size in sorted(by_field.items(), key=lambda kv: -kv[1])[:40]:
        add(f"| {name} | ~{size:,} | ~{_share(size, total_bytes)} |")
    add("")
    add("Nothing here is a recommendation to drop anything. D60: a row is USED, or RETAINED"
        " and counted, or REFUSED loudly, and what to drop is discussed before it is done."
        " This says only what each thing costs.")
    add("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--summary", type=Path, default=None,
                        help="append the table here too, e.g. $GITHUB_STEP_SUMMARY")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    text = render_report(args.result)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as handle:
            handle.write(text)
    if not args.output and not args.summary:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
