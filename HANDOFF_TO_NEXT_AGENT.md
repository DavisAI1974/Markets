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
