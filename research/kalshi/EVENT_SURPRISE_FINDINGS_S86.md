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

## The headline (Apr-Jul window only — log, no mechanism claimed): the surprise/move relation is
## opposite-signed between NG and CL

### NG (KXNATGASD)
`--big-surprise 15` (Bcf). Cells:

| cell | n | dir | time_to_peak p50 | 60s capture | sustain p50 | peak_usd p50 |
|------|---|-----|------------------|-------------|-------------|--------------|
| **beat\|big** (build >> seasonal) | 3 | **DOWN 3/3** | **9.3s** | **1.00** | 7.4s (short) | $510 |
| miss\|small | 5 | up 0.6 | 1102s | 0.59 | 337s | $560 |
| beat\|small | 3 | down 0.67 | 126s | 0.82 | 138s | $390 |

- Logged: in this window the beat|big cell (3 releases: 04-23 +40, 06-11 +33, 07-02 +39 Bcf) shows all
  three moving DOWN, fast (time_to_peak p50 9s, 60s captures the full peak), short sustain (7s). n=3.
  Consistent with the convention (bigger build than seasonal = more supply = down) but not asserted as
  causal at n=3.

### CL (KXWTI)
`--big-surprise 4` (Mbbl). CL in this window was almost all draws (summer season), so it split miss|big vs
miss|small — and the surprise-magnitude / move-size relation is opposite-signed to NG here:

| CL release | surprise (Mbbl) | cell | peak move |
|------------|-----------------|------|-----------|
| 2026-06-17 | **-3.1 (small)** | miss\|small | **$2,640 (341 bps)** |
| 2026-05-27 | -0.8 (small) | miss\|small | $1,440 |
| 2026-04-22 | +4.0 | beat\|big | $1,180 |
| ... | | | |
| 2026-06-10 | **-7.7 (biggest)** | miss\|big | $650 |
| 2026-06-03 | -6.6 | miss\|big | $490 |

- Logged: in this window the three biggest CL moves ($2,640 / $1,440 / $1,180) sit in small / contrarian
  surprise cells, and the four biggest storage surprises (-7.7 to -5.5 Mbbl) sit with the smallest moves —
  i.e. |surprise| and move size are NEGATIVELY correlated here. The S85 headline day (06-17, $2,640) was a
  -3.1 Mbbl (small) surprise. This is a logged correlation on this window; no cause is claimed for why the
  big CL moves occurred, and it is NOT asserted to hold outside Apr-Jul.

## Honest caveats (provisional — do not generalize)

1. **Prior conditions / event-stacking (load-bearing, Greg).** Events are NOT independent. Each release
   lands on a market state carrying the LASTING EFFECTS of prior events (accumulated storage level vs
   normal, recent price regime, the string of recent surprises), and the reaction to the next surprise
   STACKS on that running state — a +40 Bcf surprise into an already-oversupplied tape reacts differently
   than into a tight one. So a lone surprise->move number is incomplete; the surprise must be read
   conditional on the running condition. `eia_surprise.py` already logs `prev_level` (the accumulated level)
   as a first hook. Building the running event-state / lasting-effects context is the real requirement (see
   Next) — until then these per-window reads are unconditioned and must not be taken at face value.
2. **Time-of-year confound.** This is Apr-Jul 2026 only. CL was almost all summer draws and NG almost all
   injections — one seasonal slice. The surprise/move relation logged here may be season-specific; do NOT
   assume it holds in other months.
3. **Seasonal PROXY, not the real desk number.** `surprise = actual - 5yr-same-week-avg` captures the
   seasonal component only. For CL "miss" here means "drew more than the 5-yr avg." The real
   consensus-conditioned split comes forward as `consensus.jsonl` accrues (ForexFactory) and is preferred
   automatically when present.
4. **n=12 per contract; sub-cells are n=3-5.** Small-n logs, not validated edges. The full-year pull
   (~52/contract, all seasons) is what tests whether the surprise-cell relation is stable.
5. These are FUTURES (canary) moves = the ceiling; the Kalshi echo net-of-fee is the lag join (P3).

## Data / repro

- `research/kalshi/eia_surprise.py` (`--selftest` PASS) -> `data/eia_surprise.json`. Join via
  `event_move_baseline.py --surprise-file data/eia_surprise.json --big-surprise {15 NG | 4 CL}`.
- Persisted with the depth baselines on `data/nymex-ticks` (`nymex_mbp10/`); restored by kalshi-session-start.

## Next

- **Running event-state / lasting-effects context (the real requirement, Greg):** maintain an accumulating
  record of events and their lasting effects (storage level vs normal, price regime, the running string of
  surprises) so each new event is read as it STACKS on the prior condition, not in isolation. This is what
  turns the unconditioned per-window logs above into a conditioned read. The full-year pull supplies the
  history to build it against.
- **Forward real consensus:** as `consensus.jsonl` accrues EIA forecasts week by week, event_move_baseline
  auto-prefers it (surprise_source=consensus) — re-runs the split against the real desk number.
- **Full-year pull (all seasons):** re-run the surprise split with ~52 releases/contract to test whether
  the logged NG/CL relations are stable or seasonal/condition-dependent.
- **Lag join (P3):** carry the surprise cell onto the Kalshi echo net-of-fee measurement, per cell.
