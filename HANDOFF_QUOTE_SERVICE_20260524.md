# Handoff — Coin Exchange / Quote Service Workstream (2026-05-24, evening)

**Different project from Markets RT.** This is the off-chain RFQ → on-chain settlement market-maker the user wants to build using OD + dipole as the edge. Lives at `E:\Markets\` for code-locality with the dipole / bin loader infrastructure but is its own product.

## TL;DR

15-minute-old project. We chose the **off-chain RFQ + on-chain settlement** architecture (Option C). Mapped the quote service file layout end-to-end. Read the actual dipole code in [dipole_coupling.py](E:\Markets\dipole_coupling.py) and the [paper](https://davisai.ai/dipole/). Wrote and ran a v1 calibration script on 2 days of BTC Bybit perp bins — produced real adverse-move-by-validity-horizon floors but the market-only dipole proxy didn't discriminate states. User said "absolutely get more data." Kicked off 90-day backfills; 4 of 8 are running cleanly, 2 are blocked by US-IP geo-block (known), 2 are broken (Coinbase script bug — attempted to delegate to debugger agent, the agent crashed mid-run). Ended session with revenue projection: base case $570k Y1 / $3.6M Y2 / $5.5M Y3 net.

## Recommended new-chat opener

> Continue quote-service handoff. First action: check backfill status — Kraken BTC/ETH and Binance BTCUSDT/ETHUSDT 90-day backfills were running in background; need to verify they finished and split into the JSONL archive with `backfill_split_to_history.py`. Then re-run `dipole_state_forward_returns.py` against the now-90-day cross-venue dataset.

## The architectural decision

User asked: could we build a cheaper/faster coin exchange with OD + dipole?

Reframed: it's a **market-making venue** play, not infrastructure. "Cheaper for users" comes from tighter spreads via the signal edge, not lower matching/custody costs. Three architectures considered:

- **A. CEX-style with smart router** — 18-24 months, $5-20M, regulated. Rejected.
- **B. Pure dynamic-fee AMM** — fast to ship but on-chain latency erodes signal edge. Rejected.
- **C. Off-chain RFQ → on-chain settlement** (Cowswap/UniswapX/Hashflow filler-network pattern). **Chosen.** Signal runs off-chain at native latency; settlement is non-custodial via existing networks. ~4-6 weeks MVP if we piggyback an existing filler network, ~3-4 months if we own settlement contracts.

## Quote service architecture (designed, not built)

File layout sketched but no code beyond stubs:

```
E:\quote_service\
├── src\quote_service\
│   ├── api\          quote.py / fill_webhook.py / admin.py / schemas.py
│   ├── signal\       client.py (refrag + dipole wrapper) / cache.py
│   ├── pricing\      engine.py / spread.py / fair_value.py
│   ├── risk\         gate.py / inventory.py / limits.py
│   ├── signer\       eip712.py / uniswapx.py / zerox_rfq.py / hashflow.py / wallet.py
│   ├── ledger\       quotes.py / fills.py / models.py (Postgres)
│   ├── market_data\  client.py (reads Markets' Redis)
│   ├── hedger\       client.py (enqueues jobs to Markets execution)
│   └── telemetry\    metrics.py / adverse.py
```

Quote flow: incoming RFQ → risk gate → fair value (Redis) → signal eval (refrag + dipole) → pricing → EIP-712 sign → ledger write → return signed quote. Latency budget p99 < 50ms. Three filler-network signers (UniswapX, 0x RFQ-v2, Hashflow) from day 1 — same pricing engine, different EIP-712 schemas.

Critical design decisions baked in: mid + spread (never raw signal price); spread as adverse-cost + safety pad, not a constant; inventory reservations in Redis with TTL = quote validity; per-counterparty premiums from day 1 (even if 1.0× for everyone initially); kill switch is real; every quote logged (filled or not) for adverse-selection calibration.

## What dipole actually is (and isn't)

The [paper](https://davisai.ai/dipole/) describes abstract C = H_self / H_cross — Shannon-entropy ratio. **Do not implement that.** Greg's stack has [dipole_coupling.py](E:\Markets\dipole_coupling.py) which is a 4-channel market-specific operationalization:

```python
DipoleCoupling = {
    market_dipole, news_dipole, onchain_dipole, family_dipole,  # each [-1, 1]
    coupling_score,         # avg of active components
    coupling_state,         # "aligned" | "neutral" | "conflicting"
    conflicts: list[str],
}
```

Strictly better signal for MM than the abstract paper version. The production state ladder in [DIPOLE_PRESSURE_WATCH_PRODUCTION_NOTES.md](E:\Markets\DIPOLE_PRESSURE_WATCH_PRODUCTION_NOTES.md) (weak → forming → volume-confirmed → autocorr-confirmed transition_risk → cross-venue → confirmed) is exactly the adverse-selection ladder MM wants.

**Signal source for quote service:** refrag (regime classifier — `(n_nodes, n_edges)` signature + 16-dim operator_coefficients) AND dipole (4-channel coupling + state). Complementary, not duplicative. Do NOT run OD separately — refrag wraps it.

## What's much bigger than we touched: `E:\operator_discovery\`

User flagged: the OD platform is much bigger than `E:\od_autoresearch\od_engine.py` (which is just the Liouvillian recovery solver). The platform has 8 `op_*` modules, twobath sim, cross-domain connector, papers, validation plans. **"Somewhere in there is the only mathematical calc of where classical and quantum computing unify."** Did NOT dive in this session. Most likely starting points when we do:
- [SYSTEM_ARCHITECTURE.md](E:\operator_discovery\SYSTEM_ARCHITECTURE.md)
- [OPERATOR_DISCOVERY_MODULES_HANDOFF.md](E:\operator_discovery\OPERATOR_DISCOVERY_MODULES_HANDOFF.md)
- [cross_domain_connector.py](E:\operator_discovery\cross_domain_connector.py)
- `papers/` and `14operators_extracted/`

## V1 calibration: what we ran and what we learned

### Script: [dipole_state_forward_returns.py](E:\Markets\dipole_state_forward_returns.py) (NEW)

Replays a market-only dipole proxy over BTC Bybit perp 1-second bins, bins into empirical quintiles of |dipole|, computes forward-return distributions at 1s/5s/15s/30s/60s/300s horizons per state. Output: [_dipole_state_forward_returns_out/summary.json](E:\Markets\_dipole_state_forward_returns_out\summary.json).

### Sample: 2 days only (the only days in `live_data_history/`)

```
loaded 47,562 bins (47,562 × 1-second BTC Bybit perp)
valid dipole bins (post warm-up): 7,062
per-state n: ~1,413 each (5 quintiles)
```

### Real numbers produced (the FIRST real numbers for the spread floor)

**Control:**
- Quoted spread on Bybit book: mean 0.0135 bps, p50 0.0133 bps (extremely tight)
- 30s realized vol p50: 0.32 bps per 1-second

**Forward |move| by quote-validity horizon, unconditional:**

| Horizon | Mean adverse \|move\| | + Bybit hedge leg (2bp) | Half-spread floor |
|---|---|---|---|
| 1 s | ~0.5 bps | +2.0 | **≈2.5 bps** |
| 5 s | ~1.2 bps | +2.0 | **≈3.2 bps** |
| 15 s | ~2.2 bps | +2.0 | **≈4.2 bps** |
| 30 s | ~3.2 bps | +2.0 | **≈5.2 bps** |
| 60 s | ~4.7 bps | +2.0 | **≈6.7 bps** |
| 300 s | ~11.6 bps | +2.0 | **≈13.6 bps** |

**Key finding:** the market-only dipole proxy as built **did NOT discriminate adverse-move magnitude across states** in this 2-day sample. Strongest-dipole state had the lowest 1s adverse move (0.46 bps) vs weakest at 0.51 bps. Variance across states ~0.1-1.5 bps at every horizon, within sampling noise on n≈1,413. Plausible reasons (decreasing order):

1. **Proxy is too crude** — no news/onchain/family channels, 30s volume-imbalance window already priced in by Bybit BTC
2. Sample is 2 days
3. Real production dipole uses an autocorr-confirmation + cross-venue-confirmation cascade we didn't replicate

**Sanity-check ratio:** quoted spread 0.013 bps vs realized 1s move 0.5 bps ≈ **37×**. Standard MM adverse-selection problem. Must quote above the book.

## Backfills currently in flight (or in failed state)

Launched in parallel background. Status as of session end:

| Job | Background ID | Status |
|---|---|---|
| Coinbase BTC 90d | bx7fsj1qq | ❌ failed — cursor stopped advancing after 2 calls (0.05d depth) |
| Coinbase ETH 90d | bpfqdv886 | ❌ failed — same |
| Kraken BTC 90d | bp92d6a8f | ✅ running cleanly — was at 89.04d back, 22k bins after 92s |
| Kraken ETH 90d | b2pqwfh47 | ✅ running cleanly — was at 87.36d back, 31.7k bins after 91s |
| Binance BTC 90d | bs6jh7080 | ✅ running cleanly — processing per-day zips, 568k bins after 7 days |
| Binance ETH 90d | byeuslj8y | ✅ running cleanly — 657k bins after 8 days |
| Funding 90d (Bybit) | blvw6y5gp | ❌ HTTP 451 Binance / 403 Bybit — geo-blocked from US IP |
| OI 90d (Bybit) | bof6ptouh | ❌ same — geo-blocked |

**New chat first action:** check whether the 4 running jobs completed. They were on pace to finish in 30-90 minutes. Outputs land in `E:\Markets\backfill_staging\`. Then run:

```bash
python E:\Markets\backfill_split_to_history.py --staging-dir E:\Markets\backfill_staging
```

to split single-file JSON into date-partitioned JSONL in `live_data_history/`. After that, re-run `dipole_state_forward_returns.py` against the now-larger dataset — but only Bybit perp will have 1-second bins. Kraken/Binance backfilled bins lack bid/ask (last-trade-price-as-mid only). Acceptable for forward-return and volume-imbalance analysis, NOT for explicit quoted-spread analysis (we have that on Bybit live only).

## Coinbase script bug (unfinished)

[backfill_coinbase_spot.py](E:\Markets\backfill_coinbase_spot.py) bails at the "cursor not advancing" or "empty page" check after only 2 API calls. Likely Coinbase changed their pagination behavior (the script assumes `CB-BEFORE` header gives a monotonically-decreasing trade-id cursor; may have switched to time-based or different format, or capped public history depth).

**Attempted fix:** spawned `debugger` subagent with detailed prompt. Agent ID `a1bf181f1c101b809` ran 30 tool uses then crashed with "Internal server error." Cannot resume (SendMessage tool not available). The script file mtime updated (size 11240 bytes vs original ~9.6KB), so agent made SOME edits before crashing — but did NOT produce test files (no `_debug_*` files in `backfill_staging`). Read the script to assess what the agent did before continuing.

**Next chat:** either re-spawn debugger agent with same prompt, or fix manually. Test invocation: `python backfill_coinbase_spot.py --product BTC-USD --days 1 --max-seconds 120 --no-resume --bins-path E:/Markets/backfill_staging/_debug_test.json` — confirm depth ≥ 0.5d.

## Funding/OI — geo-block, known workaround

Memory note [reference_markets_funding_oi_backfill.md](C:\Users\A\.claude\projects\E--\memory\reference_markets_funding_oi_backfill.md) flags the geo-block and prescribes the GitHub Actions one-shot workflow pattern (same as bin files). Not blocking; defer until cross-venue funding/OI signal is needed.

## What's preserved after a session restart

Files we wrote this session:
- [E:\Markets\dipole_state_forward_returns.py](E:\Markets\dipole_state_forward_returns.py) — v1 calibration script
- [E:\Markets\backfill_split_to_history.py](E:\Markets\backfill_split_to_history.py) — converter from backfill single-file JSON → date-partitioned JSONL archive
- [E:\Markets\_dipole_state_forward_returns_out\summary.json](E:\Markets\_dipole_state_forward_returns_out\summary.json) — first calibration output
- This handoff doc

Files in flight (probably appearing as backfills finish):
- `E:\Markets\backfill_staging\btc_kraken_bins.json`
- `E:\Markets\backfill_staging\eth_kraken_bins.json`
- `E:\Markets\backfill_staging\btc_binance_perp_bins.json`
- `E:\Markets\backfill_staging\eth_binance_perp_bins.json`

Memory entries refined this session:
- [feedback_trading_visibility_opsec.md](C:\Users\A\.claude\projects\E--\memory\feedback_trading_visibility_opsec.md) — refined to 4-cell model (best long / best short / worst long / worst short), each leaderboard view monitored independently. **This is for personal trading on Hyperliquid, NOT the MM exchange business.** Different rule for the MM entity.

## Revenue scenarios (we ended the session here)

Three bands, depending on whether the OD/dipole edge holds up under adverse selection from Jump/Wintermute/Tower:

| Scenario | Y1 net | Y2 net | Y3 net |
|---|---|---|---|
| Pessimistic (edge marginal, <1% volume share) | −$200k to $100k | $500k-$1M | $1-2M plateau |
| **Base** (signal works, growth as projected) | **$570k** | **$3.6M** | **$5.5M** |
| Optimistic (signal real + durable, preferred filler) | $2-3M | $10-15M | $25-50M |

Big swing factor: how many regimes does your signal beat the big MMs in, and how much volume sits in those regimes. The 2-day calibration sample can't yet tell us — the 90-day backfills are step 1.

## Open questions / pending decisions for next chat

1. **After backfills complete:** re-run calibration. Does the dipole proxy discriminate at 90-day depth? If yes, condition spread on state. If no, ship state-independent spread for v1.
2. **Fix Coinbase script** or accept the Coinbase gap (we have Kraken + Binance + Bybit live, which is enough for 3-venue cross-confirmation)?
3. **Set up GHA workflow** for funding/OI backfill, or defer?
4. **Build the actual quote service code**, or keep doing calibration?
5. **Dive into `E:\operator_discovery\`** for the classical/quantum unification calc?
6. **MM entity capital and governance** — different from personal trading caps. Needs separate decision (legal entity, banking, custody of MM inventory).

## Pre-launch phase: red-team as competitor MMs

**Hard gate before any live capital.** Adversary-emulate Jump / Wintermute / Tower / Flow / Hashflow internal MMs and ask: how would they pick us off?

Phase structure once we have a buildable quote service:

1. **Persona profiles** — for each of {Jump, Wintermute, Tower, Flow, Hashflow}, document: known infra (colocation, signal sources), historical filler-network behavior, public wallet patterns, known regimes where they dominate. We're building a mental model of each attacker.
2. **Attack-vector catalog** — at minimum:
   - **Stale-quote arbitrage** — probe small during news/regime breaks before we update; if we sign, hammer in size
   - **Cross-network probing** — submit same RFQ to UniswapX + 0x + Hashflow simultaneously, pick the loosest fill (us, if we're slow to converge cross-network)
   - **Inventory probing** — graduated-size orders to map our position limits per pair
   - **Pattern mining** — trace our MM wallet over weeks, identify quote-update cadence, infer signal lag
   - **Latency arbitrage** — colocate near our quote endpoint, detect our signal-update sequence
   - **Quote-then-reverse** — fill at our quote, immediately reverse on the public book to capture our spread plus drift
   - **Cross-counterparty info-share** — assume Jump and Wintermute share aggregate fill outcomes (they don't, but assume worst case)
3. **Mitigation map** — for each vector, define our defense:
   - short quote validity (already in design)
   - per-counterparty rate limits + per-counterparty premium curves (already in design as plumbing, needs real values)
   - cross-network quote consistency monitor (detects probes)
   - anomaly detection on fill-then-reverse patterns
   - per-counterparty PnL kill-switch
   - MM wallet rotation cadence
4. **Wargame in shadow mode** — run our quote engine against historical aggregator flow, with our pricing AS-IF live, but no actual signing/filling. Look at: which counterparties would have systematically beaten us, which regimes were unprofitable, which attack vectors actually fired. This is the calibration step for the per-counterparty premium curves.
5. **Gate criterion for live capital** — defined kill-switch coverage for each top-3 attack vector + shadow mode showing positive expected EV across the 90-day backfill sample.

Don't go live until shadow mode is green AND the kill-switch coverage is real (tested, not just specced). The pessimistic revenue scenario in this handoff is what happens when we skip this.

## Anti-drift / do/don't

- **DO** use `backfill_split_to_history.py` after every backfill run — backfill scripts write legacy single-file format, the archive needs JSONL date-partitioned
- **DO NOT** trust the market-only dipole proxy as currently coded — it didn't discriminate in v1
- **DO NOT** implement the paper's abstract H_self/H_cross — use [dipole_coupling.py](E:\Markets\dipole_coupling.py)'s 4-channel form
- **DO NOT** apply the 4-cell long/short opsec rule to the MM business — that's for personal Hyperliquid trading only
- **DO** preserve the existing output schema for [backfill_coinbase_spot.py](E:\Markets\backfill_coinbase_spot.py) when fixing — `backfill_split_to_history.py` depends on the `{ts_str: {buy, sell, mid, high, low, n_trades}}` shape
- **DO NOT** push to git unless Greg explicitly asks
- **DO** run OD + dipole together (refrag wraps OD, dipole is its own channel set) — no separate OD invocation needed

## Cross-session pointers

- Parallel chat handed off in [HANDOFF_SESSION_20260524_PART2.md](E:\Markets\HANDOFF_SESSION_20260524_PART2.md) — quantum cross-domain + Hyperliquid execution venue. That's a different workstream (personal trading + research pipeline), tangentially relevant to this one because Hyperliquid is also where personal trading will happen and where MM might eventually quote.
- At last check the quantum cross-domain run was at 450/912 trajectories. May or may not have completed by next chat; check `E:\refrag\_full_pipeline_quantum\summary.json`.

## End of handoff

The new red-team section above makes adversary-emulation a **gate**, not a wishlist item — with persona profiles, attack-vector catalog, mitigation map, shadow-mode wargame, and explicit go-live criteria. The pessimistic Y1 number ($-200k to $100k) in the revenue section is exactly what happens when this phase gets skipped.

Sleep well. Tomorrow we pick up by checking the backfills, splitting the archive, and re-running calibration with real cross-venue data.
