# markets-watch — UI / Discord preview

ASCII / markdown renders of what users see. Real screenshots require the
React app to render in a browser; these are layout-faithful textual
representations matching the actual code (`discord_bot/signal_poster.py`,
`frontend/src/pages/*`, `frontend/src/components/*`).

---

## Discord channel post — "Big seller detected" (WHALE_DOWN)

Plain-language headline, no math jargon. Top-of-book bid/ask plus the
absolute coin volume that traded on each side. No dipole, no realized
vol, no autocorrelation — those are the detector's internal features and
don't appear in the consumer-facing surfaces.

```
┌─[red bar]─────────────────────────────────────────────────┐
│ 🔴 Big seller detected — ETH-USD on KR                    │
│                                                           │
│ One big seller dominating. Piggyback short if early; sit  │
│ out if late. Watch for capitulation bottom.               │
│                                                           │
│   Price          Bid / Ask              Confidence        │
│   $2,341.93     $2,341.86 / $2,341.95   53% (✗ single)   │
│                                                           │
│   Buy / Sell volume                                       │
│   25% buy / 75% sell                                      │
│   buy 60.94  ·  sell 182.82                               │
│   total 243.76 ETH  ·  47 trades                          │
│                                                           │
│ signal_id=8c2f3a1b4e7d · research, not advice  · 16:50 UTC│
└───────────────────────────────────────────────────────────┘
```

## Discord channel post — WHALE→HERD cascade (single venue)

When a HERD signal fires immediately after a same-direction WHALE on the
prior chunk. `cascade_event` is set, the title gets the 🌊 prefix, the
playbook is replaced with the cascade-specific text, and confidence is
boosted ×1.3.

```
┌─[dark-red bar]────────────────────────────────────────────┐
│ 🌊 WHALE→HERD CASCADE — 🟤 HERD ↓ (panic) — ETH-USD on CB │
│                                                           │
│ [CASCADE: WHALE→HERD same direction] Whale-tripped        │
│ capitulation. Big seller's pressure broke retail stops;   │
│ herd is selling the fear. Highest-conviction short-side   │
│ cascade: short the cascade with a tight stop, OR wait for │
│ the fade-buy at exhaustion (volume drops, dipole flips).  │
│ Do NOT catch the falling knife mid-cascade.               │
│ (aggressor split: 40% buy / 60% sell (13081.30 units).)   │
│                                                           │
│   Dipole          Realized vol     Confidence             │
│   -0.212          19.0 bp          97% (✓ confirmed)      │
│                                                           │
│   Aggressor split                                         │
│   40% buy / 60% sell  (13081.30 units total)              │
│                                                           │
│   Cascade                                                 │
│   WHALE_DOWN chunk immediately preceding this HERD_DOWN;  │
│   whale-tripped-the-herd cascade (higher conviction)      │
│                                                           │
│   Why                                                     │
│   • rv=0.00190 (2.4x base) + vol_ratio=3.10 = cascade     │
│   • sustained 2-chunk HERD (1/2)                          │
│   • aggressor split: 40% buy / 60% sell (13081.30 units)  │
│                                                           │
│ signal_id=4e9b1c7a2f0d · research, not advice  · 15:03 UTC│
└───────────────────────────────────────────────────────────┘
```

## Discord channel post — CROSS-VENUE WHALE+HERD cascade

The strongest emit. One venue is WHALE, the other is HERD, same direction,
same wall-clock window. Confidence is forced to `min(1.0, primary*1.5)`,
title gets the double 🌊🌊 prefix, the venue field shows both venues
joined.

```
┌─[bright green bar]────────────────────────────────────────┐
│ 🌊🌊 CROSS-VENUE CASCADE — 🌊 CROSS-VENUE WHALE+HERD ↑ —  │
│ ETH-USD on KR+CB                                          │
│                                                           │
│ CROSS-VENUE WHALE+HERD UP: one venue shows whale-style    │
│ sustained buying, the other shows herd-style multi-actor  │
│ FOMO, same direction, same wall-clock window. Independent │
│ confirmation across venues = strongest long signal we can │
│ emit. Size accordingly. Tight stop; exit before the fade. │
│ (primary aggressor split: 81% buy / 19% sell.)            │
│                                                           │
│   Dipole          Realized vol     Confidence             │
│   +0.667          19.5 bp          100% (✓ confirmed)     │
│                                                           │
│   Aggressor split                                         │
│   81% buy / 19% sell  (986.46 units total)                │
│                                                           │
│   Cascade                                                 │
│   KR shows WHALE_UP; CB shows HERD_UP over the same wall- │
│   clock window — independent cross-venue WHALE+HERD       │
│   confirmation in direction UP                            │
│                                                           │
│   Why                                                     │
│   • KR shows WHALE_UP; CB shows HERD_UP over same window  │
│   • primary aggressor split: 81% buy / 19% sell           │
│   • primary=WHALE_UP, other=HERD_UP                       │
│                                                           │
│ signal_id=a1f3c9b7d4e2 · research, not advice  · 15:00 UTC│
└───────────────────────────────────────────────────────────┘
```

