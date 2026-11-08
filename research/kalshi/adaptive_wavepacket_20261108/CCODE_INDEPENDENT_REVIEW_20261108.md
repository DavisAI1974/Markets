# CLAUDE CODE INDEPENDENT REVIEW - MARKETS SCIENCE + ADAPTIVE LOCALITY + BUILDMAP MIGRATION

Date: 2026-11-08
Reviewer: Claude Code (read-only session on `research/markets-adaptive-wavepacket-migration-20261108`)
Branch HEAD reviewed: `c073460` (Markets). Snapshot source: `DavisAI1974/BuildMap@8b4295d` (branch `feat/adaptive-locality-engine-20261108`).

STATUS: PRELIMINARY READ-ONLY REVIEW. The file transfer is still declared IN PROGRESS by the owner. No final
completeness verdict, no migration acceptance, no code modification, no merge, no deploy, no AWS/Frankie/Search
action was taken. Nothing in this review authorizes any of those.

GOVERNING RULE APPLIED THROUGHOUT: NOTHING SCIENTIFIC IS DROPPED. Every finding below that challenges an inference
records the inference, its evidence and the counter-evidence side by side. Unverified items are labelled
FOR FURTHER INSPECTION / RESEARCH. No calculation is recommended for removal.

Status vocabulary used in this document:
- IMPLEMENTED+TESTED: code exists and a bounded synthetic test exercises it.
- PROMISING-SYNTHETIC: a synthetic result that is hypothesis-generating only.
- UNVERIFIED-HYPOTHESIS: a scientific claim with no independent evidence yet.
- NOT-IMPLEMENTED: described in prose, absent from code.
- DEFECT: deterministic code problem reproducible from the source.
- PRESERVATION-GAP: a path on which evidence or an abstention reason can be lost.
- RESEARCH-HOLD: retained open question; not a defect.

---

## 0. Review verdict (one screen)

1. Migration integrity: 131 of 133 BuildMap source blobs are byte-identical in Markets (verified two ways, section 1).
   The only two absent files are the DOCX and PDF binary reports. The BuildMap branch HEAD IS the pinned commit, so
   nothing newer exists upstream that the snapshot could be missing. Transfer is correctly described as not complete.
2. Engineering: the standalone package compiles and its 87 standard-library tests are present and real (counted by
   hand, 17 files; re-run twice on scratch copies, 87 pass). The native BuildMap Node suite also passes (168).
   The science tests are bounded synthetic; several of the synthetic generators contain the term they later
   "detect" (section 4.6), so a pass is a sanity check of the fitter, not a discovery. Two reproduced engineering
   defects matter for the preservation rule: the grid index silently misses a brute-force hit at the exact radius
   boundary (E-1), and a center's retirement reason is nulled on restore (E-2). The shadow export drops
   `Decision.reason` (E-7), the same class of loss as PG-2.
3. Mathematics: the corrections the owner already made are right. `-Ha^2-Hb^2+2HaHb = -(Ha-Hb)^2` is an identity;
   the constant-donor quadratic is a reparameterization; the Fisher-like term is a histogram location-Fisher
   estimator (which is more defensible than the docs claim, section 4.2). Three further mathematical points the
   docs do not yet record are derived in section 4: the structural Ha/Ha^2 collinearity that makes the Level 2
   ratio B a ratio of two variance-inflated coefficients (4.3), the fact that the graph "Neumann residual" in
   core.py tests a harmonic-at-boundary condition rather than a normal-derivative condition (4.4), and the
   fact that the Basic_equations repo itself already confirmed the equal-entropy reading on REAL LIGO data
   (INFO-036/038), which the register omits (4.1).
4. Preservation: the archive-first wrapper covers only the two geometry diagnostics. The five-step coupling and
   Level 2 paths still fit before they archive, and `validate_series` can reject a series before anything is
   stored (section 5, PG-1). Abstention reasons are collapsed into a single status string in two places (PG-2,
   confirmed by the owner as a required fix). Conflicting re-archives raise and discard the new evidence (PG-3).
5. The original post's specific mechanism (neighbor-distance differences driving Neumann boundary conditions) is
   NOT implemented anywhere; what exists is an abstract weighted-graph finite-volume module whose conductances and
   volumes are user-supplied. A concrete formalization that would connect the two is proposed in 4.4 (NOT built).
6. Markets overlap: Markets already uses the word "dipole" for four different objects, already carries
   `EQ_QUAD = (0,0,-1,-1,2,0)/sqrt(6)` as a NULL axis in `odcore/null_extract.py:37`, and uses continuous
   estimators (Vasicek H, KSG MI) where the imported package uses frozen discrete bins. Frankie's family vocabulary
   on disk is P/O/S/X, not P/O/X/F, and its direction vocabulary is LONG/SHORT, SAME/FLIP, side A/B/N, not AB/BA.
   These are reconciliation facts, not errors in either tree (section 6).
7. BuildMap: included component, tests pending. See section 7 (native review) for what its scanner actually does.

---

## 1. Migration verification (independent)

Method 1: recomputed `sha1("blob <len>\0" + bytes)` for every entry in `MIGRATION_SOURCE_SHA_MANIFEST_20261108.json`
against the files on disk. Result: 131 exact, 0 mismatch, 2 missing (the DOCX and PDF).

Method 2: cloned `DavisAI1974/BuildMap` branch `feat/adaptive-locality-engine-20261108` read-only and diffed
`git ls-tree -r` blob ids of the real source tree against the snapshot subtree. Result: 131 common identical blobs,
2 source-only (the two binaries), 0 destination-only. BuildMap branch HEAD = `8b4295d` = the pinned commit;
`git rev-list --count 8b4295d..HEAD` = 0, so no newer upstream commits exist to preserve.

Pending (owner's call, not this review's): byte transfer of
`docs/reports/BuildMap_Work_Completed_Remaining_and_Additions_20261021.{docx,pdf}` (SHAs recorded in the manifest).
A git read path is available in this session; a push path to Markets is available; the binaries could be copied
via a plain `git show <blob> > file` from the read clone when authorized. Not done, because the owner asked that the
completeness verdict wait.

Snapshot layout note: the snapshot directory also contains the native BuildMap `package.json` and
`package-lock.json`; the Markets root has no Node project, so there is no manifest collision today.

---

## 2. What was reviewed

