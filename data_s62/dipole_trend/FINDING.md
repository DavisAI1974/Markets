# S62 dipole-as-trend-gate — FINDING (Greg's "dipole is a great trend follower")

Charter: can the dipole read the trend accurately at the ARM point (-10/-15) to gate the flip?
Agent built `dipole_trend_gate.py` (arm_trend_reads: info_dipole.divergence aligned-flow, lean,
mi-flow, reversal-conviction, ER) + `final_eval.py`. Core AUC(DEATH vs RECOVERY) among armed legs:

  arm -10/-15/-20/-30, ALL dipole reads, ALL 5 cells: ~chance (0.44-0.56). The S36 aligned-flow
  (divergence) read = 0.49-0.54 everywhere. No dipole read separates death from recovery at any depth.

THE DISTINCTION (load-bearing):
  - DEATH vs WINNER (full pop): EASY at deep arm (winners don't go deep) — AUC 0.60-0.72. This is
    what makes the E300/-30 classifier print positive $/hr (flip deep-underwater = flip non-winners).
  - DEATH vs RECOVERY (both underwater): ~CHANCE for everything (price, coeff, dipole) at all depths.
    This is the genuinely unpredictable thing.

The S36 dipole edge was REAL but a DIFFERENT task: swing-REVERSAL detection on the flip detector
(bybit_perp, ~64% oppose+exhaust), cell-specific + sub-fee (S36b). It does NOT transfer to
death-vs-recovery on Coinbase mid-band legs. The dipole did not break the winners-invisible wall;
it located it precisely: among legs already underwater, recovery-vs-death is not carried by any
causal flow/price/coeff signal at any arm depth.

Deployable reality: the positive $/hr (E300 death-classifier +1.29 BTC, trend-gate ETH/BTC/DOGE
+1.1..1.6 at -20/-30) comes from death-vs-WINNER separation (depth) + the FLATTEN fallback, NOT
from reading the trend early. Greg's early-arm (-10/-15) flip cannot be confirmed by any signal we
have — the info to tell death from recovery simply isn't present that early.
