"""Explicit opt-in offline locality-review export. No service connections or writes to source."""
import argparse
import json
from pathlib import Path

from .core import Observation, MetricContract, LocalityConfig, LocalityEngine, LocalityError
from .ledger import DecisionLedger
from .adapters import EvidenceManifest, shadow_batch, buildmap_evidence
from .visualization import scientific_frame, write_html, replay_probes


def build_review(input_data: dict, x: str, y: str, *, limit: int, window: int,
                 tolerance: float) -> dict:
    raw_metric = input_data["metric"]
    metric = MetricContract(
        tuple(raw_metric["features"]), tuple(raw_metric["scales"]),
        tuple(raw_metric["weights"]), raw_metric["version"],
    )
    manifest_data = input_data["manifest"]
    manifest = EvidenceManifest(
        manifest_data["run_id"], manifest_data["day"],
        manifest_data["source_identity"], tuple(manifest_data["planes"]),
    )
    engine = LocalityEngine(metric, LocalityConfig(**input_data["config"]))
    events = [Observation(**record) for record in input_data["events"]]
    if len(events) > 100_000:
        raise LocalityError("offline review has a strict 100000-observation source limit")
    shadow = buildmap_evidence(shadow_batch(events, engine, DecisionLedger(), manifest))
    return scientific_frame(events, shadow, metric, x, y, limit=limit,
                            window=window, tolerance=tolerance)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a local, read-only visualization of shadow locality decisions."
    )
    parser.add_argument("input", help="JSON input used by adaptive_locality.cli")
    parser.add_argument("--output", required=True, help="new offline HTML file; overwrite refused")
    parser.add_argument("--x", required=True, help="first declared metric feature")
    parser.add_argument("--y", required=True, help="second declared metric feature")
    parser.add_argument("--limit", type=int, default=350)
    parser.add_argument("--window", type=int, default=4)
    parser.add_argument("--tolerance", type=float, default=0.1)
    parser.add_argument("--probes", help="optional NEW JSON file with deterministic replay probes")
    args = parser.parse_args()
    input_path, output_path = Path(args.input), Path(args.output)
    if input_path.resolve() == output_path.resolve():
        parser.error("input and output must differ")
    if input_path.stat().st_size > 8_000_000:
        parser.error("input exceeds offline review byte limit")
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    frame = build_review(payload, args.x, args.y, limit=args.limit,
                         window=args.window, tolerance=args.tolerance)
    # Reserve optional probe destination first and publish only from a verified frame.
    if args.probes and Path(args.probes).resolve() in (input_path.resolve(), output_path.resolve()):
        parser.error("all destinations must be distinct")
    probes = replay_probes(frame)
    write_html(frame, output_path)
    if args.probes:
        with Path(args.probes).open("x", encoding="utf-8") as out:
            json.dump({"frame_sha256": frame["frame_sha256"], "probes": probes}, out,
                      sort_keys=True, indent=2)
            out.write("\n")
    print("Offline visualization:", output_path)
    print("Raw source observations:", frame["source_count"])
    print("Displayed observations:", frame["shown_count"])
    print("Frame SHA-256:", frame["frame_sha256"])
    print("No connection, deployment, scientific job suppression, or production receipt.")


if __name__ == "__main__":
    main()
