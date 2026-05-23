# Markets / frontend — LiveTape rebuild handoff

**Date**: 2026-05-15
**From**: Architect (Claude Opus 4.7, web session — Greg's "desktop" session)
**To**: Next session (any Claude — desktop chat, Claude Code, Cowork)
**Working tree**: `E:\Markets`, branch `claude/run-pass-14-classifier-nTViL`
**Status**: Working tree rolled back to Claude Code's handoff state. Product decision needed before more code work.

---

## TL;DR

1. Working tree is byte-identical to where Claude Code (the prior session) left it. Nothing this session produced is on disk anymore.
2. Code finished the RegimeCard → TapeDetail navigation PR cleanly. **Do not redo it.**
3. The LiveTape rebuild Code handed off was attempted in this session and reverted because of a product conflict that needs Greg's call.
4. The product conflict, plain language: the current live `RegimeCard` (commit 521afba, "phase 1.5e+ live tape pulse") embeds an expanded inline view with chart, chunk bar, BID/ASK cells, and a "Tap for live tape →" link. The `markets_mockup.html` `RegimeCard` is much simpler — just regime chip + three metric tiles (DIPOLE / REAL VOL / CONF) + cross-venue status + timestamp. The rebuild target for `LiveTape` (mockup's "Live tape" panel) duplicates a lot of what the live `RegimeCard` already shows. Putting both on the same page (which the Live tab does, with the "show live tape" toggle) produces visual redundancy that Greg flagged as "completely off."
5. Ask Greg the question in the next section, get his answer, then write code. Do not produce code first.

---

## The one question to ask Greg before any code

> "The live app's RegimeCard already has an expanded view with chart, chunk bar, BID/ASK cells, and a 'Tap for live tape' link. The mockup's RegimeCard is the simpler version with just the metric tiles. Which RegimeCard do you want on the Live tab — the rich live one, or the simple mockup one? And should the LiveTape panel show inline on the Live tab at all, or only on the `/tape/:asset/:venue` drill-down page?"

His answer collapses to one of three implementations:

- **Option A — Mockup RegimeCard, LiveTape on drill-down only.** Strip RegimeCard back to the simple mockup version (delete the chart, chunk bar, embedded ClickableQuote, "Tap for live tape →" inline CTA). Remove the "show live tape" toggle from Live tab. LiveTape renders only on `/tape/:asset/:venue`. **Largest scope** — touches RegimeCard, LiveStatus, undoes a chunk of phase 1.5e+ work. Get explicit OK before deleting.
- **Option B — Keep rich RegimeCard, LiveTape on drill-down only.** RegimeCard unchanged. Remove the "show live tape" toggle from Live tab. LiveTape renders only on `/tape/:asset/:venue`. **Smallest scope** — one toggle removed in LiveStatus, no RegimeCard changes.
- **Option C — Both inline, but LiveTape is minimal when inline.** Add a `compact` prop to LiveTape. When `true` (inline on Live tab), render only the table + flow callout. When `false` (default, on /tape), render the full mockup version. **Medium scope** — fork LiveTape's render, keep both panels, avoid the duplicate BID/ASK.

The next session should not pick an option for him. Greg knows the product better than any of us.

---

## What's in the working tree right now

After rollback. From `git status -s`:

```
M  frontend/package-lock.json            (npm install side effect, drop or keep)
M  frontend/src/App.jsx                  (route registration)
M  frontend/src/components/RegimeCard.jsx (nav + CTA + stopPropagation)
M  frontend/src/pages/Onboarding.jsx     (one paragraph added)
?? frontend/src/pages/TapeDetail.jsx     (Code's new file)
?? frontend/mock_backend.py              (Code's dev tool)
?? .claude/launch.json                   (Code's dev tool entry)
```

`LiveTape.jsx` and `ClickableQuote.jsx` are unchanged from commit 521afba. The `.bak` files this session created during its attempt have been used to restore the prior state. The `.bak` files themselves may still be on disk — safe to delete with:

```powershell
del frontend\src\components\LiveTape.jsx.bak
del frontend\src\components\ClickableQuote.jsx.bak
del frontend\src\pages\TapeDetail.jsx.bak
```

Nothing is committed. Branch tip is still `c5358b9 Pass-19 fresh-data analysis artifacts (supersedes stale-data run)`.

---

## DO NOT REDO — the navigation PR Code already finished

These four file changes in the working tree are correct and tested. Greg verified them in the browser before this session started.

- **`App.jsx`** (+2): registers `<Route path="/tape/:asset/:venue" element={<TapeDetail />} />` after the `/signal/:id` route.
- **`RegimeCard.jsx`** (+39 −9): outer div uses `role="link"` + `useNavigate` (NOT `<Link>`, because button-in-anchor is invalid HTML — the embedded `ClickableQuote` uses `<button>`). The `ClickableQuote` inside is wrapped in `<div onClick={e => e.stopPropagation()}>` so cell taps open the order ticket without triggering navigation. Card has an inline "Tap for live tape →" CTA with `mt-2 pt-2 border-t border-white/5`. **Note: this CTA is part of the rich expanded RegimeCard. Option A would delete it.**
- **`TapeDetail.jsx`** (NEW): back link on the left, regime chip on the right (looked up from `useStore`), renders `<LiveTape asset={asset} venue={venue} regime={regime} />`. Pair label is NOT in TapeDetail because baseline LiveTape has its own pair header. Don't add a second one.
- **`Onboarding.jsx`** (+4): one paragraph mentioning the drill-down, right after the intro.

These are the entire navigation PR. Don't touch them for Option A/B/C unless Greg explicitly asks. Option A is the only one that would partially modify RegimeCard (to strip the rich inline view), and only with his sign-off.

---

## The six gaps Code identified between mockup and baseline LiveTape

For when Greg picks an option and the implementation starts. Verbatim from `HANDOFF_TO_DESKTOP_LIVETAPE.md`:

| # | Gap | Mockup has | Baseline `LiveTape.jsx` has |
|---|---|---|---|
| 1 | Pair header | Single "BTC-USD on coinbase" + "regime: WHALE ↑" on the right | LiveTape renders its own header with pair + price + "last N min · live" |
| 2 | BID/ASK cell sizing | Big, full-width with size + tap-to-buy/sell hint | `text-2xl` truncates "$106,847.10" on mobile; no size or action-hint labels |
| 3 | Spread + last-hit line | `spread 0.20 · 1.6 bp` left, `last hit: ask · 0.4s ago` right | Not present |
| 4 | Per-minute table layout | `Min | Buy vol (bar+number) | Sell vol (bar+number) | Trd | Price` with inline numeric labels | `[time | sell-bar | buy-bar | trades | total-volume]` — centerline split, no inline numbers, no price column |
| 5 | Bottom callout | Green box: "Buy flow dominant 4/6 min. 1m vol 15.6 BTC · taker buy 79%." | Not present |
| 6 | Error state stickiness | n/a (mockup is static) | If `/api/chart` fails once, `error` is set and never cleared on later successful fetches |

If Option C is chosen, the inline-mode LiveTape skips gaps 1, 2, 3 (no pair header, no BID/ASK cells, no spread row) and addresses only 4, 5, 6. The `/tape` page renders the full version with all six fixed.

---

## What this session tried and why it didn't ship

The web session that produced this handoff attempted to close Code's six gaps in `LiveTape.jsx` plus restyle `ClickableQuote.jsx` to match the mockup's neutral-slate cell design. Three iterations of file changes were produced:

1. **First pass**: full LiveTape rebuild, ClickableQuote restyle, TapeDetail given a pair header. Greg copied them in. Visual rendered close to mockup but missing the pair header anchor and with sticky-error behavior intact.
2. **Second pass**: addressed Code's `whitespace-nowrap tabular-nums` + `px-4` notes; moved pair header into TapeDetail meta row; matched Code's `regime` prop name. Greg copied them in.
3. **Third pass**: moved pair header back into LiveTape itself (so it appears whether rendered inline on Live tab or on `/tape`). Greg copied them in.

After the third pass, Greg's screenshot showed the LiveTape panel rendering correctly with pair header — but stacked below the rich RegimeCard expanded view, producing the duplicate BID/ASK / duplicate flow info / cluttered page that prompted his "completely off" call.

**The session's mistake** was producing code on the assumption that the LiveTape rebuild was the whole job, when in fact the mockup-vs-live product conflict was the real blocker. Three rounds of code changes were correct against the literal asks but did not solve the underlying problem. The next session should not repeat this — ask the product question first.

---

## Locked design decisions (carry forward, do not re-litigate)

From earlier sessions in this arc. These are constraints.

1. **Regime color palette is final.** WHALE_UP green #22c55e, WHALE_DOWN red #ef4444, HERD_UP orange #f97316, HERD_DOWN rose #b91c1c, EQUILIBRIUM_TWO_SIDED blue #3b82f6, WASH_PAIRED yellow #eab308, DEPLETED gray #9ca3af, UNKNOWN slate #6b7280. Match `REGIME_STYLES` in `RegimeCard.jsx` and `signal_poster.py`.
2. **Bid/ask flash semantic is final.** Buy aggressor lifts the offer → ASK cell flashes red. Sell aggressor hits the bid → BID cell flashes red. The side consumed flashes. Matches Bloomberg / IBKR / Reuters. Do not invert.
3. **Flash is 350ms ease-out red.** `@keyframes tape-flash` in `index.css` is canonical.
4. **Drill-down affordance is explicit text ("Tap for live tape →")**, not a chevron. Inside RegimeCard's bottom row with thin top border separator. Onboarding mention is the secondary affordance.
5. **Executor / signal feed split is the product's regulatory moat.** The signal feed (app + Discord) is read-only research. Trading happens via `executor/executor.py` running locally on each friend's machine with their own exchange API keys. Capital and keys never touch the signal-feed infrastructure.
6. **Terminal log colors are a separate namespace from regime colors** (relevant only if an executor log dashboard ever gets built). SIGNAL = neutral white (label, not outcome), OPEN = blue, CLOSE = orange, DENY = red, ✓ = green, prices = amber, dim = gray.

---

## The mock backend missing-size note (for when the rebuild does ship)

The mockup shows `0.847 BTC` / `1.232 BTC` size lines under the BID and ASK prices. `mock_backend.py` does not currently return `bid_size` / `ask_size` fields on `/api/chart`. The rebuild's ClickableQuote should treat these as optional — if the fields are absent, hide the size line so the layout stays clean. For dev-preview pixel parity with the mockup, add hardcoded sizes (e.g. `"bid_size": 0.847, "ask_size": 1.232`) to the mock backend's chart response. The next session should read `mock_backend.py` directly from `E:\Markets\frontend\mock_backend.py` to make this change.

---

## Suggested opening prompt for the next session

Paste this into the next chat verbatim:

> I'm picking up a markets-watch React frontend handoff at `E:\Markets`. The prior session is at `HANDOFF_LIVETAPE_SESSION_2.md` (in the repo root) — read it first. Then ask me the one product question at the top of that doc. After I answer, implement only the option I pick. Do not produce code until I've answered.

---

## Save locations for this handoff

- `E:\Markets\HANDOFF_LIVETAPE_SESSION_2.md`
- `F:\Factory\knowledge\markets\HANDOFF_LIVETAPE_SESSION_2.md`

Per the standing rule: any knowledge artifact gets saved to E:\ and mirrored to F:\Factory\knowledge\ so the factory orchestrator can read it.
