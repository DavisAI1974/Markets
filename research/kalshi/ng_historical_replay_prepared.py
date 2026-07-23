#!/usr/bin/env python3
"""Replay a verified prepared G15 corpus without manual source enumeration.

``ng_historical_prepare.py`` publishes a fingerprinted index only after every
observed L1/trades and MBO object has been re-materialized, hash-checked, and
normalized. This adapter treats that index as the sole source list, revalidates
all 26 prepared files and their exact manifest lineage, performs a stable
chronological merge, and sends events through ``ng_historical_replay`` and the
same ``NGLiveOperator``/``ng_rt_feature_state`` path intended for live use.

No outcomes are read. Blind priors remain immutable, random shuffling is
forbidden, CME event contracts remain SHADOW, tastytrade remains the brokerage
contract, and the adapter cannot update ``ng_brain.json`` or start options work.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

from ng_historical_inventory import build_manifest
from ng_historical_manifest import (
    G15_CONTRACT_MAP,
    G15_DATES,
    SOURCE_KINDS,
    validate_manifest,
)
import ng_historical_prepare as preparation
from ng_historical_prepare import PrepareError, prepare_corpus, validate_prepared_index
from ng_historical_replay import ReplayError, merge_sorted_sources, read_jsonl, replay_events
from ng_rt_feature_state import validate_chronological, validate_feature_state

SCHEMA = "ng_historical_prepared_replay.v1"
REPLAY_SCHEMA = "ng_historical_replay.v1"
EVENT_BY_SOURCE_KIND = {"definition": "definition", "l1_trades": "trade", "mbo": "mbo"}
SOURCE_SORT = {"definition": 0, "l1_trades": 1, "mbo": 2}
EXPECTED_SOURCE_COUNT = 26


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


def _dependency_call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except ValueError as error:
        raise PreparedReplayError(str(error)) from error


def _manifest_entries(manifest: Mapping[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    entries: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in manifest.get("entries") or []:
        entry = copy.deepcopy(dict(raw))
        key = (str(entry.get("day") or ""), str(entry.get("source_kind") or ""))
        if key in entries:
            raise PreparedReplayError(f"duplicate manifest entry: {key[0]}:{key[1]}")
        entries[key] = entry
    expected = {(day, source_kind) for day in G15_DATES for source_kind in SOURCE_KINDS}
    missing = sorted(expected - set(entries))
    extras = sorted(set(entries) - expected)
    if missing or extras:
        raise PreparedReplayError(
            f"manifest G15 source coverage mismatch; missing={missing}, extras={extras}"
        )
    return entries


def _prepared_source_rows(
    index: Mapping[str, Any],
    *,
    verify_files: bool = True,
) -> list[dict[str, Any]]:
    """Validate canonical source coverage and return normalized index-owned rows."""
    try:
        validate_prepared_index(dict(index), verify_files=verify_files)
    except PrepareError as error:
        raise PreparedReplayError(str(error)) from error

    sources = [copy.deepcopy(dict(row)) for row in index.get("sources") or []]
    if int(index.get("source_count") or 0) != len(sources):
        raise PreparedReplayError("prepared source_count does not match sources")
    root_text = str(index.get("output_dir") or "")
    if not root_text:
        raise PreparedReplayError("prepared index lacks output_dir")
    root = Path(root_text).resolve()

    seen_paths: set[Path] = set()
    seen_pairs: set[tuple[str, str]] = set()
    definition_symbols: set[str] = set()
    rows: list[dict[str, Any]] = []

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
        path_text = str(source.get("path") or "")
        if not path_text:
            raise PreparedReplayError(f"{day}:{source_kind}: prepared path is required")
        path = Path(path_text).resolve()
        if not _inside(path, root):
            raise PreparedReplayError(f"prepared source escapes output_dir: {path}")
        if path in seen_paths:
            raise PreparedReplayError(f"duplicate prepared path: {path}")
        seen_paths.add(path)
        source["path"] = str(path)

        if source_kind == "definition":
            if int(source.get("record_count") or 0) != 1:
                raise PreparedReplayError("prepared definition source must contain one record")
            iterator = read_jsonl(path)
            try:
                definition = next(iterator)
            except StopIteration as error:
                raise PreparedReplayError(f"empty prepared definition source: {path}") from error
            try:
                next(iterator)
            except StopIteration:
                pass
            else:
                raise PreparedReplayError(f"prepared definition source has multiple records: {path}")
            symbol = str(definition.get("raw_symbol") or "")
            if symbol not in {"NGJ26", "NGK26"}:
                raise PreparedReplayError(f"unexpected prepared definition symbol: {symbol!r}")
            if symbol in definition_symbols:
                raise PreparedReplayError(f"duplicate prepared definition: {symbol}")
            definition_symbols.add(symbol)
            expected_day = G15_DATES[0] if symbol == "NGJ26" else "20260320"
            if day != expected_day:
                raise PreparedReplayError(f"{symbol}: prepared definition day mismatch")
        else:
            pair = (day, source_kind)
            if pair in seen_pairs:
                raise PreparedReplayError(f"duplicate prepared source: {day}:{source_kind}")
            seen_pairs.add(pair)
            if day not in G15_CONTRACT_MAP:
                raise PreparedReplayError(f"prepared source day is outside G15: {day}")
            normalization = source.get("normalization")
            if not isinstance(normalization, Mapping):
                raise PreparedReplayError(f"{day}:{source_kind}: normalization provenance is required")
            identity = dict(normalization.get("identity") or {})
            expected = G15_CONTRACT_MAP[day]
            if str(identity.get("session_day") or "") != day:
                raise PreparedReplayError(f"{day}:{source_kind}: normalization session mismatch")
            if (
                int(identity.get("instrument_id") or 0),
                str(identity.get("raw_symbol") or ""),
            ) != (expected["instrument_id"], expected["raw_symbol"]):
                raise PreparedReplayError(f"{day}:{source_kind}: normalization contract mismatch")
        rows.append(source)

    expected_pairs = {(day, kind) for day in G15_DATES for kind in SOURCE_KINDS}
    missing = sorted(expected_pairs - seen_pairs)
    extras = sorted(seen_pairs - expected_pairs)
    if missing or extras:
        raise PreparedReplayError(f"prepared G15 source coverage mismatch; missing={missing}, extras={extras}")
    if definition_symbols != {"NGJ26", "NGK26"}:
        raise PreparedReplayError(
            f"prepared definitions must contain NGJ26 and NGK26; observed={sorted(definition_symbols)}"
        )
    if len(rows) != EXPECTED_SOURCE_COUNT:
        raise PreparedReplayError(
            f"prepared corpus must contain 26 sources, observed {len(rows)}"
        )

    rows.sort(
        key=lambda row: (
            str(row.get("day") or ""),
            SOURCE_SORT[str(row.get("source_kind") or "")],
            str(row.get("path") or ""),
        )
    )
    return rows


def prepared_source_paths(index: Mapping[str, Any]) -> list[Path]:
    """Return only canonical paths from a fully verified prepared index."""
    return [Path(row["path"]) for row in _prepared_source_rows(index, verify_files=True)]


def _validate_manifest_lineage(
    index: Mapping[str, Any],
    manifest: Mapping[str, Any],
    sources: list[dict[str, Any]],
) -> str:
    report = _dependency_call(validate_manifest, dict(manifest))
    if report.get("status") != "READY" or report.get("can_replay_all_g15") is not True:
        raise PreparedReplayError("prepared replay requires a READY exact G15 manifest")
    expected_manifest_fingerprint = str(index.get("manifest_fingerprint") or "")
    actual_manifest_fingerprint = preparation._fingerprint(manifest)
    if not expected_manifest_fingerprint:
        raise PreparedReplayError("prepared index lacks manifest_fingerprint")
    if expected_manifest_fingerprint != actual_manifest_fingerprint:
        raise PreparedReplayError("prepared index does not belong to the supplied manifest")

    manifest_entries = _manifest_entries(manifest)
    for source in sources:
        source_kind = str(source.get("source_kind") or "")
        if source_kind == "definition":
            continue
        day = str(source.get("day") or "")
        prefix = f"{day}:{source_kind}"
        entry = manifest_entries[(day, source_kind)]
        normalization = dict(source.get("normalization") or {})
        expected_entry_fingerprint = preparation._fingerprint(entry)
        if normalization.get("manifest_entry_fingerprint") != expected_entry_fingerprint:
            raise PreparedReplayError(f"{prefix}: manifest lineage mismatch")
        if normalization.get("source_uri") != entry.get("location"):
            raise PreparedReplayError(f"{prefix}: raw source location lineage mismatch")
        if int(normalization.get("observed_raw_size_bytes") or 0) != int(entry.get("size_bytes") or 0):
            raise PreparedReplayError(f"{prefix}: raw source size lineage mismatch")
        if normalization.get("observed_raw_sha256") != entry.get("sha256"):
            raise PreparedReplayError(f"{prefix}: raw source hash lineage mismatch")
        if Path(str(normalization.get("output") or "")).resolve() != Path(source["path"]).resolve():
            raise PreparedReplayError(f"{prefix}: normalization output path mismatch")

        expected_identity = {
            "dataset": entry.get("dataset"),
            "publisher_id": entry.get("publisher_id"),
            "instrument_id": entry.get("instrument_id"),
            "raw_symbol": entry.get("raw_symbol"),
            "definition_date": entry.get("definition_date"),
            "session_day": day,
        }
        if dict(normalization.get("identity") or {}) != expected_identity:
            raise PreparedReplayError(f"{prefix}: normalization identity differs from manifest")
        for field in ("record_count", "size_bytes", "sha256", "event_start_s", "event_end_s"):
            if source.get(field) != normalization.get(field):
                raise PreparedReplayError(f"{prefix}: prepared {field} differs from normalization")
        if int(source.get("record_count") or 0) != int(entry.get("record_count") or 0):
            raise PreparedReplayError(f"{prefix}: prepared record_count differs from manifest")
        for field in ("event_start_s", "event_end_s"):
            if abs(float(source.get(field)) - float(entry.get(field))) > 1e-9:
                raise PreparedReplayError(f"{prefix}: prepared {field} differs from manifest")
    return actual_manifest_fingerprint


def replay_prepared_index(
    index: dict[str, Any],
    *,
    manifest: dict[str, Any],
    blind_prior: dict[str, Any],
    horizon: str = "close",
) -> dict[str, Any]:
    """Replay every normalized source named by a verified prepared index."""
    originals = copy.deepcopy((index, manifest, blind_prior))
    sources = _prepared_source_rows(index, verify_files=True)
    manifest_fingerprint = _validate_manifest_lineage(index, manifest, sources)
    prior_before = copy.deepcopy(blind_prior)
    result = replay_events(
        merge_sorted_sources([read_jsonl(Path(source["path"])) for source in sources]),
        manifest=manifest,
        blind_prior=blind_prior,
        horizon=horizon,
        require_ready_manifest=True,
    )
    if blind_prior != prior_before:
        raise PreparedReplayError("blind prior was mutated during prepared replay")

    result["prepared_replay_schema"] = SCHEMA
    result["prepared_corpus_fingerprint"] = index["prepared_corpus_fingerprint"]
    result["prepared_manifest_fingerprint"] = manifest_fingerprint
    result["prepared_source_count"] = len(sources)
    result["prepared_sources"] = [
        {
            "day": row.get("day"),
            "source_kind": row.get("source_kind"),
            "sha256": row.get("sha256"),
            "size_bytes": row.get("size_bytes"),
        }
        for row in sources
    ]
    result["prepared_source_fingerprints"] = [
        _fingerprint(
            {
                "day": row.get("day"),
                "source_kind": row.get("source_kind"),
                "path": row.get("path"),
                "record_count": row.get("record_count"),
                "size_bytes": row.get("size_bytes"),
                "sha256": row.get("sha256"),
            }
        )
        for row in sources
    ]
    result.update(
        {
            "actual_outcomes_used": False,
            "paid_live_data_assumed": False,
            "random_shuffle_used": False,
            "one_signal_authority_preserved": True,
            "blind_prior_immutable": True,
            "may_change_blind_forecast": False,
            "may_change_posterior": False,
            "may_update_ng_brain": False,
            "cme_event_contracts_mode": "SHADOW",
            "brokerage_contract": "tastytrade_not_ibkr",
            "options_lane_started": False,
            "note": (
                "Replay source enumeration came only from the verified prepared-corpus index; "
                "manifest lineage was revalidated, states emit on F_LAST, and CME event "
                "contracts remain SHADOW."
            ),
        }
    )
    result["prepared_replay_fingerprint"] = _fingerprint(result)
    validate_replay_output(result)
    if (index, manifest, blind_prior) != originals:
        raise PreparedReplayError("prepared replay mutated a source artifact")
    return result


def validate_replay_output(output: Mapping[str, Any]) -> None:
    candidate = copy.deepcopy(dict(output))
    observed = candidate.pop("prepared_replay_fingerprint", None)
    if observed != _fingerprint(candidate):
        raise PreparedReplayError("prepared replay fingerprint mismatch")
    if candidate.get("schema") != REPLAY_SCHEMA or candidate.get("prepared_replay_schema") != SCHEMA:
        raise PreparedReplayError("unexpected prepared replay schema")
    if candidate.get("market") != "NG" or int(candidate.get("group") or 0) != 15:
        raise PreparedReplayError("prepared replay must describe G15 NG")
    if candidate.get("authority") != "HISTORICAL_REFINE_REPLAY_ONLY":
        raise PreparedReplayError("prepared replay authority mismatch")
    for field in (
        "execution_authority",
        "actual_outcomes_used",
        "paid_live_data_assumed",
        "random_shuffle_used",
        "may_change_blind_forecast",
        "may_change_posterior",
        "may_update_ng_brain",
        "options_lane_started",
    ):
        if candidate.get(field) is not False:
            raise PreparedReplayError(f"prepared replay must keep {field}=false")
    for field in ("one_signal_authority_preserved", "blind_prior_immutable"):
        if candidate.get(field) is not True:
            raise PreparedReplayError(f"prepared replay must keep {field}=true")
    if candidate.get("cme_event_contracts_mode") != "SHADOW":
        raise PreparedReplayError("CME event contracts must remain SHADOW")
    if candidate.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise PreparedReplayError("brokerage must remain tastytrade, not IBKR")
    if int(candidate.get("prepared_source_count") or 0) != EXPECTED_SOURCE_COUNT:
        raise PreparedReplayError("prepared replay did not consume all 26 sources")
    prepared_sources = candidate.get("prepared_sources")
    source_fingerprints = candidate.get("prepared_source_fingerprints")
    if not isinstance(prepared_sources, list) or len(prepared_sources) != EXPECTED_SOURCE_COUNT:
        raise PreparedReplayError("prepared replay source summary count mismatch")
    if not isinstance(source_fingerprints, list) or len(source_fingerprints) != EXPECTED_SOURCE_COUNT:
        raise PreparedReplayError("prepared replay source fingerprint count mismatch")
    if candidate.get("duplicate_records"):
        raise PreparedReplayError("duplicate historical records block prepared replay")

    states: list[dict[str, Any]] = []
    for raw_stream in candidate.get("streams") or []:
        stream = dict(raw_stream)
        stream_states = [copy.deepcopy(dict(row)) for row in stream.get("states") or []]
        if int(stream.get("n_states") or 0) != len(stream_states):
            raise PreparedReplayError("prepared replay stream state count mismatch")
        _dependency_call(validate_chronological, stream_states)
        for state in stream_states:
            _dependency_call(validate_feature_state, state)
            if state.get("completed_mbo_event_boundary") is not True:
                raise PreparedReplayError("prepared replay state lacks completed MBO boundary")
            states.append(state)
    covered = sorted({str(state.get("session_day") or "") for state in states})
    if covered != sorted(G15_DATES):
        raise PreparedReplayError(
            "prepared replay lacks canonical G15 state coverage; "
            f"missing={sorted(set(G15_DATES)-set(covered))}"
        )
    if int(candidate.get("completed_mbo_event_boundaries") or 0) != len(states):
        raise PreparedReplayError("prepared replay boundary count differs from emitted states")
    if candidate.get("sequence_gaps"):
        visible = any(
            "collector_skipped_records"
            in list((state.get("availability") or {}).get("stand_down_reasons") or [])
            for state in states
        )
        if not visible:
            raise PreparedReplayError("sequence gaps exist without a visible stand-down")


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
        validate_replay_output(result)
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
                "fingerprint": result["prepared_replay_fingerprint"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
