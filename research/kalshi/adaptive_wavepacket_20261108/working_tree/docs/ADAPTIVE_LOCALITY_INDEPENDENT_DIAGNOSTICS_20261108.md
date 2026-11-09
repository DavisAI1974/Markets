# Adaptive Locality — Independent Geometry Diagnostics & Optional BuildMap Trial

**Date:** November 8, 2026 · **Scope:** standalone experimental Python package on
`feat/adaptive-locality-engine-20261108`, draft [PR #4](https://github.com/DavisAI1974/BuildMap/pull/4).
**Status:** engineering / bounded synthetic verification only; **NOT** independently accepted science.

## Verified execution receipts

- Latest tested code checkpoint before this documentation: `398e62f0a8b594757fd2e743e3381a98c24a4fa8`.
- Isolated Python CI: [42459918493](https://github.com/DavisAI1974/BuildMap/actions/runs/42459918493), **87 tests passed on Python 3.11, 3.12 and 3.13**. The report adds only documentation; check actual later HEAD/CI before use.
- Optional scratch BuildMap inspection CI: [42459917897](https://github.com/DavisAI1974/BuildMap/actions/runs/42459917897), **1 test passed**. The existing Node parser dependency was installed via `npm ci --ignore-scripts`; scratch source was copied to a temporary directory; no live source executed or changed.

## Scientific diagnostic matrix — what the tests do and do NOT establish

| Question | New bounded independent control / evidence | Conclusion and limitations |
| --- | --- | --- |
| Does equal marginal entropy imply dipole coupling? | 48 original RawFrames with **exactly factorizable two-channel joint bin counts**, H(a)=H(b), and empirical MI(a,b) approximately zero. Frozen-bin derivation, exact event lineage and archive reload verified. | **No.** `-Ha²-Hb²+2HaHb = -(Ha-Hb)²` is universal algebra; identical entropy occurs with independent member-bin assignments. Not a discovered interaction. |
| Does a perfect static quadratic prove novelty? | With donor `Hb=c ≠0`, `Ha²=(HaHb)²/c²` is exact by algebra. Flat donor is flagged `CONSTANT_TRAIN_DONOR_HB` and full result is put on `RESEARCH_HOLD`. | **No.** Static polynomial fit is descriptive, not a future prediction or physical geometry. Do not promote exact curve fit to coupling. |
| Could a static outlier have zero residual? | Frozen training support (x=HaHb and y=Ha²) checked independently of signed residual. Out-of-support exact-on-curve observation explicitly marked for research. | **Yes.** Residual-only screening can miss extreme extrapolation. Both values and all original point identities remain. |
| Does directional geometry predict the next target change? | Future change in target H predicted using only same-clock and past donor features, against a self-only model, matched past-lag donor control and 3 chronological holdout splits. | Can identify **synthetic candidate predictive associations** only; not physical geometry, causal proof or real-data forecasting. Repeated chronological splits overlap and are not independent replications. |
| Does the quadratic cross term add useful information *over the linear interaction*? | Added nested baseline `[1, Ha, Ha², FIa, HaHb]` versus extra `(HaHb)²`; compare on future target derivatives, including each half of the holdout. A separately generated known-quadratic toy yields incremental held-out support in at least one split. | **Possible in controlled toy dynamics.** The extra term can carry predictive signal beyond the simpler linear operator, but no real-domain effect has been established; static identities do not count. |
| Can independent channels or a regime change mimic a discovery? | Four deterministic synthetic independence seeds tested without a robust 3-split candidate; sign-changing toy fails the consistent candidate criterion. | These finite checks reduce false-positive risk for tested generators, **not** a population false-discovery rate or causality claim. Domain nulls, confounders and multiple comparisons remain unverified. |
| Do rank defects and near-collinear operators get lost? | Reorthogonalized QR refusal plus separately reported standardized quadratic-basis correlation/condition proxy; extremely ill-conditioned successful dynamic fits reclassified to research holds while preserving coefficients and errors. | **No observations discarded.** Numerical thresholds are conservative triage heuristics, not a spectral proof or estimator-invariant conclusion. Multiresolution, calibration and independent solver checks remain necessary. |
| Are the *upstream* original measurements preserved, not just InfoFrame hashes? | `preserve_geometric_holds`, `preserve_geometric_predictive_controls`, `preserve_full_raw_five_step_holds`, `preserve_full_raw_level2_holds`, and `archive_first_geometric_review`. Original RawFrames, member/order/evidence IDs, directions, raw values, frozen bins/identities, fit outputs, windows, cases and source conflicts verified and recoverable after database reopening. | **Pass in bounded local tests.** Full archive is source-bound and refuses mismatched raw derivations. Conflicting Level 1/Level 2 internal lineage is archived as a separate case, **not rejected from the archive**. No raw market observations tested. |
| Can an unverified acceptance gate disappear? | `research_gates.py` explicitly stores each gate as `UNVERIFIED`; retains immutable original gate records and hash-linked review cases, including under review; local SQLite foreign keys and current-case/history cross-checks tested. | **No silent dismissal in tested API.** Database itself is not independently signed or adversarial tamper-proof. External backup/attestation remain outside scope. |

## Archive-first path (new preferred standalone admission)

`adaptive_locality/standalone_review.py:archive_first_geometric_review` receives original `RawFrame` sequence, frozen `FixedBins` and a source-matched `ResearchHoldRegistry`. It archives **all original raw frames and derived InfoFrames before any fit**. If input is out of calibration, too short, numerical/rank-ineligible or beyond the bounded CPU review window, it stores explicit reasoned research cases instead of pretending the test passed or discarding a row. When eligible, it runs the static geometry and chronological predictive controls and archives the reports with the same originals. All statuses remain unverified research; no scheduling or scientific work elimination.

**Important admission boundary:** `RawMember` and `RawFrame` enforce constructors that reject non-finite/pre-schema records. Those *pre-admission* bytes are the importer's responsibility and **must be independently archived before decoding** for a future real-data adapter. This admission wrapper does not prove lossless retention for malformed data that were never admitted as `RawFrame` objects.

Other boundaries: too-large archives fail closed at the registry byte limit; users must design source-bound, lossless partitions instead of truncating. The local SQLite ledger is not a certified signature or substitute for external durable backup. A successful algorithmic fit is never authorization for scientific deduplication or dropping a real computation.

## Optional BuildMap experiment — decision: **KEEP INSPECTION TRIAL ONLY**

A scratch-only read-only adapter generates a draft BuildMap manifest from the standalone Python modules and their declared review gates. The native BuildMap scanner reads a *temporary copy* of the source to visualize code relationships and missing work; no production BuildMap source is changed. Its single isolated Node test asserts source-byte conservation, no false `verified/live` states, and review-gate visibility.

**Measured scratch comparison at CI 42459917897:**

| Inspection metric | Standalone numeric report | Optional BuildMap scratch review |
| --- | ---: | ---: |
| Native BuildMap source-import edges available for navigation | 0 (not a source graph) | **7 observed static edges** |
| Explicit scientific acceptance gates shown as unverified/planned | 0 in numeric report's native graph | **8** |
| False verified/live declarations | Not applicable | **0** |
| Original source files changed by trial | 0 | **0** |
| Scientific calculations eliminated | **0** | **0** |

These numbers demonstrate **a navigation/presentation improvement**, not scientific accuracy, increased predictive gain, fewer comparisons, or runtime acceleration. Retain `adaptive_locality/buildmap_trial.py` and the dedicated scratch-only CI workflow as an **optional nonruntime tool**. No automatic import into BuildMap production, no source mutation, no deployment, no merge. Remove the optional trial later if real review users find no additional inspection value.

## Eight explicit retained, currently UNVERIFIED science gates

1. `independent-replication`: independent data source, calibration and holdout.
2. `causal-controls`: common driver, feedback, multiplicity and counterfactual/domain controls.
3. `algebraic-novelty`: reproducible incremental prediction beyond reparameterization.
4. `rank-conditioning`: genuine singular spectra, perturbation sensitivity and independent solver.
5. `parameter-fisher-information`: parameter and likelihood-defined Fisher estimation, not histogram roughness.
6. `physical-neumann-boundary`: continuum geometry, valid normal vectors, PDE and boundary conditions.
7. `raw-external-validation`: full real source lineage and independent external scientific assessment.
8. `scientific-equivalence`: independent proof including event direction, causality and side effects before any calculation elimination.

**All eight are retained for further inspection.** Conflicts, no-prediction results, short windows, rank defects and outliers are also science records. Review can add history but cannot authorize omission of original data or calculations.

## Acceptance and release decision

- **Engineering:** isolated CPU-based synthetic tests for zero-drop preservation, no-lookahead controls, rank triage, one independent raw equal-entropy counterexample, nested quadratic toy and source-inspection trial **PASS**.
- **Mathematical science:** independent real-domain replication, confound/multiplicity control, estimator stability, exact conditioning/precision audit, physical geometry and Neumann PDE applicability **UNVERIFIED**.
- **Product:** optional BuildMap inspection trial **KEEP as experimental source-review aid**. Standalone mathematical engine remains independent and BuildMap native runtime is unchanged.
- **Operational:** no Frankie, AWS, Search, ingestion, production hooks, merge, deployment, real dataset processing or scientific job suppression.

The PR must stay **draft** and **unmerged**. Every unresolved item must be preserved on its original evidence and remain visible for further research, not smoothed, averaged, flattened, discarded or silently reinterpreted.
