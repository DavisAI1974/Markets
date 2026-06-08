# Handoff to the next agent — markets-watch, 2026-05-10 (Pass-14 in progress)

> **QUOTE SERVICE (added 2026-06-08, S26) — FOLLOW `QUOTE_SERVICE_PLAN.md` (repo root).** It is the architect's canonical plan for the market-quoting / market-making capability, fusing the T3.1 `mm_passive` cells (resting bid/ask on EQUILIBRIUM, spread minus 2 fee legs) with the OD coupling/dipole layer (OD signals = gates + spread adjusters, NOT entry signals; maker-rebate spread capture is the edge lever; 1s = venues synchronous, no sub-bar lead edge). Includes the reusable-asset inventory (both code parts, exact paths), a 6-phase build sequence (each verified via forward paper), constraints, and 6 open questions to answer first. The OD layer lives on branch `claude/beautiful-shaw-040328` (`backend/odcore_store.py` + `odcore/`); Phase 0 merges it in.

> The handoff doc below this section is the historical version (2026-05-05,
> Phase 1.5j status). It is preserved for context. The CURRENT state of
> the project — including major framing change from the user — is in
> this top section.

## Branch + checkout

**Branch**: `claude/continue-phase-2-pipeline-UFiGY` (origin: `davisai1974/markets`)
**Latest pushed commit**: `ca71bf2` ("Pass-14: TRADEABLE SIGNAL REPORT — reframe around current tradeability")
**Uncommitted work in progress**: `phase1_5_evaluator.py` was just modified to switch from chronological-quarter classification to **horizon-based** classification (matching `edge_tracker.py`'s intraday/daily/weekly/longterm windows). This change is the IMMEDIATE TODO for the next agent: commit it, run Pass-14, then write the result up.

```bash
git fetch origin claude/continue-phase-2-pipeline-UFiGY
git checkout claude/continue-phase-2-pipeline-UFiGY
git status   # phase1_5_evaluator.py will show as modified
```

## THE PRODUCT GOAL (reframed by user, 2026-05-10)

Direct quote: *"the goal of this is to find the strongest tradeable
signals. not to make everything pass. if something fails that just
means not a tradeable signal. we need to figure out if signals are
always tradeable, always not, sometimes yes or sometimes no. that's
the goal and that's why we track them long-term and short-term. and
why we segment them. we need to get away from all the focus being on
if a signal fades over time. we need to focus on finding strong
signals to trade on in the moment."*

Operationally: every (asset, venue, regime) cell gets classified into
exactly one of four tradability states across four time horizons:

```
horizons   : intraday (4h), daily (24h), weekly (7d), longterm (30d)
strengths  : STRONG (|r|>=0.15), MODERATE (|r|>=0.10), WEAK, NEW
categories : ALWAYS_TRADEABLE              (longterm+weekly+daily strong,
                                              signs consistent)
             CURRENTLY_TRADEABLE           (intraday or daily strong,
                                              not always)
             HISTORICALLY_TRADEABLE_NOT_NOW (longterm/weekly strong but
                                              daily+intraday quiet)
             NEVER_TRADEABLE               (no horizon ever strong)
             AMBIGUOUS                     (partial signal, no clear category)
             INSUFFICIENT_DATA             (longterm n < 30)
```

The two existing systems that implement this:

- **`edge_tracker.py`** (live, runtime): `MultiHorizonEdgeTracker` polls
  per-chunk and maintains the four horizons. Already deployed. Tagged
  per-cell summary appears on `RegimeStatus` and `SignalEvent`.
- **`phase1_5_evaluator.py`** (offline, static corpus): the new
  `classify_cell_tradability()` does the same thing on a fixed 30d
  corpus. **Just rewritten to use the same horizons** (was chronological-
  quarter; user reminded me intraday/daily/weekly was already the
  framework). Uncommitted as of this handoff.

Gates (G/H/I) and the lag scan are now **diagnostics**, not quality
bars. They tell us things about the classifier and cross-venue
agreement; they do not determine what we trade. The TRADEABLE SIGNAL
REPORT is the headline.

## Critical user pushback this session (two major corrections)

This session had two big course-corrections from the user. The next
agent must respect these and not regress.

### Correction 1: do not bend analysis to fit interpretations

The user said: *"I'm not concerned about what i think is happening,
I only care about what actually is. i don't want us to adjust things
to what we think and just go with what actually is happening."*

Three code-level reverts landed in commits `8df20ce` + `e2592de`:

1. **Removed structural-divergence pass override**. I had ETH's
   calibrated Gate H verdict auto-pass via `gate_pass_override=True`
   because the asset was flagged "structural divergence". That was
   calling an empirical FAIL a PASS based on an interpretive label.
2. **Removed strict-OR-relaxed Gate H pass**. Pass-8 introduced
   `gate_H = strict>=60% OR relaxed>=60%` where the relaxed metric
   collapses EQ + WASH_HAWKES + WASH_PAIRED + DEPLETED into a
   NO_EDGE bucket. The bucket was a definitional choice; OR-passing
   gave the gate a softer second path. Strict-only is the verdict
   now. Relaxed still computed + printed but tagged "info only".
3. **Reverted WASH_HAWKES classifier tweaks**: `BOTH_SIDES_MIN`
   restored 0.35→0.30 (Pass-9 was nearly a no-op anyway) and
   `COMBINED_MAX = 0.55` ceiling removed entirely (Pass-10 revert).
   Both changes were classifier label tweaks motivated by sub-cell
   measurements showing η-high WASH chunks predicted momentum
   (r=+0.106). The chunks themselves and their forward returns
   didn't change — only the labels did. With the reverts,
   η-saturated balanced-flow chunks go back to being labeled
   `WASH_HAWKES` per the original threshold definition. The sub-
   cell finding is reported as a measurement, not folded into labels.

### Correction 2: focus on tradeable signals, not pass/fail (Pass-14 reframe)

The product goal (above) replaces the gates-as-quality-bars framing.
The new headline is the TRADEABLE SIGNAL REPORT.

### Lessons to internalize

- **Measurement, not interpretation.** Report what the data says.
  Don't extrapolate composition claims either (Pass-12 had a "Bybit-
  perp leads KR-BTC by 15+ min total" claim composed from sub-minute
  Bybit→CB-spot + 15min CB-spot→KR-spot. The composition was not
  directly measured. Don't repeat this pattern.)
- **Goalpost shifts are easy to do accidentally** when motivated by
  wanting a gate to pass or a signal to look stronger. The user is
  going to push back hard. Just report the measurement.
- **When in doubt about a classifier knob, leave it at the original
  spec** and report the sub-cell finding separately.

## Surviving findings (robust across passes 8–13)

These are tradeable empirical reads that survived all the classifier
reverts (because they live in regimes the WASH_HAWKES override doesn't
touch, or because they're sub-cell findings that don't depend on the
override):

| Cell | n | r | p / q | Notes |
|---|---:|---:|---|---|
| **KR-ETH WHALE_UP fade** | 65 | −0.309 | BH q=0.029 | **6 consecutive replications**, including under reverted classifier. Most robust finding in the corpus. |
| KR-ETH WHALE_UP × η-mid | 28 | −0.564 | p=0.001 | Strongest single sub-cell signal in corpus. |
| KR-BTC EQ × η-high | 236 | +0.150 | p=0.020 | Pass-13 split (Pass-10 had merged into n=368 r=+0.134 p=0.010; that merge is reverted). |
| KR-BTC WASH × η-high | 291 | +0.106 | p=0.069 | The other half of the Pass-10 merged cell. |
| KR-BTC WHALE_DOWN × η-low | 22 | +0.520 | p=0.006 | Capitulation-exhaustion fade. |
| KR-BTC WHALE_NASCENT_UP × η-low | 16 | −0.559 | p=0.012 | Cross-asset divergence with ETH (KR-ETH NASCENT_UP shows momentum). |

Already wired as a paper-trade cell (`backend/forward_paper.py`):
- `eth_kr_whale_up_fade` — fades KR-ETH WHALE_UP entries based on the
  Pass-8 finding above.

## Architecture map (so next agent can navigate)

```
phase1_5_evaluator.py        offline evaluator on 30d corpora
  - Gate G  : per-venue classifier diversity
  - Gate H  : cross-venue agreement (strict-only verdict; relaxed info-only)
  - Gate H lag-scan : disambiguates timing vs structural divergence
  - Gate H calibrated : uses cross_venue_lag_calibration.json
  - Gate I  : per-regime forward predictive r (BH-FDR corrected)
  - sub-cell Gate I : η-tier × hurst-label splits per regime
  - TRADEABLE SIGNAL REPORT : (Pass-14, in flight)
                              horizon-based per-cell classification

regime_classifier.py         regime classifier (WHALE_UP, HERD_UP,
                             EQ_TWO_SIDED, WASH_HAWKES, DEPLETED, etc.)
                             Thresholds at PASS-8 baseline as of e2592de.

markets_adapter.py           data layer: MarketBar, MarketChunk,
                             MarketChunker (PELT segmentation)

edge_tracker.py              live multi-horizon edge tracker (runtime).
                             Per-(asset, venue, regime) cell tracks
                             intraday/daily/weekly/longterm strength +
                             self_trend (STRENGTHENING/DECAYING/FLIPPING
                             /STABLE).

backend/api_server.py        live polling backend. Wires edge_tracker
                             into _poll_one. RegimeStatus + SignalEvent
                             carry edge_* fields.

backend/forward_paper.py     paper-trade cells (hardcoded) + edge-driven
                             trades via try_open_edge_driven_trade.
                             Priority: intraday > daily > weekly > longterm.

cross_venue_lag_calibration.json
                             Pass-11/12 lag-scan findings persisted.
                             BTC: CB leads KR by 15 min (peak measured).
                             ETH: structural_divergence=true (informational
                             metadata only, NOT a pass override).

HANDOFF_PHASE1_5_RESULTS.md  pass-by-pass results history.
                             Pass-13 entry documents all corrections.
                             Pass-14 entry: TBD (write when run completes).

pass{N}_{eth,btc}_stdout.txt  raw evaluator output per pass
pass{N}_{eth,btc}_features.json  feature dumps per pass
```

## Immediate todo list for next agent

1. **Commit the in-flight Pass-14 horizon-based classifier change** to
   `phase1_5_evaluator.py`. The classify_cell_tradability function was
   rewritten from chronological-quarter to horizon-based (intraday/
   daily/weekly/longterm matching edge_tracker.py). The print section
   was updated to show per-horizon strength + r. The classifier docstring
   was updated. Just commit and push.

2. **Run Pass-14** on ETH and BTC:
   ```bash
   nohup python phase1_5_evaluator.py --asset ETH \
       --cb-bins eth_coinbase_bins.json --kr-bins eth_kraken_bins.json \
       --sibling-cb-bins btc_coinbase_bins.json --sibling-kr-bins btc_kraken_bins.json \
       --multi-signal-pelt --features-out pass14_eth_features.json \
       > pass14_eth_stdout.txt 2>&1 &
   nohup python phase1_5_evaluator.py --asset BTC \
       --cb-bins btc_coinbase_bins.json --kr-bins btc_kraken_bins.json \
       --sibling-cb-bins eth_coinbase_bins.json --sibling-kr-bins eth_kraken_bins.json \
       --multi-signal-pelt --features-out pass14_btc_features.json \
       > pass14_btc_stdout.txt 2>&1 &
   ```
   ETH typically ~30-40 min wall-clock, BTC ~40-50 min. Use Monitor to
   wake when both `pass14_*_features.json` files exist.

3. **Read the TRADEABLE SIGNAL REPORT section** of each stdout. The
   key question for each cell: which category did it fall into?
   - `ALWAYS_TRADEABLE` cells are the strongest claim.
   - `CURRENTLY_TRADEABLE` cells should be productized (added as
     paper cells via the same pattern as `eth_kr_whale_up_fade`).
   - `HISTORICALLY_TRADEABLE_NOT_NOW` cells go on the watchlist.

4. **Write Pass-14 entry in `HANDOFF_PHASE1_5_RESULTS.md`** at the
   top, before the Pass-13 entry. Document what categorized where.
   Resist the urge to interpret beyond what the measurements say.

5. **Commit pass14 artifacts** (stdout, features JSON, doc update).

## Open questions / future pass candidates

- **Pass-15 candidate**: each `CURRENTLY_TRADEABLE` cell from Pass-14
  should get a paper-trade cell registered in `backend/forward_paper.py`
  using the same pattern as `eth_kr_whale_up_fade` (cell_id, asset,
  venue, regime, side, kind, hold_minutes, etc.).
- **Backend uptime**: once the live backend accumulates 24h+ of
  polling, the edge-tracker's daily horizon populates and the first
  edge-driven paper trades can fire.
- **Bybit perp data >24h**: `perp_lead_evaluator.py` was built in
  Pass-9 but needs >24h of Bybit perp data to run at n≥1000.
- **CB-BTC n≥20 directional**: still data-starved (n=42 total
  across all regimes in current 30d corpus).
- **NASCENT_UP n≥80**: currently KR-ETH n=45, KR-BTC n=48. Cross-
  asset sign divergence (KR-ETH momentum vs KR-BTC fade) would reach
  BH-significance at n≥80.
- **Don't extrapolate composition claims**. If we need Bybit-perp ↔
  KR-BTC lead time, measure it directly via a new lag scan over
  those two streams. Don't compose from prior measurements.

## Operating environment notes

- Repo lives in `/home/user/Markets`. Already a git repo on the
  named branch.
- Evaluator runs accumulate ~30-50 min wall-clock per pass per asset.
  Use background processes + Monitor for progress.
- Stop hook will complain about uncommitted artifacts; commit
  evaluator dumps after each pass.
- The user prefers concrete measurements over interpretation. When
  in doubt, report numbers and let the user decide.

---

# (Below: historical handoff doc from 2026-05-05, Phase 1.5j) ===========

# Handoff to the next agent — markets-watch, 2026-05-05

**Status**: Phase 1.5j complete. Codebase end-to-end ready; remaining work is operational (deploy on user hardware) per `LAUNCH_PLAYBOOK.md`.

**Branch**: `claude/continue-phase-2-pipeline-UFiGY` (origin: `davisai1974/markets`)
**Latest commit**: `cbced41`
**Started from**: `claude/new-session-o3vnm @ 8243ca9`

```bash
git fetch origin claude/continue-phase-2-pipeline-UFiGY
git checkout claude/continue-phase-2-pipeline-UFiGY
```

The user is going to start a new chat with you. They have **not** pulled the branch locally yet — they explicitly deferred that. Any time they want to look at code locally, point them at the checkout command above.

---

## What this branch contains beyond the starting point

17 commits adding ~6500 lines across data analysis, detection, consumer surfaces, trading integration, self-audit, and operational docs. By phase:

| commit | phase | what landed |
|---|---|---|
| `6f3ec5a` | 1.5a | First Phase 1.5 ETH GHA-collection results captured |
| `5de6ea1` | 1.5a | Verified + corrected gate findings (5.83h corpus) |
| `97b1300` | 1.5b | HERD activity characterization tool + doc |
| `cac4046` | 1.5c | HERD persistence, WHALE→HERD cascade, buy/sell split, autoresearch feasibility |
| `f8f4da5` | 1.5d | Cross-venue cascade emit, push UI, Caddy template, PREVIEW.md |
| `916e13e` | 1.5e | Consumer-surface refactor: drop dipole language, click-to-trade ladder, plain-language headlines |
| `521afba` | 1.5e+ | Live tape pulse — bid/ask cells flash on every market hit |
| `720b508` | — | Coinbase / Binance / Kraken adapters + manual-trade-intent wiring |
| `e89e9f5` | 1.5f | Practice mode (default ON; simulated fills, no real money) |
| `4f8412e` | 1.5g | Frontend visual polish (skeletons, mini-charts, animations, pull-to-refresh) |
| `c6696ec` | 1.5g+ | Discord polish (multi-embed cascade, confidence-tiered colors, chart attachment) |
| `748cf6f` | — | LAUNCH_PLAYBOOK.md (operational steps for tier-1 launch) |
| `3864a3f` | — | Phase 1.5 second pass on 12.83h corpus — venue-divergent edge documented |
| `e63bc80` | — | fix: untrack accidentally-committed eth_*_bins.json |
| `954b345` | 1.5h | Registry-driven per-(asset, venue, regime) playbook generator |
| `9fe8a65` | 1.5i | **Refrag native self-audit loop** — drift detection, real-time drift_alerts |
| `cbced41` | 1.5j | Bottom-sheet signal detail + local PWA smoke-test |

---

## Five conceptual rules the codebase now enforces

These came up via explicit user direction across the chat. Respect them — don't reverse them without checking.

### 1. No "dipole" / "realized vol" / math jargon in user-facing surfaces

The detector internals use those features, but the Discord embed, PWA cards, and signal text **never expose them**. User sees plain language: "Big buyer detected", "Selling cascade", "Healthy two-sided", etc. (`EVENT_LABELS` in `backend/api_server.py`, `REGIME_HEADLINES` mirrors in PWA + Discord.)

`SignalEvent` still carries `mean_dipole` and `realized_vol` because the executor / autoresearch use them; just don't surface them to humans.

### 2. Playbooks split per (asset, venue, regime), driven by data

Static `PLAYBOOKS` dict is the **fallback**. Live system reads `playbook_registry.json` and emits text per-cell based on the recovered edge direction (momentum / mean_revert / exploring / insufficient). Same regime label produces different actionable text on different venues based on actual outcomes, not hand-coded theories.

The user explicitly **rejected** an `n>=10` minimum threshold — registry overrides default at any `n>=3`. The framing intentionally updates each rebuild so users see the read evolve. Caveat tags (`[n=5, r=+0.77, p=0.039 — small sample, expect this read to shift]`) are surfaced in the playbook text itself.

### 3. Refrag-style self-audit, two drift loops in parallel

User direction: *"we don't want to be thinking about shifts in market dynamics after we see our confidence numbers have dropped noticeably. we want to be on top of this constantly."*

Two loops feed the same `drift_alert` SSE channel:
- **Slow loop (per-GHA-cycle, every 6h)**: `build_playbook_registry.py` rebuilds with history + lifecycle metadata, emits audit events for direction flips / sample milestones / |r| decay or strengthening. `refrag_audit.py` reads them, classifies cells (`stable | evolving | unstable | decaying | strengthening | exploring | insufficient`), writes `audit_reports/YYYY-MM-DDTHHMM.md`, POSTs each event to `/api/drift-alert`.
- **Fast loop (per-signal, real-time)**: `SignalStore.resolve_pending_outcomes` tracks per-cell outcome contradiction streaks. 3 in a row from a "momentum" cell that lose → emits `outcome_contradiction_streak` drift_alert immediately.

Surfaced as: yellow Discord embed; PWA top `<DriftBanner/>`; `SignalCard` drift badge under cascade ribbon; `drift_status` field on `SignalEvent`.

### 4. Practice mode is default-ON for safety

Every new device defaults to Practice. Click-to-trade simulates fills against the live bid/ask with a 25 bp fee. Practice trades persist to `backend_practice_trades.jsonl` and never hit the SSE stream — the executor literally never sees them. Switching to Live requires `window.confirm` in the header toggle PLUS a separate checkbox confirmation in the order ticket modal (two confirmation barriers).

### 5. Click-to-trade with tape-side flash

Each bid and offer is its own large clickable cell (`ClickableQuote.jsx`). Last-hit side flashes red (red text + bold + ring + bg pulse) — driven by a 1Hz `/api/tape` poll via `useTapePulse.js` hook. Clicking the cell opens `OrderTicketModal` pre-filled with side + price.

---

## Recent data state (verified 2026-05-05 04:25 UTC)

The data-collection branch `data/eth-bins` advanced from 5.83h to 12.83h between the two passes. Findings recorded in `HANDOFF_PHASE1_5_RESULTS.md`:

**Gates:**
- Gate G: PASS on KR-ETH (5 classes), FAIL on CB-ETH (modal climbed to 73%). Flipped between venues vs pass 1.
- Gate H: FAIL at 50.6% (was 51%). Single-venue disagreement still dominates.
- Gate I: PASS on **both** venues — but with venue-divergent edge sign:
  - **CB-ETH WHALE_UP**: n=5, r=**+0.77**, p=0.039 → momentum
  - **KR-ETH WHALE_UP**: n=13, r=**−0.64**, p=0.005 → mean-reversion

**The flip is documented and structurally consistent** with the actor-mix research: CB during US hours = retail-momentum-dense (US + India retail layered with US institutional); KR during NY-session = European afternoon→close, sophisticated/institutional, no retail amplification.

**Other finds in this corpus:**
- CB-ETH HERD_DOWN run extended to 5 consecutive chunks (was 2)
- KR-ETH first WHALE_UP→HERD_UP cascade (UP-direction)
- Cross-venue WHALE+HERD simultaneity: still none

**Reproducer:**
```bash
git checkout origin/data/eth-bins -- eth_coinbase_bins.json eth_kraken_bins.json
python phase1_5_evaluator.py --asset ETH \
    --cb-bins eth_coinbase_bins.json --kr-bins eth_kraken_bins.json \
    --multi-signal-pelt
```

---

## What's NOT done (need user hands)

All from `LAUNCH_PLAYBOOK.md`:

| section | task | needs |
|---|---|---|
| §1 | VM provisioning + DNS + Caddy + backend systemd | a server + a domain |
| §1.6 | Cron chain: registry rebuild → refrag_audit → POST drift events | host above + crontab |
| §2 | VAPID keypair generation + env wiring | run `python -m backend.push --generate-keys` on host |
| §3 | Discord bot creation in Developer Portal + token + channel ID + systemd | discord.com login |
| §4 | Per-user exchange wiring (testnet → real-money keys → small-position verification) | each user's exchange dashboards |
| §5 | End-to-end smoke-test checklist | host up + at least one user wallet |
| §6 | Friend onboarding | install link + walkthrough |

Plus one item user explicitly deferred:
- **Pull the branch locally** for hands-on dev. Command above.

---

## File inventory of phase 1.5 additions (skim before answering questions)

**Detection / autoresearch core:**
- `regime_classifier.py` — adds `apply_herd_persistence`, `apply_herd_borderline_rescue`, `detect_whale_to_herd_cascades`, `detect_cross_venue_whale_herd_simultaneity`
- `phase1_5_evaluator.py` — gates G/H/I evaluator; `--multi-signal-pelt` and `--herd-rescue` flags
- `regime_feature_audit.py` — per-regime feature signature audit + WHALE/HERD breakdown
- `phase2_chunk_picker.py` — list classified chunks with `--regime-filter` for Phase 2 inputs
- `markets_autoresearch_chunk.py` — per-chunk operator-form search (8-operator family, complexity penalty, per-regime aggregation, optional Gate D check)

**Playbook + audit framework (the refrag pattern):**
- `build_playbook_registry.py` — lifecycle-aware per-(asset, venue, regime) registry builder; emits audit events to `--audit-events-path`
- `playbook_generator.py` — runtime composer: `get_playbook(asset, venue, regime)` + `get_drift_status(...)`. Reads `playbook_registry.json` with mtime hot-reload; falls back to `DEFAULT_PLAYBOOKS`
- `refrag_audit.py` — cycle-level drift detector + `audit_reports/` writer + `--post-url` relay to backend

**Backend additions (`backend/api_server.py`):**
- New SSE event type `drift_alert`
- New endpoints: `/api/drift-alert` (POST, audit relay), `/api/drift-alerts` (GET), `/api/manual-trade-intent`, `/api/manual-trade-intents`, `/api/practice-trades`, `/api/practice-trade/close`, `/api/tape/{asset}/{venue}`, `/api/push/vapid-public-key`, `/api/push/subscribe`, `/api/push/unsubscribe`
- New `SignalEvent` fields: `cascade_event`, `cascade_detail`, `chunk_buy_volume`, `chunk_sell_volume`, `chunk_n_trades`, `current_price`, `current_bid`, `current_ask`, `last_aggressor`, `event_label`, `drift_status`
- Per-cell outcome-contradiction streak tracker in `resolve_pending_outcomes`
- Cross-venue WHALE+HERD simultaneity detection in `_emit_cross_venue_cascades` (runs after both venues poll)

**Exchange adapters (in `executor/exchanges/`):**
- `coinbase.py`, `binance.py`, `kraken.py` — HMAC-signed REST adapters; **default to dry-run**, `EXCHANGE_LIVE=1` to send real orders
- `__init__.py` exports `make_exchange("coinbase"|"binance"|"kraken"|"paper", ...)` factory
- `executor/executor.py` consumes both `signal` AND `manual_trade_intent` SSE events

**Frontend additions (`frontend/src/`):**
- `components/`: `ClickableQuote.jsx`, `OrderTicketModal.jsx`, `LiveTape.jsx`, `PriceVolumeChart.jsx`, `MiniChart.jsx`, `LoadingSkeleton.jsx`, `PushNotifyButton.jsx`, `DriftBanner.jsx`, `SignalDetailBody.jsx`, `SignalDetailSheet.jsx`
- `pages/PracticeFeed.jsx` — open + closed practice trades with running P&L
- `useTapePulse.js`, `usePullToRefresh.jsx` — custom hooks
- `index.css` — keyframes for `slide-in-fade`, `cascade-pulse`, `shimmer`, `tape-flash`, `slide-in-up`, `fadeIn`
- Manifest + service-worker enriched for iOS PWA install + push notifications + tap-to-open

**Data adapter:**
- `markets_adapter.py:MarketBar` gains `n_trades`, `bid`, `ask`, `last_aggressor` fields
- Both ETH collectors (`coinbase_eth_collector.py`, `kraken_eth_collector.py`) now persist bid/ask + last_aggressor in bin records

**Docs at repo root:**
- `LAUNCH_PLAYBOOK.md` — operational steps for tier-1 launch (the user-hardware-needed list)
- `HANDOFF_PHASE1_5_RESULTS.md` — sequential evaluator passes; first pass at the top, second pass appended; registry framework note + drift-loop note
- `PREVIEW.md` — ASCII renders of Discord posts + phone-app screens
- `deploy/Caddyfile`, `deploy/README.md` — HTTPS + reverse-proxy template

---

## On first contact, run this verification

```bash
# 1. Branch + commit check
git status && git log --oneline -5

# 2. Reproduce the latest gate evaluation
git checkout origin/data/eth-bins -- eth_coinbase_bins.json eth_kraken_bins.json
python phase1_5_evaluator.py --asset ETH \
    --cb-bins eth_coinbase_bins.json --kr-bins eth_kraken_bins.json \
    --multi-signal-pelt
# Expect: Gate I PASS on both, CB WHALE_UP r=+0.77, KR WHALE_UP r=-0.64

# 3. Build the playbook registry + run the audit
python build_playbook_registry.py --asset ETH \
    --cb-bins eth_coinbase_bins.json --kr-bins eth_kraken_bins.json \
    --output-path /tmp/registry.json --audit-events-path /tmp/events.jsonl
python refrag_audit.py \
    --registry-path /tmp/registry.json \
    --audit-events-path /tmp/events.jsonl \
    --report-dir /tmp/reports
# Expect: report written; first run shows 3 milestone events (cells crossing n>=10)

# 4. Frontend builds clean
cd frontend && npm install && npm run build
# Expect: vite build with 1 size warning (recharts-driven 646 KB JS / 186 KB gzipped); no errors
```

If any of these fail on a fresh checkout, fix that first.

---

## Common pickup paths — pattern matching

| User says | What to do |
|---|---|
| "let's deploy" / "let's start the playbook" | Walk through `LAUNCH_PLAYBOOK.md` §1–§6 in order. Don't skip steps. Each section has explicit verify checks. |
| "data has more samples" / "GHA cycle finished" | Re-pull `data/eth-bins`, re-run §3 reproducer, update `HANDOFF_PHASE1_5_RESULTS.md` with a new "Nth pass" appendix preserving prior passes. Compare gate verdicts + r-signs to detect drift. |
| "add another asset" (BTC, SOL, etc.) | Three steps: (a) add a collector (clone `coinbase_eth_collector.py`); (b) add to `DATA_SOURCES` in `backend/api_server.py`; (c) extend the GHA workflow + crontab to rebuild registry per asset. The registry, playbook generator, executor, and PWA handle multiple assets without further changes. |
| "tweak a playbook string" | Don't edit `DEFAULT_PLAYBOOKS` unless changing the fallback for a regime universally. To shift per-cell text, the right path is to wait for the next registry rebuild — the text composes from recovered direction. If the current cell is wrong, that's a data issue (small n), not a string issue. |
| "push to main" / "merge" | Confirm with user before merging. Branch is `claude/continue-phase-2-pipeline-UFiGY`; main is unchanged. |
| "rerun autoresearch" | `python markets_autoresearch_chunk.py --asset ETH --cb-bins ... --kr-bins ... --gate-d-eval`. Honestly framed: in-sample only at this corpus size, true cross-chunk eval deferred until n>=30/regime. |

---

## Anti-patterns to avoid

1. **Don't put dipole/realized-vol numbers in any user-facing string.** It violates rule #1 above. The user explicitly directed this and reinforced it twice.
2. **Don't hardcode venue-specific theories** (e.g. "CB momentum / KR mean-revert") into static playbook text. The registry-driven generator is doing that automatically based on data; hand-coding fights it.
3. **Don't gate the registry on `n>=10`.** User explicitly rejected that. Override default at `n>=3` so framing updates each pass.
4. **Don't enable `EXCHANGE_LIVE=1` without explicit user instruction.** Adapters default to dry-run for safety; live mode requires user opt-in per their own machine.
5. **Don't break Practice mode default.** New devices must default to Practice. Two-confirmation barrier to switch to Live (header toggle confirm + per-modal checkbox).
6. **Don't surface flat registry entries in `playbook_generator.get_playbook()`.** Lifecycle-aware shape (`{current, history, lifecycle}`) is current; legacy flat upgrades automatically. If you see a flat registry, it's pre-1.5h — call `_upgrade_legacy_entry()` or rebuild.
7. **Don't commit bin files or build artifacts.** `eth_*_bins.json`, `frontend/node_modules/`, `frontend/dist/`, `playbook_registry.json`, `audit_reports/`, `audit_events.jsonl`, `backend_drift_alerts.jsonl`, `backend_signals.jsonl`, `backend_practice_trades.jsonl`, `backend_manual_trade_intents.jsonl` are all gitignored intentionally.

---

## Open questions you may face

These came up but weren't resolved in the chat — flag if relevant:

- **Bottom-of-the-hour gap**: GHA collectors run 5h50m on a 6h cron, leaving a ~10 min unobserved window per cycle. Time series has small gaps; aggregator handles them. Not currently a problem; mention if user worries about it.
- **n=5 vs n=13 across CB/KR WHALE_UP**: the venue-divergent r-sign may be sample artifact (CB n=5) or real structural difference. Won't be diagnostic until CB-ETH WHALE_UP n>=20. Documented in `HANDOFF_PHASE1_5_RESULTS.md` second-pass section.
- **Cross-venue cascade**: `_emit_cross_venue_cascades` is wired and working; just hasn't fired yet because no cross-venue WHALE+HERD simultaneity has appeared in the 12.83h corpus. First firing will be the first real test.
- **DPGMM auto-taxonomy**: still gated on N≥200 labeled chunks (`TODO.md` line 65). Combined corpus is ~92. Premature.
- **Phase 2 autoresearch-real**: `markets_autoresearch_chunk.py` is a curated 8-operator family, NOT the full deepnova/refrag operator-discovery engine. Bridge exists in `markets_adapter.py` if user later wants to import the real engine. Document call-out at the top of `markets_autoresearch_chunk.py`.

---

## What I'd suggest opening with

The user said they'd start a new chat. Recommended first message back to them after they say hi:

> "Branch is at `cbced41` (phase 1.5j). Want to walk through `LAUNCH_PLAYBOOK.md` to deploy the central host, or pick something else? Branch state and what's still pending are in `HANDOFF_TO_NEXT_AGENT.md`."

Then let them direct.

— end of original handoff —

---

## Session update — 2026-05-06 / 2026-05-07

**Current branch tip**: `claude/continue-phase-2-pipeline-UFiGY @ 3e4b560`
**Default branch tip**: `claude/new-session-o3vnm @ 4a86520` (now carries the
new workflow YML files so they're visible in the GitHub Actions UI)
**Data branches**:
- `data/eth-bins @ 1a2c926` — eth_coinbase_bins.json + eth_kraken_bins.json,
  56.5h corpus
- `data/btc-bins @ 7fc3d05` — btc_coinbase_bins.json + btc_kraken_bins.json,
  5.8h corpus (the BTC perp files in this commit are stale/broken — see
  perp section below; will be replaced on next workflow cycle)

### What this session shipped (commits)

| commit | what |
|---|---|
| `e613661` | phase 1.5 results: third pass on 50.7h ETH corpus |
| `b1fa1dc` | add ETH perp collectors (Binance USDT-M + Kraken Futures) — superseded |
| `343ea6a` | add BTC collectors (CB spot, BN+KR perp) + parallel BTC workflow — perp parts superseded |
| `3005b5c` | add 30-day backfill scripts (Binance Vision, Kraken /Trades, Coinbase /trades) + one-shot workflow |
| `b07d35e` | sync workflow files from phase-2 to default branch (UI visibility) |
| `277c86c` | swap broken Binance + Kraken Futures perps for Bybit V5 linear |
| `4a86520` | sync workflow updates: Bybit perps onto default branch |
| `3e4b560` | phase 1.5 results: fourth pass + first BTC corpus + perp debug |

### AWS deployment state — what's done, what's left

The user did `LAUNCH_PLAYBOOK.md` §1.1–1.4 in this session on AWS Lightsail.
Picking up §1.5+.

**Host**:
- Lightsail us-east-2, instance `market_watch`
- Public IPv4 **`3.142.250.137`** (static)
- Public IPv6 `2600:1f16:16b2:ad00:f62a:6db2:252c:4020` (stable per Lightsail)
- OS: Ubuntu 22.04 LTS
- SSH: `ssh ubuntu@3.142.250.137` (Lightsail default key in user's downloads)

**DNS**:
- `markets.davisai.ai → 3.142.250.137` (GoDaddy A record, 600s TTL, propagated)
- Domain registrar: GoDaddy. The user has a GoDaddy developer API key
  (production) on the davisholdingco@gmail.com account. **DO NOT prompt the
  user for it again — they exposed it in the prior session transcript and
  rotation is on the pending-todo list. If you need to update DNS, ask the
  user for a current key.**

**Hardening**:
- ufw active, allows 22/80/443 only
- sshd: `pubkeyauthentication yes`, `passwordauthentication no`

**Caddy**:
- Installed via Cloudsmith repo
- Config: `/etc/caddy/Caddyfile` (sourced from `deploy/Caddyfile` on
  phase-2 branch with `markets.example.com` sed-replaced by
  `markets.davisai.ai`)
- Let's Encrypt cert obtained for `markets.davisai.ai` (verified in journal)
- HTTP→HTTPS redirect verified working (308 from outside)

**PWA frontend**:
- Repo cloned to `/opt/markets`, owned by `ubuntu`
- Branch checked out: `claude/continue-phase-2-pipeline-UFiGY`
- Node 20 installed via NodeSource
- `frontend/dist/` built (vite, 8.39s build)
- Deployed to `/var/www/markets-watch/` (chowned to caddy:caddy)
- **Unverified**: whether the URL actually loads in a browser. The
  in-VM curl hit AWS NAT-hairpin issue and timed out, but external
  reachability is implied by the LE cert + 308 redirect. First task next
  session: ask user to load `https://markets.davisai.ai/` on phone or
  laptop and confirm the dark-themed PWA shell shows up (red dot top-right
  is expected; backend not running yet).

**Still to do** (per LAUNCH_PLAYBOOK.md):
- §1.5 Backend systemd service. Needs `MARKETS_WATCH_ACCESS_TOKEN`
  (long random string), VAPID env vars (next item), pip install of
  `backend/requirements.txt`. Service file template in playbook.
- §2 VAPID push key generation + wiring + phone subscription test
  - `cd /opt/markets && python -m backend.push --generate-keys`
  - paste public+private into the systemd unit env
  - test with phone Add-to-Home-Screen + "Notify me" toggle
- §3 Discord bot setup: Discord developer portal app, bot token, channel
  ID, systemd unit. Per-step in playbook §3.
- §5 End-to-end smoke test (the 7-checkbox list in playbook)

**Don't bother with**: §4 (per-user exchange wallet wiring) — that's
each member's responsibility on their own machine; the central host
never touches keys.

### Data collection — current state

Two durable workflows on schedule (every 6h):

- `eth_collectors_durable.yml` → `data/eth-bins`
  - coinbase_eth_collector.py (CB-ETH spot)
  - kraken_eth_collector.py (KR-ETH spot)
  - **bybit_ethusdt_perp_collector.py** (NEW; first run pending)

- `btc_collectors_durable.yml` → `data/btc-bins`
  - coinbase_btcusd_collector.py (CB-BTC spot)
  - kraken_btcusd_collector.py (KR-BTC spot)
  - **bybit_btcusdt_perp_collector.py** (NEW; first run pending)

Both workflows checkout `claude/continue-phase-2-pipeline-UFiGY` for the
actual collector code; the YML on the default branch only exists so GHA
surfaces the workflow in the UI.

**Coinbase futures intentionally parked** — Coinbase INTX has the real
ETH-PERP / BTC-PERP but needs a non-US account. Coinbase Derivatives nano
dated futures are too thin to compare to perps.

**Perp debug history (don't relitigate without new evidence):**
- Binance USDT-M perp (`fstream.binance.com`): WS handshake / trade stream
  doesn't deliver from GHA's egress IPs even though HTTPS is reachable.
  Result was empty bins file. Removed from workflow.
- Kraken Futures v1 (`futures.kraken.com/ws/v1`): emits one
  `feed: trade_snapshot` on subscribe, then zero live trade messages over
  25s (verified via local probe). Result was 29 active bins out of 21k
  in production. Removed from workflow.
- Bybit V5 linear (`stream.bybit.com/v5/public/linear`): verified working
  (47 trade-like messages in 15s smoke test). This is the active perp venue.
- The .py collector files for the two broken venues remain in the repo for
  reference but are not invoked.

### Backfill — running at handoff time

`backfill_oneshot.yml` is running (workflow_dispatch, started by user via
GitHub UI). Two parallel jobs (eth + btc), each runs 3 backfill scripts
in parallel:
- backfill_binance_vision.py (Vision daily aggTrades zips, 30d clean —
  Vision is an S3 bucket, NOT subject to the fstream geo-block we hit
  on the live WS)
- backfill_kraken_spot.py (paginated /Trades, 30d, ~30-90 min/pair)
- backfill_coinbase_spot.py (paginated /trades, 30d target capped by
  wallclock; realistic ~7-15d for BTC)

Wallclock estimate ~3-5h. Will land merged historical+RT bins on
`data/eth-bins` and `data/btc-bins` (existing RT bins always win,
backfill fills gaps only).

### Latest analysis findings (HANDOFF_PHASE1_5_RESULTS.md, 4 passes)

- **KR-ETH WHALE_UP fade is the most robust signal** (n=45, r=−0.369,
  p=0.009; held direction across all four passes). First cell ready to
  promote from playbook surface to live executor signal once n grows
  more.
- **Both pass-2 and pass-3 CB-ETH-specific edges have failed to
  reproduce.** Treat the venue-divergent "CB momentum / KR mean-revert"
  story as withdrawn pending dramatic new evidence.
- **First BTC pass (5.8h): Gate H clears at 60.9%** — first time any
  venue pair has cleared 60% threshold. BTC venues agree more than ETH
  venues (working hypothesis: BTC has more institutional flow).
- **3 of 4 (asset × venue) cells lean mean-revert on WHALE_UP.** The
  unified read is "WHALE_UP fades on both crypto majors, both major
  spot venues."

### Pending todos (carry over to next session)

1. **Verify PWA loads in browser** — first thing, takes 30s
2. **AWS §1.5 backend systemd** — straightforward, follow playbook
3. **AWS §2 VAPID + phone push test** — generates push keys, tests on
   real phone (iOS Safari Add-to-Home-Screen path is non-obvious)
4. **AWS §3 Discord bot** — Developer Portal account creation + bot
   token + systemd unit
5. **AWS §5 end-to-end smoke test** — 7-item checklist before opening
   to friends group
6. **Re-run phase1_5_evaluator on backfilled corpus** once `data/eth-bins`
   and `data/btc-bins` get the 30-day data committed (~3-5h after
   backfill workflow trigger time)
7. **Rotate GoDaddy API key** — exposed in prior session transcript;
   user knows. They click delete + create new at
   developer.godaddy.com/keys.
8. **Fix AWS MCP for Claude Code** (separate from Desktop install) if
   the user wants to drive AWS APIs from a session — not strictly needed
   for the playbook's remaining steps which are all SSH + Discord UI.

### First-message script for next agent

When the user's first message is a continuation cue ("ok", "continue",
"where were we"), respond with something like:

> "Picked up at commit `3e4b560` on phase-2 branch. AWS deployment is at
> §1.5 (backend systemd next). Backfill should be landing on
> `data/{eth,btc}-bins` shortly if it hasn't already. Want to (a) finish
> AWS deployment, (b) check on backfill + run analysis if it landed, or
> (c) something else?"

— end of handoff —

---

## 2026-05-07 session update — microstructure layer + calibration

User pivoted from launch-blockers to deepening the analytics. This
section is the brief for the NEXT chat.

### Branches at end of session

| Branch | Tip | Notes |
|---|---|---|
| `claude/continue-phase-2-pipeline-UFiGY` (active code) | `7886ede` | All Tier-1 microstructure work + 3 calibration scripts cherry-picked here |
| `claude/remove-handoff-info-rXuUL` (session work) | `d09de8a` (`7886ede` after cherry-pick mapping) | Where development happened |
| `data/eth-bins` | `30c27bc` (2026-05-07 07:42 UTC) | All 4 backfill jobs landed |
| `data/btc-bins` | `b5d4142` (2026-05-07 07:59 UTC) | Same |
| `claude/new-session-o3vnm` (default) | `4a86520` | Untouched this session |

### Backfill workflow status — ALL 4 JOBS DONE

The `Backfill (one-shot)` workflow on phase-2 finished cleanly. Both
`backfill_eth` / `backfill_btc` (parallel BN-vision + KR + CB rounds)
AND the new chained `cb_extend_eth` / `cb_extend_btc` (resume-from-
cursor CB-only rounds) committed bins back to the data branches. The
new `*_coinbase_bins.cursor.json` sidecar files are persisted on the
data branches, so future workflow triggers will continue extending CB
depth.

**Reminder for next agent**: pull both data branches before any
analysis. Re-running the workflow once or twice more will push CB
depth toward the 30-day target. KR is already at full 30d; BN-vision
is capped at 10d (~90 MB push limit).

### What shipped this session — Tier 1 + calibration

All 14 commits below are on phase-2 (and on rXuUL):

| Commit | What |
|---|---|
| `c169cb4` | Gate I tightened: `n>=30` + Benjamini-Hochberg FDR (`q<=0.10`). Tiny-n artifacts no longer trip the gate. |
| `c34b771` | `backend/forward_paper.py` + hooks: auto-paper-trades the 2 ETH chunk-level candidate cells (`eth_kr_nascent_up_momo`, `eth_kr_herd_up_volq3_fade`). Sweep-close + by-cell aggregates in `/api/practice-trades?source=auto`. |
| `d19bb1e` | **VPIN** per chunk (Easley/LdP toxicity proxy). `MarketFeatures.vpin`/`vpin_n_buckets`. `ClassificationResult.vpin_multiplier` (×1.15 high / ×0.85 low / ×0.7 on suspicious WASH). Threaded into `adjusted_confidence`. |
| `cd55ea3` | OFI semantics doc: current `ofi` is collinear with `dipole`. NOT Cont-Kukanov OFI. `MarketFeatures.book_ofi: float = 0.0` placeholder. |
| `95b4f70` | **Basis monitor** (`backend/basis_monitor.py`): spot-perp basis tracker emitting `BASIS_DIVERGENT_HOT/COLD/CLEARED`. `/api/basis-status`. Self-calibrating via rolling z. |
| `8410b72` | **Funding monitor** (`backend/funding_monitor.py`): polls Binance + Bybit funding rates; emits `FUNDING_OVERLEVERED_LONG/SHORT/CLEARED`. Persists every cycle to `backend_funding_history.jsonl`. `/api/funding-status`. |
| `e0db811` | **Liq monitor** (`backend/liq_monitor.py`): synthetic liquidation-burst detector on perp bins. `LIQ_BURST_UP/DOWN`. Upgrade path = real WSS feed. |
| `c5d6dc2` | **Microprice + L1 sizes**: 4 spot collectors (CB/KR × ETH/BTC) now write `bid_qty`/`ask_qty` per bin. `MarketBar.mid` = Stoikov microprice with graceful degradation. Schema-additive. |
| `f8c349d` | **VPIN calibration**: refactored `_compute_vpin` to fixed bucket SIZE in volume units (corpus-mean / 10). `calibrate_vpin.py` writes `vpin_calibration.json`. Backend reads p75/p25 per (asset, venue). |
| `08b2dc1` | **Liq calibration**: `calibrate_liq.py` walks perp bins, picks p99 of (vol_z, |dip|, |gap|) per asset, reports joint pass-rate / alerts/day. `liq_calibration.json`. |
| `4e48187` | **Funding calibration**: `calibrate_funding.py` reads funding history, computes p25/p75/p95 of `|rate|` per (asset, venue). `funding_calibration.json`. Needs ≥30 cycles. |
| `7886ede` | `forward_paper.CellSpec` doc: `notional_usd` = pure policy (vol-target Tier 3). `hold_minutes` = TODO empirical per-cell IC vs horizon curve once ≥50 closed auto trades exist. |

### Calibration runbook (RUN THESE FIRST)

The data branches are now full. Next agent should:

1. **Pull data branches** from a phase-2 checkout:
   ```bash
   git fetch origin data/eth-bins data/btc-bins
   git checkout origin/data/eth-bins -- eth_coinbase_bins.json eth_kraken_bins.json eth_binance_perp_bins.json eth_kraken_perp_bins.json
   git checkout origin/data/btc-bins -- btc_coinbase_bins.json btc_kraken_bins.json btc_binance_perp_bins.json btc_kraken_perp_bins.json
   ```
2. `python calibrate_vpin.py` → writes `vpin_calibration.json`. Inspect per-(asset, venue) p25/p75 + per-regime mean VPIN. Sanity-check that BTC and ETH percentiles diverge (literature says they should).
3. `python calibrate_liq.py` → writes `liq_calibration.json`. Inspect `joint_alerts_per_day_est`. If >5/asset/day, rerun with `--percentile=99.5` or `99.9`.
4. `python calibrate_funding.py` → likely **skips** (only 1-2 cycles of data exist; need ≥30). Re-run after ~10 days of backend uptime.
5. Commit the JSONs to phase-2 (gitignore exempt).
6. **Re-run `phase1_5_evaluator.py` on the fresh 30d corpus** — Gate I results will likely move (more cells now meet n≥30, FDR may filter some). Update `HANDOFF_PHASE1_5_RESULTS.md` with a Pass-6 section.
7. Backend startup logs show per-key `(calibrated)` vs `(hardcoded fallback)` so it's verifiable on next AWS systemd start.

### Pass-5 findings still authoritative (from `HANDOFF_PHASE1_5_RESULTS.md`)

- **KR-ETH WHALE_UP fade**: collapsed at 10× n (r=−0.073 p=0.109). Headline gone standalone.
- **Pre-registered KR _UP-fade family pool**: Stouffer combined p=0.020. Real but tiny effect.
- **ETH KR HERD_UP × vol-Q3 fade**: r=−0.20 at n=168 p=0.008. Forward paper-traded as `eth_kr_herd_up_volq3_fade`.
- **BTC BN-perp imb leads KR-spot at 1m**: most robust signal in project. r=+0.10 at n=12,955. Decile spread D10−D1 = 1.44 bps. Marginal at maker tier; impossible at retail. NOT yet wired into forward paper (requires minute-level perp evaluator — see carry-over).
- **ETH KR WHALE_NASCENT_UP momentum**: r=+0.21 over 30d, r=+0.58 in recent 9d. Forward paper-traded as `eth_kr_nascent_up_momo`.
- **BTC NASCENT divergence from ETH**: BTC NASCENT shows r=−0.21 (fade), opposite of ETH (+0.21 momentum). Asset divergence in regime lifecycle.

### Tier suggestions NOT yet shipped

The full prioritized list from the literature survey (web research
2026-05-07), with everything still pending. Recommend tackling
top-down. Sources detailed in the session that produced this list.

#### Tier 2 (high impact, requires some new data)

- **2.7 OI delta per chunk**. Open Interest on BN/BB perp APIs is free; per-chunk `oi_delta_pct` tells trend conviction (OI↑ + price↑ = trend; OI↑ + flat = position build; OI↓ + move = unwind). Add to `MarketFeatures` and as a sub-axis on regime classification.
- **2.8 Coinbase premium index**. `(CB_BTC_USD − BN_BTCUSDT/peg) / spot`. US-institutional flow proxy. We already have CB; need a USDT-peg adjustment + alignment. Use as daily-bias multiplier on US-hours signals.
- **2.9 Hawkes branching ratio per chunk**. Multivariate Hawkes self-excitation (η = α/β) — clustered (informed/cascade) vs Poisson (random). Better separator for NASCENT-vs-WHALE. Multiple recent papers on BTC LOB.

#### Tier 3 (strategy classes the playbook ignores)

- **3.1 EQUILIBRIUM market-making**. Current playbook says "no edge, sit out." That's exactly when passive top-of-book quoting earns spread. Add `MM_PASSIVE_QUOTE` playbook variant + a separate paper-trade cell that quotes both sides on `EQUILIBRIUM_TWO_SIDED` chunks and exits on regime flip.
- **3.2 Vol-targeted sizing for forward_paper**. All trades currently $1000 fixed notional. Scale notional ∝ 1/realized_vol_z. ~10 LOC in `forward_paper.open_paper_trade`.
- **3.3 Funding-rate carry / basis arb**. Delta-neutral (long spot, short perp when funding > spot lending rate by margin). Multi-hour holds, very high Sharpe, uncorrelated to direction calls. Pairs with the funding feed (already shipped).
- **3.4 Forward_paper hold_minutes empirical calibration**. Per-cell IC vs horizon curve; needs ≥50 closed auto trades per cell. Documented in `forward_paper.py:CellSpec`.

#### Tier 4 (daily-priors layer)

- **4.1 BTC→ETH cross-asset lead multiplier**. Research is consistent: BTC leads ETH intraday. Use BTC's current chunk regime as a same-direction confirmation multiplier on ETH signals (analogous to F6 cross-venue but cross-asset).
- **4.2 Calendar/event awareness**. 8h funding windows (already partially modeled), ETF flow days, US/EU/Asia session breaks (have `session_phase` but day-of-week / weekend not modeled), CPI/FOMC. Confidence dampener around scheduled events.

#### Tier 5 (classifiers worth revisiting)

- **5.1 Wash-trade detection via Hawkes**. Multivariate Hawkes on (buy, sell, cancel) reliably beats rule-based WASH. Current rule-based `WASH_PAIRED` has tiny n; would benefit from a benchmark.
- **5.2 Spoofing / quote-flicker**. Cancel-replace ratio at top-of-book. Requires order-book deltas, not just trades.
- **5.3 Hurst exponent / DFA per chunk**. Orthogonal trending-vs-reverting label that layers on top of the regime classifier.
- **5.4 Real Cont-Kukanov OFI**. Needs L1 size *deltas* (we have static sizes via the microprice work, but not deltas). Fill `MarketFeatures.book_ofi` once book-state diff machinery is in collectors.

### Carry-over from earlier sessions (still open)

1. **Verify PWA loads on phone** (30s test).
2. **AWS §1.5 backend systemd** — pickup point in `LAUNCH_PLAYBOOK.md`.
3. **AWS §2 VAPID push + phone test**.
4. **AWS §3 Discord bot deploy**.
5. **AWS §5 end-to-end smoke test** — 7-item checklist.
6. **BTC perp-lead → forward paper-trading**. The most robust signal in the project (r=+0.10, n=13k, 4/4 quarters significant) is currently NOT wired for forward paper because the existing evaluator runs on chunks, not 1-min perp imbalance. Adding it requires a minute-level evaluator that taps the perp bins separately from `_poll_one`. Modest scope (~100 LOC).
7. **Rotate GoDaddy API key** — exposed in earlier session transcript.
8. **Fix AWS MCP for Claude Code** — separate from Desktop install.

### Hardcodes in shipped code — accepted as policy/conventions

These were reviewed and explicitly kept hardcoded (NOT empirical questions):
- `regime_classifier._vpin_multiplier_for_regime`: 1.15 / 0.85 / 0.7 multipliers — policy.
- `basis_monitor`: `HOT_THRESHOLD_Z=2.0`, `CLEAR_THRESHOLD_Z=1.0` — sigma counts (auto-scale to volatility), `SUSTAINED_CYCLES=5` — noise filter.
- `Gate I`: `min_n=30`, `fdr_q=0.10`, `r²>0.05` — statistical conventions.
- `forward_paper`: `vol_z>=0.67` for HERD×Q3 cell — standard-normal Q3 cut.

### First-message script for next agent (revised)

When the user's first message is a continuation cue:

> "Picked up at `7886ede` on phase-2. All 4 backfill jobs done — data branches at `30c27bc` (eth) / `b5d4142` (btc). Tier 1 microstructure (VPIN, basis, funding, liq, microprice) plus calibration scripts shipped. Want me to (a) pull data and run the 3 calibration scripts + Pass-6 evaluator, (b) start Tier 2 (OI delta / Coinbase premium / Hawkes), (c) wire BTC perp-lead into forward paper, or (d) AWS §1.5?"

— end of 2026-05-07 update —

---

## 2026-05-07 evening session update — Tier 1 calibration + Tier 2 + Tier 3

This session ran the calibration runbook on the 30d backfilled
corpus (Pass-6), shipped Tier 2 microstructure (OI delta, Coinbase
premium, Hawkes), shipped Tier 3 (vol-target sizing, EQUILIBRIUM
market-making, carry/basis-arb scoring + paper trades), and audited
hardcoded constants for empirical reevaluation.

### Branches at end of session

| Branch | Tip | Notes |
|---|---|---|
| `claude/continue-phase-2-pipeline-UFiGY` (active code) | `fe34fcd` | All session work cherry-picked here |
| `claude/calibrate-phase-2-metrics-Z1lUW` (session) | `df64ad3` | Where development happened; merge of phase-2 + new work |
| `data/eth-bins` | `30c27bc` (unchanged this session) | KR ~30d, BN-vision ~10d, CB grown via cb_extend |
| `data/btc-bins` | `b5d4142` (unchanged this session) | Same |
| `claude/new-session-o3vnm` (default) | `4a86520` (unchanged this session) | Stale by design |

### What this session shipped (commits on phase-2 since b61a935)

| Commit | What |
|---|---|
| `f533283` | Calibration JSONs (vpin + liq) from 30d corpus |
| `cd6cd0d` | **Pass-6 evaluator results** appended to HANDOFF_PHASE1_5_RESULTS.md |
| `3c99f6a` | **Tier 2.7** OI delta backend monitor + calibrate_oi.py + /api/oi-status |
| `00d3331` | **Tier 2.8** Coinbase premium monitor + /api/cb-premium-status |
| `b5d720f` | **Tier 2.9** Hawkes branching ratio per chunk (eta on MarketFeatures) |
| `71209ff` | **Tier 3.2** vol-targeted sizing in forward_paper |
| `697ad1e` | **Tier 3.1** EQUILIBRIUM MM cells + playbook variant |
| `3bc490f` | **Tier 3.3** carry/basis-arb scoring + /api/carry-opportunities |
| `ac3f0bc` | Hardcode reevaluation: vol_target per (asset,venue) + hawkes bar inference |
| `23ee441` | TODO.md + inline calibration TODOs for deferred recalibrations |
| `e653776` | vol_target_calibration JSON (median realized_vol per cell, 3.4-5.1 bps) |
| `fe34fcd` | **Tier 3.3 finished** — paper-trade carry integration on funding alerts |

### Pass-6 headlines (still authoritative)

- **KR-ETH WHALE_UP fade dead at scale**: r=−0.073 at n=484 confirms
  Pass-5 collapse. Withdrawn hypothesis.
- **KR-ETH WHALE_NASCENT_UP** holds direction at n=45, r=+0.221 —
  sign stable across 5 passes; forward-paper-traded.
- **KR-BTC WHALE_NASCENT_UP r=−0.209 at n=48** — opposite sign vs
  ETH NASCENT. Cross-asset divergence on NASCENT confirmed.
- **BTC Gate H passes** (63.9%) again; ETH Gate H still fails (56.4%).
- **No cell BH-significant at q=0.10** in either asset at 30d.

### Vol-target finding (calibration changed real behavior)

Hand-picked `VOL_TARGET=0.005` was **10× too high**. Actual median
realized_vol per (asset, venue) is 3.4-5.1 bps (calibration JSON).
Old default clipped every chunk to 2.0× (vol-targeting was a no-op
constant). Per-cell calibration now drives [0.5×–2.0×] inverse-vol
scaling. Global fallback dropped to 0.0004.

### Tier 4 — daily-priors layer (NOT STARTED)

- **4.1 BTC→ETH cross-asset lead multiplier**. Research consistent on
  intraday lead. Use BTC's current chunk regime as a same-direction
  confirmation multiplier on ETH signals (analogous to F6 cross-venue
  but cross-asset). Plumbing: `regime_classifier` reads sibling
  asset's latest regime; multiplier in `ClassificationResult`.
- **4.2 Calendar/event awareness**. 8h funding windows (already
  partially modeled), ETF flow days, US/EU/Asia session breaks
  (`session_phase` exists but day-of-week / weekend not modeled),
  CPI/FOMC. Confidence dampener around scheduled events.

### Tier 5 — classifiers worth revisiting (NOT STARTED)

- **5.1 Wash-trade detection via Hawkes**. Multivariate Hawkes on
  (buy, sell, cancel) reliably beats rule-based WASH. Current
  rule-based WASH_PAIRED has tiny n; would benefit from a benchmark.
- **5.2 Spoofing / quote-flicker**. Cancel-replace ratio at top-of-
  book. Requires order-book deltas, not just trades. Blocked on
  collector schema upgrade.
- **5.3 Hurst exponent / DFA per chunk**. Orthogonal trending-vs-
  reverting label that layers on top of the regime classifier.
- **5.4 Real Cont-Kukanov OFI**. Needs L1 size *deltas* (we have
  static sizes via the microprice work, but not deltas). Fills
  `MarketFeatures.book_ofi` once book-state diff machinery is in
  collectors.

### Deferred from prior tiers

- **Wire hawkes_eta into the regime classifier**. The field is now
  populated on every chunk extraction (T2.9), but the classifier
  doesn't read it yet. Two paths: (a) split NASCENT/WHALE into
  eta-clustered vs eta-quiet sub-cells, (b) use eta as a confidence
  multiplier analogous to vpin_multiplier. Either path needs a
  Pass-7 evaluator to produce per-cell eta distributions first.
- **BTC perp-lead → forward paper-trading**. The most robust signal
  in the project (r=+0.10 n=13k 4/4 quarters significant) is
  currently NOT wired for forward paper because the existing
  evaluator runs on chunks, not 1-min perp imbalance. Adding it
  requires a minute-level evaluator that taps the perp bins
  separately from `_poll_one`. Modest scope (~100 LOC).
- **CB premium calibration**: `cb_premium_monitor` uses sigma-cut
  HOT_Z=2.0 / CLEAR_Z=1.0 (policy). Empirical calibration would
  ship as `calibrate_cb_premium.py` reading
  `backend_cb_premium_history.jsonl` for p95/p50 of |premium_z|.
  Defer until ≥240 obs exist on AWS.
- **Carry-analyzer per-venue rates**: `DEFAULT_SPOT_LENDING_APR=0.05`,
  `DEFAULT_FEE_ROUND_TRIP_BPS=10.0`, `expected_hold_days=1.0` are
  uniform conservative placeholders. Real values are venue +
  user-tier specific. Wire venue lending APIs and friend-group fee
  tiers to flag more opportunities.

### Calibrations awaiting AWS uptime (ALL 5 SCRIPTS SHIPPED)

Re-run as data accumulates; backend reads each JSON at module load:
- `calibrate_vpin.py` (re-run when CB depth grows materially)
- `calibrate_liq.py` (re-run as perp corpus grows)
- `calibrate_funding.py` (skips until ≥30 cycles ~ 10 days uptime)
- `calibrate_oi.py` (skips until ≥240 obs ~ 2 hours of cumulative
  uptime per asset/venue)
- `calibrate_vol_target.py` (re-run any time corpus grows ≥2×)

### Launch carry-over (still pending — needs user hardware/accounts)

- **AWS §1.5 backend systemd**
- **AWS §2 VAPID push + phone test**
- **AWS §3 Discord bot deploy** (Developer Portal + token + channel ID)
- **AWS §5 end-to-end smoke test** (7-item checklist)
- **Verify PWA loads on phone** (30s test)
- **Rotate GoDaddy API key** (exposed earlier in transcripts)
- **Fix AWS MCP for Claude Code** (separate from Desktop install)

### Hardcodes accepted as policy this session (don't relitigate)

Add to the existing list:
- OI monitor / CB premium: `BUILD_Z=2.0 / CLEAR_Z=1.0 / HOT_Z=2.0`
  — sigma cuts, match basis_monitor convention.
- Vol-target: `VOL_MULT_MIN=0.5 / VOL_MULT_MAX=2.0` — risk caps.
- Carry analyzer: `MIN_NET_APR_FOR_OPPORTUNITY=0.03` — opportunity
  threshold.
- Carry trade hold: `max_hold_minutes=480` (one funding cycle) —
  policy default; real desks roll for weeks but the paper cell is
  intentionally short-horizon for now.

### First-message script for next agent

When the user's first message is a continuation cue, respond with
something like:

> "Picked up at `fe34fcd` on phase-2. Tiers 1-3 + Pass-6 + hardcode
> reevaluation all shipped this session. Want me to (a) start Tier 4
> (BTC→ETH lead multiplier or calendar awareness), (b) start Tier 5
> (Hurst/DFA, Hawkes wash, or Cont-Kukanov OFI), (c) wire hawkes_eta
> into the regime classifier with a Pass-7 evaluator, (d) build the
> BTC perp-lead minute-level evaluator (~100 LOC, most robust signal),
> or (e) AWS §1.5?"

— end of 2026-05-07 evening update —

## 2026-05-07 late-evening session update — Tier 4 + Tier 5 + Pass-7 + F10

Continuation session on `claude/continue-phase-2-pipeline-UFiGY`.
Shipped Tier 4 (cross-asset + calendar) + Tier 5.3 + 5.1 (Hurst, Hawkes
wash) + Pass-7 evaluator extension + F10 (hawkes_multiplier).

### Branches at end of session

| Branch | Tip | Notes |
|---|---|---|
| `claude/continue-phase-2-pipeline-UFiGY` (active code) | `<see latest>` | All session work pushed here |
| `data/eth-bins` | `0b5e2c0` | Advanced from 30c27bc earlier same day |
| `data/btc-bins` | `7bb1c29` | Force-pushed; advanced from b5d4142 |

### Commits this session

| Commit | What |
|---|---|
| `b9764c5` | **Tier 4.1** F7 cross-asset directional confirmation multiplier |
| `043fb00` | **Tier 4.2** F8 scheduled-event + weekend confidence dampener (event_calendar.py + events_calendar.json) |
| `906e405` | **Tier 5.3** Hurst exponent (DFA-1) per chunk + classifier label |
| `2a7bfa6` | **Tier 5.1** Hawkes wash detection (Regime.WASH_HAWKES override) |
| `<F10 commit>` | **F10** hawkes_multiplier on directional regimes + Pass-7 evaluator extension + calibrate_hawkes_eta.py + hawkes_eta_calibration.json |

### Confidence multipliers stack

`adjusted_confidence` is now `confidence × cross-venue × vpin × cross-asset × event × hawkes`. Applied consistently in:
- `ClassificationResult.adjusted_confidence` property
- Backend `_poll_one` → SignalEvent emit (both production + demo paths)
- `_apply_cross_venue_F6` post-poll status formula

### Pass-7 evaluator (extends phase1_5_evaluator)

Per-(asset, venue, regime) feature distributions for `hawkes_eta`,
`hawkes_eta_buy`, `hawkes_eta_sell`, `hurst`, `|mean_dipole|`, plus
hurst_label counts. Two sub-cell Gate I splits:
- η-tier (low/mid/high at p33/p67)
- hurst-label (trending/reverting/random)

CLI: add `--features-out PATH` to dump JSON; `--subcell-min-n N` to
control the sub-cell threshold.

### Pass-7 ETH headline findings

KR-ETH WHALE_UP (n=65, aggregate r=−0.31, p=0.01) splits as:
- η-tier mid (n=28): **r=−0.564 p=0.001** — 2× the aggregate signal
- η-tier low (n=22): r=+0.04 (no signal)
- hurst random subset (n=15): r=−0.43 p=0.09

KR-ETH WASH_HAWKES (n=58, aggregate r=+0.22, p=0.10) splits as:
- η-tier high (n=18): r=+0.43 p=0.06 — wash-tagged chunks with
  strongest bilateral clustering show momentum bias. Surprising.
  Either the override threshold is slightly loose OR there's
  residual structure in apparently-wash chunks.

Per-cell η distributions confirm regime-dependence:
- KR-ETH EQUILIBRIUM η p25/p75 = 0.16 / 0.49
- KR-ETH WHALE_UP   η p25/p75 = 0.33 / 0.50
- KR-ETH WASH_HAWKES η p25/p75 = 0.50 / 0.53

This is why `calibrate_hawkes_eta.py` restricts to *directional* regimes
when computing thresholds — venue-wide percentiles would just relabel
WHALE as "high η" and EQUILIBRIUM as "low η" with no information gain.

BTC Pass-7 was killed mid-run (BTC corpus is ~17× ETH; full Gate I
sub-cell evaluation was estimated >50 min). The `calibrate_hawkes_eta.py`
script does the much-cheaper work of just extracting η per directional
chunk and computing p25/p75; that ran on the full corpus and produced
`hawkes_eta_calibration.json`.

### F10 hawkes_multiplier

ClassificationResult gains `hawkes_multiplier: float = 1.0`.
`classify_regime` accepts `hawkes_elevated` / `hawkes_diffuse` kwargs
(literature priors 0.45 / 0.20 by default). Applied only to directional
regimes (mirrors VPIN's policy):
- η ≥ p75 (elevated): boost 1.15 (clustered cascade)
- η ≤ p25 (diffuse): dampen 0.85 (scattered/Poisson)
- else: 1.0

Backend loads `hawkes_eta_calibration.json` at module load via
`_load_hawkes_calibration()` and passes per-(asset, venue) p25/p75
into `classify_regime`. Falls back to literature defaults when the
file is missing or an entry is absent.

### Threshold revisits (no changes warranted)

Pass-7 ETH validated current thresholds:
- **WASH_HAWKES rule**: combined η ≥ 0.40, min(η_buy, η_sell) ≥ 0.30,
  |dipole| < 0.20. The wash-tagged distribution shows η~0.50, both
  sides ~0.50, |dipole|p50=0.08 — well-separated from non-wash.
  21–27% reclassified rate is high but reflects real bar-resolution
  wash-like activity. Keep current values.
- **Hurst label thresholds**: 0.55 trending / 0.45 reverting. Pass-7
  shows ~47/28/25 split (trending/reverting/random) on both venues —
  balanced. Keep current values.

Hawkes elevated/diffuse defaults (0.45 / 0.20) backed by Pass-7 ETH
directional cells; refresh per-(asset, venue) once
`hawkes_eta_calibration.json` accumulates more BTC data.

### Open follow-ups for the next agent

- **WASH_HAWKES Gate I momentum bias**: the n=18 sub-cell with
  r=+0.43 p=0.06 deserves a Pass-8 with more data. If it holds at
  larger n, it's either a tradeable signal or a sign the threshold
  needs tightening (perhaps WASH_HAWKES_BOTH_SIDES_MIN > 0.30).
- **BTC Pass-7 sub-cell Gate I**: never landed (corpus too large
  this session). Run `python phase1_5_evaluator.py --asset BTC
  --cb-bins btc_coinbase_bins.json --kr-bins btc_kraken_bins.json
  --multi-signal-pelt --features-out pass7_btc_features.json` when
  there's a 30+ min uninterrupted runtime budget.
- **Hawkes per-regime thresholds**: current calibration uses a single
  p25/p75 per (asset, venue) over all directional chunks. A finer
  variant (per regime within (asset, venue)) would let WHALE_UP's
  multiplier respond differently from HERD_UP's. Defer until per-
  regime n is large enough.
- **Tier 5.2 / 5.4** (spoofing, real Cont-Kukanov OFI): both still
  blocked on collector schema upgrade (need L1 book-state deltas).
- **AWS §1.5** + everything below it (still pending).

### Hardcodes accepted as policy this session (don't relitigate)

- F7 cross-asset multiplier band: 1.4 / 0.6 (tighter than F6's 1.5 / 0.5).
- F8 event/weekend dampener: 0.7 (±30 min event), 0.85 (±60 min OR weekend).
- F9 Hurst label thresholds: 0.55 trending / 0.45 reverting; HURST_MIN_RETURNS_FOR_LABEL=8.
- F10 Hawkes multiplier band: 1.15 / 0.85; defaults 0.45 / 0.20 (refreshed by calibration).
- WASH_HAWKES override: η_combined≥0.40 AND min(η_buy,η_sell)≥0.30 AND |dipole|<0.20; only overrides EQUILIBRIUM_TWO_SIDED.
- WASH_CANDIDATE_ETA_FLOOR=0.30 in hawkes.py (per-side fits gated on combined η to keep cost down).

### First-message script for next agent

> "Picked up at `<F10 tip>` on phase-2. Tier 4 + 5.3 + 5.1 + Pass-7 +
> F10 all shipped. Want me to (a) Pass-8 with more data (WASH_HAWKES
> momentum sub-cell follow-up), (b) BTC perp-lead minute-level
> evaluator (~100 LOC, most robust signal in the project), (c) AWS
> §1.5 backend systemd, or (d) something else from the deferred list?"

— end of 2026-05-07 late-evening update —
