#!/usr/bin/env python3
"""Print the two run documents from a principal's output bundle: what he learned, and his own words.

Greg, 2026-09-16: "he's supposed to create an analysis doc with his findings, his opinion about
the build, his opinion about the data, any suggestions" and "we want him printing 2 for right
now so we can see what he learned along with his words about it". The two documents are
RENDERS of two append-only ledgers of the validated bundle (`native_principal_outputs`:
`what_he_learned`, `in_his_own_words`); nothing here is authored, so the documents cannot
say anything the chain-hashed ledgers do not. They are written beside his artifact under
`principal_runs/<run_id>/`, where the seed builder carries them into his memory whole.

    python3 -m research.kalshi.frankie_raw_mbo_benchmark.render_frankie_run_documents \\
        --outputs-dir principal_runs/<run_id>/principal_outputs --out-dir principal_runs/<run_id>
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from research.kalshi.frankie_raw_mbo_benchmark import native_principal_outputs as outputs  # noqa: E402

WHAT_HE_LEARNED_FILENAME = "FRANKIE_WHAT_HE_LEARNED.md"
IN_HIS_OWN_WORDS_FILENAME = "FRANKIE_IN_HIS_OWN_WORDS.md"
DOCUMENT_FILENAMES = {
    outputs.WHAT_HE_LEARNED_LEDGER: WHAT_HE_LEARNED_FILENAME,
    outputs.IN_HIS_OWN_WORDS_LEDGER: IN_HIS_OWN_WORDS_FILENAME,
}
TOPIC_HEADINGS = {
    "FINDINGS": "What I found",
    "BUILD": "My opinion of the build",
    "DATA": "My opinion of the data",
    "SUGGESTION": "What I suggest",
}


class RenderError(ValueError):
    """The documents cannot be rendered honestly from this bundle."""


def _identity(bundle: Mapping[str, Any]) -> list[str]:
    return [
        f"- run: `{bundle.get('run_id')}`",
        f"- arm: `{bundle.get('arm')}`, role: `{bundle.get('role')}`",
        f"- registry: `{bundle.get('registry_sha256')}`",
        f"- calculation contract: `{bundle.get('contract_sha256')}`",
        f"- delivery receipt: `{bundle.get('delivery_receipt_sha256')}`",
        f"- knowledge receipt: `{bundle.get('knowledge_receipt_sha256')}`",
    ]


def _entries(bundle: Mapping[str, Any], ledger_id: str) -> list[Mapping[str, Any]]:
    try:
        return outputs.ledger_entries(bundle, ledger_id)
    except outputs.PrincipalOutputError as exc:
        raise RenderError(str(exc)) from exc


def render_what_he_learned(bundle: Mapping[str, Any]) -> str:
    entries = _entries(bundle, outputs.WHAT_HE_LEARNED_LEDGER)
    if not entries:
        raise RenderError(f"{outputs.WHAT_HE_LEARNED_LEDGER} is empty; a run that learned nothing prints no document")
    lines = [
        "# What I learned",
        "",
        "Rendered from the append-only `what_he_learned` ledger of the validated output bundle;",
        "every line below is chain-hashed there and nothing here is authored by the renderer.",
        "",
        *_identity(bundle),
        f"- entries: {len(entries)}",
        "",
    ]
    for entry in entries:
        body = entry["body"]
        kind = body.get("kind")
        standing = kind if kind == "NEW" else f"{kind} against served lesson `{body.get('prior_lesson_id')}`"
        lines.append(f"## {body.get('learning_id')} ({standing})")
        lines.append("")
        lines.append(str(body.get("statement", "")).strip())
        lines.append("")
        sections = body.get("sections") or []
        if sections:
            lines.append("- contract sections: " + ", ".join(f"`{s}`" for s in sections))
        evidence = body.get("evidence") or {}
        members = evidence.get("member_group_indices") or []
        if members:
            shown = ", ".join(str(m) for m in members[:20]) + (" ..." if len(members) > 20 else "")
            lines.append(f"- exact member groups ({len(members)}): {shown}; evidence cutoff `{evidence.get('cutoff_recv_ns')}`")
        else:
            lines.append(f"- basis (rests on absence): {str(evidence.get('basis', '')).strip()}")
        lines.append(f"- written at cutoff `{entry['cutoff_recv_ns']}`, entry `{entry['entry_hash'][:16]}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_in_his_own_words(bundle: Mapping[str, Any]) -> str:
    entries = _entries(bundle, outputs.IN_HIS_OWN_WORDS_LEDGER)
    if not entries:
        raise RenderError(f"{outputs.IN_HIS_OWN_WORDS_LEDGER} is empty; a run with no words prints no document")
    by_topic: dict[str, list[Mapping[str, Any]]] = {topic: [] for topic in outputs.OWN_WORDS_TOPICS}
    for entry in entries:
        topic = entry["body"].get("topic")
        if topic not in by_topic:
            raise RenderError(f"{outputs.IN_HIS_OWN_WORDS_LEDGER}[{entry['sequence']}] names unknown topic {topic!r}")
        by_topic[topic].append(entry)
    lines = [
        "# In my own words",
        "",
        "Rendered from the append-only `in_his_own_words` ledger of the validated output bundle:",
        "what I found, what I think of the build I ran under, what I think of the data I was fed,",
        "and what I suggest. Nothing here is authored by the renderer.",
        "",
        *_identity(bundle),
        f"- entries: {len(entries)}",
        "",
    ]
    for topic in outputs.OWN_WORDS_TOPICS:
        lines.append(f"## {TOPIC_HEADINGS[topic]}")
        lines.append("")
        rows = by_topic[topic]
        if not rows:
            lines.append("(nothing filed under this topic; the validator refuses such a bundle)")
            lines.append("")
            continue
        for entry in rows:
            body = entry["body"]
            lines.append(str(body.get("statement", "")).strip())
            lines.append("")
            refers = body.get("refers_to") or []
            if refers:
                lines.append("- about: " + ", ".join(f"`{r}`" for r in refers))
            lines.append(f"- written at cutoff `{entry['cutoff_recv_ns']}`, entry `{entry['entry_hash'][:16]}`")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


RENDERERS = {
    outputs.WHAT_HE_LEARNED_LEDGER: render_what_he_learned,
    outputs.IN_HIS_OWN_WORDS_LEDGER: render_in_his_own_words,
}


def render_documents(bundle: Mapping[str, Any]) -> dict[str, str]:
    """filename -> markdown, for both documents; refuses a bundle lacking either ledger."""
    return {DOCUMENT_FILENAMES[lid]: render(bundle) for lid, render in RENDERERS.items()}


def write_documents(outputs_dir: Path | str, out_dir: Path | str) -> dict[str, str]:
    """Render both documents from the bundle on disk into `out_dir`. Idempotent: a document
    already on disk with the same bytes is left alone; one with different bytes is rewritten,
    because the documents are renders and the ledgers are the record."""
    bundle = outputs.load_bundle(outputs_dir)
    rendered = render_documents(bundle)
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}
    for name, text in rendered.items():
        path = target / name
        raw = text.encode("utf-8")
        if path.is_file() and path.read_bytes() == raw:
            written[name] = "CURRENT"
            continue
        path.write_bytes(raw)
        written[name] = "WRITTEN"
    return written


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--outputs-dir", required=True, help="the principal_outputs directory (ledgers/ + RECEIPT.json)")
    parser.add_argument("--out-dir", required=True, help="where the two documents are written (the run directory)")
    args = parser.parse_args(argv)
    try:
        written = write_documents(args.outputs_dir, args.out_dir)
    except (outputs.PrincipalOutputError, RenderError, OSError, ValueError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(written, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
