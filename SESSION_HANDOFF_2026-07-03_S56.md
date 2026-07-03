# SESSION HANDOFF — S56 (2026-07-03) — JOB 1 executed as a live walkthrough loop → every ARMED
# confirm variant (v1/v2/v2+dipole/v3-ARM) KILLED by its own gate → THE MODEL = the DEPLOYED
# fine zigzag at NATURAL CADENCE (ARM0) on the Bybit venue: full S54 gate PASS all 5 coins
# (z 6.8–14.4, 20/20 coin-weeks, reversed below the shuffle floor) → PROMOTED to platform
# SANDBOX cells (sol/eth bybit @ true MM3) → queue-honest capacity measured (+$3–37 SOL,
# +$12–47 ETH per hr @$5k — MM application = the existence condition, re-confirmed on books)

Branch: designated `claude/crypto-liquidity-signals-s56-risp3w` == canonical `5c5vg9` (synced
every push). Read `KICKOFF_2026-07-05_S57.md` next session. Walkthrough sheets:
`docs/renders/s56/legs/` (regenerate `scripts/_s56_render_worst.py`; PNGs gitignored).
Greg's loop rule (standing): print the 10 worst losers + 10 smallest winners EVERY round.

## 1. THE ARMING-RULE AUTOPSY (JOB 1 — each variant killed by a measured mechanism)
- v1 (S55, pivot-anchored, one-sided watch): the S55 20/20 was real but the machine IDLES —
  instrumented: 98% of the month stranded in a stale leg (max 289h), loss NOT bounded (max
  adverse ride 1,905bp — the "bounded by construction" claim was false), 3.9 legs/day vs
  oracle 28–60 at scale. Cadence starvation, not fees, kept $/hr down (fee-tier re-pricing
  moved the ceiling ~$3→$5.5/hr total; zero fees ≈ $6).