Primary docs (in the owner's order): `adaptive_locality/README.md`, `docs/ADAPTIVE_LOCALITY_SCIENCE_CONTEXT_REGISTER`,
`docs/ADAPTIVE_LOCALITY_INDEPENDENT_DIAGNOSTICS`, `docs/ADAPTIVE_LOCALITY_CLAUDE_CODE_REVIEW_HANDOFF`, plus the
coupling/geometry handoff, standalone acceptance ledger, P0-P9 build plan, implementation status, the earlier
next-chat handoff, the Markets migration handoff/status/drop-in, and the three Basic_equations sources
(`level2_four_sciences.py`, `static_dipole_test.py`, `three_discoveries.py`) plus its `CLAUDE.md` ledger.

Code read line by line: `information.py`, `coupling.py`, `level2_coupling.py`, `geometry_probe.py`,
`geometry_validation.py`, `core.py`, `contracts.py`, `advanced.py`, `graph_boundary.py`, `boundary_validation.py`,
`research_gates.py`, `outliers.py`, `research_holds.py`, `standalone_review.py`, `ledger.py`, `adapters.py`, the
two CI workflows, and the tests `test_adaptive_locality_independent.py`, `_geometry_controls.py`,
`_geometry_validation.py`, `_archive_first.py`. Engineering modules and the native BuildMap JS were delegated to
two read-only sub-reviews whose findings are in sections 7 and 8.

Markets side: `odcore/*`, root `_info_dipole_*`, `news_coupling_research.py`, `markets_adapter.py`,
`research/kalshi/frankie_boss/`, the sqlite-triage family artifacts and the canonical 99-registry (section 6).

---

## 3. Findings table

Severity: HIGH = changes a scientific conclusion or loses evidence; MED = wrong or misleading but recoverable;
LOW = hygiene. "Originals kept" answers: does the current code still retain the underlying data on this path.

| ID | Sev | Path:line | Evidence | Scientific / engineering consequence | Originals kept | Re-test | Class |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PG-1 | HIGH | `coupling.py:224`, `coupling.py:255`, `information.py:163-185`, `level2_coupling.py:105-146` | `discover_coupling`, `dipole_window_probe` and `discover_level2_balance_links` call `validate_series` or raise on budget/schema BEFORE any archive. `standalone_review.py` wraps only the two geometry diagnostics (L75, L92). | A series with one REVIEW_REQUIRED frame, a duplicated evidence id across frames, a node-schema change, a non-monotone clock, more than `max_nodes`, or more than `max_windows` windows raises and nothing is stored. The raise is correct; the missing archive is the gap. | No (on this path) | Add `archive_first_five_step_review` and `archive_first_level2_review` mirroring `archive_first_geometric_review`; test: feed each raising condition and assert a raw archive plus a hold case exist. | PRESERVATION-GAP |
| PG-2 | HIGH | `coupling.py:215-216`, `coupling.py:272-274` | `except (LocalityError,ZeroDivisionError,OverflowError): return neutral("ABSTAIN_RANK_OR_NUMERIC_ARTIFACT")` and the window variant store `()` coefficients and no message. Contrast `level2_coupling.py:99-101` and `geometry_validation.py:199-200`, which keep `str(exc)`. | The cause of every Level 1 abstention (which column was constant, rank defect vs overflow vs insufficient rows) is lost; the research hold created from it (`preserve_five_step_holds`, `preserve_full_raw_five_step_holds`) carries only the status. Owner has confirmed this must be fixed. | Status only | Add a `reason: str` field to `CouplingResult` and `BalanceWindow` populated from `str(exc)`; test: constant FIb column, duplicate rows, overflow row each produce a distinct reason string in the archived case. | DEFECT + PRESERVATION-GAP |
| PG-3 | MED | `research_holds.py:105-107`, `research_holds.py:151-153`, `standalone_review.py:44` | Re-archiving a different payload under an existing `archive_name` raises `immutable original evidence conflict`. The test `test_same_archive_name_cannot_replace_different_raw_observations` asserts only that the OLD archive survives. | The NEW conflicting evidence is not stored anywhere by the library; the caller must notice and choose a new prefix. A conflicting re-submission is itself a scientific observation (same name, different bytes) and should be archived as a CONFLICT case, not just refused. | No (new payload) | On conflict, archive the new payload under `<name>-conflict-<digest[:12]>` and open a `ARCHIVE_NAME_CONFLICT` hold linking both; test: assert both payloads recoverable after reopen. | PRESERVATION-GAP |
| PG-4 | MED | `research_holds.py:99-100`, `standalone_review.py:86-89` | 32 MiB archive byte cap and `max_frames` budget raise / hold BEFORE archiving the full series (the budget hold is created but the raw archive at L44 already succeeded only if under 32 MiB). | Correctly fail-closed, but there is no partition helper, so a real 30-day native series cannot enter the registry at all today. | n/a | Build a lossless partition manifest (ordered part digests, part count, whole-series digest) so large series are archived in parts with a single hold; test: 3-part series round-trips to the same whole digest. | NOT-IMPLEMENTED |
| PG-5 | MED | `level2_coupling.py:141-143`, `:158`, `:164-165` | One non-READY Level 1 window (e.g. a single `ABSTAIN_RATIO`) marks its whole channel `invalid`, so every Level 2 link touching that channel becomes `RESEARCH_HOLD`. | Design choice consistent with "no epsilon", but it means one unidentifiable window anywhere in 12,000 removes the channel from Level 2. The window itself is retained. Worth a per-segment variant (fit on contiguous READY runs) kept side by side, never replacing. | Yes | Research experiment, not a fix. | RESEARCH-HOLD |
| M-1 | HIGH | `coupling.py:26-27`, `coupling.py:81-89`, `geometry_probe.py:80`, `geometry_probe.py:215`, `geometry_validation.py:181` | Library columns `Ha` and `Ha2` (and `HaHb` vs `Hb`) are structurally near-collinear whenever H has a narrow range (derivation 4.3). The condition proxies used (`max(diag)/min(diag)` of the standardized R, threshold 1e6; two-column rho threshold 1e6) only fire when a column is essentially constant. | The Level 2 ratio `B = c_Ha2 / c_HaHb` divides two coefficients whose individual variance is inflated by that collinearity. Part of B's window-to-window instability is therefore a basis artifact, not dynamics. No code change required for preservation; the DIAGNOSTIC is missing. | Yes | Report, do not threshold: per-coefficient variance inflation factor and the full singular spectrum of the standardized design (not just the R diagonal); run the same fit on a centered/orthogonal-polynomial basis and archive BOTH coefficient sets. Test: narrow-range synthetic with known coefficients; assert VIF of Ha2 > 100 and that B on the orthogonal basis is stable across windows. | RESEARCH-HOLD (diagnostic NOT-IMPLEMENTED) |
| M-2 | MED | `geometry_probe.py:138-142` | `CONSTANT_TRAIN_DONOR_HB` fires only when donor span <= 1e-12 * scale. | A slowly varying donor gives a NEAR-exact quadratic for the same algebraic reason (Ha^2 = (HaHb)^2 / Hb^2 with Hb nearly constant) and is not flagged. A "perfect" static fit with a slow donor is still a reparameterization. | Yes | Add a reparameterization null: compare the fitted (a,b,c) against the algebraic curve (0, 0, 1/mean(Hb)^2) and report gain over THAT curve, not only over the linear baseline. Test: Hb = 1 + 0.001 sin(t) must not reach EXPLORATORY. | RESEARCH-HOLD (control NOT-IMPLEMENTED) |
| M-3 | MED | `level2_coupling.py:17-18`, `:54-58` vs `basic_equations/level2_four_sciences.py:201` | The original Level 2 fit was on `log(B + 1e-6)` with `np.gradient` (central differences) on a per-pair basis with a `B_net` mean. The new engine fits RAW B with a forward secant and no mean. | These are two different observables. The new one is cleaner (no epsilon, no mean) but it is NOT a reproduction of the original; both must be kept as distinct variants. The docs say "different experiment" (coupling.py:15) but do not record the log-vs-raw and central-vs-forward differences explicitly. | n/a | Record in the register. Optional: add a `transform="log"` variant that abstains when B <= 0 instead of padding, so the original can be re-run losslessly. | RESEARCH-HOLD |
| M-4 | MED | `coupling.py:175`, `geometry_validation.py:91`, `level2_coupling.py:47` | The "matched past-lag donor null" uses ONE lag: `len//5` or `len//6`. | A single lag is one point of a lag profile. If the donor is strongly autocorrelated the null nearly equals the full model (conservative); if it is white the null is trivially beaten (permissive). The null's strength therefore depends on donor autocorrelation, which is not reported. | Yes | Report donor lag-1 autocorrelation next to `null_gain`; add a lag sweep (3..len//3) archived as a vector, never collapsed to a best lag. | RESEARCH-HOLD |
| M-5 | LOW | `coupling.py:176-179`, `geometry_validation.py:97-99`, `level2_coupling.py:48-50` | Training stops at `split-2` and testing starts at `split`; one interval is skipped so no frame is shared between a training target and a test feature. | Correct and valuable; undocumented. A reader will think it is an off-by-one. | n/a | Add a comment and a test that asserts the training-target frames and test-feature frames are disjoint. | LOW |
| M-6 | LOW | `coupling.py:280` | `cross_domain_motif` hard-requires exactly the set {physics, biology, chemistry, geology}. | Faithful to the historical four-science precedent; blocks any other N-source independent comparison (for Markets: NYMEX vs Kalshi vs weather vs EIA would be the natural four). | n/a | Generalize to N named sources with the same disjoint-identity check; keep the four-science names as the documented precedent. | LOW |
| T-1 | MED | `tests/test_adaptive_locality_geometry_controls.py:32-34`, `:79-80` | The "coupled" generator is `ha += 0.018(-0.6 ha + 0.90 ha hb + 0.03 fia)`; the "known-quadratic" generator adds `0.08 (ha hb)^2`. The library fitted later contains exactly those terms. | A pass shows the fitter recovers a term that is in the generating model. This is a correct sanity test of the estimator, not evidence that the method discovers unknown structure. The docs say "toy", which is accurate; the register should say "generator contains the fitted term". | n/a | Add a misspecified-generator control (e.g. `ha += k * tanh(hb)` or a hidden common driver z feeding both ha and hb) and archive the result whatever it is. | PROMISING-SYNTHETIC |
| T-2 | LOW | `tests/test_adaptive_locality_geometry_validation.py:15-30` | `original_series` is period-7 deterministic (`k = (t % 7)+1`), values 0.5/1.5 in two of four bins. | The 96-frame "bounded success" archive-first test runs predictive controls on a strictly periodic sequence; any gain there is periodicity. Fine for an archive round-trip test; must not be cited as a predictive result. | n/a | None required; note in the register. | LOW |
| T-3 | LOW | `tests/test_adaptive_locality_geometry_validation.py:133-173` | The 48-frame equal-entropy control is real: exactly factorizable joint counts, H(a)=H(b) exactly, MI < 1e-12, status RESEARCH_HOLD with `EXACT_EQUAL_ENTROPY_HA_HB`, archived with full raw. | Confirms the negative control claim in the diagnostics report. | Yes | None. | IMPLEMENTED+TESTED |
| N-1 | HIGH | `core.py:189-202`, `graph_boundary.py`, grep of whole package | No code implements "difference in distance between position neighbors" as a boundary construction. `graph_neumann_residual` sums ALL incident weighted differences at boundary nodes (derivation 4.4). `FluxDomain` takes conductances and volumes as inputs. | The original post's mechanism is UNVERIFIED-HYPOTHESIS and NOT-IMPLEMENTED; the existing modules are honest graph experiments. The docs already say so; this review adds what the residual actually tests and a concrete formalization path (4.4). | n/a | Build the proposed Voronoi-spacing FluxDomain constructor as a research experiment; test against the 1-D reflecting heat equation with a manufactured solution. | NOT-IMPLEMENTED |
| R-1 | MED | `docs/ADAPTIVE_LOCALITY_SCIENCE_CONTEXT_REGISTER_20261108.md` section 6 and 8 | The register says KBK, AI Poincare, SINDy and PySR are "research leads, not implemented". They ARE implemented and were run in `DavisAI1974/Basic_equations` (`kbk_pipeline.py`, `per_domain_kbk.py`, `ai_poincare_rank.py`, `sindy_symbolic.py`, `pysr_symbolic_per_domain.py`, Sessions 6-7), and Markets has `odcore/symbolic.py` (PySR). Also, Basic_equations INFO-036/INFO-038 already confirmed on real LIGO data that the (-1,-1,+2)/sqrt(6) attractor is equal-marginal-entropy bookkeeping and that the physical signal rides the orthogonal MI axis. | True for the Adaptive Locality package, but the register's "nothing dropped" scope should link the prior implementations and the real-data correction so they are not re-derived. | n/a | Append section 13 to the register (provenance list given in section 9 of this review). | PRESERVATION-GAP (documentation) |
| R-2 | LOW | `information.py:5-6`, `research_gates.py:40-42` | `fishers[node] = 4 * sum (sqrt p[i+1] - sqrt p[i])^2 / step^2` is the Riemann sum of `4 * integral (d sqrt f / dx)^2 dx`, i.e. the location-family Fisher information of the histogram density (derivation 4.2). | The docs call it "not Fisher information". More precisely: it IS a plug-in estimator of the Fisher information for the location parameter of the binned density; what it is not is Fisher information for any model parameter of interest, and it carries the known empty-bin artifact. Keep the gate; sharpen the wording. | n/a | Add a test comparing the proxy against the closed form for a Gaussian (I = 1/sigma^2) at fine bins. | LOW |
| F-1 | MED | Markets `research/kalshi/frankie_boss/` on this branch | The Frankie tree on this branch is partial: 8 files, tests import absent modules, `CLAUDE_RECONCILIATION_20260916.md` not found in any branch history. | Any Frankie-facing interface plan written now rests on the sqlite-triage artifacts, not the live Frankie HEAD. | n/a | Reconciliation needs the fuller Frankie tree (owner-provided). | RESEARCH-HOLD |

Sections 7 and 8 add the native BuildMap and engineering-module findings from the delegated sub-reviews.

---

## 4. Mathematical derivations and counterexamples

### 4.1 The algebraic identity and the equal-entropy null (verified; register addition)

For any reals, `-Ha^2 - Hb^2 + 2 Ha Hb = -(Ha - Hb)^2`. Expanding the right-hand side gives
`-(Ha^2 - 2 Ha Hb + Hb^2)`, identical term by term. In the operator basis
`(Ha, Hb, Ha^2, Hb^2, HaHb, MI)` the unit vector `(0,0,-1,-1,2,0)/sqrt(6)` is therefore a null direction whenever
`Ha = Hb` on the window, with no reference to coupling or MI. The 48-frame control in
`test_adaptive_locality_geometry_validation.py:133-173` constructs two channels whose joint bin counts factor
exactly (`joint[a][b] = p_a p_b * 100`), so `MI = 0` to rounding while `H(a) = H(b)` exactly; the probe returns
`RESEARCH_HOLD` with the identity flag. Verified by reading, and the test is part of the 87.

Register addition (R-1): Markets already encodes this identity as a NULL axis (`odcore/null_extract.py:37`,
`EQ_QUAD`), and `DavisAI1974/Basic_equations` `CLAUDE.md` records INFO-036 (GW150914: attractor confirmed on real
data as an equal-marginal-entropy artifact) and INFO-038 (per-event asymmetry `|Ha-Hb|` 0.62/0.74/1.61 inversely
tracks attractor cosine; the merger signature rides the orthogonal MI axis). The hypothesis "the attractor is
coupling" and its real-data correction both exist upstream and should be linked, not re-derived.

### 4.2 The Fisher-like proxy is a location-Fisher plug-in estimator (sharpening, not a defect)

With bin masses `p_i` and width `h`, the histogram density is `f_i = p_i / h`. The location-family Fisher
information is `I = integral (f')^2 / f dx = 4 integral (d sqrt f / dx)^2 dx`. Approximating the derivative by a
forward difference on the bin lattice: `sqrt(f_{i+1}) - sqrt(f_i) = (sqrt(p_{i+1}) - sqrt(p_i)) / sqrt(h)`,
divided by `h`, squared, times 4, times `h` for the integral gives `4 (sqrt p_{i+1} - sqrt p_i)^2 / h^2`, which is
exactly `information.py:144-145`. So the proxy is the standard plug-in estimator of location Fisher information
for the frozen-bin density. Two caveats stay: an empty bin adjacent to a populated one contributes `4 p / h^2`
(the "roughness" artifact), and this is Fisher information in the shift parameter, not in any model parameter.
The gate `parameter-fisher-information` stays UNVERIFIED; its wording can be made exact.

### 4.3 Structural collinearity of `Ha` and `Ha^2`, and what it does to `B = |c_Ha2| / |c_HaHb|`

Let `Ha = m + d` on a window with `d` small relative to `m` (typical: `m` about 2 nats, `sd(d)` 0.05). Then
`Ha^2 = m^2 + 2 m d + d^2`. After centering, the `Ha^2` column is `2 m (Ha - m) + (d^2 - E d^2)`; its correlation
with the `Ha` column is `rho = 1 / sqrt(1 + var(d^2 - E d^2) / (4 m^2 var(d)))`. For `d` uniform on `[-w, w]`,
`rho = 1 / sqrt(1 + w^2 / (15 m^2))`. With `m = 2`, `w = 0.1`: `rho = 0.99992`, two-column condition number
`sqrt((1+rho)/(1-rho))` about 155, and the variance inflation factor of each coefficient `1/(1-rho^2)` about 6,000.
The same holds between `HaHb` and `Hb` (and `Ha`) when `Hb` is narrow. The QR in `coupling.py:71-122` will
not abstain (norm threshold `1e-7 sqrt(n)`), and `rank_diagonal_ratio` will read in the hundreds, far below the
`1e6` triage threshold. The fit is still identified, but `c_Ha2` and `c_HaHb` are each estimated with variance
thousands of times the well-conditioned value, so `B`, their ratio, inherits that. Consequence: window-to-window
swings in `B` are partly a basis artifact. This does not invalidate the Level 2 program; it says `B` should be
reported alongside the same ratio computed on an orthogonalized (centered, Gram-Schmidt or Legendre) polynomial
basis, with both archived. Counter-check available today: `geometry_probe._basis_condition_audit` already computes
exactly this `rho`; the fix is to surface it for the full library and not only for `(HaHb, HaHb^2)`.

### 4.4 What the two "Neumann" modules actually test, and a formalization of the original mechanism

`core.graph_neumann_residual` (L189-202) computes at each boundary node `a`:
`r_a = sum_{b ~ a} w_ab (u_b - u_a) - g_a`. That is `(-L u)_a - g_a` with `L` the weighted graph Laplacian.
On a 1-D chain with the endpoint as the boundary node, `r_0 = w (u_1 - u_0) - g_0`, so `r_0 = 0` with `g_0 = 0`
is `u_1 = u_0`, the mirror-ghost discretization of `du/dn = 0`. On any node with more than one incident edge
(2-D grid edge or corner), the sum includes tangential edges, and `r_a = 0` is then the statement that the
Laplace equation holds at the boundary node after reflection, which is a condition on the PDE residual, not on
the normal derivative alone. So the residual is a harmonic-at-boundary check that coincides with Neumann only
on degree-1 boundary nodes. `graph_boundary.FluxDomain` + `conservative_step` is different and is the better
object: it is a finite-volume diffusion `V_k du_k/dt = sum c_kj (u_j - u_k) - F_k` with a prescribed outward
flux `F_k` on boundary cells; `F = 0` is the natural (reflecting) boundary and mass is conserved
(`boundary_validation.checked_step` verifies it to 1e-10; the explicit step bound `dt <= 1 / max_k sum c/V_k`
is the diagonal-dominance condition and is correct). What is missing is any derivation of `c_kj` and `V_k` from
geometry; today they are inputs.

Original mechanism, formalized as a research experiment (NOT built, NOT verified): take packed centers
`c_k` along a path (or in the metric space), with neighbor distances `d_k = d(c_k, c_{k+1})`. The "difference in
distance between position neighbors" defines a non-uniform cell: half-widths `h_k^- = d_{k-1}/2`,
`h_k^+ = d_k/2`, cell volume `V_k = (d_{k-1} + d_k)/2`, conductance `c_{k,k+1} = D / d_k`. Where a neighbor is
missing (the packing boundary, soft or hard), the missing conductance IS the zero-flux condition. This produces a
`FluxDomain` directly from `advanced.PackingIndex` output with no new PDE machinery, and it can be tested against the
1-D heat equation with a manufactured solution (`u = cos(pi x)` on `[0,1]` has `du/dx = 0` at both ends, decay
`exp(-pi^2 D t)`). Higher dimensions need Voronoi facet areas; that is the real "physical normals" gate. This keeps
the Neumann hypothesis attached to the post's own construction instead of to an abstract graph.

### 4.5 Finite Cauchy diagnostics on a changing domain

`core.finite_cauchy` computes `max_{i<j in last W} d(x_i, x_j) <= eps` under ONE `MetricContract`. That is the
finite statement "the tail is `eps`-clustered in this metric"; it implies nothing about `m, n -> infinity`, and it is
not defined across two metric versions (the `MetricContract.identity()` check in `LocalityEngine.admit` refuses
that, correctly). Counterexamples the docs already list (slow drift, oscillation, jumps, deceptive stabilization)
are all real: `x_n = log n` has consecutive differences `-> 0` but is not Cauchy; the W-window test passes for
large `n` with fixed `W`. The only finite statement that is valid is the one computed. For a changing domain, the
minimum additional contract is a versioned transport map `T_{v -> v'}` with a bound on `|d'(Tx, Ty) - d(x, y)|`;
without it, cross-version comparisons must stay holds. NOT-IMPLEMENTED; the docs say so.

### 4.6 What the synthetic controls prove

The coupled generator (`test_geometry_controls.py:34`) is `dHa = 0.018(-0.6 Ha + 0.9 Ha Hb + 0.03 FIa)`; the
fitted library contains `const, Ha, Ha2, FIa, HaHb`. Recovery of `HaHb` is therefore expected by construction.
The known-quadratic generator (`:80`) adds `0.08 (HaHb)^2`, again a term in the fitted library. These are correct
estimator sanity checks. The four independent seeds and the regime-switch generator are genuine negative controls
for THOSE generators. None of this is evidence about unknown structure; the register's wording "possible in
controlled toy dynamics" is accurate and should add "generator contains the fitted term".

### 4.7 Five-step and Level 2, independently restated against the original source

Original (`basic_equations/level2_four_sciences.py`, read): per window of 30 with stride 4, per pair, fit
`dH_i/dt` (central differences) on `[H_i, H_j, H_i^2, H_j^2, H_i H_j, MI_ij, 1]` by `lstsq`, then
`B = |c_2| / (|c_4| + 1e-10)`; Level 2 on `log(B + 1e-6)` with library `[B_k, B_net, B_k^2, B_net^2, B_k B_net,
mean(B^2), 1]`, `B_net` = mean over the other pairs of a hardcoded 6-node chain, in-sample R^2. Differential
entropy with per-call `np.histogram` ranges (bins re-fit on every frame).
New engine: frozen bins, discrete entropy, holdout, no epsilon (abstain), no log, forward secant, no `B_net`,
per-pair directional. Both are retained as distinct experiments; M-3 asks that the differences be written down.

---

## 5. Evidence-preservation trace (RawMember -> RawFrame -> InfoFrame -> reports -> registry)

Branches where something can be rejected BEFORE archival (all fail-closed, none silently truncate):

1. Pre-admission: `RawMember.__post_init__` (`information.py:31-35`) and `RawFrame.__post_init__` (`:44-51`) raise
   on non-finite values, missing identity fields, duplicate evidence ids. Documented importer responsibility.
   NOT-IMPLEMENTED: a raw-bytes archive for rejected pre-admission records.
2. Derivation: `derive_information` never raises on data content; out-of-range, unrecognized node, duplicate member,
   unaligned ensemble all yield a whole-frame `REVIEW_REQUIRED` with reasons (`:113-132`). Good: no partial frame.
3. Series validation: `validate_series` (`:163-185`) raises on non-READY frame, schema change, cross-frame duplicate
   evidence id, non-monotone clocks. On the geometry path the archive-first wrapper stores raw + derived first
   (`standalone_review.py:44-49`) and converts the non-READY case to a hold (`:67-72`). On the coupling and Level 2
   paths there is no wrapper: PG-1.
4. Fit-time: all `_qr_fit` raises are caught and converted to abstentions (`coupling.py:215`, `:272`,
   `level2_coupling.py:99`, `geometry_probe.py:218`, `geometry_validation.py:199`). Reason text is kept in three of
   five sites: PG-2.
5. Registry: `archive` is content-addressed and refuses silent overwrite (`research_holds.py:105-107`); `hold`
   refuses conflicting case detail (`:151-153`); `review` allows only non-destructive states (`:161-163`) and there
   is no delete path; `verify` checks foreign keys, archive digests, the hash chain and case/history agreement
   (`:185-220`). Conflicting payloads are refused but not stored: PG-3. Byte cap: PG-4.
6. Full-raw binders (`preserve_full_raw_*`, `preserve_geometric_*`) re-derive `derive_information(r, bins)` and
   compare to the InfoFrame (`:338`, `:448`, `:508`), so a tampered or stale derived frame cannot be archived as
   if it matched. Lineage conflicts are archived as cases, not rejected (`:546-549`, `:609-613`). Good.
7. Outputs: every report carries `scientific_jobs_eliminated: 0` and preservation flags; the binders refuse any
   report where those flags are not zero/False.

Tamper model, stated plainly: SQLite with a sha256 hash chain detects accidental corruption; a writer with the
file can rewrite the chain. There is no external signature in the package and none anywhere in Markets either
(Markets uses sha256 content pins only). `raw-external-validation` and any "signed receipt" claim remain
NOT-IMPLEMENTED.

---

## 6. Markets / Frankie reconciliation map (read-only; nothing in Markets is proposed for replacement)

Five different objects are called "dipole" across the two trees. They must stay distinct in any interface:

| Name in use | Where | Definition | Estimator |
| --- | --- | --- | --- |
| Flow dipole / `imb_level` | `odcore/info_dipole.py:97`, `markets_adapter.py`, `news_coupling_research.py:138` | `(buy - sell) / (buy + sell)` | none |
| Entropy flow dipole | `odcore/info_dipole.py:58-114` | `ent_dipole = (Ha - Hb)/(Ha + Hb)`, `C = 0.5(Ha+Hb)/MI`, `mi_flow` = late-half MI minus early-half MI | discrete histogram, `bins = round(sqrt n)` per call |
| Continuous operator row | `odcore/operators.py:30-126` | basis `(Ha, Hb, Ha^2, Hb^2, HaHb, MI)`, window 40 stride 10 | Vasicek H, KSG-1 MI (k=4) |
| Centroid "algebraic dipole" | `odcore/dipole_predictor.py:97-140` | `Ha = <c, c_win>/||c_win||`, `Hb` likewise on lose centroid; fit `Ha^2 = a + b HaHb + c (HaHb)^2` | 128-dim centroid projection |
| Frankie C15 Dipole | sqlite-triage `native_dipole.py:105-190`, `dipole_classroom.py` | 19 far-side book-state columns, `normalized_imbalance = (bid - ask)/(bid + ask)`, orientation SAME/FLIP | none (book state) |
| Imported Level 2 balance | `adaptive_locality/coupling.py:163-169` | `B = |c_Ha2| / |c_HaHb|` from a frozen-bin discrete-entropy fit | discrete, frozen bins |

Facts for the interface plan (verified by the sub-review and spot-checked):
- Markets' `odcore/null_extract.py:36-39` already defines `EQ_LINEAR`, `EQ_QUAD` and `MI_AXIS` as fixed axes and
  projects the SVD null vector on them. The imported `geometry_probe` identity check is the same algebra by a
  different route. Keep both; they are independent confirmations.
- Markets' `odcore/dipole_predictor.py:13-25` carries the static quadratic with reference coefficients
  `a=0.007, b=-0.093, c=1.309, R^2=0.943` from the chemistry caricature. Under M-2 that fit needs the
  reparameterization null before it is read as more than descriptive. The coefficients stay recorded.
- Markets' leakage gate (`odcore/leakage.py:23 assert_no_leakage`) is a permutation-of-the-future test on a signal
  function. It is complementary to the imported `_operator_row` future-donor refusal; the imported fitters have
  not been run through `assert_no_leakage` and should be before any Markets data touches them.
- Estimators differ: Markets uses continuous (Vasicek, KSG) and per-call bins; the imported package uses frozen
  discrete bins. Neither replaces the other; a Markets adapter must declare which estimator produced each
  InfoFrame in `calibration_identity`.
- Frankie vocabulary on disk: families are P/O/S/X ("seed annotations, never an allowlist",
  `native_exhaustion.py`); directions are LONG/SHORT, SAME/FLIP, side A/B/N; clocks are
  `ts_event_ns`, `ts_recv_ns`, known-by and feature-availability clocks (99-registry group `causal_clocks`);
  the atomic unit is one F_LAST-closed event group. "P/O/X/F", "AB/BA" and "evidence plane" as literal strings are
  NOT FOUND in Markets. The imported `Observation.direction`/`RawMember.direction` fields are free strings, so they
  can carry SAME/FLIP or A/B without change; the register should record the actual vocabularies.
- The 99 are `full-context-audit/canonical-99-registry.json`: 99 layers in 17 groups, schema
  `FRANKIE_NATIVE_RAW_MBO_INGESTION_LAYER_REGISTRY_V1`, with per-group policies and content-sha256 proof mode.
  This is the real "planes" contract the imported `EvidenceManifest.planes` field should eventually bind to.
- Frankie's own hold/receipt mechanics: append-only output ledgers (10, including
  `output_negative_sparse_inconclusive_ledger`), `CoverageLedger`/`IsolationLedger` in
  `native_calculation_runner.py` with 8 fail-closed gates, sha-chained migration receipts in
  `frankie_boss/granite_retained_host.py:34-66`. No `RESEARCH_HOLD` concept exists in Markets today; the imported
  registry would be new, and should be mapped onto the existing negative/inconclusive ledger rather than beside it.