The push notification version (mobile lock screen / banner) is much
shorter — the SW formats it as `title=cascade_event, body=playbook[:120]`,
vibrates twice, and stays until tapped (`requireInteraction=true` for
cascade events).

```
┌─ markets-watch ────────────────────── now ─┐
│ 🌊🌊 CROSS-VENUE CASCADE — ETH on KR+CB    │
│ Independent cross-venue WHALE+HERD con-    │
│ firmation. Size accordingly. Tap to open.  │
└────────────────────────────────────────────┘
```

---

## Phone app — installed PWA, dark theme

After `Add to Home Screen` (iOS) or `Install app` (Android Chrome), the
PWA opens standalone (no browser chrome) with the icon on the home
screen. All screens use the existing dark slate theme
(`bg-slate-950 text-slate-100`).

### Screen 1 — Live Status (`/`, default)

`LiveStatus.jsx` renders one regime card + live tape per (asset, venue).
Each card is plain language + clickable bid/ask.

```
┌──────────────────────────────────────────────┐
│ Live   Signals   History   Stats   About     │ ← top tab nav
│                              [hide live tape] │
├──────────────────────────────────────────────┤
│  ETH                                         │
│  ┌──────────────────────────────────────┐    │
│  │ ETH-USD  on Coinbase  [Selling cascade] │
│  │                                      │    │
│  │ Last price            Confidence     │    │
│  │ $2,341.93             97%            │    │
│  │                                      │    │
│  │ ┌─ Sell · hit bid ─┐ ┌─ Buy · lift ─┐│    │
│  │ │   $2,341.86 (red)│ │  $2,341.95   ││    │
│  │ │  ← if last hit   │ │              ││    │
│  │ └──────────────────┘ └──────────────┘│    │
│  │ (each cell tap-target opens an order │    │
│  │  ticket pre-filled with that price)  │    │
│  │                                      │    │
│  │ Buy / Sell · this chunk    47 trades │    │
│  │ ████████████░░░░░░░░░░░░░░ 40% / 60% │    │
│  │ 5,232 ETH buy  ·  7,849 ETH sell     │    │
│  │                                      │    │
│  │ cross-venue: ✓ confirmed   16:18 UTC │    │
│  └──────────────────────────────────────┘    │
│                                              │
│  ┌─ Live tape · ETH-USD on Coinbase ───┐    │
│  │ ETH-USD on Coinbase  $2,341.93   live│   │
│  │ ┌─ Sell ─────┐ ┌── Buy ──────┐       │   │
│  │ │ $2,341.86  │ │  $2,341.95  │       │   │
│  │ └────────────┘ └─────────────┘       │   │
│  │                                      │   │
│  │ 16:18 ▌▌▌▌▌▌  ▌▌▌▌▌▌▌▌▌▌  18t 1.8k  │   │
│  │ 16:17 ▌▌▌  ▌▌▌▌▌▌▌▌▌▌▌▌▌▌  31t 3.2k  │   │
│  │ 16:16 ▌▌▌▌▌▌▌▌  ▌▌▌▌▌▌      14t 0.9k  │   │
│  │ 16:15 ▌▌  ▌▌▌▌▌▌▌▌▌▌         9t 0.4k  │   │
│  │       sell    buy       trades volume│   │
│  └──────────────────────────────────────┘   │
└──────────────────────────────────────────────┘
```

**Click-to-trade**: each bid and ask is its own large tappable cell.
Tapping opens an order-ticket modal with price locked, side locked,
and a size input. Confirming records a manual-trade intent in the
audit log; the user then executes on their own exchange. The PWA
never holds API keys or places real orders directly.

### Screen 2 — Signal Feed (`/signals`)

`frontend/src/pages/SignalFeed.jsx` lists all recent signals with the
SSE stream pushing new ones in. Cascade events get a 🌊 ribbon.

