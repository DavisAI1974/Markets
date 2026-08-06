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

## Demo-first wiring (S114)

The dashboard now loads a versioned demonstration opportunity feed before any firing mechanism
is connected. The demo layer is additive and read-only:

- `/api/v1/signals/in-use?day=YYYYMMDD` reads `research/kalshi/SIGNALS_IN_USE.json` and joins
  each consumed signal definition to its real as-of `decision_state` value when available.
- `/api/v1/demo/opportunities?day=YYYYMMDD` returns demonstration rows bound to named consumed
  signals. Economics and clocks are illustrative and every row has `execution_authority=NONE`.
- `/api/v1/demo/credentials` reports only whether server-side Demo credential variables are
  present. It never returns an API key ID, private-key path, or private-key content.
- `frontend/signals_demo.js` replaces the prototype opportunity queue and state tape with those
  API responses and disables execution-looking controls.

Optional server-side variables for the next authenticated-read stage:

    KALSHI_DEMO_API_KEY_ID=...
    KALSHI_DEMO_PRIVATE_KEY_PATH=/run/secrets/kalshi-demo-private-key.pem

Do not commit either value. The current build makes no authenticated Kalshi request and exposes
no create, amend, decrease, cancel, or route endpoint.

Future firing design and code are documented in `dashboard/KALSHI_EXECUTION_FIRING_MECHANISM.md`.

## Layout

    dashboard/
      server.py            FastAPI app: /api/v1 snapshots + serves frontend/
      adapters/            read-only bridges to the signal core (never edits it)
        paths.py           repo paths + explicit AWS creds (container placeholders ignored)
        brain.py           ng_brain.json inventory (provenance carried per play)
        decision.py        decision_state per day, blockwise-guarded fallback
        signals.py         SIGNALS_IN_USE definitions joined to as-of values
        demo.py            versioned demonstration opportunities, no execution authority
        lagmap.py          feed M per-cell windows (the anti-fixed-constant source)
        fees.py            kalshi_fill_model wrapper (maker-first framing)
        market.py          Kalshi candles (both schema vintages) + NYMEX minute bars
        health.py          data-plane truth: stores present, creds, live-feed reality
      frontend/            the S100 prototype + adapter.js + demo-first signals_demo.js
      data-contracts.md    proposed canonical event contracts (from the prototype bundle)
      KALSHI_EXECUTION_FIRING_MECHANISM.md

## Truth badges (every panel carries one)

- REAL DATA - backed by an actual store on this machine.
- AWAITING DATA - the store exists on S3 but is not in the local cache (or no AWS creds).
- SIMULATED / DEMO FEED - demonstration layer with no order authority.

## Doctrine bound into the UI

- Per-event rows, never pooled means as headlines.
- Ledgers never pooled (NYMEX / Kalshi / future lanes); Polymarket = CONTEXT-ONLY.
- Expected repricing windows come from the lag map per cell (ATM med ~112-180s this regime),
  never the fixed winter 7-20s constant.
- Maker-first economics; taker reserved for the measured fast tail; maker fills are BOUNDS ONLY.
- Every play shows brain provenance (status, forward_evidence, requires, scope).
- Missing data renders as missing (missing==None doctrine); nothing interpolated.
- A demo opportunity never becomes an executable call by being displayed.

## AWS

Data plane: S3 `bento-568968024170-us-east-2-an` via `platform_sync.py` pulls into `data/`.
Credentials resolve from `scratchpad/aws.env` or `~/.aws/credentials` ONLY - the cloud
container's placeholder `AWS_*` env vars are deliberately ignored (see CLAUDE.md "AWS KEY").
Deploy target is AWS (app service + static assets + SSE endpoint per the prototype handoff);
the server is self-contained and environment-driven so it moves to a box unchanged.

## Not yet wired (deliberate order)

1. Authenticated Kalshi Demo reads (key is intentionally not required for the first UI pass).
2. S3 store pulls on the deployment box.
3. Kalshi follower overlay on the leader chart (candle join).
4. The signal-core canonical emit feed (one voice per target).
5. Live SSE from an AWS box collector.
6. Firing-policy service and immutable structured intents.
7. Kalshi Demo executor and reconciliation service.
8. Production execution review (LAST; separate credentials and approval).