- Name collisions if the package were ever flattened onto `PYTHONPATH`: `queue.py` shadows the stdlib `queue`
  (Frankie CI puts module directories on `PYTHONPATH`, `frankie_cycle_identity_ci.yml:26`); `coupling`, `adapters`,
  `core`, `contracts`, `checkpoints`, `benchmark`, `index` collide with Markets names. Import it only as a package.
- Markets has no pytest config and `research/`, `research/kalshi/` are namespace packages. The imported tests use
  `unittest discover -s tests` and import sibling test modules by bare name (`from test_adaptive_locality_coupling
  import frame`), so they must be run from the snapshot directory or with `tests/` on `sys.path`.
- Frankie tree on this branch is partial (F-1). The `CLAUDE_RECONCILIATION_20260916.md` that Markets `CLAUDE.md:9`
  cites is not present in any branch history.

Proposed Markets-native layout (PROPOSAL, not implemented):

```
research/kalshi/adaptive_wavepacket_20261108/
  buildmap_source_snapshot/            (immutable, byte-exact; never edited)
  markets_adaptive_locality/           (future: Markets-owned fork, imports as a package)
    estimators.py                      (declares vasicek/ksg/frozen-bin; writes calibration_identity)
    frankie_adapter.py                 (F_LAST groups -> RawFrame; P/O/S/X, SAME/FLIP, ts_recv_ns/ts_event_ns)
    archive_first.py                   (five-step + Level 2 + geometry, all archive-before-fit; PG-1)
    ledgers_bridge.py                  (ResearchHoldRegistry <-> Frankie negative/inconclusive ledger)
  tests/
```

