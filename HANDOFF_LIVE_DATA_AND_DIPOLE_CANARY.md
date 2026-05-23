# Handoff: Live Data POC + Dipole Canary Research

Date: 2026-05-15

## Current Product State

We have a working live-data proof of concept for `markets-watch`.

The app is no longer just static mock cards. The live stack has been wired locally:

- Frontend Vite app running on a local browser port, most recently `http://localhost:5174`
- Backend FastAPI running on `http://localhost:8000`
- Live collectors running through `live_collectors.py`
- Coinbase, Kraken, and Bybit data paths are present
- Bybit is included and has been used for the tape route
- Discord bot can post market signal summaries and tape links into the `markets-watch` server

The live app has already been viewed locally and over a Cloudflare tunnel on a phone. The phone path initially showed no data because the frontend needed a preload/live-data path, but that was fixed enough to show data. Keep validating mobile after any route/API change.

Important: mock data may still exist for practice/demo surfaces, but the product direction is live-data-first. Do not optimize around temporary mock data.

## Core Product Vocabulary

Trader-facing language should stay simple and intuitive:

- Whale
- Herd
- Equilibrium

Do not expose internal terms like `dipole` to traders. The user explicitly said traders do not need to see dipole and it will not make sense to them. Internally, dipole remains important.

The trader rationale is:

- If one big player is throwing weight around, strategy is different.
- If the herd is moving, strategy is different.
- The product should help distinguish those states quickly.

## Live Data Next Step

The immediate next product priority is to test with live data running continuously.

Goals:

1. Keep collectors running and confirm the app populates from live Coinbase/Kraken/Bybit reads.
2. Verify BTC and ETH routes across venues.
3. Verify tape pages continue to populate on desktop and phone.
4. Confirm bid/offer cells still flash when hit/lifted.
5. Confirm Signals, History, Stats, and Discord posts are driven by live backend state rather than static demo fixtures.
6. Start logging live signal outcomes so we can evaluate whether Whale/Herd/Equilibrium reads are useful in practice.

Likely useful commands from the prior session:

```powershell
cd E:\Markets
python live_collectors.py --reset --save-interval 2 --keep-seconds 21600
python -m uvicorn backend.api_server:app --host 0.0.0.0 --port 8000
cd frontend
npm run dev -- --host 0.0.0.0
```

The exact running ports may differ if another Vite process is already active.

## Discord State

The Discord bot code was updated in `discord_bot/signal_poster.py`.

The bot successfully logged in and posted to the user-created Discord server:

- Server: `markets-watch`
- Channel: `#signals`

It posted examples including:

- Recent signal stats
- Tape link to the Bybit BTC tape route

If continuing Discord work, preserve the split:

- Discord should be concise and alert-like.
- Mobile/web app should be richer and more exploratory.
- They should share the same vocabulary and confidence logic.

## Dipole Canary Insight

The user had an important insight: dipole looked weak as a direct trade signal, but maybe we looked at it wrong.

New hypothesis:

> Dipole may be a canary in the coal mine: an early warning that pressure is forming before Whale or Herd becomes obvious.

We investigated this by reframing the analysis away from "is dipole a standalone trade signal?" and toward "does internal dipole pressure lead same-direction Whale/Herd regimes?"

Created files:

- `dipole_canary_analysis.py`
- `pass20_dipole_canary_out/dipole_canary_report.md`
- `pass20_dipole_canary_out/dipole_canary_results.json`

Verification run:

```powershell
cd E:\Markets
python dipole_canary_analysis.py --output-dir pass20_dipole_canary_out
python -m py_compile dipole_canary_analysis.py
```

## Dipole Canary Findings

The insight is directionally supported.

Best overall framing:

- Dipole is not a trader-facing signal.
- Dipole is an internal early-warning/watch state.
- It can give us a jump before Whale/Herd confirms.

Key results:

- Moderate non-strong dipole with volume confirmation was cleanest:
  - Next 2 chunks:
    - Base same-direction Whale/Herd rate: `13.43%`
    - Volume-confirmed `abs(mean_dipole) >= 0.30`: `28.24%`
    - Lift: about `2.1x`
    - Average signed return: `+2.93 bps`

- Weak-only dipole also worked as a watch state:
  - Persistent weak band `0.15-0.25`
  - Next 2 chunks:
    - Hit rate: `20.76%`
    - Base: `13.43%`
    - Lift: about `1.55x`
    - Positive signed return

- Cross-venue weak dipole confirmation looked especially interesting on BTC:
  - BTC weak band `0.15-0.25`
  - Same-direction pressure on at least two venues
  - 45-minute horizon:
    - Base: `31.58%`
    - Hit: `48.15%`
    - Lift: `1.525x`

