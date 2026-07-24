#!/usr/bin/env python3
"""Attest the compiler-backed exact G16 lock and publication path.

The exact G16 context compiler resolves fingerprinted JSON references and builds the
canonical pre-outcome curve lock or post-lock publication completion. This gate makes
that operational path independently auditable: it snapshots the UTF-8 inputs,
reconstructs the compiler in an isolated directory, rejects references outside the
specification directory, and emits a standalone deterministic attestation suitable
for historical-readiness validation.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

import ng_g16_exact_publication_context_compiler as compiler

SCHEMA = "ng_g16_exact_context_compilation_attestation.v1"
LOCK_MODE = compiler.LOCK_MODE
COMPLETE_MODE = compiler.COMPLETE_MODE
MODES = compiler.MODES

_STATUS = {
    LOCK_MODE: "EXACT_G16_LOCK_CONTEXT_COMPILATION_ATTESTED",
    COMPLETE_MODE: "EXACT_G16_PUBLICATION_CONTEXT_COMPILATION_ATTESTED",
}


class G16ExactContextCompilationGateError(ValueError):
    """Raised when compiler inputs cannot be reproduced exactly and safely."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _read_utf8(path: Path, *, label: str) -> str:
    try:
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeError) as error:
        raise G16ExactContextCompilationGateError(
            f"cannot read UTF-8 {label} {path}: {error}"
        ) from error


