# DavisAI Markets Dashboard (Mission Control read plane)

The control-plane UI for the trading platform, built per `DASHBOARD_HANDOFF_S100.md` and
`research/kalshi/TWO_COACH_SPEC_S100.md`. v1 is the READ PLANE: a replay/as-of console over
the real stores. The executor toggle / structured-intent lane comes LAST (Greg, 2026-07-20)
and nothing here holds credentials or routing authority in the browser.

## Run (from the repo root)

    pip install fastapi uvicorn
    python -m uvicorn dashboard.server:app --host 127.0.0.1 --port 8100

Open http://127.0.0.1:8100/. The server must run with the repo root as CWD (the signal core
reads `data/` relative paths). API docs at `/api/docs`.

## Layout

    dashboard/
      server.py            FastAPI app: /api/v1 snapshots + serves frontend/
      adapters/            read-only bridges to the signal core (never edits it)
        paths.py           repo paths + explicit AWS creds (container placeholders ignored)
        brain.py           ng_brain.json inventory (provenance carried per play)
        decision.py        decision_state per day, blockwise-guarded fallback
        lagmap.py          feed M per-cell windows (the anti-fixed-constant source)
        fees.py            kalshi_fill_model wrapper (maker-first framing)
        market.py          Kalshi candles (both schema vintages) + NYMEX minute bars
        health.py          data-plane truth: stores present, creds, live-feed reality
        novel.py           Novel Edge Lab registry, local readiness, and 48h watch clocks
      novel_candidates.json canonical preregistered candidate + balance-mode registry
      frontend/            the S100 prototype (visual language preserved) + adapter.js
        novel.js           additive Novel navigation/view and separate candidate cards
        novel.css          Novel panel styles using the existing S100 design tokens
      data-contracts.md    proposed canonical event contracts (from the prototype bundle)

## Novel Edge Lab

The Novel panel is a read-only research and readiness surface. It does not score or route
trades. It shows one separate card per preregistered candidate with:

- structural or predictive status;
- ordinal potential, causal defensibility and testability;
- exact causal clock and permitted instruments;
- required local stores and existing supporting code;
- use conditions and kill test;
- balance convention (`PAYOFF_NEUTRAL`, `DELTA_NEUTRAL`, `INVENTORY_SKEWED`,
  `DIRECTIONAL`, or `WATCH_ONLY`);
- dynamically generated ET watch windows for the next 48 hours.

Endpoint: `GET /api/v1/novel/candidates`.

Every candidate is emitted with `execution_enabled=false`. Authority is restricted to
`WATCH_ONLY` or `SHADOW`. A structural seam is not labeled realized arbitrage, and a
predictive candidate is not labeled proven edge.

The baseline `index.html` remains untouched. `dashboard.server` injects `novel.css` and
`novel.js` when serving `/`, allowing the panel to coexist with Claude's current dashboard
wiring without replacing the S100 shell.

## Truth badges (every panel carries one)

- REAL DATA - backed by an actual store on this machine.
- AWAITING DATA - the store exists on S3 but is not in the local cache (or no AWS creds).
- SIMULATED - prototype placeholder; no real counterpart exists yet (executor lane is last,
  coach emit feed does not exist yet).

The Novel panel additionally distinguishes `WIRED INPUTS`, `PARTIAL INPUTS`, and
`AWAITING DATA`. These describe local input readiness, not edge validation.

## Doctrine bound into the UI

- Per-event rows, never pooled means as headlines.
- Ledgers never pooled (NYMEX / Kalshi / future lanes); Polymarket = CONTEXT-ONLY.
- Expected repricing windows come from the lag map per cell (ATM med ~112-180s this regime),
  never the fixed winter 7-20s constant.
- Maker-first economics; taker reserved for the >=4c fast tail; maker fills are BOUNDS ONLY.
- Every play shows brain provenance (status, forward_evidence, requires, scope).
- Missing data renders as missing (missing==None doctrine); nothing interpolated.
- Novel candidates remain preregistered and non-executable until their own untouched-forward,
  rule-identity, cost and latency gates pass.
- Buy and sell sides are balanced by the intended risk, not equal dollars or equal order count.

## AWS

Data plane: S3 `bento-568968024170-us-east-2-an` via `platform_sync.py` pulls into `data/`.
Credentials resolve from `scratchpad/aws.env` or `~/.aws/credentials` ONLY - the cloud
container's placeholder `AWS_*` env vars are deliberately ignored (see CLAUDE.md "AWS KEY").
Deploy target is AWS (app service + static assets + SSE endpoint per the prototype handoff);
the server is self-contained and environment-driven so it moves to a box unchanged.

## Not yet wired (deliberate order)

1. S3 store pulls (needs the key pair on this machine).
2. Kalshi follower overlay on the leader chart (candle join).
3. The signal-core emit feed (one voice per target) - the opportunity queue stays SIMULATED
   until that feed exists; the dashboard never elects owning plays itself.
4. Live SSE from an AWS box collector.
5. Executor toggle + structured intents (LAST; server-side risk pipeline, browser holds nothing).
6. Novel exact-rule canonicalizer and cross-wrapper executable-book scanner.
7. Novel CME narrow-vertical digital builder and contract-month/source normalizer.
8. EIA-930 first-vintage/revised-vintage archival seam and causal timestamp audit.
9. Session-preserving five-step agnostic-coupler runner with untouched-forward exploitability.
