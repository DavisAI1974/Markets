# PIECES_TEST_dipole.md — DIPOLE / OD-flow COVERAGE + exploratory-test audit (per Kraken coin)

**Ask (Greg):** "not 100% we haven't missed something." Systematic coverage audit of the DIPOLE / OD-flow
toolkit against the 5 Kraken coins (btc, eth, sol, xrp, doge) + quick provisional tests of the gaps, with
STACKING (tools are complementary, not competing).

**⚠ LOAD-BEARING CAVEAT (every number below):** the 30d edge-bearing Kraken TAPE is ABSENT from the box.
All tests ran on the **~30–42h L2 BOOK window** — ONE low-edge window (S63 §17: ideal-fill net already
≈−2/−1 on eth/btc here; NOT the +8–9/hr tape regime). Every $/hr and every z is **PROVISIONAL, not
sizing-grade.** The book-window baselines even disagree with the 30d-tape verdict on xrp/doge (see below),
which is itself the reminder that one window ≠ the regime. Leakage: the flip detector is causal (passed
`assert_no_leakage` in S63) and `divergence`/`QuietFloor` read **strictly pre-entry** windows only — no
look-ahead added.

Probes (scratchpad, ephemeral): `/tmp/probe_dipole_gates.py`, `/tmp/probe_dipole_stack.py`,
`/tmp/probe_g1_null.py`. Reuse `scripts/_s63_kraken_makerfill.py::load_book_1s`, `odcore/flip_detector.py`,
`odcore/info_dipole.py`, `odcore/quiet_floor.py`.

---

## 1. COVERAGE MATRIX — dipole/OD pieces × Kraken coins

Legend: ✅tried/result · 🔬NEW-tested-this-audit · ❌UNTESTED-gap (testable on-box) · ⛔UNTESTED (needs
off-box data) · —n/a.

| # | Piece (module) | btc | eth | sol | xrp | doge | notes |
|---|---|---|---|---|---|---|---|
| A | **flow-lean zigzag** `flip_detector` (the ride) | ✅fwd PASS | ✅fwd PASS | ✅rev | ✅null(tape) | ✅fade(diff tool) | S63 §10–15, the deployed core |
| B | early-arm `retime_flips` | ✅+ | ✅+ (×2) | ✅hurts | ✅+ | ✅flat(sparse) | S63 §11 |
| C | deep-bail / cover_grace / swingfloor | ✅ | ✅ | ✅ | ❌**never run** | ❌**never run** | makerfill/covergrace/deepstop CELLS = eth,btc,sol ONLY |
| D | **`info_dipole.divergence` as DIRECTION classifier** | ✅null | ✅null | ✅null | ✅null | ✅null | S63 §13 dipole_agent: dir-acc 0.50–0.53, AUC≈0.5 |
| E | **`info_dipole.divergence` as a leg-GATE (take/skip)** | 🔬**null** | 🔬**+lift z1.8** | 🔬**+rescue z1.8** | 🔬null | 🔬**+lift z1.5** | THIS AUDIT — the real gap (never tried as a filter) |
| F | **exhaustion stack (opp+exh, the S36 64% read)** | 🔬null(z−1.1) | 🔬**best z1.9** | 🔬**best z1.8** | 🔬**anti(z−2.0)** | 🔬weak(z0.5) | THIS AUDIT |
| G | **`QuietFloor` book-depth shock-gate** | 🔬neg | 🔬neg | 🔬neg | 🔬+small-n | 🔬+small-n | THIS AUDIT — **NEVER wired on Kraken before** (no mention in any doc/script) |
| H | book-depth imbalance direction (S42) | ❌ | ❌ | ❌ | ❌ | ❌ | never run on Kraken books (S42 was btc_coinbase only) |
| I | `coupling_scanner` / `leadlag` (cross-venue lead-lag) | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ | needs ≥2 time-aligned venue tapes; only Kraken books on-box |
| J | `dipole_predictor` / `dipole_trade` (algebraic chem dipole) | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ | needs win/lose centroids from discovery archives (E-drive, off-box) |
| K | 128-dim OD fingerprint (`fingerprint*`) | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ | heavy tier, needs E-drive encoder+archives (S59 micros-tier = clean null) |

