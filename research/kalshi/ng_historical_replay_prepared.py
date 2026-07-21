#!/usr/bin/env python3
"""Replay a verified prepared G15 corpus without manual source enumeration.

``ng_historical_prepare.py`` publishes a fingerprinted index only after every
observed L1/trades and MBO object has been re-materialized, hash-checked, and
normalized. This adapter treats that index as the sole source list, validates
its canonical 12-session/2-contract layout, and sends the merged events through
``ng_historical_replay.replay_events`` and therefore the same ``NGLiveOperator``
and ``ng_rt_feature_state`` path intended for live use.

The original READY manifest remains required so the prepared-corpus fingerprint
can be tied back to the exact observed AWS/S3 inventory. Blind priors are copied
by the replay layer and CME event contracts remain SHADOW.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

from ng_historical_inventory import build_manifest
from ng_historical_manifest import G15_CONTRACT_MAP, G15_DATES, SOURCE_KINDS
from ng_historical_prepare import PrepareError, prepare_corpus, validate_prepared_index
from ng_historical_replay import ReplayError, merge_sorted_sources, read_jsonl, replay_events

SCHEMA = "ng_historical_prepared_replay.v1"
EVENT_BY_SOURCE_KIND = {"definition": "definition", "l1_trades": "trade", "mbo": "mbo"}
SOURCE_SORT = {"definition": 0, "l1_trades": 1, "mbo": 2}


class PreparedReplayError(ReplayError):
    """Raised when a prepared corpus cannot safely enter causal replay."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def prepared_source_paths(index: Mapping[str, Any]) -> list[Path]:
    """Validate canonical source coverage and return the index-owned paths.

    File sizes and hashes are verified by ``validate_prepared_index``. Additional
    checks here prevent an otherwise fingerprinted index from omitting a G15 day,
    duplicating one lane, pointing outside its declared output directory, or
    labelling a source with the wrong event type/contract identity.
    """
    try:
        validate_prepared_index(dict(index), verify_files=True)
    except PrepareError as error:
        raise PreparedReplayError(str(error)) from error

    sources = [dict(row) for row in index.get("sources") or []]
    if int(index.get("source_count") or 0) != len(sources):
        raise PreparedReplayError("prepared source_count does not match sources")
    root_text = str(index.get("output_dir") or "")
    if not root_text:
        raise PreparedReplayError("prepared index lacks output_dir")
    root = Path(root_text).resolve()

    seen_paths: set[Path] = set()
    seen_pairs: set[tuple[str, str]] = set()
    definition_symbols: set[str] = set()
    paths: list[tuple[str, str, Path]] = []

    for source in sources:
        day = str(source.get("day") or "")
        source_kind = str(source.get("source_kind") or "")
        event_type = str(source.get("event_type") or "")
        expected_event = EVENT_BY_SOURCE_KIND.get(source_kind)
        if expected_event is None or event_type != expected_event:
            raise PreparedReplayError(
                f"{day or '<missing-day>'}:{source_kind or '<missing-kind>'}: "
                f"event_type {event_type!r} is not canonical"
            )
        path = Path(str(source.get("path") or "")).resolve()
        if not _inside(path, root):
            raise PreparedReplayError(f"prepared source escapes output_dir: {path}")
        if path in seen_paths:
            raise PreparedReplayError(f"duplicate prepared path: {path}")
        seen_paths.add(path)

        if source_kind == "definition":
            try:
                definition = next(read_jsonl(path))
            except StopIteration as error:
                raise PreparedReplayError(f"empty prepared definition source: {path}") from error
            symbol = str(definition.get("raw_symbol") or "")
            if symbol not in {"NGJ26", "NGK26"}:
                raise PreparedReplayError(f"unexpected prepared definition symbol: {symbol!r}")
            if symbol in definition_symbols:
                raise PreparedReplayError(f"duplicate prepared definition: {symbol}")
            definition_symbols.add(symbol)
        else:
            pair = (day, source_kind)
            if pair in seen_pairs:
                raise PreparedReplayError(f"duplicate prepared source: {day}:{source_kind}")
            seen_pairs.add(pair)
            if day not in G15_CONTRACT_MAP:
                raise PreparedReplayError(f"prepared source day is outside G15: {day}")
            identity = dict((source.get("normalization") or {}).get("identity") or {})
            expected = G15_CONTRACT_MAP[day]
            if str(identity.get("session_day") or "") != day:
                raise PreparedReplayError(f"{day}:{source_kind}: normalization session mismatch")
            if (
                int(identity.get("instrument_id") or 0),
                str(identity.get("raw_symbol") or ""),
            ) != (expected["instrument_id"], expected["raw_symbol"]):
                raise PreparedReplayError(f"{day}:{source_kind}: normalization contract mismatch")
        paths.append((day, source_kind, path))

    expected_pairs = {(day, kind) for day in G15_DATES for kind in SOURCE_KINDS}
    missing = sorted(expected_pairs - seen_pairs)
    extras = sorted(seen_pairs - expected_pairs)
    if missing or extras:
        raise PreparedReplayError(f"prepared G15 source coverage mismatch; missing={missing}, extras={extras}")
    if definition_symbols != {"NGJ26", "NGK26"}:
        raise PreparedReplayError(
            f"prepared definitions must contain NGJ26 and NGK26; observed={sorted(definition_symbols)}"
        )
    if len(paths) != 26:
        raise PreparedReplayError(f"prepared corpus must contain 26 sources, observed {len(paths)}")

    paths.sort(key=lambda row: (row[0], SOURCE_SORT[row[1]], str(row[2])))
    return [row[2] for row in paths]