- v2 (extreme-anchored + trailing-ARM fallback): cadence FIXED (129 legs/day) but gross/leg
  −3bp — the first 25bp price dip after arming is a COIN FLIP mid-trend (47% win); the
  fallback structurally sells troughs (plain-zigzag θ-giveback + mean reversion). Executor
  P&L verified bit-exact vs independent hand computation; toy path proved side semantics
  correct; "losers look swapped" = drift (P&L tracks each coin's 30d drift sign) + trough
  fallbacks, NOT a sign bug.
- v2 + R4 dipole veto (tight/loose): gross lifted (−3 → 0..+5) with cadence kept (the
  fallback floor means the gate CAN'T remove trades, only re-price confirms) — but thin, and
  the ARM40 tight-gate pass proved a KNIFE-EDGE: the ARM30/35/45 response curve is dead
  (z ~ 0). BTC 0-legs anomaly = mode-0 bootstrap deadlock (diagnosed, fix noted, moot).
- v3-ARM (Greg: "use the enter and exit from zig zag"): deployed flip detector does ALL
  enters/exits, ARM = chop filter. ARM40 passed (z 8.0/6.3/3.1 sol/eth/doge, 20/20 weeks)
  but the curve around it is dead → the ARM FILTER FAMILY fails as a family.
- ARM0 (Greg: "we need to be doing arm 0") = the deployed machine at natural cadence:
  **FULL GATE PASS ALL 5 COINS** — z = 9.0/11.3/13.0/14.4/6.8 (sol/eth/btc/doge/xrp),
  20/20 coin-weeks positive, forward > shuffle on all 5, reversed BELOW the floor on all 5.

## 2. THE SHUFFLE FLOOR (load-bearing concept, Greg walked through it)
At MM3-class fees a shuffled (structure-free) tape still earns ~$90–106/hr/coin — the
detector still rings ~127k times/30d and every round trip collects the rebate. That is the
VOLUME PAYCHECK, not trading skill; reversed and coin-flip machines collect it too. The fair
zero-line is the floor, not $0: the model's DIRECTION PREMIUM above the floor is +$7–17/hr
per coin at z 6.8–14.4. (~$99 of SOL's headline +$112/hr bins ceiling is floor; +$13 is edge.)

## 3. FEE SCORING STANDARD (Greg S56): the 10%-TAKER BLEND
Measured taker share: Coinbase forward ledger 0–5%; Bybit 12.6h books at deployed mechanics
0.0–0.1% (cover-grace is what does it; grace=0 → 8–17%). Greg's worst case = 10% taker on
every side: taker11 (11.0, no-MM floor) / std_bl (+4.70) / mm3_bl (−1.15) rt/leg. Executor
runs once at taker; tiers are linear per-leg arithmetic (`TIERS` + `tier_row` in
`_s56_armed_gate.py`). On BOOKS the platform uses TRUE fees — the blend is bins-only.

## 4. PROMOTION (the current model, in code)
- `odcore/platform.py`: `venue` = first-class CellConfig dimension (cell = coin_venue,
  path = /tmp/<coin>_<venue>_book.jsonl.gz); NEW `SANDBOX` registry = sol/eth bybit @ TRUE
  MM3 fees (−1.25/5.5, grace 300), gate record + deploy conditions documented in the
  registry comment.
- `scripts/paper_trade.py`: runs SANDBOX cells every run → `paper_ledger_sandbox.jsonl`
  (S53 rule; baseline forward ledger untouched). Seeded: sol_bybit 1,593 + eth_bybit 2,142
  legs @ 0% taker, win 93/88% (rebate-inflated), flat +6,776/+6,194bp on the 12.6h books.
- CANARY PASS: baseline bit-identical (+0 trades, ledger 25,845, exact shakeout).
- ⚠ Bybit book cron IS accruing (12.6h now vs the single 5.83h window since S52).

## 5. QUEUE-HONEST CAPACITY (`scripts/_s56_bybit_capacity.py` — the honest number)
Real books, deployed executor, S52 price-eligible flow caps, S51 v1/v2 truth bracket,
$5k flat: **sol_bybit +$3.05 (v2) … +$37.19 (v1) /hr; eth_bybit +$12.22 … +$46.73/hr**;
ceilings v2 +$52/+$25. net/leg +4.25/+2.89bp, taker 0.0–0.1%. Binding constraint = FILL
SIZE (median fillable $137–169/leg even front-of-queue — $5k mostly does not fill), not the
edge. std +2bp fees NEGATIVE everywhere (−$7..−$116/hr) → **the MM application is the
existence condition, re-confirmed on real books.** One 12.6h window — re-measure as books
accrue.

## 6. WALKTHROUGH SHEETS (the every-round loop)
- Worst-10 (every machine, both directions at ARM0): FADE-THE-FREIGHT-TRAIN — counter-entries
  into violent spikes/flushes, 36s–2min, −89..−132bp, dipole class at pivot `continue`
  rc=0.00 on 10/10. At ARM0 the tail is small (~1,100bp of a huge book) — candidate
  freight-train veto (continue-class + extreme velocity) = SANDBOX VARIANT ONLY, NO-GATES
  judged (S53 law held every time it was tested today).
- Smallest winners: seconds-long noise round trips, gross ≈ −1.1bp, rebate-only economics —
  the legs most exposed to queue reality; the books cells resolve them (0% taker measured).

## 7. DEAD (S56 adds)
v1 arming (stranded states, unbounded adverse); v2 bare price-dip confirm (mid-trend coin
flip); trading fallback (sells troughs — risk control must FLAT, not flip); the ARM chop
filter as a family (knife-edge at one grid point, curve dead); citing rebate-floor $/hr as
edge (shuffle collects it); fee-tier re-pricing as a cadence rescue.

## NEXT (S57)
1. GREG: the Bybit MM application (institutional_services@bybit.com) — now carries a
   gate-passed model + queue-honest brackets behind it. THE existence condition.
2. Sandbox ledger accrual (cron runs it now) + queue-honest re-measure as the bybit books
   grow; extend bybit book collectors to doge/xrp/btc (cron currently sol/eth only).
3. Freight-train veto as a sandbox variant (NO-GATES scoring).
4. S56 JOB 2 (never run): Binance spot R4 descriptor second-venue check.
5. S56 JOB 3 (still broken): BTC Coinbase collector 155h gap.
