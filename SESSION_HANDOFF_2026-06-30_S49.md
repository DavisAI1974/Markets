# SESSION HANDOFF — S49 (2026-06-30) — the 2nd-window gate PASSES; conviction sizing wired into the executor (leakage PASS)

Branch: `claude/crypto-liquidity-signals-s49-rqtcfk`. The harness landed on a stale S37-era cut whose only
unique commit (`paper_trade.yml`) was byte-identical to canonical `5c5vg9` — so I `git reset --hard` onto
`5c5vg9` (0 work lost, all S44–S48 history present). Keep `5c5vg9` synced.

Read order: `S49_SECOND_WINDOW_FINDINGS.md` → `S48_TAKER_CUT_FINDINGS.md` → `S47_SIZING_FINDINGS.md` →
CLAUDE.md S49 delta.

## What S49 did

### Job #0 — ran paper_trade, found the data ROLLED FORWARD (the unblock)
`python scripts/paper_trade.py` → **+3463 new trades** (ledger total **22,702**). The alt book branches advanced
to **06-30 17:01Z** — alt book now spans **29.2h** (06-29 11:49 → 06-30 17:01), well past S46/S47's one 11.7h
window (ended 06-29 23:29). The `paper_trade.yml` cron on the default branch has ALSO been auto-firing — the
ledger already carried forward trades to 06-30 11:10 before this session. btc spans an 8-day book (196h). **The
2nd-window gate is open for the first time since S46.**

### Job #1 — 2nd-window CONFIRM — PASS (the milestone)
`scripts/_s49_window_confirm.py` segments the deduped ledger at 06-29 23:29Z: W1 = in-sample, **W2 = fresh/OOS**.
Strategy params (WFLIP=600, REV=0.10, per-cell GRACE, alpha=1.0, roll=200, K) fixed on W1, applied unchanged to
W2 — a genuine out-of-sample test. Result, net/leg W1 → **W2(OOS)**:
| cell | W1 | **W2 OOS** | W2 win% | W2 taker% | W2 sizing lift/leg |
|------|----|-----------|---------|-----------|--------------------|
| sol  | +1.94 | **+1.59** | 63% | 0% | +0.15 |
| doge | +1.42 | **+1.28** | 58% | 7% | +0.82 |
| xrp  | +1.33 | **+1.02** | 61% | 1% | +0.19 |
| eth  | +0.69 | **+0.46** | 52% | 0% | +0.15 |
| btc  | +0.55 | **+0.34** | 59% | 0% | +0.23 |
All three claims reproduce OOS: net-of-fee positive on every cell (sign + ranking preserved); cover-grace holds
taker% near 0; two-factor sizing adds positive lift on all 5. Modest regime softening (W2 < W1), intact edge.

### Job #3 prep — leakage gate PASS, then conviction sizing wired into the executor
`scripts/_s49_conviction_leakage.py` runs `odcore.leakage.assert_no_leakage` on BOTH conviction axes
(clmx_60 quality + size_score) at the flip cells — **PASS on all 5 cells** (120 sampled cells/cell × 3 reps).
The dive_depth pivot is causal (forward ZigZag); precomputed once so the test stays fast and faithful.
Then extracted the two-factor sizing OUT of `paper_trade.py` INTO the executor module (don't fork — one shared
impl): `odcore/swing_maker.py` gains `SwingLeg.size` + `size_legs(legs, quality, size_axis, *, alpha=1.0,
roll=200)` (causal rolling rank+z, `clip(1+α·z, 0.25, 4)`). **Bit-identical** to the old inline pass
(max |Δsize| = 0.0 on a 500-leg synthetic). `paper_trade.py` now calls `size_legs`.

## Files
- `S49_SECOND_WINDOW_FINDINGS.md` (findings), `SESSION_HANDOFF_2026-06-30_S49.md` (this), CLAUDE.md S49 delta.
- `scripts/_s49_window_confirm.py`, `scripts/_s49_conviction_leakage.py` (the two gates).
- `odcore/swing_maker.py` (`SwingLeg.size` + `size_legs`), `scripts/paper_trade.py` (calls `size_legs`).
- `paper_ledger.jsonl` (+3463 forward trades; pre-S49 backup in scratchpad).

## Honesty / caveats (carry forward)
Fill model is optimistic (same both windows → relative reproduction fair, absolute bps an upper bound). The edge
is THIN and **requires maker fee ≤ 0** (a +1 bp maker fee is fatal at 2–4 bps mean swing). Two windows is two,
not many — but the forward ledger auto-accrues so the OOS record keeps growing.

### Job #2 — maker fee ≤ 0 on Coinbase — ANSWERED (the binding deploy gate)
Coinbase Advanced Trade (2026 published schedule): maker fee floor is **0.00% (ZERO), never negative** — only at
the top tier ($250M+/30d) or the fee-upgrade program (≥$500K/mo proof → as low as 0.0% maker). Retail tiers are
0.25–0.60% maker (25–60 bps, fatal). **No maker REBATE on Coinbase**, so S47's rebate column (rescues XRP/ETH)
needs a different, rebate-paying venue. Deployable scenario = **mk0/tk5 (zero maker)** — cover-grace clears it on
all 5 cells OOS, but mk0 on Coinbase requires the top VIP/upgrade tier.

## NEXT (S50)
1. **Pick the deploy venue path** (the binding gate): EITHER (a) qualify for Coinbase's zero-maker tier
   (top VIP / fee-upgrade with ≥$500K/mo proof), OR (b) stand up book collection + execution on a rebate-paying
   venue (then S47's rebate column returns, rescuing XRP/ETH and fattening SOL/BTC). Greg's call.
2. Wire `size_legs` into the per-cell **emit path** — a sizing analogue of `odcore/quiet_registry.py` (per-cell
   alpha/roll + deploy flag) — once a maker ≤ 0 venue is secured.
3. Keep watching the auto-accruing forward ledger (3rd/4th window strengthens the OOS record).
DEAD (don't re-chase): entry-timing retiming, wrong-tail entry-gates, spread/dive as timing.
