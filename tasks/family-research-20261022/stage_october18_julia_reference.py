"""Verify or stage the exact eight pre-dispatch Julia scripts from October 18."""

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FAMILIES = Path("artifacts/sqlite-triage/20261022/families")
PLAN = FAMILIES / "joint-models-v4-candidate-20261022/rerun_plan.json"
V1 = FAMILIES / "joint-models-v1/scripts"
V2 = FAMILIES / "joint-inputs-v2/scripts"
REBOUND = {
    "run_joint_models.jl", "run_neural_models.jl", "analyze_joint_interactions.jl",
    "summarize_joint_models.jl", "analyze_observed_price_paths.jl",
}
RULES = {"model_rules.jl", "test_model_rules.jl"}
DESCRIPTIVE = "descriptive_math.jl"


def sha256(payload):
    return hashlib.sha256(payload).hexdigest()


def verify(root):
    plan = json.loads((root / PLAN).read_bytes())
    expected = plan["scripts"]
    if expected.keys() != REBOUND | RULES | {DESCRIPTIVE}:
        raise ValueError("Unexpected October 18 launch script inventory")

    verified = {}
    receipt = {}
    for name, digest in expected.items():
        source = (V2 if name in RULES else V1) / name
        raw = (root / source).read_bytes()
        lf = raw.replace(b"\r\n", b"\n")
        if name in REBOUND:
            old = b'const OUT=joinpath(BASE,"joint-models-v1")'
            if lf.count(old) != 1:
                raise ValueError(f"Original output binding differs for {name}")
            candidates = [lf.replace(old, b'const OUT=ENV["JOINT_MODEL_OUT"]')]
            reconstruction = "Bind output to JOINT_MODEL_OUT using the verified original source"
        else:
            candidates = [raw, lf, lf.replace(b"\n", b"\r\n")]
            reconstruction = "Select the source line endings by the original byte hash"
        payload = next((candidate for candidate in candidates if sha256(candidate) == digest), None)
        if payload is None:
            raise ValueError(f"Original October 18 hash mismatch for {name}")
        verified[name] = payload
        receipt[name] = {
            "source": source.as_posix(), "reconstruction": reconstruction,
            "bytes": len(payload), "sha256": digest,
        }
    return verified, {
        "trade_date": "20231018", "launch_plan": PLAN.as_posix(),
        "scope": "Original pre-dispatch Julia scripts, not generated worker adapters or execution readiness",
        "scripts": receipt,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Stage verified scripts in a new directory")
    args = parser.parse_args()
    scripts, receipt = verify(ROOT)
    if args.output is not None:
        args.output.mkdir(exist_ok=False)
        for name, payload in scripts.items():
            (args.output / name).write_bytes(payload)
        for name, entry in receipt["scripts"].items():
            if sha256((args.output / name).read_bytes()) != entry["sha256"]:
                raise ValueError(f"Staged bytes changed for {name}")
        (args.output / "verified-scripts.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
