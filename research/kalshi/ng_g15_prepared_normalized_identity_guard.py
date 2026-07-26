#!/usr/bin/env python3
"""Public recursion-safe entrypoint for the prepared G15 identity/time guard."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import ng_g15_prepared_normalized_identity_guard_impl as _impl

for _name in dir(_impl):
    if not _name.startswith("__") and _name not in {"build_guard", "validate_guard", "main"}:
        globals()[_name] = getattr(_impl, _name)


def build_guard(
    bridge: Mapping[str, Any],
    prepared_index: Mapping[str, Any],
    *,
    verify_files: bool = True,
) -> dict[str, Any]:
    """Build once while keeping implementation validation non-recursive.

    Public dependency hooks are mirrored into the implementation for the duration of
    the call. The lane scanner also records an event-type mismatch before deeper row
    validation, so malformed MBO-shaped rows cannot hide inside the L1/trades lane (or
    vice versa).
    """
    original_validate = _impl.validate_guard
    original_bridge_validator = _impl.validate_bridge_output
    original_prepared_validator = _impl.validate_prepared_index
    original_scan_source = _impl._scan_source

    def envelope_only(guard: Mapping[str, Any], *, verify_files: bool = True) -> None:
        original_validate(guard, verify_files=False)

    def scan_source_with_lane_guard(
        source: Mapping[str, Any],
        *,
        expected_event_type: str,
        **kwargs: Any,
    ) -> tuple[dict[str, Any], list[str]]:
        evidence, blockers = original_scan_source(
            source,
            expected_event_type=expected_event_type,
            **kwargs,
        )
        path = Path(str(source.get("path") or ""))
        if path.is_file():
            for line_number, row in enumerate(_impl._iter_jsonl(path), 1):
                if str(row.get("event_type") or "") != expected_event_type:
                    blockers.append(f"NORMALIZED_EVENT_TYPE_MISMATCH:{line_number}")
        return evidence, sorted(set(blockers))

    _impl.validate_guard = envelope_only
    _impl.validate_bridge_output = globals()["validate_bridge_output"]
    _impl.validate_prepared_index = globals()["validate_prepared_index"]
    _impl._scan_source = scan_source_with_lane_guard
    try:
        result = _impl.build_guard(
            bridge,
            prepared_index,
            verify_files=verify_files,
        )
    finally:
        _impl.validate_guard = original_validate
        _impl.validate_bridge_output = original_bridge_validator
        _impl.validate_prepared_index = original_prepared_validator
        _impl._scan_source = original_scan_source
    original_validate(result, verify_files=False)
    return result


def validate_guard(guard: Mapping[str, Any], *, verify_files: bool = True) -> None:
    """Validate the envelope, then optionally rebuild exactly once from source files."""
    _impl.validate_guard(guard, verify_files=False)
    if verify_files:
        rebuilt = build_guard(
            guard["bridge"],
            guard["prepared_index"],
            verify_files=True,
        )
        if rebuilt != dict(guard):
            raise PreparedNormalizedIdentityGuardError(
                "guard is not the deterministic rebuild"
            )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", nargs="?")
    parser.add_argument("--bridge", type=Path)
    parser.add_argument("--prepared-index", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.bridge or not args.prepared_index or not args.out:
        parser.error("--bridge, --prepared-index, and --out are required")
    result = build_guard(
        json.loads(args.bridge.read_text(encoding="utf-8")),
        json.loads(args.prepared_index.read_text(encoding="utf-8")),
    )
    _atomic_json(args.out, result)
    print(json.dumps({"out": str(args.out), "status": result["status"]}, sort_keys=True))
    return 0 if result["status"] == READY else 2


if __name__ == "__main__":
    raise SystemExit(main())
