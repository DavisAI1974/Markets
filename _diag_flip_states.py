"""_diag_flip_states.py — is the buy/sell 33% the FLIP states? (trend-following lead)

The coeff residual makes buy/sell perfect mirrors ~67% of the time. Greg: the other 33% is NOT random.
Hypothesis: the mirror is clean when there's a STRONG trend (strong flow); it breaks at EXHAUSTION /
transition — i.e. the 33% are the FLIP points (S36: dipole -> 0.5 = change in flow). Test: does the
buy/sell classification MARGIN track flow strength, and are the low-margin samples the weak-flow / turn
states? If yes, the flip detector lives in the low-margin tail = the complement to the 67%.
"""
from __future__ import annotations
import numpy as np
from odcore.fingerprint_predictor import assemble, global_mean_coeff, MICRO_KEYS, FLOW_KEYS

IDX, LAB = "_alt_labels/coeffs/alt_coeff_index.json.gz", "_alt_labels"


def _l2(v): v = np.asarray(v, float); n = np.linalg.norm(v); return v / n if n else v


def main():
    per_cell = assemble(IDX, LAB)
    g = global_mean_coeff(per_cell)
    R, side, mic, flw, net = [], [], [], [], []
    for cell, recs in per_cell.items():
        s = 0 if cell.endswith("_buy") else 1
        for r in recs:
            R.append(_l2(np.asarray(r["coeff"], float) - g)); side.append(s)
            mic.append(r["micros"]); flw.append(r["flow"]); net.append(r["net_bps"] or 0.0)
    R = np.array(R); side = np.array(side); mic = np.array(mic); flw = np.array(flw); net = np.array(net)
    md = mic[:, MICRO_KEYS.index("mean_dipole")]
    onset = mic[:, MICRO_KEYS.index("trade_from_onset_bps")]
    imb = flw[:, FLOW_KEYS.index("imb_level")]
    csig = flw[:, FLOW_KEYS.index("C_signed")]

    # LOO buy/sell margin on the centered coeff residual: + = correctly mirror-aligned, near 0 = ambiguous
    margin = np.zeros(len(R))
    for i in range(len(R)):
        keep = np.arange(len(R)) != i
        cb = _l2(R[keep][side[keep] == 0].mean(0)); cs = _l2(R[keep][side[keep] == 1].mean(0))
        own, oth = (cb, cs) if side[i] == 0 else (cs, cb)
        margin[i] = float(R[i] @ own - R[i] @ oth)
    correct = margin > 0
    print(f"buy/sell LOO accuracy = {correct.mean():.1%}  (n={len(R)})")

    # the test: does MARGIN (mirror clarity) track FLOW STRENGTH? strong flow -> clean mirror; exhaustion -> ambiguous
    def corr(a, b): return float(np.corrcoef(a, b)[0, 1])
    print("\ncorrelation of buy/sell MARGIN with flow strength (>0 supports 'mirror clean when trend strong'):")
    print(f"  margin vs |mean_dipole|        : {corr(margin, np.abs(md)):+.3f}")
    print(f"  margin vs |imb_level|          : {corr(margin, np.abs(imb)):+.3f}")
    print(f"  margin vs |C_signed|           : {corr(margin, np.abs(csig)):+.3f}")
    print(f"  margin vs |trade_from_onset|   : {corr(margin, np.abs(onset)):+.3f}")
    print(f"  margin vs net_bps              : {corr(margin, net):+.3f}")

    # correct (mirror) vs wrong (the 33%): are the wrong ones the WEAK-FLOW / exhaustion states?
    print("\ncorrect (clean mirror, 67%) vs WRONG (the 33%) — mean of |feature|:")
    for name, v in [("|mean_dipole|", np.abs(md)), ("|imb_level|", np.abs(imb)),
                    ("|C_signed|", np.abs(csig)), ("|trade_from_onset|", np.abs(onset)), ("net_bps", net)]:
        cw, ww = v[correct].mean(), v[~correct].mean()
        flag = "  <-- weaker in the 33%" if ww < cw else ""
        print(f"  {name:20s} correct={cw:9.3f}   wrong={ww:9.3f}{flag}")

    # the low-margin TAIL = candidate FLIP states; profile the bottom quintile
    q = np.quantile(margin, 0.20)
    tail = margin <= q
    print(f"\nlow-margin tail (bottom 20%, margin<= {q:+.3f}) = candidate FLIP states:")
    print(f"  |mean_dipole| tail={np.abs(md)[tail].mean():.3f} vs rest={np.abs(md)[~tail].mean():.3f}")
    print(f"  |imb_level|   tail={np.abs(imb)[tail].mean():.3f} vs rest={np.abs(imb)[~tail].mean():.3f}")
    print("\nREAD: if margin correlates with flow strength AND the 33%/low-margin tail are the WEAK-FLOW "
          "states, then the buy/sell mirror IS the trend signal and its breakdown IS the flip -> the flip "
          "detector is the low-margin / low-|dipole| complement. That's the trend-following lever to triple down on.")


if __name__ == "__main__":
    main()
