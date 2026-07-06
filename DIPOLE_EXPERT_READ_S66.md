# DIPOLE / OD-TOOLKIT EXPERT READ — S66 (2026-07-06)

**Mandate:** adversarial, opinionated expert read of the dipole/OD flow toolkit against the *current
Kraken deployment*. Not a coverage audit (`PIECES_TEST_dipole.md` already did that); this goes past it
to say where the REAL unrealized edge is, what's dead, and whether any of it should change the
capital-allocation model design.

**Discipline honored throughout:** per-cell law, net-of-cost, tautology/shuffle nulls, leakage-gate
before wiring, tools-complementary-not-competing. Every claim is tagged **[measured]** (a number in
code/docs) or **[hypothesis]** (my reasoning). No heavy compute was run.

---

## TL;DR verdict

The dipole/OD toolkit's *alpha* contribution to the Kraken deployment is **largely spent** — the deployed
D4 lean-flip zigzag (`flip_detector.py`) is the one live winner, and every other dipole read either nulls
or fails the honest queue-fill. The two genuinely-unrealized pieces are both **FILL/RISK-side, not
alpha-side**: (1) **S42 book-depth direction as a which-side-to-post fill signal** — the only OD read that
structurally *dodges* the S45 adverse-selection fill penalty that kills the divergence gate; and (2) the
**coupling_scanner/lead-lag dive-propagation structure**, which is a *capital-model risk input*, not a
per-cell edge. Direction-as-a-swing-bet is dead and airtight. The capital model **should** change — on
its risk/allocation axis, not its alpha axis (§4).

---

## 1. Where is the REAL unrealized edge? (ranked by expected $/hr, with the kill test)

First, the honest frame: at kr_mk0 the deployed ride has **~0.5 bp/swing headroom** (`STRATEGY_INVENTORY`
§2.A: "razor-thin"; a 1 bp maker fee is FATAL, kr_mk2 nets −13..−20). So any dipole candidate has to clear
the **honest queue-fill**, not the 0 bp-ideal fill — and that single constraint kills most of the toolkit
(`PIECES_TEST_dipole.md` §2c). Ranked:

### #1 — S42 book-depth DIRECTION as a FILL-SIDE (which-side-to-post) signal — **the best unrealized piece**
- **What:** `_liquidity_dive.py` (S42) — top-K depth-imbalance predicts the *signed* next move, OOS +0.164,
  63% hit, leads +0.1 s (`STRATEGY_INVENTORY` §8.1). Never run on Kraken (`PIECES_TEST_dipole.md` row H,
  ⛔ all 5 coins).
- **Why it's the one to build:** every *other* dipole gate fails for the same structural reason — the
  divergence `opp` gate selects **opposing-flow legs = the S45 adverse-selected worst-filling legs**
  (`PIECES_TEST_dipole.md` §2c: xrp fill 49%→11% when gated). S42 is categorically different: it is a
  **maker/quoting signal (which side of the book to rest on), not a leg take/skip filter** — the dipole
  audit itself flags this (`PIECES_TEST_dipole.md` §3 item 3: "a FILL-side (which-side-to-post) signal…
  so it may dodge the §2c fill penalty"). The deployed leak is the FILL (`STRATEGY_INVENTORY` §2.A: 54–79%
  of ALL loss is forced-taker closes), and this is the one OD read aimed at the FILL rather than adverse to it.
- **Expected impact [hypothesis]:** sub-bp per event, but it acts on the ~0.5 bp headroom precisely where
  it's binding (the cover fill). If it lifts fill% or biases the post side favorably, that flows straight
  to net — plausibly the same order as the cover_grace fix (ETH taker 55%→12%). Medium-high.
- **Kill test:** fit depth-imb next-move per Kraken cell, OOS, `assert_no_leakage` on the strictly-pre-
  arrival feature; grade on **fill-adjusted net**, not raw hit-rate. **Kill if** the depth-imb lead is
  lag-0 (no actionable horizon) OR conditioning the maker post-side/timing on it gives no fill-net lift.

### #2 — 128-dim fingerprint tier as a SIZING axis (winner-magnitude), off-box — **highest ceiling, blocked**
- **What:** `fingerprint.py`/`dipole_predictor.py` centroid dual-print, hist AUC **0.72–0.84** winner-vs-
  loser (`STRATEGY_INVENTORY` §8.9; §2.A carry-forward). Archived on Greg's E: drive, not in container.
