# Build questions / decisions for Greg (review when back)

Running log of decisions I made with best judgment while building unattended, plus
questions where your input would change direction. We can revisit any of these.

## BLOCKERS needing your action
1. **`DavisAI1974/Basic_equations` is access-denied this session** (scope locked to
   `davisai1974/markets`). It almost certainly holds `_markets_algebraic_dipole.py`,
   `s13_chemistry_residual.py`, `s12_coupling_decomposition.py` — the EXACT chem-dipole
   construction. **Please add it (and maybe `od-engine`, `evolution`) to this session's
   allowed repos.** Then I can port the originals verbatim and run them on the real bins.
   - Until then: the chem QUADRATIC dipole does NOT reproduce on the channels I
     reconstructed (real buy/sell entropies are near-symmetric H_a≈H_b → trivial identity
     `H_a²≈H_a·H_b`, c≈0; nothing scores "structured"). I tried 5 channel types × 3
     timescales × 3 conditionings. This may be a channel/preprocessing mismatch vs the
     original — which the blocked repo would resolve. OR it's a genuine "construction not
     nature" result (the log's own open question). I am NOT fabricating a chem-dipole win.

## DECISIONS I made (best judgment; easy to change)
- Built a new `odcore/` package; kept the existing platform shell intact (no destructive
  housekeeping while you're away — I will NOT delete/unwire anything risky unattended).
- Estimators: Vasicek m-spacing for marginal entropy, KSG (k=4) for MI (the log says these
  agree on the structural core; INFO-022/034).
- Channel conditioning: global log1p/z-score so entropies are comparable scale (INFO-051).
  NOTE this symmetrizes buy/sell — possibly the wrong choice for the chem dipole (see #1).
- All substantive runs are on the REAL data/* branch bins (materialized to gitignored
  `realbins/`). Synthetic only used for unit-test controls.

## QUESTIONS for you
- **Zero synthetic enforced (your call).** Removed `odcore/synthetic.py` and all synthetic
  tests. Tests now run on REAL bins (the lead-lag "known lag" test injects a known shift into
  a REAL BTC return series and recovers it). Tests skip if `realbins/` isn't materialized.
  - ONE place synthetic would otherwise help: proving PySR *rediscovers a known governing
    equation* (e.g. the Brusselator chem coeffs) needs a system with a known closed-form law,
    which real markets don't have. I did NOT bake that in. If you want that sanity check,
    say so and I'll add a single clearly-labeled known-law fixture; otherwise PySR is
    validated only by fit quality on real data.
- Decoupling detector found **145 real decoupling events** on Coinbase↔Bybit (coupling mean
  0.57). Default thresholds (lookback=20, drop_k=2.5σ) are a guess — tune later against P&L.