**Biggest genuine gaps surfaced:** row **E/F** (divergence *as a gate* — only ever tried as a direction
classifier, which nulled), row **G** (QuietFloor never touched Kraken), row **C** (xrp/doge never went
through the fill/bail models), row **H** (book-depth direction never on Kraken).

---

## 2. TESTS RUN THIS AUDIT (Kraken book, deployed side, 0bp, per-leg ride to next turn)

### 2a. Single dipole gates (`probe_dipole_gates.py`) — bp/leg (baseline → gate)
G1=take-opposing (aligned_flow<0), G3=exhausting-only, G4=QuietFloor shock-gate.

| coin | dir | base bp/leg | G1 opp | G3 exh | G4 quiet |
|---|---|---|---|---|---|
| eth | fwd | +0.34 | **+1.14** | +0.19 | −0.77 |
| btc | fwd | +0.23 | +0.00 | +0.29 | −0.61 |
| sol | rev | −0.12 | **+0.89** | +0.13 | −0.17 |
| xrp | fwd | +1.88 | +1.91 | +0.74 | +2.05(n77) |
| doge| fwd | +0.16 | **+2.34** | −0.52 | +1.30(n65) |

### 2b. Stacks + LABEL-SHUFFLE NULL (`probe_dipole_stack.py` / `probe_g1_null.py`)
z = does the dipole-selected subset beat a RANDOM same-size subset (real selection vs just "fewer legs").
opp+exh = the canonical S36 2-factor stack; +quiet = 3-stack.

| coin | dir | base bp/leg | **G1 opp** (n, bp, z) | **opp+exh** (n, bp, z) | opp+quiet | opp+exh+quiet |
|---|---|---|---|---|---|---|
| eth | fwd | +0.34 | 216, +1.14, **z+1.8** | 121, +1.60, **z+1.9** | 38, −1.60 | 24, −0.46 |
| btc | fwd | +0.23 | 306, +0.00, z−1.1 | 156, −0.15, z−1.1 | 53, −0.90 | 34, −1.01 |
| sol | rev | −0.12 | 173, +0.89, z+1.2 | 99, **+1.98**, **z+1.8** | 36, +0.90 | 15, +2.74 |
| xrp | fwd | +1.88 | 126, +1.91, z−0.0 | 68, −1.55, **z−2.0** | 17, +2.12 | 10, −5.34 |
| doge| fwd | +0.16 | 137, **+2.34**, z+1.5 | 62, +1.40, z+0.5 | 20, +2.37 | 8, +0.25 |

**Reads (honest, one window):**
- **The divergence-as-a-GATE gap is real and pays on eth/sol/doge**, and it is a *different use* from the
  nulled dipole_agent (which used the same features to PREDICT direction). As a FILTER on the flow-lean
  ride it concentrates the ride onto its profitable legs. **eth 0.34→1.60, sol −0.12→+1.98 (sign flip),
  doge 0.16→2.34.**
- **Stacking helps where Greg said it would:** opp+exh (the S36 2-factor stack) BEATS opp-alone on **eth**
  (1.14→1.60) and **sol** (0.89→1.98) — the complementary stack is the best single per those two coins.
- **But nothing clears z>2 on this one window** — best are z1.8–1.9 (eth, sol). So these are
  "worth a real-tape run," NOT deploy-grade. Per Greg's own README discipline (never size off one window).
- **Clean NULLS (valuable):**
  - **btc: divergence/dipole gate is NULL/negative (z−1.1).** btc does not want the divergence filter —
    consistent with G1=+0.00. btc's edge is the plain ride; leave it un-gated.
  - **xrp: gate null (z−0.0); exhausting is ANTI-signal (z−2.0).** xrp's book-window strength (+1.88) is
    BASELINE, not from any gate — and it contradicts the 30d-tape verdict (xrp null → stand aside). Do NOT
    read xrp as "rescued"; it's a window artifact + the exhaustion piece actively hurts it.
  - **QuietFloor (G/quiet-shock): weak-to-negative on this window** — negative on eth/btc/sol, small-n
    positive on xrp/doge, and as a stack component (opp+quiet, opp+exh+quiet) it collapses to tiny-n and
    adds nothing significant. First time it was ever run on Kraken → **tried, ~null here.** (Caveat: the
    QuietFloor's real domain is between-trade book-depth churn; this per-leg-entry gating may be the wrong
    harness for it. A cleaner test = gate the *tick-level* signal, not the leg.)