def _parse_object(raw: str, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise G16ExactContextCompilationGateError(
            f"invalid JSON in {label}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise G16ExactContextCompilationGateError(f"{label} must be a JSON object")
    return value


def _safe_relative_reference(path_value: Any) -> PurePosixPath:
    if not isinstance(path_value, str) or not path_value:
        raise G16ExactContextCompilationGateError("compiler reference path is missing")
    path = PurePosixPath(path_value)
    if path.is_absolute() or ".." in path.parts:
        raise G16ExactContextCompilationGateError(
            "compiler references must remain inside the specification directory"
        )
    return path


def _snapshot_references(
    receipt: Mapping[str, Any], *, spec_dir: Path
) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    for row in receipt.get("references") or []:
        if not isinstance(row, Mapping):
            raise G16ExactContextCompilationGateError(
                "compiler receipt references must be objects"
            )
        relative = _safe_relative_reference(row.get("path"))
        raw = _read_utf8(spec_dir / Path(*relative.parts), label="referenced artifact")
        observed_sha = _sha256_text(raw)
        if observed_sha != row.get("sha256"):
            raise G16ExactContextCompilationGateError(
                f"referenced artifact SHA-256 changed: {relative.as_posix()}"
            )
        if len(raw.encode("utf-8")) != row.get("byte_size"):
            raise G16ExactContextCompilationGateError(
                f"referenced artifact byte size changed: {relative.as_posix()}"
            )
        _parse_object(raw, label=f"referenced artifact {relative.as_posix()}")
        snapshots.append(
            {
                "context_path": row.get("context_path"),
                "path": relative.as_posix(),
                "sha256": observed_sha,
                "byte_size": len(raw.encode("utf-8")),
                "raw_utf8": raw,
            }
        )
    return sorted(
        snapshots,
        key=lambda item: (item["context_path"], item["path"], item["sha256"]),
    )


def _write_reconstruction_bundle(
    root: Path, bundle: Mapping[str, Any]
) -> tuple[Path, Path, Path, Path]:
    spec_path = root / "spec.json"
    context_path = root / "context.json"
    artifact_path = root / "artifact.json"
    receipt_path = root / "receipt.json"
    for path, key in (
        (spec_path, "spec_raw_utf8"),
        (context_path, "context_raw_utf8"),
        (artifact_path, "artifact_raw_utf8"),
        (receipt_path, "receipt_raw_utf8"),
    ):
        raw = bundle.get(key)
        if not isinstance(raw, str):
            raise G16ExactContextCompilationGateError(f"source bundle lacks {key}")
        path.write_text(raw, encoding="utf-8")
    for snapshot in bundle.get("reference_snapshots") or []:
        if not isinstance(snapshot, Mapping):
            raise G16ExactContextCompilationGateError(
                "reference snapshots must be objects"
            )
        relative = _safe_relative_reference(snapshot.get("path"))
        raw = snapshot.get("raw_utf8")
        if not isinstance(raw, str):
            raise G16ExactContextCompilationGateError(
                f"reference snapshot lacks raw UTF-8: {relative.as_posix()}"
            )
        target = root / Path(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(raw, encoding="utf-8")
    return spec_path, context_path, artifact_path, receipt_path


def _validate_source_bundle(
    bundle: Mapping[str, Any], *, mode: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    if mode not in MODES:
        raise G16ExactContextCompilationGateError(f"unsupported mode: {mode}")
    with tempfile.TemporaryDirectory() as tempdir:
        root = Path(tempdir)
        spec_path, context_path, artifact_path, receipt_path = (
            _write_reconstruction_bundle(root, bundle)
        )
        spec_raw = _read_utf8(spec_path, label="specification")
        context_raw = _read_utf8(context_path, label="resolved context")
        artifact_raw = _read_utf8(artifact_path, label="compiled artifact")
        receipt_raw = _read_utf8(receipt_path, label="compiler receipt")
        spec = _parse_object(spec_raw, label="specification")
        context = _parse_object(context_raw, label="resolved context")
        artifact = _parse_object(artifact_raw, label="compiled artifact")
        receipt = _parse_object(receipt_raw, label="compiler receipt")

        snapshots = list(bundle.get("reference_snapshots") or [])
        for snapshot in snapshots:
            relative = _safe_relative_reference(snapshot.get("path"))
            raw = _read_utf8(root / Path(*relative.parts), label="reference snapshot")
            if _sha256_text(raw) != snapshot.get("sha256"):
                raise G16ExactContextCompilationGateError(
                    f"reference snapshot fingerprint mismatch: {relative.as_posix()}"
                )
            if len(raw.encode("utf-8")) != snapshot.get("byte_size"):
                raise G16ExactContextCompilationGateError(
                    f"reference snapshot byte-size mismatch: {relative.as_posix()}"
                )

        rebuilt_context, rebuilt_artifact, rebuilt_receipt = compiler.compile_context(
            spec_path, mode=mode
        )
        if rebuilt_context != context:
            raise G16ExactContextCompilationGateError(
                "saved resolved context differs from deterministic compiler output"
            )
        if rebuilt_artifact != artifact:
            raise G16ExactContextCompilationGateError(
                "saved exact artifact differs from deterministic compiler output"
            )
        if rebuilt_receipt != receipt:
            raise G16ExactContextCompilationGateError(
                "saved compiler receipt differs from deterministic compiler output"
            )
        if receipt.get("references") != [
            {
                key: snapshot.get(key)
                for key in ("context_path", "path", "sha256", "byte_size")
            }
            for snapshot in snapshots
        ]:
            raise G16ExactContextCompilationGateError(
                "reference snapshots do not exactly match the compiler receipt"
            )
        return spec, context, artifact, receipt


def build_attestation(
    *,
    mode: str,
    spec_path: Path,
    context_path: Path,
    artifact_path: Path,
    receipt_path: Path,
    lock_attestation_path: Path | None = None,
) -> dict[str, Any]:
    spec_raw = _read_utf8(spec_path, label="specification")
    context_raw = _read_utf8(context_path, label="resolved context")
    artifact_raw = _read_utf8(artifact_path, label="compiled artifact")
    receipt_raw = _read_utf8(receipt_path, label="compiler receipt")
    spec = _parse_object(spec_raw, label="specification")
    context = _parse_object(context_raw, label="resolved context")
    artifact = _parse_object(artifact_raw, label="compiled artifact")
    receipt = _parse_object(receipt_raw, label="compiler receipt")

    compiler._validate_spec(spec, requested_mode=mode)
    compiler.validate_receipt(receipt, context=context, artifact=artifact, mode=mode)
    rebuilt_context, rebuilt_artifact, rebuilt_receipt = compiler.compile_context(
        spec_path, mode=mode
    )
    if (rebuilt_context, rebuilt_artifact, rebuilt_receipt) != (
        context,
        artifact,
        receipt,
    ):
        raise G16ExactContextCompilationGateError(
            "saved compiler outputs are not an exact deterministic reconstruction"
        )

    source_bundle: dict[str, Any] = {
        "spec_raw_utf8": spec_raw,
        "context_raw_utf8": context_raw,
        "artifact_raw_utf8": artifact_raw,
        "receipt_raw_utf8": receipt_raw,
        "reference_snapshots": _snapshot_references(receipt, spec_dir=spec_path.parent),
    }
    lock_attestation: dict[str, Any] | None = None
    if mode == COMPLETE_MODE:
        if lock_attestation_path is None:
            raise G16ExactContextCompilationGateError(
                "publication compilation requires the pre-outcome lock attestation"
            )
        lock_raw = _read_utf8(
            lock_attestation_path, label="lock compilation attestation"
        )
        lock_attestation = _parse_object(
            lock_raw, label="lock compilation attestation"
        )
        validate_attestation(lock_attestation)
        source_bundle["lock_attestation_raw_utf8"] = lock_raw
        exact_lock = context.get("exact_curve_lock")
        if not isinstance(exact_lock, Mapping):
            raise G16ExactContextCompilationGateError(
                "publication context lacks exact_curve_lock"
            )
        if exact_lock.get("lock_fingerprint") != lock_attestation.get(
            "artifact_fingerprint"
        ):
            raise G16ExactContextCompilationGateError(
                "publication context lock does not match the attested pre-outcome lock"
            )
    elif lock_attestation_path is not None:
        raise G16ExactContextCompilationGateError(
            "lock mode must not accept a prior lock attestation"
        )

    attestation: dict[str, Any] = {
        "schema": SCHEMA,
        "mode": mode,
        "status": _STATUS[mode],
        "spec_sha256": _sha256_text(spec_raw),
        "context_sha256": _sha256_text(context_raw),
        "artifact_sha256": _sha256_text(artifact_raw),
        "receipt_sha256": _sha256_text(receipt_raw),
        "context_fingerprint": compiler._fp(context),
        "artifact_fingerprint": compiler._artifact_fingerprint(mode, artifact),
        "compiler_receipt_fingerprint": receipt.get("fingerprint"),
        "reference_count": receipt.get("reference_count"),
        "reference_set_fingerprint": _fp(receipt.get("references") or []),
        "lock_context_compilation_attestation_fingerprint": (
            lock_attestation.get("fingerprint") if lock_attestation else None
        ),
        "source_lock_artifact_fingerprint": (
            lock_attestation.get("artifact_fingerprint") if lock_attestation else None
        ),
        "source_bundle": source_bundle,
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
    attestation["fingerprint"] = _fp(attestation)
    validate_attestation(attestation)
    return attestation


def validate_attestation(value: Mapping[str, Any]) -> None:
    candidate = copy.deepcopy(dict(value))
    observed = candidate.pop("fingerprint", None)
    if candidate.get("schema") != SCHEMA or observed != _fp(candidate):
        raise G16ExactContextCompilationGateError(
            "context compilation attestation schema or fingerprint mismatch"
        )
    mode = candidate.get("mode")
    if mode not in MODES or candidate.get("status") != _STATUS[mode]:
        raise G16ExactContextCompilationGateError(
            "context compilation attestation mode or status mismatch"
        )
    bundle = candidate.get("source_bundle")
    if not isinstance(bundle, Mapping):
        raise G16ExactContextCompilationGateError(
            "context compilation attestation lacks source bundle"
        )
    spec, context, artifact, receipt = _validate_source_bundle(bundle, mode=mode)
    raw_fields = {
        "spec_sha256": "spec_raw_utf8",
        "context_sha256": "context_raw_utf8",
        "artifact_sha256": "artifact_raw_utf8",
        "receipt_sha256": "receipt_raw_utf8",
    }
    for field, raw_key in raw_fields.items():
        if candidate.get(field) != _sha256_text(str(bundle.get(raw_key))):
            raise G16ExactContextCompilationGateError(f"{field} mismatch")
    if candidate.get("context_fingerprint") != compiler._fp(context):
        raise G16ExactContextCompilationGateError("context fingerprint mismatch")
    if candidate.get("artifact_fingerprint") != compiler._artifact_fingerprint(
        mode, artifact
    ):
        raise G16ExactContextCompilationGateError("artifact fingerprint mismatch")
    if candidate.get("compiler_receipt_fingerprint") != receipt.get("fingerprint"):
        raise G16ExactContextCompilationGateError(
            "compiler receipt fingerprint mismatch"
        )
    if candidate.get("reference_count") != receipt.get("reference_count"):
        raise G16ExactContextCompilationGateError("reference count mismatch")
    if candidate.get("reference_set_fingerprint") != _fp(
        receipt.get("references") or []
    ):
        raise G16ExactContextCompilationGateError("reference set fingerprint mismatch")

    if mode == COMPLETE_MODE:
        lock_raw = bundle.get("lock_attestation_raw_utf8")
        if not isinstance(lock_raw, str):
            raise G16ExactContextCompilationGateError(
                "publication attestation lacks lock attestation snapshot"
            )
        lock_attestation = _parse_object(
            lock_raw, label="embedded lock compilation attestation"
        )
        validate_attestation(lock_attestation)
        if candidate.get(
            "lock_context_compilation_attestation_fingerprint"
        ) != lock_attestation.get("fingerprint"):
            raise G16ExactContextCompilationGateError(
                "publication attestation lock-attestation fingerprint mismatch"
            )
        exact_lock = context.get("exact_curve_lock")
        if not isinstance(exact_lock, Mapping):
            raise G16ExactContextCompilationGateError(
                "publication context lacks exact_curve_lock"
            )
        if exact_lock.get("lock_fingerprint") != lock_attestation.get(
            "artifact_fingerprint"
        ):
            raise G16ExactContextCompilationGateError(
                "publication context bypasses the attested pre-outcome lock"
            )
        if candidate.get("source_lock_artifact_fingerprint") != lock_attestation.get(
            "artifact_fingerprint"
        ):
            raise G16ExactContextCompilationGateError(
                "publication source-lock fingerprint mismatch"
            )
    else:
        if candidate.get("lock_context_compilation_attestation_fingerprint") is not None:
            raise G16ExactContextCompilationGateError(
                "pre-outcome lock attestation must not claim an upstream lock attestation"
            )
        if candidate.get("source_lock_artifact_fingerprint") is not None:
            raise G16ExactContextCompilationGateError(
                "pre-outcome lock attestation must not claim a source lock artifact"
            )

    if candidate.get("actual_g16_outcomes_used") is not (mode == COMPLETE_MODE):
        raise G16ExactContextCompilationGateError(
            "context compilation outcome boundary mismatch"
        )
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
            raise G16ExactContextCompilationGateError(
                f"context compilation attestation must keep {field}=false"
            )
    for field in ("one_signal_authority_preserved", "blind_forecasts_immutable"):
        if candidate.get(field) is not True:
            raise G16ExactContextCompilationGateError(
                f"context compilation attestation must keep {field}=true"
            )
    if candidate.get("fixed_outcome_boundary") != "POST_LOCK_ONLY":
        raise G16ExactContextCompilationGateError("fixed outcome boundary mismatch")
    if candidate.get("cme_event_contracts_mode") != "SHADOW":
        raise G16ExactContextCompilationGateError(
            "CME event contracts must remain SHADOW"
        )
    if candidate.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise G16ExactContextCompilationGateError(
            "brokerage contract must remain tastytrade, not IBKR"
        )


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def selftest() -> int:
    print("[ng_g16_exact_context_compilation_gate] import/selftest PASS")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=False)
    for mode in MODES:
        subparser = subparsers.add_parser(mode)
        subparser.add_argument("--spec", type=Path, required=True)
        subparser.add_argument("--context", type=Path, required=True)
        subparser.add_argument("--artifact", type=Path, required=True)
        subparser.add_argument("--receipt", type=Path, required=True)
        subparser.add_argument("--out", type=Path, required=True)
        if mode == COMPLETE_MODE:
            subparser.add_argument("--lock-attestation", type=Path, required=True)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest or args.mode is None:
        return selftest()
    attestation = build_attestation(
        mode=args.mode,
        spec_path=args.spec,
        context_path=args.context,
        artifact_path=args.artifact,
        receipt_path=args.receipt,
        lock_attestation_path=getattr(args, "lock_attestation", None),
    )
    _write_json(args.out, attestation)
    print(
        json.dumps(
            {
                "mode": args.mode,
                "status": attestation["status"],
                "artifact_fingerprint": attestation["artifact_fingerprint"],
                "out": str(args.out),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
