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

— end of handoff —