### 2c. ⭐ HONEST QUEUE-FILL test (`/tmp/_kraken_dipole_fillgate_probe.py`, cover_grace=300, kr_mk0)
Grades the divergence gate on the REAL fill (queue-honest), via the executor's native `entry_gate`.
This is the decisive lens (the basket-sim XRP lead is a *fill* result, not a 0bp-ideal one).

| coin | cfg | legs | fill% | takerCl% | net/leg | $/hr |
|---|---|---|---|---|---|---|
| **xrp** | **base** | 226 | **49%** | **11%** | **+3.32** | **+12.50** |
| xrp | opp | 52 | 11% | 13% | −8.72 | −7.55 |
| xrp | opp+exh | 28 | 6% | 11% | −15.72 | −7.33 |
| eth | base | 163 | 28% | 26% | −2.89 | −7.84 |
| eth | opp | 62 | 11% | 31% | −3.34 | −3.45 |
| btc | base | 212 | 30% | 36% | −2.94 | −7.45 |
| sol(rev) | base | 150 | 27% | 47% | −4.48 | −8.01 |
| doge | base | 49 | 13% | 43% | +4.24 | +2.88 |
| doge | opp | 11 | 3% | 64% | +37.0(n11) | +5.65 |

**⭐ XRP answer (coordinator's question) — NO, the dipole gate does not turn XRP's fill-friendliness into
an edge; it WRECKS it.** XRP's basket-sim standout reproduces (**base: fill 49% / taker 11% / +3.32 net/leg
/ +12.50 $/hr honest** — the only cleanly-positive honest-fill cell on this window). The divergence `opp`
gate collapses it to fill 11% / net/leg −8.72 / −7.55 $/hr. **XRP's edge is the BASE ride's fill-
friendliness; gating removes it.** Deploy read for XRP = ride the base flow-lean (fwd, no gate).

**⚠ LOAD-BEARING RECONCILIATION — the §2a/b 0bp-ideal opp-gate lift does NOT survive honest fills.** On the
queue-honest fill, the `opp` gate cuts fill% hard on EVERY coin (xrp 49→11, eth 28→11, btc 30→13). Reason
is the S45 lesson: a maker resting into *opposing* taker flow is precisely the **adverse-selected** leg —
it gets filled when flow presses against it. So the opposing-flow legs that looked best at 0bp-ideal (they
had the biggest reversions) are the WORST-filling legs in reality. The apparent $/hr "improvement" from
gating on eth/btc/sol (e.g. eth −7.84→−0.89) is just fewer legs = less total bleed on a negative-edge
window (net/leg stays negative), NOT the gate finding good legs. **The opp-gate lift is a 0bp-ideal-fill
artifact; a real-tape re-run MUST grade on the honest queue-fill.**

---

## 3. BEST STACK PER COIN (the deliverable) + RANKED shortlist for a real-tape run

**Best configuration per coin, this window (all PROVISIONAL, z<2):**

| coin | best dipole config | bp/leg vs base | vs deployed baseline | verdict |
|---|---|---|---|---|
| **eth** | ride + **opp+exh gate** (2-stack) | +0.34 → **+1.60** (z1.9) | deployed = ride+early-arm+bail | **top candidate** |
| **sol** | ride(rev) + **opp+exh gate** (2-stack) | −0.12 → **+1.98** (z1.8) | deployed = rev, fragile | **de-fragilizer candidate** (flips sign) |
| **doge** | ride + **opp gate** (1-piece; exh HURTS) | +0.16 → **+2.34** (z1.5) | deployed = fade-8h (diff tool) | flow-lean+gate is an alt candidate |
| **btc** | **plain ride, NO dipole gate** | gate null (z−1.1) | deployed = ride+early-arm+bail | dipole adds nothing — leave un-gated |
| **xrp** | **plain ride / stand-aside** | gate null; exh anti | deployed = stand-aside | dipole does not rescue xrp |

**RANKED shortlist "dipole pieces worth a real-tape run per coin":** *(every candidate must be graded on
the HONEST queue-fill, not 0bp-ideal — see §2c: the opp-gate lift is ideal-fill-only.)*

