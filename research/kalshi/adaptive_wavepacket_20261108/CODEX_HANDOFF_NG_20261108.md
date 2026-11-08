# CODEX HANDOFF - ADAPTIVE LOCALITY ENGINE FOR HENRY HUB NG (pre paper-trading review)

**Current NG discovery handoff.** Use the [standalone discovery plan](markets_bridge/tasks/plan.md) on `codex/ng-shadow-discovery-20261108`. Git is the durable source of truth. Use a repository-backed workspace without a dependency on C:, E:, or desktop copies. October 3 and October 18 are both discovery evidence. Complete the October 3 comparison before paper orders. The migration-era instructions below are retained as historical provenance.

Date: 2026-11-08. Branch: `research/markets-adaptive-wavepacket-migration-20261108`. Everything below is
committed on that branch; the frozen BuildMap snapshot is never edited.

Purpose of this handoff: Greg wants an independent look, before paper trading starts, at whether running
historical NG data through this engine strengthens or finds trade signals worth testing in the paper
environment. This document says what is built and tested, what is not, how to run it on NG, how to read the
output, and what would and would not count as a signal. It is an independent piece for now; a Frankie
attachment is a later task.

## 0. Standing rule set tonight (Greg, 2026-11-08) and what it changed

Trade cost is not a market condition. Fees play no part in deriving market conditions or trade signals; they
can be layered on at the execution stage later if ever wanted. This is now written at the top of the trading
rules in `CLAUDE.md` and in the `kalshi-backtest` skill (Rule 3). Repo-wide effects, all committed:

- `research/kalshi/lag_join.py` (the NYMEX-to-Kalshi lag engine the NG forecaster imports; not a crypto file)
  now reports the echo GROSS: entry at the stale Kalshi mark, exit at the mark when the dollar trailing stop
  fires (`pnl_taker` key) or at the favorable extreme when the echo made a wave (`pnl_maker` key). Fee,
  slippage and maker offset are removed; output keys are unchanged; `--selftest` passes.
- `coach_replay.py` round-trip fee is 0; `lag_exploit_backtest.py` and `level_hit_dataset.py` fee functions
  return 0 (the observable bid/ask spread is still measured there as a book condition).
- Nothing from the crypto-era trade strategies (S36 dipole-fade rules, fee floors, maker/taker thresholds,
  the `DEPLOY` cell map) influences the NG program. The dipole toolkit itself (imbalance read, pre-entry
  look-ahead window, leakage gate) is what carries over.
- The session-start hook no longer materializes the crypto bins.
- Past findings files (S85 to S87) still describe net-of-fee readouts as records of what was measured then;
  they are history, not instructions.

## 1. What is built and verified (today, on this branch)

| Piece | Where | Verified by |
| --- | --- | --- |
| Adaptive Locality engine with every review fix applied | `working_tree/adaptive_locality/` | 87 original + 31 science-fix + engineering-fix tests, all green (`python3 -m unittest discover -s tests -p 'test_adaptive_locality*.py'` from `working_tree/`) |
| Native BuildMap scanner/viewer with every review fix | `working_tree/src`, `public`, `.buildmap` | 183 Node tests (`node --test tests/*.test.js` from `working_tree/`) |
| Estimator bridge: frozen-bin and Vasicek/KSG on the same frames, distinct identities, no mixing | `markets_bridge/estimators.py` | `markets_bridge/tests/test_markets_bridge.py` |
| Leakage gate: imported fitters pass `odcore/leakage.py`; a planted leak is caught | `markets_bridge/leakage_gate.py` | same file |
| NG workflow: tape -> per-second Lee-Ready buy/sell -> RawFrames -> frozen bins from history -> both estimators -> archive-first five-step, Level 2, static geometry, predictive controls, circular-shift null -> registries + `summary.json` | `markets_bridge/ng_runner.py` | CLI and arithmetic tests pass; the real-day end-to-end test is written and SKIPS until an NG day is cached (see 3) |
| Findings, math, register, fix log | `CCODE_INDEPENDENT_REVIEW_20261108.md`, `working_tree/FIX_LOG_20261108.md`, `working_tree/docs/SCIENCE_CONTEXT_REGISTER_ADDENDUM_20261108.md` | read |

## 2. What is NOT verified (say it before anyone reads a number)

- No real NG data has been through the engine yet. AWS was not accessible from the session that built
  this; no day is cached under `data/nymex_cont/`. The first real run is yours.
- All eight scientific gates in the register remain UNVERIFIED (replication, causal controls, algebraic
  novelty, rank/conditioning, parameter Fisher information, physical Neumann, raw external validation,
  scientific equivalence), plus the review's additional holds.