---

## 7. Native BuildMap component (included; tests pending)

Method: the whole snapshot was copied to a scratch directory outside the repo; `npm ci --ignore-scripts` from the
registry; Node and Python suites run there; the scanner's static mode run read-only against the real Markets tree
with JSON to stdout only (no manifest, no HTML, no `--observe-python`; `git status` clean afterwards, checked
twice). The four load-bearing defect citations below were re-read in the source by the lead reviewer.

### 7.1 Test results (exact)

| Suite | Result |
| --- | --- |
| Node `node --test` (Node 22.23.4; package engines >= 20) | 168 pass, 0 fail, 0 skip, 6.4 s. Per file: trial 1, collected-runs 8, completion 11, export 2, guide-tasks 3, intent 4, inventory 4, outcomes 8, recovery-extension 3, review-evidence 14, scan 37, server 18, ui 37, workflow 18. `ui.test.js` uses a hand-written DOM double (`tests/ui.test.js:11-13`), not a browser. |
| Python `pytest tests/test_adaptive_locality*.py` (3.13.18) | 87 passed, 6 subtests passed, 4.1 s. Matches the 87 counted by hand. CI uses `unittest discover` on 3.11/3.12/3.13. |
| `tests/adaptive-locality-buildmap-trial.test.js` | 1 pass; prints `trialNativeSourceEdges: 7, declaredUnverifiedScienceGates: 8, falsifiedVerificationClaims: 0, changedSourceFiles: 0`. |
| `.buildmap/workflow-browser-check.mjs` (Chromium 153, playwright-core 1.63) | 14/14 PASS. |
| `.buildmap/browser-check.mjs` | FAILS at its first assertion (`browser-check.mjs:30`, expects 6 dogfood cards, snapshot renders 56 because `adaptive_locality/` and its tests are not in `.buildmap/project.json`). The "30-case Chromium baseline passes" line in `BUILD_GAPS.md` is stale at `8b4295d`. |
| Static scan of real Markets tree, bounded `--json` | 2.6 s; 639 files (498 .py, 44 .js, 41 workflow .yml); 299 code edges; statuses coded 461 / connected 178 / verified 0; intent `unknown` (`intent.js:5-6` reads only README/ARCHITECTURE/DESIGN/SPEC, never CLAUDE.md); gaps: 639 `unproved`, 461 `no-observed-connection`, 1 `missing-intent`, 1 `javascript-parse-failed` (`research/kalshi/forecaster_month_pass.workflow.js:107`, a Workflow-tool script with top-level `return`; acorn parses .js as module, `javascript.js:40`). Bounded mode analyzed only 64/498 Python files (434 `analysis-limit`, `workflow.js:46-48`). Repeat run: identical fingerprint and statuses. |
| Static scan, `--json --workflow-all` | 14.4 s; 498/498 analyzed; 4,265 calculations, 5,871 call links, 46,487 of 52,358 call sites unresolved, 5,536 findings. |