1. **`opp+exh` divergence gate on SOL-rev** — *rationale:* the only piece that changes a cell's SIGN at
   0bp-ideal (−0.12 → +1.98 bp/leg, z1.8); SOL is the current fragile reversed cell (S63 fwd z=−1.6).
   *Big caveat:* on the honest fill the opp legs fill worse (S45 adverse selection) — so the real question
   is whether opp+exh's reversion edge beats its fill penalty on a NORMAL-edge tape. *Next test:* re-pull
   30d Kraken tape, ride(rev) + `divergence(opposing & exhausting)` `entry_gate`, graded per-week +
   shuffle-null AND on the honest queue-fill (`_s63_kraken_flipzz.py` + `simulate_swing_maker(fill_model=
   "queue")` with the divergence mask).
2. **`opp+exh` divergence gate on ETH-fwd** — *rationale:* best z (1.9) at 0bp-ideal, 0.34→1.60 bp/leg;
   on the honest fill it at least stops the bleed (net/leg −2.89→−1.57). *Next test:* same dual-graded
   harness; also stack ONTO the deployed early-arm entry (does gate + retime_flips compound?).
3. **book-depth imbalance DIRECTION (S42, row H) on all 5** — never run on Kraken; the books carry it;
   cheap; a FILL-side (which-side-to-post) signal, not an adverse-selected leg filter — so it may dodge
   the §2c fill penalty. *Next test:* fit S42 depth-imbalance next-move on each Kraken book, per-cell OOS.
4. **`opp` gate on DOGE-fwd** — biggest 0bp-ideal lift (0.16→2.34) and would make the flow-lean ride a
   2nd (fade-8h is the deployed doge tool), but honest-fill n collapses to 11 legs (noise). Low priority.

**Explicitly NOT worth re-chasing (nulls confirmed this audit):** divergence gate on **btc** (z−1.1, and
honest-fill worse); **any dipole gate on XRP** (§2c: base ride is the edge, the gate WRECKS the 49%-fill;
0bp-ideal z0, exh anti z−2.0); **QuietFloor** as a per-leg entry gate (weak/neg on eth/btc/sol).

**Pure coverage gap to close (cheap):** add **xrp/doge to the `makerfill`/`covergrace`/`deepstop` CELLS
lists** (currently eth,btc,sol only) — one line each; XRP is the honest-fill standout so it especially
belongs in the fill-model coverage.

**Could-not-test-on-box (need data, flag for Greg):** cross-venue `leadlag`/`coupling_scanner` (row I —
needs a 2nd time-aligned venue tape), algebraic `dipole_predictor` + 128-dim fingerprint (rows J/K —
E-drive discovery archives + encoder). These remain genuine untested surface, but off-container.

---

## 4. Bottom line
The audit found **one real, previously-missed USE** of a piece we already have: `info_dipole.divergence`
had only ever been tried as a *direction classifier* (S63 §13, null) — never as a **leg-filter on the
ride**. As a filter at 0bp-ideal it lifts eth (z1.9), flips sol-rev positive (z1.8), lifts doge (z1.5),
with the canonical **opp+exh stack** the best per-coin config on eth/sol (stacking > single piece, as Greg
predicted). Clean per-cell nulls: **btc** (dipole gate z−1.1), **QuietFloor** (weak/neg on eth/btc/sol).

**But the decisive honest-fill test (§2c) tempers it hard:** the opp-gate's 0bp-ideal lift does NOT survive
the queue-honest fill — the opposing-flow legs are exactly the adverse-selected (worst-filling) legs (S45).
And **XRP — the basket-sim honest-fill standout (+12.50 $/hr, 49% fill) — is WRECKED by any dipole gate;
its edge is the plain base ride, so leave XRP un-gated.**

Nothing clears z>2 on this ~30h low-edge book window; the honest-fill winner (XRP base) is a single-window
result. So the deliverable is: (a) **XRP base flow-lean is the honest-fill standout — do not gate it**;
(b) a ranked **candidate list for a 30d-tape re-run graded on the honest queue-fill** (SOL opp+exh
de-fragilizer, ETH opp+exh quality-gate, S42 book-depth direction) — not a deploy change. Per-cell law and
"never size off one window" both hold.
