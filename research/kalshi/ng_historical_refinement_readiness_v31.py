#!/usr/bin/env python3
"""Public readiness-v31 entrypoint with a robust linked-fixture self-test."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

import ng_historical_refinement_readiness_v31_impl as _impl

for _name in dir(_impl):
    if not _name.startswith("__") and _name not in {"_linked_fixture_chain", "selftest", "main"}:
        globals()[_name] = getattr(_impl, _name)


def _linked_fixture_chain() -> dict[str, dict[str, Any]]:
    """Build a complete fixture while materializing the new source-side link fields."""
    values = v30._linked_fixture_chain()
    export = values["replay_catalog_export"]
    replay = values["g15_exact_replay"]

    export.setdefault("g15_bridge_fingerprint", "b" * 64)
    export.pop("fingerprint", None)
    export["fingerprint"] = _fingerprint(export)

    replay.setdefault("manifest_fingerprint", "m" * 64)
    replay.setdefault("prepared_corpus_fingerprint", "p" * 64)
    replay.pop("completion_fingerprint", None)
    replay["completion_fingerprint"] = _fingerprint(replay)

    guard = legacy._fixture_artifact(
        _PREPARED_IDENTITY,
        "G15_PREPARED_NORMALIZED_IDENTITY_AND_TIME_ATTESTED",
    )
    guard.update(
        {
            "bridge_fingerprint": export["g15_bridge_fingerprint"],
            "manifest_fingerprint": replay["manifest_fingerprint"],
            "prepared_corpus_fingerprint": replay["prepared_corpus_fingerprint"],
            "source_evidence_fingerprint": "n" * 64,
            "source_count": 26,
            "all_publishers_explicit_and_positive": True,
            "all_rows_match_exact_manifest_identity": True,
            "all_events_within_definition_and_lane_periods": True,
            "all_sources_chronological": True,
            "definitions_precede_trade_and_mbo_replay": True,
            "blockers": [],
            "next_action": "RUN_EXACT_G15_CAUSAL_REPLAY",
            "actual_outcomes_used": False,
            "paid_live_data_assumed": False,
            "random_shuffle_used": False,
            "one_signal_authority_preserved": True,
            "blind_forecasts_immutable": True,
            "may_change_blind_forecast": False,
            "may_change_posterior": False,
            "may_update_ng_brain": False,
            "execution_authority": False,
            "cme_event_contracts_mode": "SHADOW",
            "brokerage_contract": "tastytrade_not_ibkr",
            "options_lane_started": False,
        }
    )
    guard.pop("fingerprint", None)
    guard["fingerprint"] = _fingerprint(guard)
    values["g15_prepared_normalized_identity"] = guard

    incoming: dict[str, list[tuple[str, str, str]]] = {}
    for source_key, source_path, target_key, target_path in LINK_RULES:
        incoming.setdefault(target_key, []).append((source_key, source_path, target_path))
    for spec in STAGES:
        value = values[spec.key]
        for source_key, source_path, target_path in incoming.get(spec.key, []):
            legacy._path_set(
                value,
                target_path,
                legacy._path_get(values[source_key], source_path),
            )
        value.pop(spec.fingerprint_field, None)
        value[spec.fingerprint_field] = _fingerprint(value)
    return values


def selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        overrides = {spec.key: (lambda value: None) for spec in STAGES}
        missing = build_readiness_report(root, validator_overrides=overrides)
        assert missing["first_blocking_stage"] == "corpus_expected_day_contract"

        values = _linked_fixture_chain()
        for spec in STAGES:
            _atomic_json(root / spec.filename, values[spec.key])
        complete = build_readiness_report(root, validator_overrides=overrides)
        assert complete["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V31"
        assert complete["prepared_rows_exact_manifest_identity"] is True

        (root / _PREPARED_IDENTITY.filename).unlink()
        blocked = build_readiness_report(root, validator_overrides=overrides)
        assert blocked["first_blocking_stage"] == "g15_prepared_normalized_identity"
        assert blocked["g15_replay_bound_to_prepared_normalized_identity"] is False

    print("[ng_historical_refinement_readiness_v31] selftest PASS")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-dir", type=Path, default=Path("renders/ng_refine_s95")
    )
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    report = build_readiness_report(args.artifact_dir)
    output = args.out or args.artifact_dir / "ng_historical_refinement_readiness_v31.json"
    _atomic_json(output, report)
    print(json.dumps({"out": str(output), "status": report["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
