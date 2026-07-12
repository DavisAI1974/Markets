# EVENT SURPRISE SPLIT — resolving surprise=unknown on the canary (S86, P2)

The S85 event-move baseline had `surprise=unknown` for all 24 windows (the real street consensus is only
archived forward; ForexFactory is current-week-only). S86 joins a **seasonal-PROXY surprise** so the cells
finally split beat/miss x big/small. Proxy (established, `eia_bucket_study.py` / EVENT_WEIGHT_STUDY):
`surprise = actual weekly change - 5-yr average change for the same ISO calendar week`. Actuals from the EIA
API v2 (free DEMO_KEY): NG national working gas `NW2_EPG0_SWO_R48_BCF` (Bcf), crude ex-SPR `WCESTUS1`
(Mbbl). Tool: `eia_surprise.py` -> `data/eia_surprise.json` (NG 703 / CL 2116 historical surprises;
**12/12 of our release dates matched both contracts**). `event_move_baseline.py --surprise-file` consumes it
(tagged `surprise_source=seasonal_proxy`; real consensus preferred when present). Convention: a build BIGGER
than seasonal = more supply = bearish = expect price DOWN.

## The headline: NG's move IS surprise-driven; CL's big moves are NOT

### NG (KXNATGASD) — the surprise is the catalyst
`--big-surprise 15` (Bcf). The **big-bearish cell is crisp**:

| cell | n | dir | time_to_peak p50 | 60s capture | sustain p50 | peak_usd p50 |
|------|---|-----|------------------|-------------|-------------|--------------|
| **beat\|big** (build >> seasonal) | 3 | **DOWN 3/3** | **9.3s** | **1.00** | 7.4s (short) | $510 |
| miss\|small | 5 | up 0.6 | 1102s | 0.59 | 337s | $560 |
| beat\|small | 3 | down 0.67 | 126s | 0.82 | 138s | $390 |

- **A big bearish NG surprise (build much bigger than seasonal) = a fast, all-down, short burst** — peaks in
  ~9s, the 60s window captures the WHOLE move, then it's done (sustain 7s). This is precisely the fast
  lag-scalp the S85 hold-time map pointed at, now with a DIRECTION (down) and a TRIGGER (the big beat). The
  three cell members are the three biggest beats (04-23 +40, 06-11 +33, 07-02 +39 Bcf) and all three fell.
- So for NG the merged architecture's "catalyst = trigger + coarse direction/size" is REAL: the storage
  surprise sign + magnitude give direction (down on a big build) and the fast-burst shape.

### CL (KXWTI) — the storage surprise does NOT drive the big moves
`--big-surprise 4` (Mbbl). CL in this window was almost all draws (summer), so it split miss|big vs
miss|small — and the **relationship to move size is INVERTED**:

| CL release | surprise (Mbbl) | cell | peak move |
|------------|-----------------|------|-----------|
| 2026-06-17 | **-3.1 (small)** | miss\|small | **$2,640 (341 bps)** |
| 2026-05-27 | -0.8 (small) | miss\|small | $1,440 |
| 2026-04-22 | +4.0 | beat\|big | $1,180 |
| ... | | | |
| 2026-06-10 | **-7.7 (biggest)** | miss\|big | $650 |
| 2026-06-03 | -6.6 | miss\|big | $490 |

- **The three biggest CL moves were SMALL / contrarian surprises; the four biggest storage surprises made
  the smallest moves.** The S85 headline day (06-17, $2,640 over 17 min) was only a -3.1 Mbbl surprise.
  So for crude the weekly EIA storage number is **anti-correlated with move size** here — CL's big fires are
  **exogenous to the storage report** (macro / geopolitical / the Tuesday API pre-empt), exactly the
  "crude is diffuse / pre-empted" read from EVENT_WEIGHT_STUDY, now confirmed on the true-tick tape.
- **Consequence:** do NOT size/gate CL off the EIA storage surprise. CL's catalyst for the big moves lives
  elsewhere; the lag + book signal must carry it, and the release is a weak trigger for crude. This is a
  KEEP-per-cell result (the surprise works as a catalyst on NG, not on CL) — not "the surprise failed."

## Honest caveats (provisional)

1. **Seasonal PROXY, not the real desk number.** It captures the seasonal component only; the real
   consensus-conditioned split comes forward as `consensus.jsonl` accrues (ForexFactory). For CL the window
   is almost all draws, so "miss" here means "drew more than the 5-yr-avg" — a coarse read; the NG bearish
   cell (big build vs seasonal) is the cleaner one.
2. **n=12 per contract; sub-cells are n=3-5.** The NG beat|big direction (3/3 down, 9s peak) and the CL
   surprise-vs-size inversion are crisp but small-n. The full-year pull (~52/contract) is what confirms
   the surprise-cell split; the forward real consensus sharpens it further.
3. These are FUTURES (canary) moves = the ceiling; the Kalshi echo net-of-fee is the lag join (P3).

## Data / repro

- `research/kalshi/eia_surprise.py` (`--selftest` PASS) -> `data/eia_surprise.json`. Join via
  `event_move_baseline.py --surprise-file data/eia_surprise.json --big-surprise {15 NG | 4 CL}`.
- Persisted with the depth baselines on `data/nymex-ticks` (`nymex_mbp10/`); restored by kalshi-session-start.

## Next

- **Forward real consensus:** as `consensus.jsonl` accrues EIA forecasts week by week, event_move_baseline
  auto-prefers it (surprise_source=consensus) — sharpens the NG bearish cell and gives CL a real (vs
  seasonal) surprise to re-test the exogeneity claim.
- **Lag join (P3):** carry the NG beat|big fast-down-burst and the CL exogenous-mover into the Kalshi echo
  net-of-fee measurement — NG fire on the big bearish surprise, CL do not rely on the release.
</content>
