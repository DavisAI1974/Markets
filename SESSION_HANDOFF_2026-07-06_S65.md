# SESSION HANDOFF — S65 (2026-07-06) — Job 1 basket sim (front-of-line, sim=live code) + the enticing close + the fill/churn autopsy

Branch reconciled to canonical at open (designated `davisai-s65-kickoff-ia18ve` was cut from an S59-era
parent — reset --hard to the S64 tip). **WE ARE ON KRAKEN** (Greg); Coinbase is parked/legacy.
Read `STRATEGY_INVENTORY.md` FIRST (updated live all session, esp. §2.A + the S65 blocks + §8 PIECES).

## THE PROCESS FIXES (Greg, load-bearing — "things not matching")
1. **SIM = LIVE CODE + NEW PIECES** (new standing rule, top of STRATEGY_INVENTORY): every sim/probe DECIDES
   through the live code (`platform.run_stream`/`run_kraken_cell` → `swing_maker`), never a reimplementation.
   New mechanics go INTO `odcore/` first, then the sim uses them. Restates the no-rewrite-of-existing-files rule.
2. **MAKER NUMBERS ARE FRONT-OF-LINE** (`fill_model="front"` — the deployed S46 premise). The S65 basket sim
   first used `queue`/back-of-line and the numbers didn't match live — that mismatch is exactly the failure.
3. **NO AGGREGATE-AS-SUM.** $5k is the TOTAL, not per-cell; the sim's "aggregate @ $Nk" line is wrong. Per-coin
   $/hr is the edge and DOESN'T change; the aggregate gain comes from ALLOCATING the $5k (the capital strategy).

