# Science context register - Markets addendum (2026-11-08)

Appends to `ADAPTIVE_LOCALITY_SCIENCE_CONTEXT_REGISTER_20261108.md` (kept verbatim in the frozen snapshot).
Nothing in the original register is removed or reworded here; this file adds provenance and corrections
found by the independent review (finding ids in `../../CCODE_INDEPENDENT_REVIEW_20261108.md`).

## 13. Prior implementations and real-data results that already exist upstream (R-1)

The register (sections 6 and 8) lists KBK, AI Poincare, SINDy and PySR as "research leads, not implemented".
That is true of the Adaptive Locality package and false of the lineage as a whole:

- `DavisAI1974/Basic_equations` holds runnable implementations that were executed in its Sessions 6-7:
  `kbk_pipeline.py`, `per_domain_kbk.py`, `ai_poincare_rank.py`, `sindy_symbolic.py`,
  `pysr_symbolic_per_domain.py` (with result JSONs beside them).
- `DavisAI1974/Markets` holds `odcore/symbolic.py` (PySR over the operator matrix) and the session start hook
  bootstraps PySR and Julia.
- Basic_equations `CLAUDE.md` INFO-036 (Session 10, GW150914): the `(-1,-1,+2)/sqrt(6)` attractor was
  confirmed on REAL data as an equal-marginal-entropy artifact, not coupling. INFO-038 (Session 11, three
  LIGO events run separately, never pooled): per-event `|Ha-Hb|` of 0.62 / 0.74 / 1.61 inversely tracks the
  attractor cosine; the merger signature rides the orthogonal MI axis; removing MI from the basis restores the
  attractor. The register's synthetic equal-entropy control therefore has a real-data precedent.
- Markets `odcore/null_extract.py:36-39` already encodes the identity as fixed null axes `EQ_LINEAR`,
  `EQ_QUAD = (0,0,-1,-1,2,0)/sqrt(6)` and `MI_AXIS`.
- Open cross-repo thread, retained so it is not lost between repositories (Basic_equations `CLAUDE.md:231`):
  "pull dipole JSONs from the Markets repo + list the flow dipole equation separately (Greg's call)".

Status of the leads is unchanged: NOT applied to Adaptive Locality frames. The point of this section is that
they do not need to be re-derived.

## 14. Corrections and sharpenings from the review (each keeps the original statement beside it)

- Fisher-like proxy (R-2). Original: "not parameter Fisher information". Sharpened: it is the standard plug-in
  estimator of the LOCATION-family Fisher information of the frozen-bin density
  (`4 * sum (sqrt p_{i+1} - sqrt p_i)^2 / h^2` is the Riemann sum of `4 * integral (d sqrt f / dx)^2`). It
  matches `1/sigma^2` for a well-populated truncated Gaussian and is inflated by sparse tail bins
  (`tests/test_adaptive_locality_review_fixes.py::FisherProxyClosedFormTests`, both facts pinned). It is still
  not Fisher information in any model parameter; the gate stays open.
- Level 2 ratio `B = |c_Ha2| / |c_HaHb|` (M-1). `Ha` and `Ha^2` are structurally near-collinear on a narrow
  entropy range (correlation `1/sqrt(1 + w^2/(15 m^2))` for `Ha` uniform on `[m-w, m+w]`), so each coefficient
  is variance-inflated and `B` inherits it. `B` itself is translation-invariant (the top-degree coefficients
  do not change under `H -> H + c`), which is why no "dual basis" changes its value; what changes is its
  uncertainty. Every fit now reports the standardized singular spectrum, VIF per column, coefficient standard
  errors and covariance, and every `B` carries a delta-method standard error. Nothing is thresholded on these.
- Static quadratic `Ha^2 = a + b HaHb + c (HaHb)^2` (M-2). Original: constant donor makes it exact. Added: a
  slowly varying donor makes it near-exact for the same reason; the fitted quadratic is now compared against the
  fixed curve `x^2 / mean(Hb_train)^2` and must beat it by `min_gain` to leave research hold. Markets'
  chemistry reference coefficients in `odcore/dipole_predictor.py:25` have NOT yet been put through this null.
- Original Level 2 observable (M-3). The Basic_equations code fitted `d log(B + 1e-6)/dt` with central
  differences and a six-node `B_net` mean; the standalone engine fits `dB/dt` on raw `B` with a forward secant
  and no mean. These are different observables. The log variant now exists as `balance_transform="log"` with
  abstention (never an epsilon) on nonpositive `B`; both are retained as distinct experiments.
- Past-lag donor null (M-4). Original: one lag of `len//5` (or `len//6`). Added: a profile over up to 12 lags
  and the donor lag-1 autocorrelation, so the strength of the null can be read. No lag is selected.
- Graph "Neumann residual" in `core.py` (4.4 of the review). `sum_b w_ab (u_b - u_a) - g_a = 0` is a
  harmonic-at-boundary condition that coincides with `du/dn = 0` only on degree-1 boundary nodes. The
  finite-volume `FluxDomain` is the correct abstract reflecting boundary. Both stay; the labels now say what
  each tests.
- The post's own mechanism (N-1). "Difference in distance between position neighbors" now has one concrete
  meaning in `adaptive_locality/packing_boundary.py`: on a path of packed centers, neighbor distances define
  finite-volume cell widths and conductances, and a missing neighbor IS the zero-flux boundary. Verified against
  the manufactured solution `u = 1 + cos(pi x) exp(-pi^2 t)` with reflecting ends. What remains open: facet areas
  and normals in more than one dimension (Voronoi), and any claim that market-state vectors diffuse.
- Synthetic controls (T-1, T-2). The "coupled" and "known-quadratic" generators contain the terms later fitted;
  a pass is an estimator sanity check. Added controls: a hidden common driver and a `tanh` misspecified
  generator, whose outcome is recorded whatever it is. The archive-first round-trip fixture is period-7
  deterministic and is not a predictive result.
- Frankie vocabulary (review section 6). On disk the families are P/O/S/X, directions LONG/SHORT and
  SAME/FLIP with side A/B/N, clocks `ts_recv_ns` / `ts_event_ns`. "P/O/X/F", "AB/BA" and "evidence plane"
  remain the register's wording; the fields that carry them are free strings and need no change.

## 15. Preservation guarantees added (PG-1 to PG-5)

- Five-step and Level 2 now have archive-first wrappers (`standalone_review.archive_first_five_step_review`,
  `archive_first_level2_review`): raw and derived series are archived before any validation or fit, and every
  refusal (`validate_series`, budget, schema, rank) is a research hold on archived evidence.
- Every abstention carries its exact cause (`CouplingResult.reason`, `BalanceWindow.reason`).
- A conflicting re-archive under an existing name is retained as `<name>-conflict-<digest>` with an
  `ARCHIVE_NAME_CONFLICT` hold, and the call still fails closed.
- Series over the byte cap are archived losslessly as ordered parts plus a manifest
  (`archive_partitioned` / `read_partitioned`).
- A channel with one held Level 1 window keeps its strict holds and gains side-by-side `SEGMENT_*` links on the
  longest fully READY run; neither replaces the other.
