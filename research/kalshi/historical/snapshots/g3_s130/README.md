# G3 S130 sealed current-Frankie historical state

Window: 2025-09-08 through 2025-09-19. Starter anchor: 2025-09-05 close 3.026.

This directory is the durable materialized decision-state snapshot for the S130 historical
replay. It stores inputs only, not realized NG outcomes. It exists so a clean runner does not
lose historically reconstructible values simply because runtime caches are ephemeral.

Causal rules:
- Current S128 serving contract and current brain/schema; no old Frankie forecasts are reused.
- EIA storage payloads recovered from the legacy causal archive are rejoined STRICTLY before
  each decision day; same-Thursday own prints are hidden.
- Legacy realized-weather-as-forecast proxy is rejected and never copied here.
- Missing vintage feeds remain unavailable; no zeros or synthetic replacements.
- Grid stack was unavailable in this build because the public EIA DEMO_KEY rate-limited the
  multi-BA pull. That failure is recorded explicitly and the field remains unavailable.
- This snapshot does not make a post-reveal replay pristine blind; it preserves input state.
