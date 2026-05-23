# Dipole Pressure Watch Production Notes

Date: 2026-05-16

## Production Shape

Dipole is now treated as an internal pressure primitive, not trader-facing copy.

Backend `/api/status` exposes trader-safe fields:

- `pressure_watch_state`
- `pressure_watch_label`
- `pressure_watch_direction`
- `pressure_watch_intensity`
- `pressure_watch_priority`
- `pressure_watch_reasons`

The word `dipole` should stay out of the UI, Discord, and push copy.

## Current Scenarios

- Weak dipole: internal amber watch.
- Persistent weak dipole: visible `Buy/Sell pressure forming`.
- Volume-confirmed moderate dipole: stronger `Buy/Sell pressure forming`.
- Autocorr-confirmed moderate dipole: `Buy/Sell pressure transition risk`.
- Same-direction pressure on at least two venues: `Buy/Sell pressure across venues`.
- Active Whale/Herd: `Buy/Sell pressure confirmed`.

## Current Surfaces

- Live status cards show pressure watch copy when present.
- Tape detail shows the same pressure read below the live flow summary.
- Discord `/status` includes the pressure watch label.
- Signal events now preserve the pressure watch context present when they fired.
- Stats split signal counts and resolved outcomes by pressure-watch state.
- Regime history marks chunks where pressure watch was active.
- High-priority cross-venue pressure emits a guarded amber drift alert.
- Live status now includes a trade-option decision object: watch, early probe, or confirmed follow.
- Tape detail can open an explicit early-probe ticket when the setup is mature enough but still early.
- Header now has a Manual/Auto toggle. Auto currently opens eligible early-probe trades in practice mode by default.

## Trading Decision Policy

Confidence is not the only trade gate. The live trade option combines:

- market read confidence
- pressure-watch state and priority
- venue/cross-venue confirmation
- spread and liquidity
- extension/chase risk
- predefined exit rules

`early_probe` is the less risk-averse profile:

- allowed before full Whale/Herd confirmation
- requires visible pressure, acceptable spread, non-extended entry, and readiness around 55+
- uses probe sizing, currently about 25% of normal
- exits if pressure flips, confirmation fails within the hold window, or price rejects the entry side
- can be auto-practiced when Auto is enabled; real-money auto is server-blocked unless `MARKETS_WATCH_ALLOW_LIVE_AUTO_TRADE=1`

`confirmed` is the follow profile:

- active once Whale/Herd confirmation exists
- normal sizing if risk gates pass
- still invalidated when pressure weakens or flips

## Auto Trade Tolerance

Full auto is now modeled as a tolerance preset rather than a raw confidence gate:

- `conservative`: confirmed-follow only, 75+ readiness, 1 open auto trade, smaller base notional
- `balanced`: early probes and confirmed follows, 65+ readiness, 3 open auto trades
- `aggressive`: early probes and confirmed follows, 55+ readiness, 6 open auto trades, larger base notional

The auto loop opens only when the current trade option has no blockers and the selected tolerance allows that profile. Practice auto is available from the UI; live auto remains blocked unless `MARKETS_WATCH_ALLOW_LIVE_AUTO_TRADE=1` is set on the server.

Auto exits are not just time-based. Open auto trades are swept closed when pressure flips against the position, an opposite Whale/Herd regime appears, an early probe degrades back to watch-only, or setup blockers appear.

## Fits To Consider Next

- Practice mode: allow a `watch-only` intent before a real signal fires, then measure whether waiting for confirmation helps.
- Drift/outcome loop: if pressure watch frequently flips or fails for an asset/venue, dampen its priority until fresh live evidence improves.
- Copy system: keep all trader language in the Whale/Herd/Equilibrium family: `Pressure forming`, `Whale watch`, `Herd watch`, `Equilibrium under pressure`.
- Calibration: accumulate enough live pressure-watch outcomes to tune asset/venue-specific thresholds instead of using the current global bands.

## Product Policy

Pressure watch is an amber light. It should never look like a trade button until Whale/Herd or another actionable confirmation layer appears.