### 7.2 What `buildmap_trial.py` measures (verified)

It emits a hand-written manifest (`buildmap_trial.py:16-36`): six components mapped 1:1 to
`information, coupling, geometry_probe, geometry_validation, level2_coupling, research_holds`, with hand-declared
`dependsOn`, plus eight `unverified-<gate>` components (`:47-57`) from `research_gates.py` whose declared file
`adaptive_locality/unverified_review/<gate>.py` does not exist, so they are `planned/missing` by construction.
The Node test copies the six files into a temp root and asserts at least one observed edge, gates planned and
missing, no verified/live state, bytes unchanged. `baselineNativeSourceEdges: 0` is a hard-coded constant
(`:58`); the "gain" assertion is `7 > 0`. The seven edges are the real `from .x import` relations among those six
files; every `.core` import is dropped silently because `core.py` is not copied and Python unresolved imports are
never diagnosed (BM-1 below). Three of the ten hand-declared `dependsOn` links (research_holds to the two geometry
reports and Level 2 links) have no source backing and surface as `unobserved-dependency` warnings.

Verdict: real but trivial static import counting on six files; a self-referential scaffold; zero contact with
Markets data, prediction, or the wavepacket mathematics. "7 static edges, 8 gates" is an accurate description of
the scaffold and nothing more. It does demonstrate the one thing it claims: the scanner does not invent verified
states.

### 7.3 How "verified" is produced, and whether it can be faked

Source-derived states stop at `connected` (`scan.js:90-93`). `computing`, `verified` and `live` come only from
hand-written `.buildmap/evidence.json` receipts: `resolveStatus = max(base, receipt.status)` (`scan.js:174-178`)
after `assessEvidence` (`:180-203`), which requires the implementation complete, a valid status, for index >= 3 a
non-empty `note|command|proof` string, and, only if `sourceHashes` is present, that they equal the current file
sha256s. A receipt without `sourceHashes` is accepted as `binding: 'unbound'` with an info-level gap (`:194`,
`:234`). So a `verified` state can be produced by typing `{"status":"verified","note":"anything"}`; BuildMap never
runs, authenticates or inspects the claimed check, and the hash match proves only that files have not changed since
the receipt was typed. `BUILD_GAPS.md:38,51` says exactly this. The one authenticated artifact (Ed25519-signed
collector receipts, `collected-runs.js`) never promotes component states and is forgeable in-process (7.4).

Consequence for Markets: BuildMap evidence is a navigation and bookkeeping surface. It cannot be the acceptance
oracle for any scientific claim; the owner's handoff already says so, and this confirms it from the code.

### 7.4 Defects and security notes (file:line)

