## Note (Session 28 — 2026-06-09) — MARKETS: trade-data binning corruption ROOT-CAUSED + FIXED (forward); coeff-gen re-run scope = small

> **Read THIS file (and the dated handoff/kickoff), not the 207 KB `CLAUDE (5).md`.** The master is archive; the
> daily note + `SESSION_HANDOFF_2026-06-09_S28.md` + `KICKOFF_2026-06-10_S29.md` are the live read. Memories still
> auto-load (`dipole-real-on-128dim-per-pair`, `markets-canonical-plan`, etc.).

**Project one-liner.** OD (operator-discovery) on real per-second crypto bins (btc/eth × coinbase/kraken/bybit-perp),
KEEP PAIRS SEPARATE. The validated result: 128-dim per-pair algebraic dipole, honest cs100 acc 0.947, perm-null
z=+9.6 (12/12 z>3). Heavy coeff-gen + win/lose pool building run on Greg's LOCAL box (refrag-bound: `E:\refrag`,
`F:\Factory`, `live_data_history`) — NOT in this cloud repo. Bins come from the `data/*` git branches.

**S28 pivot.** Greg flagged that a lot of trade data was missing/duplicated and that the coeff-gen runs consumed it.
S28 root-caused the binning corruption and fixed it forward. Three bugs:

- **Bug 1 — Kraken snapshot-replay duplication (the "duplicated").** `kraken_{btcusd,eth}_collector.py` accumulated
  on `mtype in ("update","snapshot")`. Kraken v2 replays a `snapshot` of recent trades on every (re)subscribe, so
  each reconnect re-counted the same trades and dumped them into the reconnect wall-clock second. Footprint in data:
  isolated seconds at ~100–150× the local median (btc_kraken 9 such, eth_kraken 5) = **~10% of btc_kraken volume in
  9 seconds**. FIX: accumulate `mtype == "update"` only. Kraken-only; coinbase/bybit never had it.
- **Bug 2 — inconsistent grid policy (apparent "missing").** kraken skips quiet seconds (18–28% raw coverage), bybit
  zero-pads (13% empty), coinbase fills ~99%. Breaks cross-venue alignment. FIX: `scripts/bins_integrity.py
  --normalize` (one regular 1 s grid, lossless) + `odcore.io.load_bins` already gap-fills.
- **Bug 3 — `if: always()` force-push clobber (real "missing").** Both collector workflows force-push even when a
  collector crashed (BTC/ETH collectors fail intermittently), overwriting good cumulative seconds. FIX: anti-clobber
  guardrail — never push a file with fewer bins than the data branch already holds.

**Shipped (all pushed).**
- Collector dedup (Bug 1) + workflow guardrail (Bug 3): on `new-session-o3vnm` (default), `continue-phase-2-pipeline-UFiGY` (code ref), `beautiful-shaw-040328` (canonical).
- `scripts/bins_integrity.py` — `--report` audit + `--normalize` lossless re-grid (flags spike seconds `_suspect`). Verified 17652/17652 kraken bins preserved.
- `odcore/io.load_bins` — auto-zeroes `_suspect` seconds + opt-in `mask_spikes`; mid preserved (price series intact).
- `CLEANUP_RUNBOOK.md` — the definitive repair/re-run plan.

**Coeff-gen re-run scope (Greg's real question — "do we rerun all the trade data we ran for coefficients?"): NO.**
- coinbase/bybit coeffs → KEEP (clean inputs; 16 of 24 buckets).
- kraken coeffs → only **≤4.0% (btc) / ≤2.7% (eth)** of kraken trades have a feature window overlapping a spike
  (bounded from actual spike timestamps, 256 s window). Just DROP those (`_suspect`/`mask_spikes` identifies them),
  or re-run the 8 kraken buckets. Cheap, not the 44 h.
- win coeffs (all venues) → **UNRESOLVED, depends on which bucket file the coeff runs read** (Greg's screenshots,
  below). Decide via two checks on the local box: (1) which win file the coeff run pointed at; (2) one per-trade
  discovery JSON's window key vs the trade's real time. If coeff-gen read `.fixed_ts.json` (or anchors on
  `source_id`/`window_start`) → keep wins. If it read the collapsed `.json` AND anchors on `entry_ts` → re-run wins
  from `.fixed_ts.json` (already exists). Then re-run `od_larger_set_val.py` for an honest temporal split.

**Win-bucket `entry_ts` collapse = CONFIRMED by Greg's pre-coeff-run screenshots (S28).** Every one of the 12
`markets_*_win.json` buckets has **`1 unique_ts`** (all win entry timestamps collapsed to one value); the matching
`*_win.fixed_ts.json` (from `_patch_win_buckets_entry_ts.py`) restores spread (btc_bybit buy 482→245, btc_kraken buy
344→188, eth_coinbase buy 367→130, …); every `*_lose.json` is fine (1000s of unique_ts). Wins-only. The builder +
patch are NOT in this repo (refrag-bound). The collapse is in the refrag trade-gen overwriting `entry_ts` with a
constant. Fix at source → rebuild win buckets → re-validate. This is also why `od_larger_set_val.py` says "no time
key exists" (it read a 1-unique_ts file).

**Branch map (matters — live collectors are NOT on the working branch).** default `new-session-o3vnm` governs the
scheduled workflow YAML; checkout `ref:` `continue-phase-2-pipeline-UFiGY` governs collector code; `beautiful-shaw-040328`
is the canonical OD working branch (`zealous-cannon-aej9yf` is its session mirror). Next scheduled run (cron `0 */6 * * *`)
is the first clean one.