- The engine's "candidate" is a predictive association between ENTROPY changes of two channels. It is not a
  price-direction call. Direction on NG is the S92 nowcast (`dip_imb_level`, OOS 34/34 on strong flow,
  validated on NG); the realistic contribution of this engine is to the WHEN and the hold length, not the
  WHICH side.
- Trade cost is not a market condition. No fee, slippage or execution assumption enters any calculation or
  output here, by design; do not add one.
- Kalshi KXNATGASD channel and the depth channels in the runner are coded but untested on data.
- The synthetic controls that pass contain the fitted term by construction (review 4.6). They prove the
  fitter, not the science.

## 3. How to run it on NG (one day at a time, never pooled)

Cache a day with the repo's own loader (needs working AWS credentials for the bucket in
`event_move_baseline.py`; otherwise copy the `NG_YYYYMMDD.jsonl.gz` files from the box that holds them into
`data/nymex_cont/`):

```bash
PYTHONPATH=research/kalshi python3 -c "import event_move_baseline as e; e._s3_fetch_cont_gz('NG','20260617')"
```

Run the probe (from the Markets root; output directory outside git):

```bash
PYTHONPATH=.:research/kalshi:research/kalshi/adaptive_wavepacket_20261108/working_tree \
  python3 -m research.kalshi.adaptive_wavepacket_20261108.markets_bridge.ng_runner \
  --day 20260617 --source local --out /tmp/ng-probe-20260617 --mark-utc 14:30
```

Several days in one command, each run INDEPENDENTLY into `<out>/<day>/`, with bins frozen from a prior day
so no probed day is its own calibration, and a no-pooling replication table written to
`<out>/replication.json` (criteria 1 to 4 of section 5 checked per day, days counted, nothing averaged):

```bash
PYTHONPATH=.:research/kalshi:research/kalshi/adaptive_wavepacket_20261108/working_tree \
  python3 -m research.kalshi.adaptive_wavepacket_20261108.markets_bridge.ng_runner \
  --calibrate-from-day 20260616 --day 20260617 --day 20260618 --day 20260619 \
  --source local --out /tmp/ng-probe-june --mark-utc 14:30
```

Then the real-day test, which asserts the registries verify and prints the one-screen summary:

```bash
NG_PROBE_DAY=20260617 PYTHONPATH=.:research/kalshi:research/kalshi/adaptive_wavepacket_20261108/working_tree \
  python3 -m unittest research.kalshi.adaptive_wavepacket_20261108.markets_bridge.tests.test_ng_runner
```

Defaults and knobs: 60-second windows, stride 20 (a trading day gives on the order of a thousand frames);
settle exclusion 21:00 UTC with a 1800 s guard (`SETTLE_UTC["KXNATGASD"]`); the EIA storage release 14:30 UTC
is recorded as a mark, not a fit boundary; bins frozen from the first 30 percent of the day's frames (values
outside them later in the day make the whole frame REVIEW_REQUIRED, which is retained and counted, not
dropped); both estimators; circular-shift null with 20 shifts per direction; `--kalshi-bins` adds the Kalshi
channels; `--depth` adds the MBP-10 depth channels.

Cost: pure-Python fits; a full day at the defaults is minutes, not hours. Registries are SQLite files in the
output directory; a day's archives are tens of megabytes.

## 4. How to read `summary.json`

Per estimator:
- `review_required_frames`: frames the frozen bins could not admit (regime moved outside calibration). High
  numbers after a release are expected and are themselves an observation.
- `five_step.directions[*]`: for `ng_buy <- ng_sell` and the reverse: `status`, `improvement` (holdout gain of
  the full library over the self-only model), `shifted_null_improvement` (the matched past-lag null),
  `lag_profile` (the same at up to 12 lags), `dipole_balance` B with `balance_standard_error`,
  `donor_lag1_autocorrelation`, and `reason` for any abstention.
- `circular_shift_null[*].fraction_of_shifts_at_or_above_actual`: the Markets tautology-killer; small means the
  association is not an artifact of the donor's own spectrum.
- `level2`: candidate and held link counts across balance channels, with `segment_clocks` when one held window
  forced a side-by-side segment fit.
- `geometry[*].static`: the quadratic probe with its reparameterization null (`gain_over_algebraic_curve`) and
  degeneracy flags; `geometry[*].predictive`: future-rate controls per chronological split.
- `registry_cases` and `registry_verified`: every abstention, conflict, out-of-range frame and unverified
  result is a case you can open with `ResearchHoldRegistry.get(case_id)`.

## 5. What would count as something to carry into paper trading (and what would not)

