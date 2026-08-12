#!/usr/bin/env python3
"""S115 forecaster harness for Frankie.

The blind engine remains the predictor. Frankie extends it with explicit object state, typed output,
a causal lens book, generated track-record attachments, a toolbox catalogue, and a grading duty.
Nothing here replaces spawn.py or writes the canonical brain.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from frankie_nova_optimizer import BPE_CONTRACT, HARNESS_ACTION_CONTRACT  # noqa: E402
from frankie_render_s115 import FrankieAgentObject, TypedPosterior, assert_byte_identical  # noqa: E402
from frankie_s115 import (  # noqa: E402
    LensBookEntry,
    S115Stop,
    append_lens_book,
    assert_future_absent,
    assert_ownership_clean,
    causal_lens_view,
)

STATE_ROOT = HERE / "data" / "frankie_s115"
BOOK_ROOT = STATE_ROOT / "lens_books"
POSTERIOR_ROOT = STATE_ROOT / "posteriors"
TRACK_RECORD_PATH = STATE_ROOT / "specialist_track_records.json"
ACCESS_LEDGER_ROOT = STATE_ROOT / "harness_access"

TOOLBOX = {
    "spawn": {
        "path": "research/kalshi/spawn.py",
        "use": "canonical slot lookup and prompt rendering; never bypass its stop gates",
    },
    "store_check": {
        "path": "research/kalshi/store.py",
        "use": "prove generated renders still reproduce committed artifacts",
    },
    "failure_judge": {
        "path": "research/kalshi/failure_localization.py",
        "use": "FJ-1 frozen taxonomy grading after outcomes are available",
    },
    "actual_builder": {
        "path": "research/kalshi/group_actual.py",
        "use": "build actuals only after the blind decision; preserve the state's contract basis",
    },
    "databento_s115": {
        "path": "research/kalshi/databento_backfill_s115.py",
        "use": "cwd-independent S115 pull/redecode with physical landing assertion",
    },
}

GRADING_DUTY = (
    "After the outcome becomes available, grade the run with FJ-1 against the frozen taxonomy. "
    "Localize the earliest unrecovered failure. The grading result may update this lens's track "
    "record/lens book; a general lesson still requires the normal brain proposal/adjudication/merge."
)

PLAY_POLICY = (
    "Additive in what is available, selective in what is consulted: retain whole plays and use the "
    "existing play_index/retrieval-on-demand. Never shrink the toolbox merely to make choosing easier."
)

HARNESS_POLICY = (
    "BPE is a view over existing Frankie state, not a replacement store. Retrieval is an explicit "
    "costed action. Start with lossless NOVA compaction and access telemetry; any lossy view must "
    "declare withheld content and pass A-65 decision-equivalence validation before becoming load-bearing."
)


def _book(lens: str) -> Path:
    return BOOK_ROOT / f"{lens}.jsonl"


def prepare_day(
    *, template: str, gid: str, day: str, specialist: str, directive: str | None = None,
) -> dict[str, Any]:
    """Prepare one specialist without changing the canonical prompt bytes."""
    assert_ownership_clean()
    agent = FrankieAgentObject(template, gid, day, specialist, directive)
    assert_byte_identical(agent)
    book_view = causal_lens_view(_book(specialist), lens=specialist, current_day=_iso_day(day))
    assert_future_absent(book_view, _iso_day(day))
    return {
        "template": template,
        "gid": gid,
        "day": day,
        "specialist": specialist,
        "canonical_prompt": agent.render_prompt(),
        "canonical_prompt_byte_identity": True,
        "toolbox_catalogue": TOOLBOX,
        "toolbox_rule": "availability is additive; consultation is selective and task-local",
        "play_policy": PLAY_POLICY,
        "lens_book": book_view,
        "lens_book_rule": "strictly earlier days only; absent means absent",
        "track_record_attachment": str(TRACK_RECORD_PATH) if TRACK_RECORD_PATH.is_file() else None,
        "grading_duty": GRADING_DUTY,
        "external_state_contract": BPE_CONTRACT,
        "external_state_actions": HARNESS_ACTION_CONTRACT,
        "harness_policy": HARNESS_POLICY,
        "harness_access_ledger": str(ACCESS_LEDGER_ROOT / f"{specialist}.jsonl"),
        "harness_access_rule": (
            "append-only telemetry; record bytes/tokens/source/action/state class and any withheld content; "
            "do not use telemetry to reveal future/current outcomes"
        ),
        "token_optimizer": {
            "implementation": "research/kalshi/frankie_nova_optimizer.py",
            "origin": "Frankie-specific adaptation of DavisAI1974/Nova-Optimizer; original remains untouched",
            "default_mode": "lossless",
            "lossy_views_require_a65": True,
            "canonical_prompt_modified": False,
        },
        "execution_enabled": False,
    }


def record_day(*, posterior_raw: dict[str, Any], carried_state: dict[str, Any]) -> dict[str, Any]:
    posterior = TypedPosterior.from_mapping(posterior_raw)
    path = POSTERIOR_ROOT / posterior.group / posterior.specialist / f"{posterior.day}.json"
    posterior.write(path)
    entry = LensBookEntry(
        lens=posterior.specialist,
        day=_iso_day(posterior.day),
        decision_at=str(posterior_raw.get("decision_at") or f"{_iso_day(posterior.day)}T20:00:00Z"),
        event_id=str(posterior_raw.get("event_id") or f"{posterior.group}:{posterior.specialist}:{posterior.day}"),
        carried_state=carried_state,
        action={
            "direction": posterior.direction,
            "magnitude": posterior.magnitude,
            "fired": list(posterior.fired),
            "stood_down": list(posterior.stood_down),
        },
        source_hashes=posterior.source_hashes,
    )
    row_hash = append_lens_book(_book(posterior.specialist), entry)
    return {
        "posterior_path": str(path),
        "lens_book_path": str(_book(posterior.specialist)),
        "lens_book_entry_hash": row_hash,
        "grading_duty": GRADING_DUTY,
        "execution_enabled": False,
    }


def _iso_day(day: str) -> str:
    day = day.replace("-", "")
    if len(day) != 8 or not day.isdigit():
        raise S115Stop(f"invalid day: {day}")
    return f"{day[:4]}-{day[4:6]}-{day[6:]}"


def _read_object(path: str) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise S115Stop(f"expected JSON object: {path}")
    return raw


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare-day")
    p.add_argument("template")
    p.add_argument("gid")
    p.add_argument("day")
    p.add_argument("specialist")
    p.add_argument("--directive")
    p = sub.add_parser("record-day")
    p.add_argument("posterior")
    p.add_argument("--carried-state", required=True)
    args = ap.parse_args()
    try:
        if args.cmd == "prepare-day":
            out = prepare_day(
                template=args.template,
                gid=args.gid,
                day=args.day,
                specialist=args.specialist,
                directive=args.directive,
            )
        else:
            out = record_day(
                posterior_raw=_read_object(args.posterior),
                carried_state=_read_object(args.carried_state),
            )
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"STOP - {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())