| ID | Sev | Path:line | Finding | Consequence for Markets |
| --- | --- | --- | --- | --- |
| BM-1 | HIGH | `src/scan.js:401` | `else if (!target && ext !== '.py' && spec.startsWith('.'))`: unresolved Python imports are never diagnosed. Confirmed with a fixture. | Holes in the Python dependency map are invisible; the trial's dropped `.core` edges are one instance. |
| BM-2 | HIGH | `src/imports.js:73-81` vs `src/workflow.js:184-196` | Two Python resolvers disagree: `resolveImport` resolves non-relative specs only from the project root (`:76`); `moduleCandidates` tries root AND importer directory (`:191`). | Markets' dominant style is script-level absolute sibling imports (`import kalshi_history`). 33 of 45 `research/kalshi` scripts get no map edge at all; at least 9 absolutely import existing siblings (`bucket_continuation`, `coach_replay`, `forecast_harness`, `forward_curve`, `kalshi_score`, `kalshi_weather_forecast`, `pull_year_mbp10`, `redownload_mondays`, ...). `connected` status and `no-observed-connection` gaps are wrong for Markets. The test named "sibling imports" (`tests/scan.test.js:194-200`) covers only `from . import b`. |
| BM-3 | MED | `src/scan.js:92` | `wired` is true if ANY import edge touches a present file, including intra-component edges. | `connected` does not mean cross-piece wiring. |
| BM-4 | LOW | `src/scan.js:141` | Progress denominator includes `__mission__` (always planned, weight 0). | Progress index systematically deflated. |
| BM-5 | MED | `src/scan.js:151,170` | Fingerprint hashes the absolute `project.root` and `inventoryMode`. | Same tree at another checkout path yields a different fingerprint; Guide task keys and "stale" labels are machine-specific. Otherwise deterministic (repeat run identical; file list sorted at `:47`). |
| BM-6 | MED | `src/workflow.js:26-28,36-37` | Python analyzer batch has a hard 5 s wall timeout; bounded mode has no bisection. | On a slower box the whole 64-file batch flips to `analyzer-unavailable`, silently changing findings and fingerprint. Markets whole-inventory ran about 1.8 s per batch here. |
| BM-7 | LOW | `src/imports.js:38-45` | Multi-line `from x import (a,\n b)` captures only the first line's names; backslash continuation likewise. | Name-level specs lost; module edge still resolves. |
| BM-8 | LOW | `src/cli.js:76` | A mistyped local target silently `mkdirSync`s a new directory. | "Read-only mapping" has a write side effect. |
| BM-9 | MED | `src/server.js:19-21`, `public/app.js:70` | Every `/api/map` and `/api/gaps` request runs a full `scanProject` (git ls-files, hash every file, spawn python3); client polls every 1.6 s. | On Markets a bounded scan is 2.6 s, so the server is permanently busy; no fingerprint cache, no concurrency guard. |
| BM-10 | MED | `.buildmap/evidence.json`, `BUILD_GAPS.md:1,34-36`, `docs/MVP_COMPLETION_20261013.md` | All dogfood receipts are stale at `8b4295d`: self-scan gives verified 0, five `unsupported-evidence` blockers (scanner receipt binds 12 files, component declares 14; `src/scan.js` bound hash `4716ce..` vs current `aae3aa..`), notes still say "154 cases" (168 now). | The tool reports this correctly; the docs do not. Do not cite "MVP verified" for this commit. |
| BM-11 | LOW | `.buildmap/browser-check.mjs:30` | Hard-coded 6-card assumption. | Fails on the current snapshot (7.1). |
| BM-S1 | INFO | `src/server.js:13-26` | GET/HEAD only; assets from a fixed four-entry map (no path traversal); binds 127.0.0.1; no CORS. No Host-header check, so DNS rebinding from a malicious page can read `/api/map` (file names, sha256s, docstrings, step narratives); `--host 0.0.0.0` exposes that with no auth; `/api/health` leaks the absolute root (`:18`). No write path. | Acceptable for a local inspector; never bind beyond loopback on a Markets box. |
| BM-S2 | HIGH (policy) | `src/collected-runs.js:50`, `src/python-observer.py:330-340` | `--observe-python` executes project code in the same process as the profiler; a hostile entry can reach the observer globals, disable `sys.setprofile`, or write its own packet to fd 3 and `os._exit(0)`; the parent then signs whatever arrives (`collected-runs.js:61-70`). Acknowledged in code (`python-observer.py:297`, `collected-runs.js:104`). | Must never be pointed at Markets trading or ingestion scripts. Add a CI guard (7.6 item 8). |
| BM-S3 | INFO | static scan path | Spawns only `git ls-files` and `python3 -I -S src/python-analyzer.py` (stdin JSON, ast only, 5 s / 16 MB); `safeFile` realpath containment (`scan.js:316-322`); `boundedFile` O_NOFOLLOW + size caps (`review-evidence.js:61-75`); `prepareTarget` clones only `https://github.com/owner/repo` with `--` and check-ref-format (`setup.js:57-65`); client interpolations pass `escapeHtml` (`public/app.js:1337`); export escapes `<` and `</script` (`export.js:18-21`); no eval/Function. | Static mode is safe to run against Markets read-only. |

### 7.5 Author-recorded open gaps (retained verbatim in spirit)

`BUILD_GAPS.md`: full accessibility and assistive-tech coverage, real devices, Firefox/Safari/other Chromium
(rows 24, 28, line 42); evidence capture manual, no authenticated CI/runtime/deployment receipts (`:51`); wiring
heuristic only, no TS aliases, Python src layouts, frameworks or other languages (`:52`); no scale benchmark
(`:53`); intent/mechanism modelling shallow (`:54`); remote/history/zoom deferred (`:55`); Guide continuity,
accounts, billing unbuilt (`:66-67`); "full roadmap remains pending, billing deferred to a final Stripe stub"
(`:1`); PR #1 open, nothing merged (`:44`). `REVIEW_NOTES.md:33-40`: exercise the UI in a real browser on a real
project; parser-backed language resolution; authenticated receipts; capability navigation and a real layout engine;
"next useful dogfood gap remains the server-to-visualizer HTTP connection". `docs/ROADMAP_COMPLETION_LEDGER.md`:
all twelve criteria BM-01..BM-12 still need completion evidence; `docs/RUNTIME_OBSERVATION.md:3` and
`docs/BROWSER_ACCEPTANCE_20261013.md:27-35` repeat the open list.

### 7.6 Tests still needed before BuildMap can be trusted on the real Markets tree

1. Markets-shaped import characterization fixture: absolute sibling imports from `research/kalshi` scripts,
   `sys.path.insert` script style, `odcore.*` package imports, `from . import` inside `frankie_boss`, `__main__`
   modules; assert map edges AND agreement between map edges and workflow call links (BM-2).
2. An unresolved-Python-import diagnostic test (BM-1).
3. Determinism: two scans at the same commit (bounded and `--workflow-all`) yield identical fingerprint and
   per-file analyzer statuses; a cross-checkout-path run (expected to differ today, BM-5); a wall-time bound so the
   5 s analyzer timeout cannot flip statuses (BM-6).
4. Analyzer budget on the real tree: assert 0 `analyzer-unavailable` for 498 files with `--workflow-all`.
5. Workflow YAML: 41 `.github/workflows/*.yml` are inventoried but inert (`coded`, outside every adapter); test that
   the map makes no claim about them, or add an adapter; same for Workflow-tool `*.workflow.js` with top-level
   `return` (parse error today).
6. Manifest and intent for Markets: without `.buildmap/project.json` and README the scan yields 640 file nodes and
   639 `unproved` gaps. Test that a Markets manifest (collectors, lag thread, level-hit, weather, odcore,
   frankie_boss, adaptive_wavepacket) yields component-level edges, and that intent can be sourced from
   `CLAUDE.md` / `KALSHI_TRADING.md` or a manifest mission.
7. Nested-snapshot exclusion: scanning Markets today also scans BuildMap's own copy under
   `buildmap_source_snapshot/` (50 of the 95 `research/kalshi` .py nodes). Test an exclusion rule.
8. Non-execution guard: a CI assertion that `--observe-python` is never run against Markets (it executes code; zero
   synthetic data rule) and that any scan leaves `git status` clean.
9. Server load: assert `/api/map` latency on a Markets-sized tree or add fingerprint caching (BM-9).
10. Re-baseline `browser-check.mjs` to the real dogfood card count; refresh or stop citing the stale dogfood
    receipts (BM-10, BM-11).

### 7.7 Status (owner decision, 2026-11-08)

BuildMap is a planned, included component of the Markets scientific workflow. It is NOT experimental and there is no
keep/drop question; any earlier "optional" or "experimental" wording in the historical BuildMap documents is
superseded by the owner's decision. What remains is testing: the scanner and viewer work on their own fixtures,
are not yet correct on Markets' import style (BM-2), and their evidence states are bookkeeping rather than proof
(7.3). Measured value today: a navigable static map that found one real parse problem
(`forecaster_month_pass.workflow.js`) and correctly surfaced its own stale receipts. Measured cost: BM-2 makes its
connectivity claims wrong for the Markets tree until fixed. `buildmap_trial.py` and its Node test are a scaffold
that stays as part of the component; the scaffold must not be cited as integration evidence. The ten tests in 7.6
are the path to trustworthy use on the real tree.

---

## 8. Engineering modules (grouping, index, queues, cache, checkpoints, visualization)

Method: delegated read-only sub-review of `grouping, index, disk_index, queue, durable_queue, checkpoints,
result_cache, visualization, review_cli, cli, experiments, benchmark` and their tests; suite re-run on a second
scratch copy (`unittest discover`: `Ran 87 tests, OK`, Python 3.13.18). The two highest-priority findings (E-1, E-2)
were reproduced by the lead reviewer from the source.

