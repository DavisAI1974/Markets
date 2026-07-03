# SESSION HANDOFF — S55 (2026-07-03) — the LEG WALKTHROUGH session: 15 tested rounds with Greg
# (his markups = the spec pipeline) → THE ONE VERSION (odcore/platform.py: paper=live=research,
# canaried bit-identical) → both lag halves MEASURED (entry 151→26bp, exit collapse @~28bp) →
# the MIDDLE BAND priced (+$2,900–3,700/day 5-coin projection) → ARMING RULE v1 first pass
# POSITIVE 20/20 cells on 30d deep tape, reversed negative — NOT adopted, full gate = S56 JOB 1

Branch: designated `claude/s55-leg-walkthrough-fnspeg` == canonical `5c5vg9` (synced every push).
Read `KICKOFF_2026-07-04_S56.md` next session. ROUND-BY-ROUND detail (all 15, with numbers):
`S55_WALKTHROUGH_NOTES.md` — the primary artifact of this session; this handoff is the summary.
Renders: `docs/renders/s55/legs/` (regenerate `scripts/_s55_render_legs.py` +
`_s55_walkthrough_probes.py`; PNGs gitignored). PACE RULE (Greg, standing): one round = one
defined test, run, read, THEN next — "we get too far ahead and forget things."

## 1. THE ONE VERSION (Greg: "compile 1 version — live, paper, all sizes and whatever")
`odcore/platform.py` = the single decision layer. Composes by IMPORT (zigzag machinery stays its
own component): flip_detector (WHEN) + swing_maker (WHETHER/HOW) + size_legs (S47 sizing —
ALWAYS on in run_cell) + info_dipole (gate + descriptors). `DEPLOYED` per-cell registry;
`run_cell` (paper + future live); `run_stream` (ANY flip stream — research runs through the
platform's own mechanics, killing the "two versions" drift; sized-trades-missing was the tell).
`scripts/paper_trade.py` -> THIN HARNESS (CLI/ledger/GHA cron unchanged). NO live order code
exists yet (venue-gated S49/S50); live will consume this module. CANARIES ALL PASS: baseline
+0 trades / ledger 25,845 intact / shakeout bit-identical; S49 leakage gate PASS all 5 cells;
every consumer script imports clean.

## 2. EXECUTOR ADDITIONS (all opt-in, defaults bit-identical, canaried)
- `lean_exit=(arm_hi, exit_lo)` — the R8 dipole lean-collapse EXIT in the decision loop.
  Canary finding: INERT at fine scale (0/25,845 — the flip detector's REV=0.1 lean retrace IS
  the lean-collapse exit there); its value is at coarse scales (price-theta exits).
- `fill_mode="taker"` — ONE EXECUTOR ANY SCALE: immediate spread-crossing fills so dump-bin
  research (no book depth) runs through the platform. Equivalence PROVEN: zz150 + bigline
  through the executor reproduce the S54 leg tables exactly (bigline 351/352 legs, diff = the
  final still-open leg).
- `exit_gate` — STRUCTURE-SAYS-OUT (flatten via cover machinery, open nothing): the missing
  long/short/FLAT third state; how bigline breaks / coarse leg-ends speak to the executor.
- ⚠ FOUND: S46-original doc/code mismatch — docstring said non-actionable flips FLATTEN, code
  has always HELD (ride the trend). All gated research since S46 (incl. S52 accum) ran under
  HOLD. Docstring corrected; semantics NOT silently changed; exit_gate is the explicit flatten.
- `--dipole-entry` (S36 divergence read feeds the entry_gate socket) + `--dipole-exit` flags in
  paper_trade; variant runs auto-route to `paper_ledger_sandbox.jsonl` (gitignored).
- R1 descriptors on EVERY ledger row: dive_depth, lean_flip, lean_close, dipole_class, rev_conv,
  lean_exit, mode — the forward ledger accrues per-cell OOS validation of each descriptor.

## 3. THE WALKTHROUGH FINDINGS (rounds 1–9, measured; detail in the notes file)
- R1 "losers look side-flipped": NOT a bug (semantics + P&L verified; flip test loses more;
  matches S54 reversed controls). Real mechanism: on a FAKEOUT the theta-trigger move IS the
  whole ripple -> confirm lands at the extreme on the wrong side BY CONSTRUCTION. Real catch:
  bigline Bybit wins only 21-25% and flipping improves it — alignment entry fires at exhaustion.
- R2 Greg's pencil window (XRP 06-05): his marks = oracle theta60 sequence, 11 legs avg 116bp,
  +1,277bp available; zz150 took 3 legs net −87 (8/11 invisible, 150bp late); zz60 matched all
  11 turns and still lost (2x61bp confirm > legs). LAW: capture = swing − 2·theta − fees.
- R4 descriptor: zz150 reversal-class = only positive class (+30.2/leg, 4/5 coins, XRP outlier)
  but z=1.82 < bar; zz100 INVERTED -> dipole descriptions are SCALE-LOCAL. (Binance spot
  second-venue check still QUEUED.)
- R5 THE LAG: theta-confirm enters 151bp/54min from the true pivot; fine 25bp confirm 26bp/1min
  = 125bp/side saved. Fine confirm equally fast on fakeouts; dipole at that moment lifts P(real)
  0.36->0.48 only. (Hindsight-armed — motivated the arming rule.)
- R6/R7 loss-cap clone: v0/v1 FAIL on re-entry churn (fine exits free-running = fee bleed);
  joint lesson: trade at coarse cadence with fine execution, ARMED at both ends.
- R8 THE INVERTED GRAPH (765 exits): flow CLIMAXES at the exact top (+0.40) then collapses
  through zero in ~60s at ~28bp giveback (vs 151bp theta-exit). The top IS the S45 "can't
  refuse" maker moment. Exit-side saving ~123bp measured.
- R9 dive depth descriptors WIRED (`_s55_dump_legs_dipole.py` + ledger fields); depth->|move|
  does NOT reproduce at coarse scale (sign-inconsistent 3/5) — fine-scale deployed usage stands;
  every (scale, descriptor) pair earns its own validation. Steepness = noise re-confirmed.
- R11 sizing gap (Greg): coarse thread was scoring FLAT while the platform sizes everything.
  Fixed process-wise (sized column standard via platform size_legs); the coarse sizing AXES are
  NOT earned (shuffle control muddies; n too small at coarse cadence).

## 4. WHERE WE SIT (rounds 13–15 — the money picture)
- BIGLINE rerun through the platform (R13): Bybit 30d gate REPRODUCES S54 exactly (bleeds,
  reversed also negative) — verdict unchanged. Coinbase one-window at DEPLOY mechanics (maker
  mk0/tk5 + cover-grace): SOL +4.81 / DOGE +5.71 / XRP +4.40 / ETH +2.55 / BTC −0.11 $/hr @$5k
  = ~2x the parked taker number (front-of-queue optimism caveat; still ONE window; PARKED).
- CADENCE decomposition (same window/executor): fine zigzag 153.4 legs/hr x 1.73bp = +$132/hr
  (front-of-queue; honest capacity ~$19/hr per S50) vs bigline 0.4 x 22.5bp = +$4.81/hr —
  capture% IDENTICAL (36%); the gap is pure cadence. Coarse's real lever = SIZE (legs live
  hours -> 10-50x capital where fine is fill-capped).