## WHAT WAS BUILT / FOUND (in order)
- **Authoritative per-coin config documented** (Greg's anti-amnesia concern): STRATEGY_INVENTORY §2.A, reconciled
  from code + docs. The peak model = deployed fine flow-lean zigzag at NATURAL CADENCE (ARM0, no arming — S55/56
  armed variants killed). Flagged the code-vs-deploy nuances (SOL eps in scripts is analysis-only; early-arm window-fragile).
- **§8 PIECES catalog** — exhaustive S19→S65 inventory of every piece ever built/proposed (dead included), 14
  categories + the "may have missed" reservoirs. (Miner agent.)
- **Job 1: `scripts/basket_sim_kraken.py`** — multi-sleeve basket sim through the LIVE `run_kraken_cell`. Loads
  Kraken books, composes the per-coin stack, portfolio correlation + Sharpe. All 5 cells positive at front-of-line:
  eth +6.77 / btc +6.66 / sol +6.01 / doge +6.59 / xrp +14.02 $/hr @ $5k; correlations ~0; portfolio Sharpe +0.810
  > best single +0.629. (⚠ one 30h LOW-EDGE book window — provisional; deliverable is the STRUCTURE.)
- **ENTICING CLOSE** — new opt-in `swing_maker.close_improve_bps` (threaded through `run_stream`/`run_kraken_cell`;
  default 0 = bit-identical, canaried). Post a price-improved cover conceding ~0.5bp to jump to FRONT of line →
  maker close instead of taker cross. At back-of-line it adds +4–7/hr (converts forced-taker 26–47%→2–7%); at
  front-of-line +0.0 (nothing to convert — front already fills maker). It's the mechanism that SECURES front-of-line.
- **Winner/loser + fill autopsy:** the majors' apparent "bleed" was the back-of-line assumption. Front-of-line flips
  every cell positive, forced-taker→0. NEW bleed = SIGNAL-LOSS (wrong-direction swings, win 52–57%, W/L 1.05–1.40);
  the fill bleed is FIXED; deep-bail never fired (calm window). Cheap bleed (fill) done; residual is the direction cost.
- **The 2.5× leg explosion at front-of-line is CHURN, not edge** (`_kraken_newlegs.py`/`_kraken_legbleed.py`): money
  is ONLY in the big swings (eth ≥20bp = 23 legs = 97% of $/hr; net/leg +17bp); mid legs [2,20)bp have winners ≈
  losers (±25/hr gross → +6.77 net). Bleed = quick-reversal whipsaws (87–96% of loss).
- **Per-coin REV sweep** (`_kraken_revsweep.py`) — Greg: "don't cut positive churn, only negative." Max-$/hr REV:
  **eth/btc/sol stay 0.10** (fine churn is net-POSITIVE — coarsening loses money); **DOGE→0.30 and XRP→0.13 ADOPTED**
  (Greg: cut churn where NEGATIVE): doge +6.59→+9.13 (win 54→63%), xrp +14.02→+16.05, portfolio Sharpe +0.810→+0.946.
  Still book-provisional for LIVE CAPITAL (one window) but employed in the registry as the current book-best.
- **Direction RE-ADJUDICATION employed** (execution agent; `_kraken_readjudicate.py`): FWD wins ALL 5 on the book —
  SOL +6.51 > rev +2.17 (contradicts deployed reversed), XRP +14.02 (was stand-aside), DOGE +5.46 fwd flow-lean.
  Employed in the KRAKEN registry (SOL/XRP/DOGE fwd), FLAGGED book-provisional — the 30d-tape deploy map stands live.
- **sim=live wiring:** `platform.py` gained the `KRAKEN` registry + `run_kraken_cell` + `kraken_flips`; CellConfig
  gained `side/rev/eps/bail/improve` (defaults preserve the legacy Coinbase `DEPLOYED` path — verified unchanged).

## THE AGENTS (3 background, all landed)
- **Execution agent:** XRP has a real solution "stand aside" missed (fwd + cover_grace = +13.5); FWD is right sign
  for all 5 on the book (re-adjudicate, not overturn); cover_grace is the fill fix (untested XRP/SOL/DOGE); early-arm
  window-fragile; DOGE blocker is fill% not signal. Ranked: XRP fwd+grace, **E300 on Kraken for XRP/DOGE**, SOL fwd-vs-rev,
  bigline on all 5, QuietFloor/divergence gate on Kraken. Report: `PIECES_TEST_execution_kraken.md`.
- **Dipole agent:** the one miss = divergence as a leg-FILTER (never tried) — but it WRECKS honest fill% (selects the
  adverse-selected worst-filling legs, S45); XRP wants the plain un-gated ride; QuietFloor weak on Kraken; S42
  book-depth DIRECTION never run on Kraken. Report: `PIECES_TEST_dipole.md`.

## NEXT (S66)
1. **⭐ CAPITAL STRATEGY (Greg's next):** ONE $5k pool ALLOCATED across the (5) uncorrelated cells with an
   ANTI-RESTING rotation so it's NEVER idle (majors ~57% idle, sol 40%). Per-coin $/hr is FIXED (the edge) — the
   aggregate gain is the allocation. Replace the bogus $25k aggregate with the honest $5k-pool number.
2. **Confirm the book-provisional bits on a 30d tape / Tardis:** direction re-adjudication (SOL fwd, XRP, DOGE) +
   the REV pick (DOGE 0.30, XRP 0.13). The 30d Kraken tape is NOT on-box (re-pull = `backfill_kraken_trades.py`, hours).
3. **Replace the paper/live path (legacy Coinbase DEPLOYED) with the KRAKEN registry** — wire a live Kraken book
   loader into a `run_cell`-style path + repoint the paper cron. We are on Kraken; stop accruing the parked Coinbase ledger.
4. Agent-ranked probes: E300 on Kraken tape for XRP/DOGE; bigline on all 5; S42 book-depth direction on Kraken.
5. Small-cap eligible basket (APE/RE/XDC/SHX/AIOZ/ARPA @ −2bp) — folds into the capital/anti-resting layer.

## Files (S65, all kraken-tagged per Greg): basket_sim_kraken.py, analyze_basket_kraken.py, _kraken_enticing.py,
_kraken_newlegs.py, _kraken_legbleed.py, _kraken_readjudicate.py, _kraken_revsweep.py; PIECES_TEST_{execution,dipole}_kraken.md.
odcore: swing_maker.close_improve_bps; platform.KRAKEN/run_kraken_cell/kraken_flips + CellConfig side/rev/eps/bail/improve.
Data: Kraken books in /tmp/kbook (30h overlap; re-materialize `git show origin/data/<coin>-kraken-book:<coin>_kraken_book.jsonl.gz | gunzip`).