## Product Recommendation For Dipole

Do not display `dipole`.

Instead, treat it as internal intelligence that can surface as:

- `Pressure forming`
- `Buy pressure forming`
- `Sell pressure forming`
- `Whale watch`
- `Herd watch`
- `Equilibrium under pressure`

This should be an amber light, not a trade button.

Suggested behavior:

- Weak dipole alone: quiet internal watch, maybe subtle UI state.
- Persistent weak dipole: visible watch state.
- Volume-confirmed moderate dipole: stronger watch state.
- Cross-venue same-direction dipole: high-priority watch state.
- Whale/Herd confirmation: actionable trader-facing signal.

This preserves Apple-like UX: simple surface, smart machinery underneath.

## AWS Note

The user asked about AWS MCP. No AWS MCP/connector is currently exposed in this chat.

AWS can still be handled later through local terminal/AWS CLI if credentials are configured. Do not jump to AWS yet. The agreed priority is:

1. Get live data solid.
2. Prove signal loop with live reads.
3. Then package/deploy to AWS.

Future AWS needs will likely include:

- Backend API hosting
- Frontend hosting
- Collector worker/service
- Persistent storage for live bins and signal outcomes
- Secrets handling
- Logs/monitoring
- Domain/TLS

## Important Working-Tree Caution

The repo has many dirty changes from the live-data and product work. Do not revert unrelated changes.

Observed dirty/new files from the prior session included:

- `backend/api_server.py`
- `discord_bot/signal_poster.py`
- multiple frontend files
- `live_collectors.py`
- `frontend/public/live-preload.js`
- `frontend/src/pages/TapeDetail.jsx`
- `frontend/src/marketReadCopy.js`
- `dipole_canary_analysis.py`
- `pass20_dipole_canary_out/`

Before editing, inspect the relevant files and work with existing changes.

## Paste Block For New Chat

```text
We are working in E:\Markets on the markets-watch product.

Current state:
- We have a live-data POC running locally.
- Backend FastAPI has been running on http://localhost:8000.
- Frontend Vite has been running around http://localhost:5174.
- Live collectors are wired through live_collectors.py.
- Coinbase, Kraken, and Bybit are included.
- Bybit tape route exists and has shown live data.
- Discord bot has posted into the markets-watch Discord server #signals channel.

Product direction:
- This is no longer mock-data-first. Mock data is temporary only.
- Next priority is live-data testing: keep collectors running, verify BTC/ETH and Coinbase/Kraken/Bybit populate, verify mobile, verify tape pages, Signals, History, Stats, and Discord are powered by live backend state.
- We want market-ready UX, as intuitive as an Apple product.

Trader-facing vocabulary:
- Keep Whale, Herd, and Equilibrium.
- Do NOT expose dipole to traders. It is internal.
- The user’s trading insight: strategy differs if a big player is moving the market versus the herd moving.

Dipole insight:
- User suspects dipole was misjudged as a weak direct trade signal.
- New hypothesis: dipole is a canary/early-warning signal before Whale/Herd confirms.
- I created:
  - dipole_canary_analysis.py
  - pass20_dipole_canary_out/dipole_canary_report.md
  - pass20_dipole_canary_out/dipole_canary_results.json
- Run with:
  python dipole_canary_analysis.py --output-dir pass20_dipole_canary_out

Dipole findings:
- Moderate non-strong dipole with volume confirmation was cleanest:
  next 2 chunks base same-direction Whale/Herd rate 13.43%, volume-confirmed abs(mean_dipole)>=0.30 hit 28.24%, about 2.1x lift, +2.93 bps avg signed return.
- Weak-only dipole works as a watch state:
  persistent weak band 0.15-0.25 hit 20.76% over next 2 chunks vs 13.43% base, about 1.55x lift.
- Cross-venue weak dipole is interesting, especially BTC:
  weak band 0.15-0.25 same-direction on at least two venues hit 48.15% within 45 minutes vs 31.58% base.

Product recommendation:
- Use dipole internally as an amber light:
  Pressure forming / Buy pressure forming / Sell pressure forming / Whale watch / Herd watch / Equilibrium under pressure.
- Do not make dipole a direct trade button.
- Weak alone = internal watch.
- Persistent weak = visible watch.
- Volume-confirmed moderate = stronger watch.
- Cross-venue same direction = high-priority watch.
- Whale/Herd confirmation = actionable signal.

AWS:
- No AWS MCP/connector is exposed in this chat.
- User wants AWS soon, but priority is live data first, then deployment packaging.

Important:
- Repo has many dirty changes from live-data work. Do not revert unrelated files.
- Inspect before editing.
```
