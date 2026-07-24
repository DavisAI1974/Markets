#!/usr/bin/env python3
"""Compile exact G16 lock/publication contexts from fingerprinted JSON references.

The exact G16 publication gate accepts nested Python mappings. Historically those
mappings were supplied through a hand-authored context JSON, leaving an operational
seam where a stale or substituted artifact could be embedded even though the final
gate itself was fail-closed. This compiler resolves every referenced JSON file,
checks optional byte hashes, rejects outcome-bearing inputs at the pre-outcome lock
boundary, builds the exact gate artifact, and emits a deterministic provenance
receipt.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import ng_g16_exact_counterfactual_publication_gate as gate

SPEC_SCHEMA = "ng_g16_exact_publication_context_spec.v1"
RECEIPT_SCHEMA = "ng_g16_exact_publication_context_compiler.v1"
LOCK_MODE = "lock"
COMPLETE_MODE = "complete"
MODES = (LOCK_MODE, COMPLETE_MODE)

_REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    LOCK_MODE: (
        "exact_curve_authorization",
        "exact_causal_authorization",
        "counterfactual_curve_authorization",
        "curve_kwargs",
        "legacy_lock_kwargs",
    ),
    COMPLETE_MODE: (
        "exact_curve_lock",
        "exact_lock_kwargs",
        "legacy_completion_kwargs",
    ),
}

_G16_OUTCOME_TOKENS = ("actual", "outcome", "score", "comparison", "render")


class G16ExactPublicationContextCompilerError(ValueError):
    """Raised when an exact G16 context is incomplete, mutable, or outcome-leaking."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path, *, label: str) -> Any:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise G16ExactPublicationContextCompilerError(
            f"cannot read {label} {path}: {error}"
        ) from error
    try:
        return json.loads(raw.decode("utf-8")), raw
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise G16ExactPublicationContextCompilerError(
            f"invalid UTF-8 JSON in {label} {path}: {error}"
        ) from error