- **Why it matters and why it's NOT a rescue of direction:** buy/sell are a **perfect −1.0 mirror** in the
  residual space (`DIPOLE_PAPER_S60.md`:108; §8.9) — the tier is **side-agnostic**, so it can never predict
  direction. Its real use is a **magnitude/death signal** = a *sizing* axis: size predicted-winner legs up,
  predicted-death legs down. That is the "winner-side prize" and it's the one OD object that beat the cheap
  0.606 floor.
- **Expected impact [hypothesis]:** high IF it ports (the S61/S62 3-piece ORACLE that this would feed is
  +26/hr, 508/508 winners kept) — but it's been "carry-forward, needs E: drive" since S61 and the causal
  in-container tiers all nulled (S59 micros = clean null, S62 coeff = ~chance mid-band). Rank on ceiling,
  discount hard on the blocked precondition.
- **Kill test:** get E-drive archives + encoder → **onset canary must pass** (reproduce onset micros from
  strictly pre-entry bars, `_canary_fingerprint.py`) → per-mid-band revalidation → wire as a **size
  multiplier**, never a direction call. **Kill if** the onset canary fails (look-ahead) or per-cell AUC
  collapses on current legs like the coeff tier did.

### #3 — E300 death-selector as its own uncorrelated sleeve (OD-family, already in flight)
- **What:** at 300 s realized depth predicts DEATH (gross ≤ −40) at **AUC 0.69–0.77 all 5 coins**
  (`STRATEGY_INVENTORY` §8.4; S66 Binance preview XRP +3.08/DOGE +1.32). Not "dipole" narrowly but OD-family
  and it is the **strongest cross-coin classifier the program has ever produced.**
- **Why here:** it's the OD read that actually generalizes, and it's ~uncorrelated with the lean ride, so it
  fills the majors' ~57% idle as a second sleeve — directly relevant to the capital model.
- **Kill test:** already being run deploy-grade on Kraken tape (S66). It's causal (mid-leg *realized* depth).
  **Kill per-coin** where the Kraken $/hr doesn't clear the shuffle floor per-week.

### #4 — divergence `opp+exh` gate, re-graded on honest fill on a NORMAL-edge tape — **low confidence, one test owed**
- **What:** the S65/S66 "one genuine miss" — divergence as a leg-FILTER (never tried, only as a nulled
  direction classifier). At 0 bp-ideal it lifts eth 0.34→1.60 (z1.9), flips sol-rev +1.98 (z1.8), doge
  →2.34 (`PIECES_TEST_dipole.md` §2b). `info_dipole.divergence` (info_dipole.py:126) is the 2-factor read.
- **Why I rank it LOW despite the headline:** the honest-fill test already killed it on the one window
  (`PIECES_TEST_dipole.md` §2c/§4), and the reason is **structural not window-specific** — opposing-flow
  legs are adverse-selected by construction (S45). The audit's own reconciliation says the 0 bp-ideal lift
  "is a 0 bp-ideal-fill artifact." The SOL sign-flip is the only reason to spend one test.
- **Kill test:** re-pull 30d Kraken tape, ride(rev)+`divergence(opposing&exhausting)` `entry_gate`,
  **dual-graded** (0 bp-ideal AND honest queue-fill), per-week + shuffle null. **Kill (expected)** if the
  reversion edge doesn't beat the fill penalty on a fat-edge window. Do NOT wire on the 0 bp number.

### #5 — QuietFloor at TICK resolution on THIN books (wrong-harness rerun) — cheap, plausibly mis-tested
- **What:** `quiet_floor.py` AR(1) book-depth relaxation gate. Ran weak/neg on Kraken majors as a per-leg
  entry gate (`PIECES_TEST_dipole.md` G4/§2b) — **but the audit itself notes the harness was wrong**: "the
  QuietFloor's real domain is between-trade book-depth churn; this per-leg-entry gating may be the wrong
  harness… gate the *tick-level* signal, not the leg." (§2b). See §3 — its design regime is thin books.
- **Kill test:** wire as a tick-level gate on a THIN-OK small-cap book (mostly-quiet cells = its native
  regime), grade on churn reduction + net. **Kill if** it still adds nothing at tick resolution on thin books.

### Explicitly DEAD — do not re-chase (confirmed nulls, cite these)
- **divergence gate on BTC** — z−1.1, honest-fill worse; btc wants the plain ride (`PIECES_TEST_dipole.md` §3).
- **any dipole gate on XRP** — XRP's +12.5/hr honest-fill edge is the **base ride's fill-friendliness**; the
  gate WRECKS it (49%→11% fill, §2c). Leave XRP un-gated.
