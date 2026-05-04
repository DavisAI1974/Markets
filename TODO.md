# TODO — deferred items + things to revert before launch

A tracked-in-repo memory for the team. Anything here should land before Tier 1
launch (closed friends-group signal feed) unless explicitly marked as "later."

## Must revert before Tier 1 launch

### `DEMO_MODE_EMIT_EQUILIBRIUM_EXTREMES` in `backend/api_server.py`

**Currently**: `True` (default; can be disabled with `MARKETS_WATCH_DEMO_MODE=0`).
Causes the backend to emit synthetic signal events for any new EQUILIBRIUM
chunk where `|mean_dipole| > 0.3` and `|volume_zscore| > 0.5` (the autoresearch
mean-reversion candidate condition). Each demo signal carries the synthetic
regime label `EQUILIBRIUM_EXTREME_DEMO`, a 0.6× confidence multiplier, and an
explicit `[DEMO]` prefix in the playbook text.

**Why it exists**: when the backend boots with no recent regime transitions
in the bins data, the signal feed is empty and the UI demo experience is
uninteresting. Demo mode populates the feed with the actual mean-reversion
candidates we expect to act on once data validates.

**Revert by**: setting the constant to `False` (or removing the elif branch
entirely). Search for `XXX DEMO_MODE` in `backend/api_server.py` to find both
the flag definition and the emit branch.

**When to revert**: when the multi-day GitHub Actions data has produced ≥10
real WHALE/HERD/WASH signal events, demonstrating the production path
populates the feed naturally.

## Implement when multi-day data accumulates

- **Operator-drift alarm**: compare day-over-day autoresearch reports. When
  recovered operator coefficients shift beyond a threshold, flag regime
  fundamentally changed (Cox proportional hazards alpha-decay analog from
  the cyber DARPA work).
- **DPGMM auto-taxonomy**: replace hand-coded rule classifier with learned
  regime classes via `task_meta_learner`. Spec says wait for N≥200 labeled
  chunks; currently ~50.
- **Per-(asset, session_phase, day_of_week) baselines**: current baselines
  are global-per-asset. With multi-week corpus we can bucket finer (Monday
  morning ETH on Coinbase has different baselines than Friday afternoon).

## Implement before Tier 1 launch

- **PWA app icons**: generate `frontend/public/icon-192.png` and
  `icon-512.png` (manifest references both). Any 512×512 PNG of the project
  logo on the slate-950 background works. Without these, "Add to Home
  Screen" on iOS/Android will fail.
- **Backend auth**: closed group means closed access. Either Discord OAuth2
  wrapper around `/api/*` (most natural since users are already on Discord)
  or a simple shared-secret bearer token. Currently the API is open.
- **Backend HTTPS**: PWA service worker requires HTTPS in production. Caddy
  with Let's Encrypt is the cheapest path.
- ~~**Fix backtester strategy**: current backtester fades raw `mean_dipole` in
  EQUILIBRIUM. Per autoresearch, the right operator is `dipole × volume_z`.
  Update `backtester.py` to use the composite, re-sweep parameters.~~ ✅ Done
  in commit after `a7ea0c6`. `--strategy=dipole_x_volz` is now default;
  `--compare` runs both side-by-side. Note: on the single-day CB-ETH window,
  `raw_dipole` actually outperformed `dipole_x_volz` (the autoresearch winner).
  Multi-day data will tell which is robust.

## Need collector changes (defer until F4/F5 actually wanted)

- **Trade-size retention in collectors**: currently we aggregate trades to
  per-second sums in the bins. To compute F4 (trade-size multimodality) and
  F5 (inter-trade burstiness), we need per-trade timestamps + sizes retained.
  ~30 lines of collector changes + ~10× storage cost. Worth it once whale
  detection becomes a priority differentiator.

## Tier 2 prerequisites (not Tier 1)

- **Audit log endpoint**: institutional compliance requires every signal
  emission, every classifier rule fired, every operator update logged
  immutably. SQLite append-only or Postgres with row-level immutability.
- **Multi-account / multi-tenant API**: each customer desk gets its own
  API key, their own data isolation, their own configurable thresholds.
- **Databento ICE energy collector**: port `coinbase_btcusd_*_collector.py`
  pattern to Databento ICE futures. Same `MarketBar` output shape; encoder
  + classifier + everything downstream works unchanged.

## Nice-to-haves (no urgency)

- **Discord OAuth2 frontend login**: replaces "share-the-link" auth model.
  Once we have it, can per-user mute / signal preferences / push subscriptions.
- **Push notifications**: web push from backend to subscribed clients on
  signal events. `service-worker.js` already has the push handler stub;
  needs `/api/subscribe` endpoint + VAPID keys + push library on backend.
- **Multi-signal PELT default-on**: currently opt-in via `--multi-signal-pelt`
  flag; make default once we've validated it doesn't fragment chunks badly
  on multi-day data.
- **Cross-domain expansion (Tier 3)**: FX, rates, commodities. Same
  architecture, paid data feed. Documented in `OPTION_E_PRODUCT_SPEC.md`
  but not implemented.