def replay_prepared_index(
    index: dict[str, Any],
    *,
    manifest: dict[str, Any],
    blind_prior: dict[str, Any],
    horizon: str = "close",
) -> dict[str, Any]:
    """Replay every normalized source named by a verified prepared index."""
    expected_manifest_fingerprint = str(index.get("manifest_fingerprint") or "")
    actual_manifest_fingerprint = _fingerprint(manifest)
    if not expected_manifest_fingerprint:
        raise PreparedReplayError("prepared index lacks manifest_fingerprint")
    if expected_manifest_fingerprint != actual_manifest_fingerprint:
        raise PreparedReplayError("prepared index does not belong to the supplied manifest")

    paths = prepared_source_paths(index)
    result = replay_events(
        merge_sorted_sources([read_jsonl(path) for path in paths]),
        manifest=manifest,
        blind_prior=blind_prior,
        horizon=horizon,
        require_ready_manifest=True,
    )
    result["prepared_replay_schema"] = SCHEMA
    result["prepared_corpus_fingerprint"] = index["prepared_corpus_fingerprint"]
    result["prepared_manifest_fingerprint"] = expected_manifest_fingerprint
    result["prepared_source_count"] = len(paths)
    result["prepared_sources"] = [
        {
            "day": row.get("day"),
            "source_kind": row.get("source_kind"),
            "sha256": row.get("sha256"),
            "size_bytes": row.get("size_bytes"),
        }
        for row in index.get("sources") or []
    ]
    result["note"] = (
        "Replay source enumeration came only from the verified prepared-corpus index; "
        "states emit on F_LAST and CME event contracts remain SHADOW."
    )
    return result


def _fixture(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    definitions = {
        "NGJ26": {
            "dataset": "GLBX.MDP3", "publisher_id": 1, "instrument_id": 1008,
            "raw_symbol": "NGJ26", "definition_date": "2026-03-01",
            "definition_start_s": 0.0, "definition_end_s": 10_000.0,
            "observed_at": "2026-07-21T00:00:00Z",
        },
        "NGK26": {
            "dataset": "GLBX.MDP3", "publisher_id": 1, "instrument_id": 996,
            "raw_symbol": "NGK26", "definition_date": "2026-03-20",
            "definition_start_s": 0.0, "definition_end_s": 10_000.0,
            "observed_at": "2026-07-21T00:00:00Z",
        },
    }
    for position, day in enumerate(G15_DATES, 1):
        contract = G15_CONTRACT_MAP[day]
        definition_date = "2026-03-01" if contract["raw_symbol"] == "NGJ26" else "2026-03-20"
        identity = {
            "dataset": "GLBX.MDP3", "publisher_id": 1,
            "instrument_id": contract["instrument_id"], "raw_symbol": contract["raw_symbol"],
            "definition_date": definition_date, "session_day": day,
        }
        trade = {
            **identity, "ts_event_s": float(position * 10), "price": 3.0,
            "size": 1, "side": "B", "sequence": 1,
        }
        mbo = {
            **identity, "ts_event_s": float(position * 10), "action": "A", "side": "B",
            "price": 3.0, "size": 1, "order_id": position, "flags": 128, "sequence": 1,
        }
        (root / f"l1_{day}.jsonl").write_text(json.dumps(trade) + "\n", encoding="utf-8")
        (root / f"mbo_{day}.jsonl").write_text(json.dumps(mbo) + "\n", encoding="utf-8")
    manifest = build_manifest(
        l1_pattern=str(root / "l1_{day}.jsonl"),
        mbo_pattern=str(root / "mbo_{day}.jsonl"),
        publisher_id=1,
        definitions=definitions,
    )
    index = prepare_corpus(manifest, root / "prepared")
    return manifest, index


def selftest() -> int:
    with tempfile.TemporaryDirectory() as tempdir:
        manifest, index = _fixture(Path(tempdir))
        prior = {"up": 0.4, "flat": 0.2, "down": 0.4}
        result = replay_prepared_index(index, manifest=manifest, blind_prior=prior)
        assert result["prepared_source_count"] == 26
        assert result["completed_mbo_event_boundaries"] == len(G15_DATES)
        assert result["processed_records"] == {"trade": 12, "mbo": 12, "definition": 2}
        assert prior == {"up": 0.4, "flat": 0.2, "down": 0.4}
    print("[ng_historical_replay_prepared] selftest PASS")
    return 0


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay a verified prepared G15 corpus")
    parser.add_argument("--prepared-index", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--blind-prior", type=Path)
    parser.add_argument("--horizon", default="close")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if not args.prepared_index or not args.manifest or not args.blind_prior or not args.out:
        parser.error("--prepared-index, --manifest, --blind-prior, and --out are required")
    index = json.loads(args.prepared_index.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    blind_prior = json.loads(args.blind_prior.read_text(encoding="utf-8"))
    result = replay_prepared_index(
        index,
        manifest=manifest,
        blind_prior=blind_prior,
        horizon=args.horizon,
    )
    _atomic_json(args.out, result)
    print(
        json.dumps(
            {
                "processed": result["processed_records"],
                "boundaries": result["completed_mbo_event_boundaries"],
                "prepared_sources": result["prepared_source_count"],
                "fingerprint": result["prepared_corpus_fingerprint"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
