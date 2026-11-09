"""Overlay the four original M1 SAME distributions, without rescaling or smoothing."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DAYS = ["20231002", "20231003", "20231017", "20231018"]
COLORS = ["#0072B2", "#D55E00", "#009E73", "#CC79A7"]
DEFINITIONS = {
    "quote_relocation": "Quote relocation",
    "touch_size_change": "Touch-size change",
    "wire_aggressor_run_start": "Aggressor run start",
}


def run():
    sources = {}
    provenance = []
    for day in DAYS:
        path = ROOT / "tables" / f"{day}-detector-free-nearest.csv"
        sources[day] = pd.read_csv(path, float_precision="round_trip")
        provenance.append({"path": str(path.relative_to(ROOT)),
                           "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    previous = pd.read_csv(ROOT / "tables/crossday-moonshot-figure-reconciliation.csv")
    reconciliation = []
    points = []
    plt.rcParams.update({"font.size": 11, "font.family": "DejaVu Sans"})
    for definition, title in DEFINITIONS.items():
        filename = f"shape-overlay-{definition}-SAME.png"
        fig, ax = plt.subplots(figsize=(9, 6.6))
        for day, color in zip(DAYS, COLORS):
            frame = sources[day]
            frame = frame[(frame.orientation == "SAME") & (frame.definition == definition)]
            assert not frame.candidate_id.duplicated().any()
            defined = frame.recognition_advantage_s.notna()
            ordered = frame.loc[defined].sort_values("recognition_advantage_s", kind="stable")
            values = ordered.recognition_advantage_s.to_numpy()
            assert np.isfinite(values).all()
            n, plotted = len(frame), len(values)
            old = previous[(previous.figure == "crossday-M1-SAME.png") &
                           (previous.panel == day + " " + definition)]
            assert len(old) == 1
            assert (n, plotted, n-plotted) == tuple(
                old.iloc[0][["rows_in", "points_plotted", "rows_excluded"]].astype(int))
            label = f"Oct {int(day[-2:])}: {n} / {plotted} / {n-plotted}"
            ax.plot(np.arange(plotted), values, color=color, linewidth=1.65,
                    marker="o", markersize=2.5, markeredgewidth=0, label=label)
            reconciliation.append(dict(figure=filename, day=day, orientation="SAME",
                definition=definition, rows_in=n, points_plotted=plotted,
                rows_excluded=n-plotted, reason="finalization-only or no later event"))
            points.extend(dict(day=day, definition=definition, orientation="SAME",
                candidate_id=ident, ordered_observation=rank, recognition_minus_event_s=value)
                for rank, (ident, value) in enumerate(zip(ordered.candidate_id, values)))
        ax.axhline(0, color="#555555", linewidth=0.65, zorder=0)
        ax.set_title(title + "\nSAME births: four days overlaid", loc="left", pad=14)
        ax.set_xlabel("Ordered observation (each day sorted separately)")
        ax.set_ylabel("Recognition minus first event (seconds)")
        ax.grid(axis="y", color="#dddddd", linewidth=0.55)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(title="Rows in / points plotted / unavailable", loc="lower right",
                  frameon=True, framealpha=0.96, fontsize=10, title_fontsize=10)
        fig.text(0.12, 0.035,
            "Original values and ranks. Points joined without smoothing.\n"
            "Oct 2 and 17 are partial sessions. Oct 18 includes the seam supplement.",
            fontsize=9, color="#444444")
        fig.tight_layout(rect=(0, 0.09, 1, 1))
        fig.savefig(ROOT / "figures" / filename, dpi=170, facecolor="white")
        plt.close(fig)
    out = pd.DataFrame(reconciliation)
    assert (out.rows_in == out.points_plotted + out.rows_excluded).all()
    out.to_csv(ROOT / "tables/shape-overlay-figure-reconciliation.csv", index=False)
    pd.DataFrame(points).to_csv(ROOT / "tables/shape-overlay-points.csv", index=False)
    (ROOT / "tables/shape-overlay-source-provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    print(out.to_string(index=False))


if __name__ == "__main__":
    run()