Carry forward only if ALL of these hold, per direction, with nothing pooled across days:
1. `CANDIDATE_ASSOCIATION_REVIEW_ONLY` under BOTH estimators on the same day.
2. `fraction_of_shifts_at_or_above_actual` at or below 0.05 under both estimators.
3. The predictive geometry controls read `CONSISTENT_MULTISPLIT_ASSOCIATION_REVIEW_ONLY` or the direction's
   `improvement` exceeds every entry in its `lag_profile` by the null margin.
4. `|dipole_balance| / balance_standard_error` above 2 (otherwise B is noise, see review 4.3).
5. The same reading on at least three separate days (replication without pooling; multiplicity is otherwise
   uncontrolled: only two directed pairs are pre-registered here, do not add pairs after looking).
6. Then carry the day and direction into the paper-trading test as an input to hold length and timing,
   layered on the S92 direction nowcast; it is not a stand-alone entry rule.

Criteria 1 to 4 are evaluated per day by `replication.json` (`directions.<pair>.meets_criteria_by_day` and
`days_meeting_criteria`); criterion 5 is its day count reaching 3; criterion 6 is the paper-trading test
itself, outside this engine.

Does NOT count: a perfect static quadratic (algebra), a candidate under one estimator only, a candidate on
one day, anything inside the settle guard, anything whose frames were REVIEW_REQUIRED, any result where the
registry did not verify.

## 6. Overlooked or worth bolstering (honest list, in priority order)

1. BUILT: `--calibrate-from-day` freezes bins from all frames of a prior day (the version string records the
   calibration day); default remains the probed day's earliest 30 percent. Untested on data like the rest of
   the runner.
2. Pre-register the directed pairs for NG (ng_buy <- ng_sell, ng_sell <- ng_buy, and if Kalshi bins are
   present kalshi_* <- ng_*) and keep the count fixed; the engine tests every permutation of whatever channels
   you give it.
3. Per-event runs around the EIA release (a window of minutes has too few frames for the five-step minimums;
   use second-resolution windows of 8 to 16 seconds with stride 1 inside the release hour, which the runner
   supports via `--window`, `--stride`, `--start-ts`, `--end-ts`).
4. The Kalshi channel: verify `kalshi_coupling_adapter.load_kalshi_market` bar fields (`ts`, `buy_vol`,
   `sell_vol`) match what `kalshi_channels` reads; untested here.
5. DONE: the session-start hook no longer materializes the crypto bins (`scripts/session_start.sh`,
   opt-in via `KALSHI_MATERIALIZE_CRYPTO_BINS=1`; the data branches are untouched).
6. Frankie adapter and the fuller Frankie tree (review F-1) remain open; the RawFrame contract already carries
   free-string family and direction fields for P/O/S/X and SAME/FLIP when that time comes.
7. No signing anywhere (sha256 content pins only); the registries are local evidence, not attestations.
8. The static-geometry chemistry coefficients in `odcore/dipole_predictor.py` have still not been put through
   the reparameterization null; the engine can do it on any series with `geometric_dipole_probe`.
9. Nothing from the crypto-era strategy work (S36 dipole-fade rules, fee floors, maker/taker thresholds, the
   `DEPLOY` cell map) is used here. The only odcore pieces this piece touches are the two numerical estimators
   (`vasicek_entropy`, `ksg_mi`) and the leakage gate, which are data-agnostic.

## 7. State at handoff

Workflow status (2026-11-08, end of session): the NG workflow (`markets_bridge/ng_runner.py`) is complete in
code and is under a final double-check. Everything else in this handoff is done except the items explicitly
noted as open (no real NG day run yet, Kalshi channel untested on data, Frankie adapter later, AWS not in use).
Git-workflow verification at `0456eca`: local equals remote, merge base is the trunk tip, working tree clean,
every commit typed and single-purpose, zero secrets in the branch diff, zero stray artifacts tracked, all
suites green at HEAD, frozen snapshot still byte-exact. PR: https://github.com/DavisAI1974/Markets/pull/12.


Branch `research/markets-adaptive-wavepacket-migration-20261108`, 30 commits on top of the Markets base
`c93895e`, working tree clean, last commit the one that carries this document. Frozen snapshot untouched
(133/133 byte-exact). Suites green: Python engine 87 + 31 + engineering tests, Node 183, bridge 10 (one
real-day test skipped until an NG day is cached), `lag_join.py --selftest` and `coach_replay.py --selftest`
pass. Nothing merged, nothing deployed, no AWS, Frankie or Search action, launch HOLD.

## 8. Rules that bind every run

Zero synthetic trading data. Leakage gate before any backtest (passed for these fitters; re-run if you change
them). Settle window excluded. Each event individually, never averaged. Distributions and per-trade
fingerprints, never means. No trade cost in any calculation. Provisional until live. Launch is HOLD. Nothing
scientific is dropped: every abstention is in the registry with its reason.