- **D1 flow dipole (dMI/dt) standalone** — blind, R²<0.02, opposition is construction-generated (§8.8; paper
  Exp.1). **D2 algebraic dipole on order-flow entropies** — no convex c>0 (§8.8). **D7 entropy-asymmetry/C** —
  units bookkeeping. These are settled dead as market signals.

---

## 2. Is "direction is dead" airtight? (adversarial both ways)

**The claim:** direction ~0.50 at entry AND every mid-leg time (t=0/60/120/300/600), closed 4 ways (coeff,
momentum, fade-flip, dipole agent); depth predicts DEATH (magnitude) not direction (`CLAUDE.md` S63; §7).

**For the claim (it IS airtight, in-scope):**
- It is airtight for **same-venue flow at the swing (600 s) horizon.** The mechanism is understood: the
  market mean-reverts at 600 s (the machine's own contrarian edge), so the same flow that would signal
  direction is already priced into the reversion. `info_dipole.divergence` carries `DEPLOY_VALIDATED=False`
  in code (info_dipole.py:49) — the program's own honest flag that the directional map never validated.
- The **fingerprint tier cannot rescue it** — side-agnostic (−1.0 mirror), correctly excluded for direction.

**Against the claim (two angles NOT fully closed on Kraken):**
- **Direction is NOT dead at the multi-hour horizon.** The fade-N-hour trend WORKS: DOGE-8h p=0.016,
  SOL-4h (`STRATEGY_INVENTORY` §2.C / §8.1). This is already deployed as Family C. So the precise statement
  is "direction is dead at the 600 s swing horizon; it is tradeable at the multi-hour horizon as a
  mean-reversion fade." That refinement matters for the capital model (a slow directional sleeve exists).
- **Cross-venue raw-cov lead-lag as a direction gate — genuinely untested on-box, but likely lag-0.**
  `leadlag.py::detect_leadlag` (D6) with the circular-shift null is the *one* tool that could give an
  **exogenous** direction read (another venue's flow leading Kraken price), which would dodge the
  "same-venue flow already priced" wall. **BUT** prior work found venues **synchronous at lag-0** (S20
  Coinbase↔Bybit cc=0.656 z=580; `DIPOLE_PAPER_S60.md`:192 kill = "lag-0 dominance… venues synchronous"),
  and the paper ranks it A-with-a-deflationary-caveat: any apparent lead may be collector clock skew. My
  read: **worth exactly one test (Binance-spot flow → Kraken price, per coin, circular-shift-nulled), but
  expect lag-0** — in which case it's a synchrony confirmer, not a direction edge.
- **S42 book-depth micro-direction on Kraken — untested, sub-bp.** Real but it's a fill/quoting-horizon
  signal (+0.1 s lead), not a swing-direction bet. Covered as edge #1 above; it does not resurrect
  directional *swing* trading.

**Verdict:** "direction is a dead swing-alpha" is **airtight** for same-venue flow at the trading horizon.
Two micro/exogenous direction angles remain worth one test each (cross-venue lead-lag; S42 book-depth), but
both are **fill/quoting-side, not a revival of directional swing trading** — expect them to help the FILL,
not predict the swing. Don't reopen the direction hunt; do run those two as fill-side probes.

---

## 3. Anything for the ~116 THIN-OK small-cap cells? (where the edge is stronger)

The efficiency gradient (S64: liquid=weak, thin=strong; HYPE $8.8M was NULL) says the alpha is *stronger*
on thin books — but the toolkit's contribution here is **different in kind** from the majors, and this is
where several "dead-on-majors" pieces get a legitimate second life:

1. **The economics invert: THIN-OK pairs are −2 bp MAKER REBATE, not 0 bp** (`STRATEGY_INVENTORY` §5/§8.12:
   select low-liq pairs, $10M+/30d, majors excluded). This is decisive and under-appreciated. On a rebate
   venue the whole calculus shifts from *capture > fee* to *capture + 2 bp > adverse-selection cost*. Two
   consequences for the toolkit: (a) the shuffle floor is **positive** (you're paid to provide liquidity —
   the legal-Kraken version of the S52 Bybit-MM "existence condition"); (b) the divergence gate's
   **adverse-selection fill penalty is partly offset** — being adversely selected still pays the rebate.
   So the piece that's dead on majors (divergence gate, killed by fill) is *worth re-testing on rebate
   cells* where the fill penalty is subsidized. **[hypothesis]** This is the single most important small-cap
   reframe and it is not in any current test plan.

2. **QuietFloor finds its design regime here.** It was weak on majors because liquid books have few "quiet"
   (no-trade) cells — but thin books are **mostly** quiet cells with long relaxation gaps between trades
   (`quiet_floor.py` docstring: the AR(1) relaxation "quiet AND STILL between trades"). The audit tested it
   on the wrong venue (liquid majors). **[hypothesis]** Its churn-cut is most valuable exactly where churn
   through quiet periods is worst = thin books. Cheap to test, and the design intent lines up.

3. **Cell-SELECTION is the real dipole job at 116-cell scale.** You cannot hand-tune 116 cells. The OD
   toolkit offers per-cell selectors that are *built for this*: the **algebraic-convexity cell-selector**
   (D2, rank B — convex c>0 with blind next-cell scoring, `DIPOLE_PAPER_S60.md`:202) to prune to cells with
   genuine two-channel structure; and **coupling_scanner** to find which thin cells are structurally coupled
   to majors (so a BTC/ETH dive → alt-dive flatten works, §4). This turns the dipole from a per-leg gate
   into a **universe-pruning selector** — the right altitude for 116 cells.

4. **Sizing matters LESS, gating/selection MORE.** Thin books are size-capped by liquidity (DOGE fill%
   ceiling 13% at hs=0.43, `PIECES_TEST_execution_kraken.md` §2b), so the conviction/dive-depth SIZE axes
   (which need headroom to size *up*) are largely inert. The value moves to **which cells to be in** and
   **when they're alive**, not how big.

**Net for small caps:** the dipole toolkit's contribution is **cell-selection + a rebate-subsidized gate +
QuietFloor in its native regime**, not the majors' per-leg alpha reads. New gates worth building: an
algebraic-convexity/coupling **cell-selector** to prune 116→tradeable, and a re-test of the divergence gate
**on the rebate economics** where the fill penalty it dies from is subsidized.

---

## 4. THE PIVOTAL QUESTION — does this change the $5k-pool capital-model design?

**Answer: YES on the RISK/ALLOCATION axis; NO on the ALPHA axis.** This split IS the answer.

**NO on alpha:** the capital model must **not** embed any dipole *direction* signal or *divergence entry
gate*. Both are dead (§1 dead-list, §2). The per-cell alpha stays the flow-lean ride + fill fix. Any
allocator that tries to time cells on a dipole direction read is building on the one thing the program
closed four ways.

**YES on risk/allocation — three concrete, disciplined design changes:**

1. **The pool is NOT N independent bandits — it needs a shared-regime DIVE-PROPAGATION kill switch.**
   The anti-resting rotation assumes uncorrelated cells (basket sim: eth-btc 0.42, rest <0.22, Sharpe
   +0.946 > best single). But average correlation is the wrong measure — what breaks a pool is **tail
   co-movement**: do cells DIE together? The coupling_scanner + lead-lag (D6) cross-coin dive-propagation
   proposal (`DIPOLE_PAPER_S60.md`:194, rank A) is *exactly a capital-model input*: if a BTC/ETH dive
   precedes alt dives above the circular-shift null, then during a major dive **every** cell enters its
   death regime simultaneously — the "uncorrelated" assumption fails precisely when it costs the most.
   **Design consequence:** the allocator carries a pool-wide de-risk/flatten overlay keyed on the major-dive
   propagation state, not independent per-cell risk. This is a structural change from a naive round-robin.

2. **A dipole/E300 death-probability SIZE THROTTLE (continuous, not a gate) drives the anti-resting rotation.**
   The E300 death-selector (AUC 0.69–0.77) and the divergence regime read tell you WHEN a cell is in a
   healthy-continuation vs reversal/death regime. For an anti-resting allocator you want idle capital to
   rotate **toward** healthy-regime cells and **away** from about-to-die ones. Greg's own dipole menu names
   the correct framing: **dipole-class as a *size* throttle, not a gate** (`DIPOLE_PAPER_S60.md`:202, D5
   rank B). So the throttle is a continuous size multiplier per cell = healthy→up, death-prob→down. This is
   the OD toolkit's legitimate, validated (E300 is cross-coin real) contribution to allocation.

3. **OD cell-selectors define the eligible universe for the pool (small-cap side).** §3 — convexity/coupling
   selectors prune 116 thin cells to the tradeable subset the allocator rotates across. Without this the
   anti-resting rotation has no principled cell set on the small-cap side.

**The load-bearing precondition on #1:** the dive-propagation coupling **must clear the circular-shift
tautology null** (already in `coupling_scanner.py`) and **beat lag-0 synchrony** — prior work says venues
are synchronous at 1 s, so this may collapse to a *simultaneous*-flatten rule rather than a *precursor*.
Even then it's worth having (a simultaneous pool-wide de-risk on major dives), just weaker. And per Greg's
rule, **a flatten overlay is a gate by another name — it must win on TOTAL net, not tail-trimming**
(`DIPOLE_PAPER_S60.md`:194 kill).

**Bottom line:** design the $5k allocator as a **regime-aware, tail-coupled sizer** — (i) a shared dive-
propagation de-risk switch, (ii) a continuous E300/dipole death-prob size throttle for the rotation, (iii)
OD cell-selection for the small-cap universe — NOT a naive N-cell round-robin, and NOT anything that leans
on dipole direction. That is a meaningful, specific "yes."

---

## 5. Prioritized BUILD/WIRE-NEXT list (with leakage-gate + validation preconditions)

| # | Build | Axis | Leakage gate | Validation precondition | Kill condition |
|---|---|---|---|---|---|
| 1 | **S42 book-depth direction as a fill-side (which-side-to-post) signal** on all 5 Kraken books + a THIN-OK sample | fill/alpha | `assert_no_leakage` on strictly-pre-arrival depth-imb | per-cell OOS; grade **fill-adjusted net** not hit-rate | lag-0 lead OR no fill-net lift |
| 2 | **Dive-propagation / coupling-collapse pool overlay** (coupling_scanner+leadlag; BTC/ETH → alts) | capital risk | circular-shift null (native to coupling_scanner) | must beat lag-0 AND raise **total** pool net | lag-0 simultaneity with no total-net gain |
| 3 | **E300 death-prob as the capital-model SIZE THROTTLE** (continuous multiplier) | capital sizing | E300 is causal (mid-leg realized depth) | per-cell Kraken-tape AUC confirmed; used as multiplier not binary gate | AUC collapses per-cell on Kraken tape |
| 4 | **Algebraic-convexity/coupling CELL-SELECTOR** to prune 116 THIN-OK → tradeable | small-cap universe | blind next-cell scoring (no in-sample fit) | selected cells beat un-selected on OOS net | selector adds no OOS separation |
| 5 | **QuietFloor at tick resolution on THIN-OK books** (native regime rerun) | small-cap gate | fit on training quiet cells only (already causal) | churn reduction + net on thin books | still null at tick res on thin books |
| 6 | **divergence opp+exh gate re-graded on honest fill, NORMAL-edge 30d tape** (SOL-rev de-fragilizer) | alpha (low conf) | `divergence` reads strictly pre-entry (already) | **dual-graded** 0 bp-ideal AND honest queue-fill; per-week+shuffle | reversion edge < adverse-selection fill penalty (expected) |
| 7 | **Fingerprint 128-dim tier as a SIZING axis** (winner-magnitude, NOT direction) | sizing (blocked) | onset canary (`_canary_fingerprint.py`) MUST pass | E-drive archives+encoder; per-mid-band revalidation | onset canary fails OR per-cell AUC collapses like coeff tier |

**Sequencing logic:** #1 and #5 are cheap on-box wins on the FILL/thin-book side (the actual leak / the
strong-edge regime). #2–#4 are the capital-model inputs — build them *as* the allocator, not before it.
#6 is the one alpha test owed to the dipole gate before it's finally shelved. #7 is high-ceiling but
data-blocked — pursue only when the E: drive lands.

---

## Appendix — one-line status of every D-tool vs Kraken

- **D1 flow dipole (dMI/dt):** DEAD standalone (blind, construction-generated). Do not use.
- **D2 algebraic dipole:** DEAD on order-flow entropies as a signal; **alive as a small-cap CELL-SELECTOR** (rank B).
- **D3 centroid dual-projection:** research, confounded (z=+9.6 needs same-period losers); off-box.
- **D4 trading lean dipole:** **LIVE** — the deployed edge (`flip_detector.py`, z 6.8–14.4). The one winner.
- **D5 divergence/exhaustion:** gate DEAD on honest fill (adverse selection); **alive as a SIZE throttle** (rank B, §4).
- **D6 raw-cov lead-lag / coupling_scanner:** research tool → **the capital-model dive-propagation input** (§4). Circular-shift-nulled.
- **D7 entropy-asymmetry/C:** DEAD (units bookkeeping).
- **D8 fingerprint dual-print:** research; the winner-side SIZING prize, off-box (§1 #2).
- **M1 mutual-info-in-null discriminator:** research tool (marks state-dependent coupling) — feeds the D2/D6 cell-selection.
- **QuietFloor:** null on majors (wrong harness); **untested in its native thin-book regime** (§3).
- **S42 book-depth direction:** **the best on-box unrealized piece** — fill-side, dodges the adverse-selection trap (§1 #1).