def _display_path(path: Path, *, base: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(base.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _resolve_reference(
    value: Any,
    *,
    base: Path,
    references: list[dict[str, Any]],
    trail: tuple[str, ...] = (),
) -> Any:
    if isinstance(value, list):
        return [
            _resolve_reference(
                item,
                base=base,
                references=references,
                trail=(*trail, str(index)),
            )
            for index, item in enumerate(value)
        ]
    if not isinstance(value, dict):
        return copy.deepcopy(value)

    if "$file" in value:
        allowed = {"$file", "$sha256"}
        if set(value) - allowed:
            raise G16ExactPublicationContextCompilerError(
                f"file reference at {'.'.join(trail) or '<root>'} contains unsupported keys"
            )
        requested = value.get("$file")
        if not isinstance(requested, str) or not requested.strip():
            raise G16ExactPublicationContextCompilerError("$file must be a non-empty string")
        path = Path(requested)
        if not path.is_absolute():
            path = base / path
        loaded, raw = _load_json(path, label="referenced artifact")
        observed_sha = _sha256_bytes(raw)
        expected_sha = value.get("$sha256")
        if expected_sha is not None and expected_sha != observed_sha:
            raise G16ExactPublicationContextCompilerError(
                f"referenced artifact SHA-256 mismatch: {_display_path(path, base=base)}"
            )
        references.append(
            {
                "context_path": ".".join(trail),
                "path": _display_path(path, base=base),
                "sha256": observed_sha,
                "byte_size": len(raw),
            }
        )
        return loaded

    return {
        str(key): _resolve_reference(
            item,
            base=base,
            references=references,
            trail=(*trail, str(key)),
        )
        for key, item in value.items()
    }


def _is_empty_or_false(value: Any) -> bool:
    return value is None or value is False or value == "" or value == [] or value == {}


def _assert_lock_outcome_blind(value: Any, *, trail: tuple[str, ...] = ()) -> None:
    if isinstance(value, list):
        for index, item in enumerate(value):
            _assert_lock_outcome_blind(item, trail=(*trail, str(index)))
        return
    if not isinstance(value, dict):
        return
    for key, item in value.items():
        normalized = str(key).lower()
        targets_g16 = "g16" in normalized or "target_group_16" in normalized
        if (
            targets_g16
            and any(token in normalized for token in _G16_OUTCOME_TOKENS)
            and not _is_empty_or_false(item)
        ):
            raise G16ExactPublicationContextCompilerError(
                "pre-outcome lock context contains G16 outcome-bearing value at "
                + ".".join((*trail, str(key)))
            )
        _assert_lock_outcome_blind(item, trail=(*trail, str(key)))


def _assert_lock_reference_paths_outcome_blind(
    references: list[dict[str, Any]],
) -> None:
    for reference in references:
        normalized = str(reference.get("path") or "").lower()
        if "g16" in normalized and any(
            token in normalized for token in _G16_OUTCOME_TOKENS
        ):
            raise G16ExactPublicationContextCompilerError(
                "pre-outcome lock context references a G16 outcome-bearing path: "
                + normalized
            )


def _validate_spec(spec: Mapping[str, Any], *, requested_mode: str) -> None:
    if spec.get("schema") != SPEC_SCHEMA:
        raise G16ExactPublicationContextCompilerError("context spec schema mismatch")
    if spec.get("mode") != requested_mode:
        raise G16ExactPublicationContextCompilerError(
            f"context spec mode must be {requested_mode!r}"
        )
    context = spec.get("context")
    if not isinstance(context, dict):
        raise G16ExactPublicationContextCompilerError("context spec must contain an object context")
    expected = set(_REQUIRED_KEYS[requested_mode])
    observed = set(context)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise G16ExactPublicationContextCompilerError(
            f"context keys mismatch; missing={missing}, extra={extra}"
        )


def _artifact_fingerprint(mode: str, artifact: Mapping[str, Any]) -> str:
    field = "lock_fingerprint" if mode == LOCK_MODE else "completion_fingerprint"
    value = artifact.get(field)
    if not isinstance(value, str) or not value:
        raise G16ExactPublicationContextCompilerError(
            f"compiled {mode} artifact lacks {field}"
        )
    return value


def compile_context(
    spec_path: Path,
    *,
    mode: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if mode not in MODES:
        raise G16ExactPublicationContextCompilerError(f"unsupported mode: {mode}")
    spec_value, spec_raw = _load_json(spec_path, label="context spec")
    if not isinstance(spec_value, dict):
        raise G16ExactPublicationContextCompilerError("context spec must be a JSON object")
    _validate_spec(spec_value, requested_mode=mode)

    references: list[dict[str, Any]] = []
    context = _resolve_reference(
        spec_value["context"],
        base=spec_path.parent,
        references=references,
    )
    if not isinstance(context, dict):
        raise G16ExactPublicationContextCompilerError("resolved context must be an object")
    for key in _REQUIRED_KEYS[mode]:
        if not isinstance(context.get(key), dict):
            raise G16ExactPublicationContextCompilerError(
                f"resolved context field {key!r} must be an object"
            )
    if mode == LOCK_MODE:
        _assert_lock_outcome_blind(context)
        _assert_lock_reference_paths_outcome_blind(references)
        artifact = gate.build_curve_lock(**context)
    else:
        artifact = gate.build_completion(**context)

    references = sorted(
        references,
        key=lambda item: (item["context_path"], item["path"], item["sha256"]),
    )
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "mode": mode,
        "status": (
            "EXACT_G16_LOCK_CONTEXT_COMPILED"
            if mode == LOCK_MODE
            else "EXACT_G16_PUBLICATION_CONTEXT_COMPILED"
        ),
        "spec_schema": SPEC_SCHEMA,
        "spec_sha256": _sha256_bytes(spec_raw),
        "context_fingerprint": _fp(context),
        "artifact_schema": artifact.get("schema"),
        "artifact_status": artifact.get("status"),
        "artifact_fingerprint": _artifact_fingerprint(mode, artifact),
        "references": references,
        "reference_count": len(references),
        "actual_g16_outcomes_used": mode == COMPLETE_MODE,
        "fixed_outcome_boundary": "POST_LOCK_ONLY",
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_g16_blind_prior": False,
        "may_change_g16_blind_forecast": False,
        "may_change_posterior": False,
        "may_select_lessons_from_g16_outcomes": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "options_implementation_authorized": False,
    }
    receipt["fingerprint"] = _fp(receipt)
    validate_receipt(receipt, context=context, artifact=artifact, mode=mode)
    return context, artifact, receipt


def validate_receipt(
    receipt: Mapping[str, Any],
    *,
    context: Mapping[str, Any],
    artifact: Mapping[str, Any],
    mode: str,
) -> None:
    candidate = copy.deepcopy(dict(receipt))
    observed = candidate.pop("fingerprint", None)
    if candidate.get("schema") != RECEIPT_SCHEMA or observed != _fp(candidate):
        raise G16ExactPublicationContextCompilerError("compiler receipt schema or fingerprint mismatch")
    if candidate.get("mode") != mode:
        raise G16ExactPublicationContextCompilerError("compiler receipt mode mismatch")
    if candidate.get("context_fingerprint") != _fp(context):
        raise G16ExactPublicationContextCompilerError("compiler receipt context fingerprint mismatch")
    if candidate.get("artifact_fingerprint") != _artifact_fingerprint(mode, artifact):
        raise G16ExactPublicationContextCompilerError("compiler receipt artifact fingerprint mismatch")
    if candidate.get("actual_g16_outcomes_used") is not (mode == COMPLETE_MODE):
        raise G16ExactPublicationContextCompilerError("compiler receipt outcome boundary mismatch")
    for field in (
        "paid_live_data_assumed",
        "random_shuffle_used",
        "may_change_g16_blind_prior",
        "may_change_g16_blind_forecast",
        "may_change_posterior",
        "may_select_lessons_from_g16_outcomes",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
        "options_implementation_authorized",
    ):
        if candidate.get(field) is not False:
            raise G16ExactPublicationContextCompilerError(f"compiler receipt must keep {field}=false")
    for field in ("one_signal_authority_preserved", "blind_forecasts_immutable"):
        if candidate.get(field) is not True:
            raise G16ExactPublicationContextCompilerError(f"compiler receipt must keep {field}=true")
    if candidate.get("cme_event_contracts_mode") != "SHADOW":
        raise G16ExactPublicationContextCompilerError("CME event contracts must remain SHADOW")
    if candidate.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise G16ExactPublicationContextCompilerError("brokerage contract must remain tastytrade")
    references = list(candidate.get("references") or [])
    if references != sorted(
        references,
        key=lambda item: (item["context_path"], item["path"], item["sha256"]),
    ):
        raise G16ExactPublicationContextCompilerError("compiler references are not canonical")
    if candidate.get("reference_count") != len(references):
        raise G16ExactPublicationContextCompilerError("compiler reference count mismatch")


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def selftest() -> int:
    print("[ng_g16_exact_publication_context_compiler] import/selftest PASS")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=False)
    for mode in MODES:
        subparser = subparsers.add_parser(mode)
        subparser.add_argument("--spec", type=Path, required=True)
        subparser.add_argument("--context-out", type=Path, required=True)
        subparser.add_argument("--out", type=Path, required=True)
        subparser.add_argument("--receipt-out", type=Path, required=True)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest or args.mode is None:
        return selftest()
    context, artifact, receipt = compile_context(args.spec, mode=args.mode)
    _write_json(args.context_out, context)
    _write_json(args.out, artifact)
    _write_json(args.receipt_out, receipt)
    print(
        json.dumps(
            {
                "mode": args.mode,
                "status": artifact.get("status"),
                "context_out": str(args.context_out),
                "out": str(args.out),
                "receipt_out": str(args.receipt_out),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
