"""Render the isolated NG exhaustion runway clock validation view."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import matplotlib.pyplot as plt

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))

from ng_exhaustion_runway_clock import ExhaustionRunwayClock, FrozenAClassifier, SCALES


def render(classifier_path: Path, output_path: Path, *, state_fixture: str, elapsed_s: float, microstructure: str) -> dict:
    classifier = FrozenAClassifier.load(classifier_path)
    engine = ExhaustionRunwayClock(classifier)
    if state_fixture == "persistent":
        curve = classifier.centroids[1]
    elif state_fixture == "fast-collapse":
        curve = classifier.centroids[0]
    else:
        raise ValueError("state_fixture must be persistent or fast-collapse")

    result = engine.update(
        event_id=f"validation-{state_fixture}",
        session_id="frozen-validation-fixture",
        t0="fixture",
        family="A",
        elapsed_s=elapsed_s,
        a_t0_to_plus60=curve,
        microstructure=microstructure,
    )

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), constrained_layout=True)

    x = list(range(61))
    axes[0].plot(x, result["normalized_exhaustion_curve"], linewidth=2, label="normalized roll-20 dipole")
    marker_x = min(max(elapsed_s, 0.0), 60.0)
    marker_y = result["normalized_exhaustion_curve"][int(marker_x)]
    axes[0].scatter([marker_x], [marker_y], s=70, label=f"as-of {elapsed_s:.0f}s (classifier window caps at +60s)")
    axes[0].axvline(60.0, linestyle="--", linewidth=1, label="legal A confirmation +60s")
    axes[0].set_title(f"NG exhaustion classifier window | {result['post_state']}")
    axes[0].set_xlabel("seconds from t0")
    axes[0].set_ylabel("normalized dipole")
    axes[0].legend(loc="best")
    axes[0].grid(True, alpha=0.25)

    baselines = [result["runways"][scale]["baseline_total_s"] for scale in SCALES]
    remaining = [result["runways"][scale]["remaining_s"] for scale in SCALES]
    elapsed_portion = [min(elapsed_s, baseline) for baseline in baselines]
    y = list(range(len(SCALES)))
    axes[1].barh(y, elapsed_portion, label="elapsed")
    axes[1].barh(y, remaining, left=elapsed_portion, label="remaining")
    axes[1].set_yticks(y, labels=list(SCALES))
    axes[1].set_xlabel("seconds")
    axes[1].set_title(f"Frozen reveal runway clocks | microstructure={microstructure} | confidence modifier={result['confidence_modifier']}")
    axes[1].legend(loc="best")
    axes[1].grid(True, axis="x", alpha=0.25)
    for idx, scale in enumerate(SCALES):
        row = result["runways"][scale]
        axes[1].text(
            row["baseline_total_s"] * 1.005,
            idx,
            f"base {row['baseline_total_s']:.0f}s | rem {row['remaining_s']:.0f}s | conf {row['confidence']['base']}/{row['confidence']['modifier']}",
            va="center",
            fontsize=9,
        )

    fig.suptitle("Isolated deterministic NG exhaustion runway clock V0\nNo future price consumed; direction remains separate", fontsize=14)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=160)
    plt.close(fig)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--classifier", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--state", choices=("persistent", "fast-collapse"), default="persistent")
    parser.add_argument("--elapsed", type=float, default=300.0)
    parser.add_argument("--microstructure", choices=("same_side", "mixed", "opposite", "unavailable"), default="same_side")
    args = parser.parse_args()
    result = render(args.classifier, args.output, state_fixture=args.state, elapsed_s=args.elapsed, microstructure=args.microstructure)
    print(result["post_state"])
    print({scale: result["runways"][scale]["remaining_s"] for scale in SCALES})
    print(f"future_price_accessed={result['future_price_accessed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