- THE MIDDLE BAND (R14, Greg: "we're not picking up the trades I drew"): his pencil scale
  (theta 60-100, 100-175bp, 7-42 legs/day/coin) is where theta-confirm nets −25..−40bp/leg on
  EVERY coin = structurally unharvestable by confirm-theta. At MEASURED fine-confirm costs
  (26+28bp): +37..52bp/leg (th60), +106..122 (th100) -> SOL +$845-1,073/day, 5-coin
  +$2,900-3,700/day @$5k flat. PROJECTION — oracle legs, NO fakeout cost; the arming rule's
  false-arm rate decides what survives (breakeven precision ~13%; naive R5 arming was 36%).
- ARMING RULE v1 (R15, `_s55_armed_zigzag_probe.py::armed_fine_zigzag`): two-stage confirm
  zigzag — extension >= ARM arms (paid during the ride, costless at the turn), first 25bp fine
  reversal confirms (paid at the turn). FIRST PASS: POSITIVE ALL 20 coin×ARM cells on the 30d
  tape, REVERSED negative every row, net/leg tracks the R14 projection (ARM150 +100..+121bp).
  NOT ADOPTED: n thin outside SOL (eth 2 legs); entries fire on the FIRST post-arm dip (often
  mid-leg — partly mean-reversion capture; R4 dipole reversal class = the natural veto); S54
  FULL GATE not run. -> S56 JOB 1.

## 5. INFRA (unchanged from S54 — still broken, still blocks deploy-cell truth)
BTC Coinbase book collector: 155h gap of 196h. Bybit book cron: STILL the single 5.83h window.
Both on the default branch (`claude/new-session-o3vnm` — LEAVE IT, crons live there).
/tmp dies with the container: 30d bins re-pull ~40min (`backfill_bybit.py` x5, commands in
kickoff); books re-materialize from `data/<coin>-book` branches (~2min).

## NEXT (S56) — see `KICKOFF_2026-07-04_S56.md`
1. JOB 1: the S54 FULL GATE on armed_fine_zigzag (shuffle + reversed + per-week splits x 5
   coins, z-stats), + dipole-gated variant (R4 reversal class veto on the post-arm dips), +
   maker fee tiers, + sized column. PASS -> promote to odcore + paper-trade sandbox cell.
2. Binance spot second-venue check for the R4 descriptor (bins via backfill_binance_spot.py).
3. Fix BTC book collector + Bybit book cron (default branch).
4. Greg standing: Bybit MM application (institutional_services@bybit.com; MM3 flips the whole
   fee ledger — the zz150 table goes positive as-is at −1.25bp).