| ID | Sev | Path:line | Finding (verified) | Consequence | Re-test |
| --- | --- | --- | --- | --- | --- |
| E-1 | HIGH | `index.py:40-51,113-124`, `disk_index.py:86-94,178-179` | Grid key is `floor(sqrt(w) v / radius)` and only offsets (-1,0,1) are scanned, but the exact filter accepts `distance <= radius`. Rounding lets two points sit at `distance == radius` two cells apart. Reproduced: scale 1, radius 1.0, center `x = 1 - 2^-53` (cell 0), query `x = 2.0` (cell 2): `metric.distance = 1.0`, `LocalityEngine.propose` returns PROPOSE_ONLY with that candidate, `ExactGridIndex.candidates` and `DiskGridIndex.candidates` return `()`. | The "accelerated candidates equal brute force" claim (acceptance ledger, "Candidate completeness") is false at ulp level and the miss is silent (no abstention record). | Add the exact pair above to both randomized differential tests; fix by scanning offsets (-2..2) or by keying with cell width `radius (1 + 8 eps)`; keep the exact recheck. |
| E-2 | HIGH | `disk_index.py:155` | `UPDATE centers SET active=1, reason=NULL` on restore; one `reason` slot, no history table, `get()` returns None for retired rows (`:113`), snapshot gives counts only. | The retire/restore decision history (a review decision) is unrecoverable after restore. | Retire with a reason, restore, assert the reason is still retrievable; add a `center_history` table. |
| E-3 | MED | `review_cli.py:54-60` | Comment says the probe destination is "reserved first" but only path distinctness is checked; `write_html` runs before `open(probes, "x")`. | With an existing probes file the HTML is written and then the probe write fails; rerun is then refused by the HTML no-clobber. Partial publication. | Open both outputs with "x" before writing either, or seal via temp + link. |
| E-4 | MED | `grouping.py:43-110`, `:119-127` | Every refusal is a raised `LocalityError` with nothing appended to the grouper ledger; `snapshot()` exports only `ledger_head/ledger_count`, never `_entries` (which hold ALIAS_VIEW / REVERT_ALIAS / FLAG_OUTLIER reasons); no `recover()`. `_members` and aliases are in-memory while the index is on disk. | Abstention reasons and alias/outlier review reasons are volatile; a restart loses memberships while the index survives (state divergence). | Export entries in `snapshot()`, add `recover()`, log refusals as ledger entries. |
| E-5 | MED | `durable_queue.py:127-136`, `:92` | `retry()` takes no reason; expiry sweeps are unrecorded; no history table; `attempts` is the only trace; no attempts cap. | A retry or sweep reason cannot be recovered; unbounded re-lease loop possible. | Add reason + history table + attempts cap. |
| E-6 | MED | `index.py:127-128`, `disk_index.py:198-199` | `max_neighbors` truncation discards further in-radius hits with no `truncated`/`total_hits` indicator. | Caller cannot tell more neighbors existed. | Return total hit count alongside the truncated list. |
| E-7 | MED | `adapters.py:30-32`, `cli.py:25-27` | `shadow_batch` exports `event_id, status, center, candidate_weights, event_identity` and drops `Decision.reason` (e.g. "kernel underflow"); `visualization.py:76,96` therefore has no slot for it. | ABSTAIN reasons leave the system at the first export boundary. Same class as PG-2. | Add `reason` to the exported decision dict and to the visualization frame. |
| E-8 | LOW | `index.py:104` vs `disk_index.py` | `ExactGridIndex.candidates` has no `same_direction`/`historical_only` filters (DiskGridIndex does). `benchmark.py:31-34` brute force filters are vacuous (all "AB", all centers earlier than all queries). | A BA query returns an AB center with a later clock from the memory index; the benchmark differential cannot see it. | Benchmark with mixed directions and interleaved clocks. |
| E-9 | LOW | `disk_index.py:201-209`, `grouping.py:44,54` | `candidates()` runs batched autocommit SELECTs with no enclosing BEGIN; `grouping.propose` reads `index.revision` separately. | Single-process: fail-closed via `admit` recompute. Multi-process: TOCTOU, result may match no single revision. | Wrap the read in a deferred transaction and return the revision from inside it. |
| E-10 | LOW | `durable_queue.py:88,105,127` | `now` is caller-supplied; token fencing holds (verified two-connection double-complete refused, `:121`), time fencing is honor-system. Docstring already disclaims distributed fencing. | Clock skew can sweep a live lease or let a stale holder complete. | Documented limit; keep. |
| E-11 | LOW | `queue.py:55` | `recover()` reports "duplicate pending entry" for any non-QUEUED status including BACKPRESSURE overflow. | Wrong reason string. | Fix message; test the overflow path. |
| E-12 | LOW | `experiments.py:17-25` | `Workload` accepts `nan`, `inf` and bool counters; `distinct_pairs` and `bytes_read` are collected but never reported (`:27-37`). | Deltas can be `nan`; inconsistent with the package's finiteness discipline. | Add finiteness checks; report all collected counters. |
| E-13 | LOW | `checkpoints.py:39-40`, `:17`, `:28` | `load_snapshot` collapses FileNotFound, permission and corrupt-JSON into "missing or torn snapshot" (cause in `__cause__`); NaN payload raises bare `ValueError`; `os.link` fails on FAT/some network FS and Windows; files are mode 0600. No-clobber and fsync are real (verified). | Message collapse (same class as PG-2); platform limits. | Distinct messages; document platform limits. |
| E-14 | NOTE | `visualization.py:127-138,235,279` | Display sampling IS disclosed (`sampled_for_display_only`, counts, `source_event_set_sha256` over all ids); science runs on every event; over-limit fails closed. Omitted ids are not listed and per-point reason text is absent (E-7). `write_html` is no-clobber but not atomic. | Good, with the E-7 gap. | List omitted ids in the frame. |
| E-15 | NOTE | `result_cache.py:42,58` | Key has all 8 fields; put is atomic and no-clobber; nothing in the package calls `get` to short-circuit work; the `scientific_jobs_eliminated` guard is honor-system (payload lacking the field passes). Identical re-put raises (no idempotent put). | The cache cannot by itself prevent a caller from skipping a computation; only policy can. Matches the docs. | Require the field on put; add idempotent identical put. |
| E-16 | NOTE | `grouping.py:124,127`, `experiments.py` | `averaged/flattened/discarded/scientific_jobs_eliminated` in snapshots are hard-coded zeros, not measurements; tests asserting them prove the constant. | These counters are declarations, not evidence. | State this in the docs; derive the counters where possible. |

Engineering tests not covered by any existing test (from the sub-review): the float-boundary cell case (E-1); the
non-indexed streaming fallback (> 5 dims at `max_cells`) has zero tests; `allow_cross_family=True`,
`same_direction=False`, `historical_only=False`; `max_neighbors` truncation actually triggering; metric/radius
mismatch on reopen; retire-reason survival; corrupt payload decode; grouper DUPLICATE, non-monotone rejection,
pre-existing untracked center, `verify()` after tampering; `complete` on a pending row; `retry` with a stale token;
conflicting `result_identity`; lease sweep with skewed `now`; `CacheKey` missing-field rejection; cache put with
`scientific_jobs_eliminated != 0`; `checkpoints` tampered-digest branch, torn JSON, hard-link race; `experiments`
non-comparable and NaN paths; `review_cli.main()` probe path (E-3); visualization ABSTAIN/DUPLICATE statuses,
MAX_SOURCE rejection, INSUFFICIENT_WINDOW vs WITHIN branches.

---

## 9. "Nothing dropped" research register (additions; nothing removed)

Every item below is retained as-is from the owner's documents, plus provenance this review adds. Status is the
review's reading; the owner's own status text stands next to it.

1. Cauchy-like sequences under computability bounds on a dynamic domain. Owner: hypothesis. Review: finite
   diagnostic IMPLEMENTED (`core.finite_cauchy`, `advanced.window_drift`); dynamic-domain transport
   NOT-IMPLEMENTED (4.5). Counterexamples retained.
2. Wave packet as localization. Owner: analogy only. Review: real Gaussian IMPLEMENTED; oscillatory/complex packet
   forms, anisotropy, density-adaptive width: RESEARCH-HOLD.
3. Merge by distance. Owner: proposal only. Review: proposal path IMPLEMENTED with no job elimination; equivalence
   gate correctly fail-closed (`ledger.ScientificGate`).
4. Sphere packing / covering. Owner: heuristic. Review: exclusion-radius packing IMPLEMENTED (`advanced.PackingIndex`);
   coverage objective, high-dimensional concentration: RESEARCH-HOLD.
5. Neighbor-distance differences enabling Neumann BCs. Owner: inspiration, unverified. Review: NOT-IMPLEMENTED;
   formalization proposed (4.4); `graph_neumann_residual` tests a harmonic-at-boundary condition (4.4);
   `FluxDomain` is a correct abstract finite-volume reflecting boundary.
6. "Soft launching hard boundaries". Owner: design question. Review: hysteresis + abstain + reversible retire/restore
   IMPLEMENTED; no path from soft membership to any hard deletion exists. Retained as a question.