```
┌──────────────────────────────────────────────┐
│ Live   Signals   History   Stats   About     │
├──────────────────────────────────────────────┤
│  Recent signals · live                       │
│ ┌──────────────────────────────────────────┐ │
│ │ 🌊🌊 CROSS-VENUE CASCADE  · 15:00 UTC    │ │
│ │ ETH-USD  KR+CB  WHALE+HERD ↑             │ │
│ │ Conf 100%  · 81% buy / 19% sell          │ │
│ │ Independent cross-venue confirmation —   │ │
│ │ size accordingly. Tight stop.            │ │
│ ├──────────────────────────────────────────┤ │
│ │ 🌊 WHALE→HERD CASCADE  · 15:03 UTC       │ │
│ │ ETH-USD  CB  HERD ↓                      │ │
│ │ Conf 97% confirmed  · 40% buy / 60% sell │ │
│ │ Whale-tripped capitulation. Short the    │ │
│ │ cascade with tight stop OR wait for…     │ │
│ ├──────────────────────────────────────────┤ │
│ │ 🟢 WHALE ↑                · 15:00 UTC    │ │
│ │ ETH-USD  KR    Conf 70%                  │ │
│ │ Aggressor: 81% buy / 19% sell            │ │
│ │ Piggyback if early; get out if late.     │ │
│ ├──────────────────────────────────────────┤ │
│ │ 🔴 WHALE ↓                · 14:48 UTC    │ │
│ │ ETH-USD  CB    Conf 70% confirmed        │ │
│ │ Aggressor: 43% buy / 57% sell            │ │
│ │ One big seller dominating. Watch for…    │ │
│ └──────────────────────────────────────────┘ │
│                                              │
│ ⏵ tap a signal for full detail + outcome     │
└──────────────────────────────────────────────┘
```

### Screen 3 — Onboarding (`/about`) — push-subscribe banner

The `<PushNotifyButton/>` (committed in this batch) renders as a
green panel under the intro paragraphs:

```
┌──────────────────────────────────────────────┐
│ Live   Signals   History   Stats   About     │
├──────────────────────────────────────────────┤
│  What is markets-watch?                      │
│  It's a system that detects what kind of     │
│  energy state a market is in at any moment…  │
│                                              │
│  ┌─[emerald border]─────────────────────────┐│
│  │ Get pushed when a high-conviction signal ││
│  │ fires                                    ││
│  │                                          ││
│  │ Subscribe to web-push notifications:     ││
│  │ WHALE / HERD / WASH transitions and      ││
│  │ WHALE→HERD cascade events show up as a   ││
│  │ system notification within seconds.      ││
│  │                                          ││
│  │ [ ⏵ Notify me on new signals ]           ││
│  │                                          ││
│  │ permission: default · status: unsubscribed│
│  └──────────────────────────────────────────┘│
│                                              │
│  What the regime labels mean                 │
│  ▸ Equilibrium  — healthy two-sided trading  │
│  ▸ Whale ↑      — one big buyer …            │
│  …                                           │
└──────────────────────────────────────────────┘
```

After tapping, the browser shows the OS permission prompt:

```
┌──────────────────────────────────────────────┐
│  markets.example.com wants to send you       │
│  notifications.                              │
│                                              │
│         [ Block ]      [ Allow ]             │
└──────────────────────────────────────────────┘
```

If granted, the button switches to:

```
┌─[slate]──────────────────────────────────────┐
│ [ Notifications ON — tap to disable ]        │
│ permission: granted · status: subscribed     │
└──────────────────────────────────────────────┘
```

### Screen 4 — Stats (`/stats`)

Existing screen; no changes from this batch.

```
┌──────────────────────────────────────────────┐
│ Live   Signals   History   Stats   About     │
├──────────────────────────────────────────────┤
│  Last 24h                                    │
│  Signals fired:           14                 │
│  WHALE / HERD / Cascade:  8 / 4 / 2          │
│  Cross-venue confirmation rate:    71%       │
│  Avg adjusted confidence:          0.74      │
│                                              │
│  By regime                                   │
│  WHALE_UP        ████████      5             │
│  WHALE_DOWN      ██████        4             │
│  HERD_DOWN       ████          3             │
│  CASCADE         ███           2             │
└──────────────────────────────────────────────┘
```

### iOS install prompt

After the user opens the URL in Safari and taps Share → Add to Home
Screen, iOS shows an install dialog with the icon and the app title
from `manifest.json`:

```
┌──────────────────────────────────────────────┐
│  Add to Home Screen                          │
│                                              │
│   [icon-192]  markets-watch                  │
│                markets.example.com           │
│                                              │
│  An icon will be added to your Home Screen   │
│  so you can quickly access this website.     │
│                                              │
│   Cancel                                Add  │
└──────────────────────────────────────────────┘
```

After install, opening from the home screen shows the app standalone
(no Safari address bar), with the dark theme color matching the iOS
status bar (`apple-mobile-web-app-status-bar-style: black-translucent`).
