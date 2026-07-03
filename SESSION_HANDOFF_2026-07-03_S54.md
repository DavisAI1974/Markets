# SESSION HANDOFF — S54 (2026-07-03) — THE BIG LINE built (Greg's trendline ride/break, 3 spec
# rounds from his chart markups) → +$1-4/hr on 4/5 Coinbase book windows → then the deep-history
# OOS gate (30d x 5 coins, Bybit dumps) FAILS it on that venue; coarse dipole side-picker DEAD at
# all scales; strategy converged to: dipole bell + can't-refuse maker quote + ride + dive exit —
# every piece now has a measured status

Branch: designated `claude/crypto-liquidity-signals-s54-d9pwbp` == canonical `5c5vg9` (synced
every push). Read `KICKOFF_2026-07-04_S55.md` next session. Renders: `docs/renders/s54/bigline/`
(regenerate via `_s54_render_bigline.py`; PNGs gitignored). All S53-and-earlier standing rules
carry (NO GATES scoring, sandbox-first, never tune off one window — this session is why).

## 1. GREG'S SPEC (built up over 5 chart markups — the session WAS this conversation)
The S53 zoom-out became a strategy: **the BIG LINE** — trend support line touching successive
confirmed pivot lows (long; mirror for shorts on the way down), ride while price respects it,
exit on the break. His refinements, in order, each measured:
- **Trend alignment** ("we have it backwards"): line below ONLY in an uptrend = higher highs AND
  higher lows; mirror for down. Killed the bear-bounce longs (BTC h14 render).
- **Adaptive scale** ("when it gets choppier, scale the lines down"): theta = 0.25 x trailing 4h
  range, re-measured CONTINUOUSLY (in-ride too) so plateaus ratchet the line instead of trailing
  the entry-era chord. Bounce-back-confirmed pivots ARE the chop filter ("you don't want it
  hitting every little peak or valley — some bounce back first").
- **Cadence gist** (his black-line markups): ~his hand-drawn legs = the theta~60-100bp zigzag
  oracle stream (~15 legs/day on SOL, med ~150-180bp). His pencil over 15h SOL ~ +1,400bp; the
  engine took +37bp — capture fraction is THE metric (his "different algebra": $/hr = waves/day
  x wave size x CAPTURE - fees; coin choice = opportunity terms, engine work = capture).
- **Multi-role zigzag**: chop meter + veto ("don't fire, it's just chop"), on entries AND exits,
  scale-aware (only veto when measured chop < fee-worthy scale).
- **The exit** = the S40 dipole turn anatomy (his jpg) + "a little bounce back" (x_profit_loss,
  vol-calibrated, data-picked). **Maker posture**: "we can still be makers — dipole tells us when
  to jump in front of everyone and give them something they can't refuse" (= S45 maker-at-the-
  turn + price-improvement at the 2x-volume climax, at coarse cadence). Longer trades => lag
  tolerance is loose (a 10-20bp hair on 150-500bp legs).
- Fun guess on record (Greg): **BTC wins** (bigger climbs/slides). Untestable yet — BTC book is
  80% collection gap (155h of 196.3h flat-filled; see §5).

## 2. WHAT WAS BUILT (all new files; zigzag/one-shot/accum untouched per Greg)
- `odcore/swing_bigline.py`: `run_bigline` (fixed theta, align param), `run_bigline_adaptive`
  (continuous adaptive scale + optional lean fast-confirm x_frac/require_flip), `ride_from_entries`
  (zigzag-entry + ratcheting line exit — built for an architecture Greg later superseded; kept),
  leakage adapters. ALL leakage gates PASS.
- `scripts/_s54_bigline_probe.py`: oracle sweep (60/100/150/250bp) + bigline grid + adaptive grid
  + zigzag-flip baseline, taker-taker fills (no queue => Q1 moot), shuffle/reversed controls,
  splits, gap accounting. `scripts/_s54_render_bigline.py`: ride renders.
- `scripts/_s54_flip_threshold.py`: the BELL diagnostic — dipole flip + x_PL bounce, bracket-
  scored, detector-scale sweep (lean W 60s..2h, REV 0.25/0.3/0.5), pooled rows.