7. Five-step H/MI/FI operator coupling. Owner: built, synthetic. Review: IMPLEMENTED+TESTED with PG-1/PG-2; original
   Basic_equations variant (log B, central differences, epsilon, B_net, six-node chain) retained as historical
   precedent; both are distinct experiments (M-3).
8. Level 2 directional `B_ij(t)`. Owner: built. Review: IMPLEMENTED; B is a ratio of two variance-inflated
   coefficients under narrow entropy ranges (M-1); per-channel invalidation on one bad window (PG-5).
9. `(-1,-1,+2)/sqrt(6)` as coupling. Owner: hypothesis, corrected. Review: identity confirmed; real-data correction
   exists upstream (INFO-036/038) and in Markets (`EQ_QUAD` null axis); hypothesis retained with its correction.
10. Static quadratic `Ha^2 = a + b HaHb + c (HaHb)^2`. Owner: descriptive. Review: constant-donor tautology handled;
    slow-donor tautology not yet (M-2); Markets' chemistry reference coefficients (`dipole_predictor.py:25`)
    retained and subject to the same null.
11. Frozen-support novelty vs residual. Owner: built. Review: IMPLEMENTED+TESTED (`geometry_probe.py:177-206`).
12. Nested quadratic vs linear interaction on FUTURE targets. Owner: toy positive. Review: PROMISING-SYNTHETIC with
    generator-contains-term caveat (4.6).
13. Rank/conditioning. Owner: heuristic triage. Review: thresholds effectively detect only constant columns
    (M-1, 4.3); full spectrum and VIF diagnostic NOT-IMPLEMENTED; no observation discarded.
14. Parameter Fisher information. Owner: proxy only. Review: location-Fisher plug-in (4.2); model-parameter FI
    NOT-IMPLEMENTED.
15. Independent four-science replication. Owner: unverified. Review: Basic_equations ran four caricatures and then
    retired caricature work in favor of real data (Session 10); `cross_domain_motif` refuses shared identities
    (correct); real independent sources NOT yet supplied.
16. KBK, AI Poincare, SINDy, PySR. Owner: leads. Review: implemented and run in Basic_equations (files listed in R-1)
    and PySR in Markets `odcore/symbolic.py`; NOT applied to the Adaptive Locality frames. Retained as leads with
    their prior implementations linked.
17. Causal controls, multiplicity, regime drift. Owner: unverified. Review: single-lag null (M-4); up to 132 directed
    tests per run with no multiplicity control; RESEARCH-HOLD, all results retained.
18. Slayer-inspired raw/display separation, replay probes, cache keys. Owner: adopted architecture. Review: see
    section 8 for display-only sampling disclosure.
19. BuildMap as observer/inspector. Owner (superseded): optional. Owner (current): included component, tests
    pending. Review: section 7.
20. Markets application: ID-driven group explosion, 99 planes, FIFO/queue age, replenishment/withdrawal/absorption,
    causal clocks, P/O/S/X families, LONG/SHORT and SAME/FLIP directions, 20231018 / e2e-20231018-a2. Owner:
    historical context. Review: real Frankie contracts located (section 6); vocabulary differences recorded, not
    resolved; nothing in Markets touched.
21. Pre-admission raw-bytes archive, lossless partition manifests, signed external receipts, multi-host recovery.
    Owner: NOT built. Review: confirmed NOT-IMPLEMENTED (PG-4; section 5 tamper model).
22. Open cross-repo thread recorded in Basic_equations `CLAUDE.md:231`: "pull dipole JSONs from the Markets repo +
    list the flow dipole equation separately (Greg's call)". Retained here so it is not lost between repos.

---

## 10. Tests remaining (matrix)

| Area | Test to add | Status today |
| --- | --- | --- |
| Preservation | Archive-first wrappers for five-step and Level 2; every `validate_series` raise produces a raw archive + hold | NOT-IMPLEMENTED (PG-1) |
| Preservation | Abstention reason strings survive into `CouplingResult`, `BalanceWindow` and archived cases | NOT-IMPLEMENTED (PG-2) |
| Preservation | Conflicting re-archive stores both payloads and a CONFLICT hold | NOT-IMPLEMENTED (PG-3) |
| Preservation | Lossless partition manifest round-trip over the 32 MiB cap | NOT-IMPLEMENTED (PG-4) |
| Preservation | Pre-admission invalid bytes archived by an importer before `RawMember` | NOT-IMPLEMENTED |
| Conditioning | Full singular spectrum + VIF reported for every fit; B on raw vs orthogonal basis both archived | NOT-IMPLEMENTED (M-1) |
| Controls | Slow-donor reparameterization null for the static quadratic | NOT-IMPLEMENTED (M-2) |
| Controls | Donor lag sweep archived as a vector; donor autocorrelation reported | NOT-IMPLEMENTED (M-4) |
| Controls | Misspecified-generator and hidden-common-driver synthetic controls | NOT-IMPLEMENTED (T-1) |
| Controls | Leakage gate: run imported fitters through `odcore/leakage.assert_no_leakage` | NOT-RUN |
| Neumann | Voronoi-spacing FluxDomain from PackingIndex; manufactured-solution 1-D test | NOT-IMPLEMENTED (N-1) |
| Fisher | Proxy vs closed form for Gaussian at fine bins | NOT-IMPLEMENTED (R-2) |
| Estimators | Same RawFrames through frozen-bin, Vasicek and KSG; archive all three InfoFrame sets | NOT-IMPLEMENTED |
| Frankie adapter | F_LAST group -> RawFrame with ts_recv_ns clock, P/O/S/X family, SAME/FLIP direction; identity round-trip | NOT-IMPLEMENTED (needs fuller Frankie tree) |
| Markets data | Zero synthetic trading data: first real run must be on archived native tape under HOLD rules | NOT-RUN (launch is HOLD) |
| Index | Exact radius-boundary pair (`x = 1 - 2^-53` vs `x = 2.0`, radius 1) in both grid differential tests; mixed-direction, interleaved-clock benchmark | NOT-IMPLEMENTED (E-1, E-8) |
| Index | Retire reason survives restore; center history table round-trips | NOT-IMPLEMENTED (E-2) |
| Exports | `Decision.reason` present in shadow export, visualization frame and CLI output; grouper ledger entries exported and recoverable | NOT-IMPLEMENTED (E-4, E-7) |
| Queue | Retry/sweep reasons recorded; attempts cap; stale-token retry; skewed-`now` sweep | NOT-IMPLEMENTED (E-5, E-10) |
| Review CLI | Both outputs reserved before either is written; probe-path failure leaves no partial HTML | NOT-IMPLEMENTED (E-3) |
| Truncation | `max_neighbors` truncation reports total hit count | NOT-IMPLEMENTED (E-6) |
| BuildMap | Ten items in 7.6 (Markets import style, unresolved-Python diagnostic, determinism across checkout paths, analyzer budget, workflow YAML/Workflow-tool JS, Markets manifest and intent, nested-snapshot exclusion, no-execution guard, server load, stale receipts) | NOT-IMPLEMENTED |
| Migration | Binary DOCX/PDF byte copy and SHA verification; MIGRATION_COMPLETE report | PENDING (owner) |

---

## 11. Prioritized build plan (recommendations only; nothing started)

Phase 0 (owner): finish the two binary transfers, publish MIGRATION_COMPLETE, confirm the snapshot stays immutable.
Phase 1 (preservation, small, safe, authorized separately): PG-2 reason fields; PG-1 archive-first wrappers for
  five-step and Level 2; PG-3 conflict archiving. All three are additive, standard-library only, and testable in
  the existing 87-test harness. Do them in a Markets-owned copy, never in the snapshot.
Phase 2 (diagnostics, additive): M-1 spectrum/VIF reporting and dual-basis B; M-2 reparameterization null;
  M-4 lag sweep; T-1 misspecified controls; R-2 Fisher closed-form check. Every output archived; no thresholds
  tightened.
Phase 3 (estimator bridge): declare estimators in `calibration_identity`; run the same frames through frozen-bin,
  Vasicek, KSG; leakage gate on all fitters. This is where Markets and the imported package first meet, offline.
Phase 4 (Neumann research): N-1 Voronoi-spacing FluxDomain + manufactured solution. Pure research; keep
  "not applicable" as a legitimate outcome.
Phase 5 (Frankie adapter, needs the fuller Frankie tree and explicit go): F_LAST -> RawFrame, 99-registry binding,
  hold registry mapped onto the negative/inconclusive ledger. Read-only against archived tape. Launch stays HOLD.
Phase 6 (BuildMap as a Markets component): per section 7.

Separately authorized later, not recommended now: anything that connects to AWS, Frankie live runs, Search, the
30-day ingestion, or that eliminates a calculation.

---

## 12. Things this review did NOT do

- Did not run the BuildMap scanner against the real Markets tree in any write mode.
- Did not modify, move or re-run anything inside `buildmap_source_snapshot/`.
- Did not transfer the two binary reports.
- Did not inspect the live Frankie HEAD (not on this branch) or any AWS resource.
- Did not declare the migration complete.
