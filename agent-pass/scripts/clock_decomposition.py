"""Separate the common recognition clock from first structural-event timing.

SPECULATIVE prediction recorded before execution: the common recognition delay
may account for part of the similar M1 centers. No causal claim or cutoff is fit.
All original observations, null endpoints and orientations remain in the table.
"""
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
DEFINITIONS = ["quote_relocation", "touch_size_change", "wire_aggressor_run_start"]
NS = 10**9


def run():
    parts, provenance = [], []
    for day in DAYS:
        npth = ROOT / "tables" / f"{day}-detector-free-nearest.csv"
        cpth = ROOT / "tables" / f"{day}-candidate-operands.csv"
        n = pd.read_csv(npth, dtype={"first_after_birth_receive_ns": "Int64"},
                        float_precision="round_trip")
        c = pd.read_csv(cpth, dtype={"recognition_ns": "Int64"})
        assert not c.candidate_id.duplicated().any()
        assert not n.duplicated(["candidate_id", "definition"]).any()
        q = n.merge(c[["candidate_id", "birth_second", "recognition_ns"]],
                    on="candidate_id", validate="many_to_one")
        assert len(q) == 3*len(c)
        birth = q.birth_second.astype("int64") * NS
        q["event_wait_ns"] = q.first_after_birth_receive_ns - birth
        q["recognition_delay_ns"] = q.recognition_ns - birth
        q["recognition_minus_event_ns"] = q.recognition_ns - q.first_after_birth_receive_ns
        valid = q.recognition_minus_event_ns.notna()
        assert (q.loc[valid, "recognition_minus_event_ns"] ==
                q.loc[valid, "recognition_delay_ns"] - q.loc[valid, "event_wait_ns"]).all()
        assert q.loc[q.event_wait_ns.notna(), "event_wait_ns"].ge(0).all()
        for field in ["event_wait", "recognition_delay", "recognition_minus_event"]:
            q[field + "_s"] = q[field + "_ns"].astype("Float64") / NS
        assert np.allclose(q.loc[valid, "recognition_minus_event_s"].astype(float),
                           q.loc[valid, "recognition_advantage_s"], rtol=0, atol=1e-9)
        q["day"] = day
        parts.append(q)
        for p in [npth, cpth]:
            provenance.append({"path": str(p.relative_to(ROOT)),
                               "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
    all_rows = pd.concat(parts, ignore_index=True)
    all_rows.to_csv(ROOT / "tables/clock-decomposition-observations.csv", index=False)
    recon = []
    plt.rcParams.update({"font.size": 11})
    for orientation in ["SAME", "FLIP", "NO_PREDECESSOR"]:
        for definition, field in [(x, "event_wait_s") for x in DEFINITIONS] + [
                ("quote_relocation", "recognition_delay_s")]:
            slug = definition if field == "event_wait_s" else "recognition_delay"
            name = f"clock-decomposition-{slug}-{orientation}.png"
            fig, ax = plt.subplots(figsize=(9, 6.6))
            for day, color in zip(DAYS, COLORS):
                q = all_rows[(all_rows.day == day) & (all_rows.orientation == orientation) &
                             (all_rows.definition == definition)]
                values = np.sort(q[field].dropna().to_numpy(dtype=float))
                ax.plot(np.arange(len(values)), values, color=color, linewidth=1.65,
                        marker="o", markersize=2.5, markeredgewidth=0,
                        label=f"Oct {int(day[-2:])}: {len(q)} / {len(values)} / {len(q)-len(values)}")
                recon.append(dict(figure=name, day=day, orientation=orientation,
                    definition=slug, rows_in=len(q), points_plotted=len(values),
                    rows_excluded=len(q)-len(values), reason="missing next event or live recognition"))
            title = (definition.replace("_", " ").capitalize() + ": time after birth"
                     if field == "event_wait_s" else "Recognition delay after birth")
            ax.set_title(title + f"\n{orientation} births: four days overlaid", loc="left", pad=14)
            ax.set_xlabel("Ordered observation (each day sorted separately)")
            ax.set_ylabel("First event minus birth (seconds)" if field == "event_wait_s"
                          else "Recognition minus birth (seconds)")
            ax.legend(title="Rows in / points plotted / unavailable", loc="upper left",
                      fontsize=10, title_fontsize=10, framealpha=.96)
            ax.grid(axis="y", color="#dddddd", linewidth=.55)
            ax.spines[["top", "right"]].set_visible(False)
            fig.text(.12, .035, "Original seconds and ranks. No smoothing or rescaling.\n"
                     "Oct 2/17 partial. Oct 18 includes the seam supplement.", fontsize=9)
            fig.tight_layout(rect=(0, .09, 1, 1))
            fig.savefig(ROOT / "figures" / name, dpi=170, facecolor="white")
            plt.close(fig)
    reconciliation = pd.DataFrame(recon)
    assert (reconciliation.rows_in == reconciliation.points_plotted + reconciliation.rows_excluded).all()
    reconciliation.to_csv(ROOT / "tables/clock-decomposition-figure-reconciliation.csv", index=False)
    # Distribution plots precede compact descriptive counts. No statistical gate.
    summaries = []
    for (day, orientation, definition), q in all_rows.groupby(["day", "orientation", "definition"]):
        valid = q.recognition_minus_event_ns.notna()
        joint = q.loc[valid]
        pearson = (joint.recognition_minus_event_s.astype(float).corr(
            joint.recognition_delay_s.astype(float)) if len(joint) > 1 and
            joint.recognition_minus_event_s.nunique() > 1 and
            joint.recognition_delay_s.nunique() > 1 else np.nan)
        summaries.append(dict(day=day, orientation=orientation, definition=definition,
            rows_in=len(q), exact_identity_rows=int(valid.sum()), unavailable=int((~valid).sum()),
            event_in_birth_second=int((q.event_wait_ns < NS).sum()),
            first_event_before_recognition=int((q.recognition_minus_event_ns > 0).sum()),
            first_event_at_recognition=int((q.recognition_minus_event_ns == 0).sum()),
            first_event_after_recognition=int((q.recognition_minus_event_ns < 0).sum()),
            pearson_original_with_recognition_delay=pearson))
    summary = pd.DataFrame(summaries)
    summary.to_csv(ROOT / "tables/clock-decomposition-summary.csv", index=False)
    (ROOT / "tables/clock-decomposition-source-provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    print(summary[summary.orientation == "SAME"].to_string(index=False))
    print("all rows", len(all_rows), "exact identities", int(all_rows.recognition_minus_event_ns.notna().sum()))


if __name__ == "__main__":
    run()
