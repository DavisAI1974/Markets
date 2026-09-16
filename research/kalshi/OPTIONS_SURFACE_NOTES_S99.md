# OPTIONS SURFACE FEED - BUILDER NOTES (feed I phase i, S99, built 2026-07-20)

Module: `research/kalshi/options_surface.py`. Store: `data/options_ng/surface.json.gz` (81
sessions Oct 31 2025 - Feb 27 2026, 715,843 OI points, 1,124,806 settle points), raw DBN substrate
+ store on S3 `options_ng/`. Wired as decision_state block `options_surface`; audit class
`options_session`. Module selftest 11/11 PASS; harness selftest PASS; audit 0 violations / 101
days, present on all 101. **G13 gate-closure item 6 (feed I phase i built AND wired): CLOSED.**

## WHAT IT IS

The NG options OI pin map off GLBX definition + statistics, BOTH roots (ON American + LNE
European; $4.67 total for the winter window, quoted before pulling). Per read: the two nearest
live option months, each with top-5 OI strikes + concentration shares (the walls), total P/C OI +
ratio, OI-weighted strike, per-asset splits, opex clock. Distance-from-settle deliberately left to
the agent against contract_structure's calendar-front settle (no cross-module coupling).

## MEASURED FACTS AND TRAPS

1. **Symbology: CME NG options live under ON/LNE roots, NOT NG** - "NG.OPT" resolves to nothing;
   the $4.67 quote succeeded on ON.OPT + LNE.OPT parent symbology. Any future options pull on
   another product should expect a distinct options root.
2. Statistics decoding: stat_type 3 = SETTLEMENT (price @1e9), 9 = OPEN INTEREST (quantity);
   session date in ts_ref (ns); INT64_MAX/UINT64_MAX null sentinels; definitions repeat per
   session (dedupe by instrument_id); underlying field names the future month directly (NGQ26).
3. Pull mechanics: the 4-month statistics range 504s server-side - MONTHLY CHUNKS pass. Quality
   warnings: 2025-11-28 degraded (post-Thanksgiving), Saturdays missing - benign, named.
4. BLIND WALL: CME next-morning publication (same rule as the futures OI join) - asof serves the
   latest session STRICTLY before iso; audit walks all 101 days at 0 violations.
5. OPEX CROSS-CHECK: the defs' expiration dates reproduce the flow calendar's independently
   verified anchors exactly (ON NGG26 opex 2026-01-27; NGH26 opex 2026-02-24) - two builds, two
   sources, same dates.
6. Post-opex month roll is by OPEX date: on futures-expiry day (e.g. Feb 25) the front OPTION
   month has already rolled (H-options expired Feb 24) - the unpinned expiry day is itself the
   read; flow_calendar carries the futures expiry clock.

## THE SQUEEZE-EVE VIEW (selftest-pinned)

On 2026-01-27 (opex day, squeeze week) the agent sees the 01-26 session: NGG26 at days_to_opex 0,
pin map populated (total C 619,175 / P 448,038), top-5 walls with shares, NGH26 alongside. G13's
opex day (Feb 24) shows NGH26 at days_to_opex 0. Phase ii (settle-implied ATM IV + 25d RR skew
from settlement prices - computation on real settles, not synthesis) remains post-gate.
