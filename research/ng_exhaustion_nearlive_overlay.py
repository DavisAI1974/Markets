"""Isolated S3-backed near-live overlay for NG exhaustion V0.

This is deliberately not permanent Frankie. It reads one hash-verified S3 day at a
time, runs the deterministic clock causally, and emits the validated NOVA model-facing
packet plus a small audit summary. Microstructure stays unavailable until a separate
validated live classifier is wired; it cannot alter runway seconds here.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any, Iterable, Mapping, Sequence

from ng_exhaustion_runway_clock import ExhaustionRunwayClock, EXPECTED_CLASSIFIER_SHA256
from ng_exhaustion_s3_store import NGExhaustionS3Store, S3StoreError
from nova_ng_exhaustion_packet import FrankieRunwayPacket, Provenance, ReductionError

DEFAULT_CHECKPOINTS = (0.0, 30.0, 60.0, 300.0)


class OverlayError(RuntimeError):
    pass


@dataclass(frozen=True)
class LiveClockUpdate:
    event_id: str
    session_id: str
    t0: str | int | float
    family: str
    elapsed_s: float
    a_t0_to_plus60: Sequence[float] | None = None
    microstructure: str = "unavailable"
    data_flags: Mapping[str, bool] | None = None


class IsolatedRunwayOverlay:
    def __init__(self, clock: ExhaustionRunwayClock):
        self.clock = clock

    def update(self, event: LiveClockUpdate) -> dict[str, Any]:
        out = self.clock.update(
            event_id=event.event_id,
            session_id=event.session_id,
            t0=event.t0,
            family=event.family,
            elapsed_s=event.elapsed_s,
            a_t0_to_plus60=event.a_t0_to_plus60,
            microstructure=event.microstructure,
            data_flags=event.data_flags,
        )
        if out.get("future_price_accessed") is not False:
            raise OverlayError("clock future-price invariant failed")
        return out


def record_to_update(row: Mapping[str, Any], elapsed_s: float) -> LiveClockUpdate:
    family = str(row["family"])
    window = None
    flags = {"event_clock": True, "microstructure": False}
    if family == "A" and elapsed_s >= 60.0:
        full = row.get("dipole_roll20_oriented_t_minus60_to_plus60")
        if not isinstance(full, list) or len(full) != 121:
            flags["a_classifier_window"] = False
        else:
            window = full[60:]
            flags["a_classifier_window"] = True
    return LiveClockUpdate(
        event_id=str(row["blind_id"]),
        session_id=str(row["day"]),
        t0=int(row["t0_second_utc"]),
        family=family,
        elapsed_s=float(elapsed_s),
        a_t0_to_plus60=window,
        microstructure="unavailable",
        data_flags=flags,
    )


def replay_day(
    *,
    store: NGExhaustionS3Store,
    clock: ExhaustionRunwayClock,
    day: str,
    checkpoints: Sequence[float] = DEFAULT_CHECKPOINTS,
) -> tuple[str, dict[str, Any]]:
    source_start = time.perf_counter()
    cache_start = time.perf_counter()
    cache_path, cache_hit_initial = store.ensure_day_cached(day)
    cache_ensure_ms = (time.perf_counter() - cache_start) * 1000.0
    decode_start = time.perf_counter()
    rows = store.day_records(day)
    record_decode_verify_ms = (time.perf_counter() - decode_start) * 1000.0
    source_load_ms = (time.perf_counter() - source_start) * 1000.0
    overlay = IsolatedRunwayOverlay(clock)
    outputs: list[dict[str, Any]] = []
    states = Counter()
    mismatch = 0
    start = time.perf_counter()
    for row in rows:
        for elapsed in checkpoints:
            out = overlay.update(record_to_update(row, float(elapsed)))
            outputs.append(out)
            states[out["post_state"]] += 1
            if float(elapsed) >= 60.0 and row["family"] == "A":
                frozen = row.get("frozen_post_state_assignment", {}).get("label")
                if frozen and out["post_state"] != frozen:
                    mismatch += 1
    compute_ms = (time.perf_counter() - start) * 1000.0
    if mismatch:
        raise OverlayError(f"A frozen assignment mismatch count: {mismatch}")

    prov_dict = store.provenance(day)
    provenance = Provenance(**prov_dict)
    packet_start = time.perf_counter()
    packet = FrankieRunwayPacket.pack_batch(outputs, provenance)
    packet_ms = (time.perf_counter() - packet_start) * 1000.0
    restored = FrankieRunwayPacket.unpack_batch(packet)
    if len(restored["rows"]) != len(outputs):
        raise OverlayError("NOVA packet row count mismatch")
    if restored["header"].get("future_price_accessed") is not False:
        raise OverlayError("NOVA packet future-price invariant failed")

    canonical_bytes = sum(len(json.dumps(x, sort_keys=True, separators=(",", ":")).encode()) for x in outputs)
    packet_bytes = len(packet.encode())
    summary = {
        "schema": "markets.ng_exhaustion.nearlive_overlay.v0",
        "status": "PASS",
        "mode": "s3_causal_replay",
        "day": str(day),
        "source": {
            **prov_dict,
            "cache_path": str(cache_path),
            "cache_hit_initial": bool(cache_hit_initial),
            "cache_ensure_ms": round(cache_ensure_ms, 3),
            "record_decode_verify_ms": round(record_decode_verify_ms, 3),
            "source_load_and_verify_ms": round(source_load_ms, 3),
        },
        "records": len(rows),
        "checkpoints_s": [float(x) for x in checkpoints],
        "clock_updates": len(outputs),
        "state_counts": dict(sorted(states.items())),
        "a_assignment_mismatches": mismatch,
        "microstructure_policy": "unavailable_confidence_only_until_separately_validated_live_mapping",
        "clock_compute_ms": round(compute_ms, 3),
        "nova_pack_and_verify_ms": round(packet_ms, 3),
        "canonical_clock_json_bytes": canonical_bytes,
        "nova_packet_bytes": packet_bytes,
        "nova_reduction_pct": round(100.0 * (1.0 - packet_bytes / canonical_bytes), 3) if canonical_bytes else 0.0,
        "classifier_sha256": EXPECTED_CLASSIFIER_SHA256,
        "future_price_accessed": False,
        "permanent_frankie_mutated": False,
        "live_contract_ready": True,
        "live_contract_blocker": "existing live collector does not yet emit the legal 61-sample t0..+60 roll20 exhaustion window",
    }
    return packet, summary


def _parse_checkpoints(text: str) -> tuple[float, ...]:
    vals = tuple(float(x.strip()) for x in text.split(",") if x.strip())
    if not vals or any(x < 0 for x in vals):
        raise argparse.ArgumentTypeError("checkpoints must be comma-separated non-negative seconds")
    return vals


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", required=True)
    ap.add_argument("--classifier", required=True)
    ap.add_argument("--cache-dir")
    ap.add_argument("--checkpoints", type=_parse_checkpoints, default=DEFAULT_CHECKPOINTS)
    ap.add_argument("--packet-out", required=True)
    ap.add_argument("--summary-out", required=True)
    args = ap.parse_args()
    try:
        store = NGExhaustionS3Store(cache_dir=args.cache_dir)
        clock = ExhaustionRunwayClock.from_classifier_path(args.classifier)
        packet, summary = replay_day(store=store, clock=clock, day=args.day, checkpoints=args.checkpoints)
    except (S3StoreError, OverlayError, ReductionError, Exception) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True))
        return 2
    Path(args.packet_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.packet_out).write_text(packet, encoding="utf-8")
    Path(args.summary_out).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