- `scripts/_s54_zz_entry_bigline_exit.py`: hybrid harness (parked, superseded by Greg's v3).
- `scripts/_s54_backfill_sweep.py`: bell + bigline multi-week gate on backfill bins.
- `backfill_binance_spot.py` NEW: Binance Vision SPOT daily aggTrades -> 1-sec bins (us/ms
  timestamp handling); canary PASS. Bybit dumps (`backfill_bybit.py`) VERIFIED working
  in-container: 30d x 5 coins pulled in ~40min (public.bybit.com CDN not geo-blocked).

## 3. RESULTS — the one-window highs, then the OOS gate
**Oracle (coarse theta, one book window/cell):** SOL theta100 ~20 sw/day med 175bp = $1,822/day
@$5k; DOGE $894; XRP $614; ETH $703; BTC $60 (gap-riddled). The pool is deep; fees are 2-6%.
**Adaptive aligned big line (f0.25/w4h, taker-taker, ONE window):** DOGE +$3.95/hr, SOL +2.39,
XRP +2.35, ETH +1.18, BTC -0.56; reversed AND shuffle negative on all 5; DOGE+ETH positive both
halves. Fixed-theta version ~dead; f0.15 rows dead (fee floor).
**THE GATE (30d x 5 coins Bybit perp dumps, 3 coins reported before session end):** adaptive big
line **NEGATIVE on all coins, all 12 coin-weeks** (SOL -2.63/hr, DOGE -3.00, XRP -4.61) and
~= its shuffle control => on that tape it behaves like a random-walk trader paying giveback.
**The Coinbase one-window result did NOT reproduce on Bybit deep history.**
**THE BELL (coarse dipole flip as side-picker):** pooled books gradient P(real) 0.50->0.59 toward
coarse — then the 30d n killed it: P ~= 0.50 at every cadence 43/day -> 2/day; the 2h-lean cell
0.54-0.57 at z<=2, net/leg negative. **Bare coarse dipole flip picks no side. DEAD standalone.**
(x_PL bounce never rescued any scale; at coarse scales k=0 beat k>0.)

## 4. OPEN VERDICTS (running at session close — S55 reads these FIRST)
- `/tmp/sweep5.log`: full 5-coin Bybit sweep (adds BTC/ETH weeks). Partial already conclusive.
- Binance SPOT 30d x 5 pulls + sweep (spot-vs-perp = the venue-vs-window-luck decider for the
  Coinbase result). If spot ALSO fails => big line as parameterized was window luck => redesign
  with Greg (capture-fraction ladder). If spot passes => Coinbase-cell edge plausible => get
  Coinbase history (REST grind via cron — no bulk dumps exist) + let books accrue.
- NOTE: /tmp does not survive the container. Bins are re-pullable in ~40min (scripts + exact
  commands in kickoff). Consider gz-pushing bins to data branches (gz ~15-30MB each, under cap).

## 5. INFRASTRUCTURE FINDINGS
- **BTC Coinbase book collector: BROKEN WINDOW** — 155.4h of the 196.3h file is one flat-filled
  gap. ETH book has 23.4h of gaps. Diagnose the collector cron (default branch) before trusting
  any BTC-cell number. Bybit book cron STILL stuck at the same single 5.83h window (S52-S54).
- Coinbase spot backfill = REST-paginated (1k trades/call) — no bulk path; multi-day pulls need
  a long-running cron, not a session.
- Fill-model reality: taker-taker throughout => Q1 honest-queue problem does not apply to any
  S54 number. The "can't refuse" maker quote (S45 at coarse turns) is UNMEASURED — needs the
  corrected price-eligible fill model at measured climax moments (books have the data).

## 6. DEAD / PARKED / ALIVE (falsification ledger)
DEAD: bare coarse dipole side-picker (all scales, n in thousands); pure dive+bounce flip engine
(rung 1 — killed by diagnostic before build); fixed-theta big line; x_PL bounce as rescue at any
lean scale; bigline-on-bybit-perp as parameterized.
PARKED: Coinbase adaptive big line +$1-4/hr (awaiting spot verdict + more Coinbase windows);
`ride_from_entries` hybrid; S53 SOL accum candidate (unchanged status).
ALIVE/UNTESTED: dive as EXIT timing (bracket test measured entries only — exit quality is a
different, untested question); maker-at-the-coarse-turn fills at climaxes; two-scale machine
(coarse side-picker x fine turn-timing); capture-fraction ladder vs Greg's pencil.

## NEXT (S55) — see `KICKOFF_2026-07-04_S55.md`
1. Read the spot + full-bybit verdicts (re-pull bins if container recycled). Decide: redesign vs
   Coinbase-history grind.
2. Walkthrough loop with Greg on renders (his markups are the spec pipeline — keep sending).
3. Dive-as-EXIT measurement on whichever engine survives.
4. Fix BTC book collector + Bybit book cron (both broken, both block deploy-cell truth).
5. Greg standing: Bybit MM application.
