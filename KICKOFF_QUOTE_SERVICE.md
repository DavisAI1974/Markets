# KICKOFF — Quote Service (markets-watch market-making) — written 2026-06-08 (S26)

## OPERATING CONTEXT (before you read)
- Your **global `~/.claude/CLAUDE.md` (htmx/CRO) auto-loads** — use it for all frontend work (FastAPI returns HTML fragments, not JSON).
- This branch has **no project `CLAUDE.md`**, and you do **NOT** need to read the OD-research master `CLAUDE (5).md` (on `claude/beautiful-shaw-040328`; ~2,749 lines, mostly physics — skip it).
- The operating discipline you DO need is in the handoffs + `QUOTE_SERVICE_PLAN.md §4F`: **no synthetic data**; **Result Discipline** (every claim needs a falsifiable test — here, forward-paper validation); **Adaptive-Markets "cell strength" framing** (not "structural signal yes/no"); and the **SETTLED list — do not relitigate** (VPIN mults, sigma cuts, Gate I conventions, VOL_MULT bounds, notional, registry-driven playbooks, no math jargon in user strings).

WORKING BRANCH: `claude/continue-phase-2-pipeline-UFiGY` (the markets-watch platform — this branch).
The OD layer it fuses with lives on `claude/beautiful-shaw-040328` (`odcore/` + `backend/odcore_store.py`).

## READ FIRST, in order
1. **`QUOTE_SERVICE_PLAN.md`** (repo root) — THE canonical plan. Follow it to a T. Has the reusable-asset inventory (both code parts, exact file paths — so you don't re-derive), the recommended architecture, a 6-phase build sequence (each verified via forward paper), constraints, and 6 open questions.
2. **`HANDOFF_TO_NEXT_AGENT.md`** — the top/latest section = the platform pickup brief (Pass-14: framing, what's built, settled decisions).
3. **`HANDOFF_PHASE1_5_RESULTS.md`** — the latest Pass section = authoritative empirical findings.
4. **`LAUNCH_PLAYBOOK.md`** — AWS deploy at §1.5. **§1.5 BLOCKS forward-paper data — do it first** (token, VAPID keys, requirements, systemd unit).
5. OD context (branch `claude/beautiful-shaw-040328`): `STATUS_S26_async.md`, `odcore/` (leadlag / coupling_scanner / dipole_predictor / validation), `backend/odcore_store.py` (`CouplingStore` + the `/api/coupling_matrix`, `/api/leadlag`, `/api/dipole_signals`, `/api/strength`, `/api/decoupling` endpoints).

## ANSWER FIRST — the plan's 6 open questions (Greg)
1. Maker-rebate access on Kraken/Coinbase? (the economic thesis rides on it)
2. Paper fee assumption: keep 25 bps taker (mm cells will paper-lose) or switch to ~5 bps/leg?
3. Quote on Bybit-perp too, or CB+KR spot only?
4. Decoupling pull threshold: any severity, or only "severe"?
5. Live execution: your machine w/ personal keys (friend-group model) vs central AWS?
6. Dipole-integration bar: gate on net-of-cost proven in `odcore/validation.py` walk-forward?

## FIRST BUILD STEPS (from the plan)
- **LAUNCH_PLAYBOOK §1.5** first (unblocks forward-paper data).
- **Phase 0:** merge `CouplingStore` + the `odcore/` package from `claude/beautiful-shaw-040328` into this branch; register the 5 OD endpoints; ensure `odcore/` on `sys.path`. Degrades gracefully if `realbins/` absent.
- **Phase 1:** new `backend/quote_gate.py` (pure `evaluate(...) -> QuoteDecision`) + `tests/test_quote_gate.py`. Then Phase 2 (wire into `poll_all()` + monitor `current_state_for()` accessors), Phase 3 (`quote_state_change` SSE), Phase 4 (htmx `QuoteStatus` fragment + PracticeFeed MM tab), Phase 5 (calibrate/validate net-of-cost).

## CORE DESIGN — don't drift
- **`mm_passive` IS the edge:** maker-rebate spread capture on `EQUILIBRIUM_TWO_SIDED` (resting bid/ask, spread minus 2 fee legs). The 4 cells already exist in `backend/forward_paper.py` — EXTEND, don't rewrite.
- **OD signals = GATES + spread adjusters, NOT entry signals.** 1s resolution = venues synchronous (cc=0.656 z=580) → no sub-bar lead edge. OD directional signals lose net-of-cost vs ~3 bps. The 128-dim dipole (z=+9.6) is a classifier input only until net-of-cost is proven.
- **Frontend = htmx fragments** (FastAPI returns HTML, not JSON); extend `PracticeFeed.jsx`, no new page.
- Honor the SETTLED list (plan §4F) — do not relitigate (VPIN mults, sigma cuts, Gate I, VOL_MULT bounds, notional, "cell strength" framing, no synthetic data).

## CONTEXT POINTERS
- Master: `CLAUDE (5).md` (S26 — has "Quote Service" + "Other Coins" sections) on the OD branch.
- The OD coin work (separate workstream) is mid-run: btc/eth 16k 128-dim coeff-gen, then doge/link/xrp, then 44h chunks (see `STATUS_S26_async.md`).
