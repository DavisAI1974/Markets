# Markets program — brief for friends

**Date**: May 4, 2026

## What we're doing

We're building a system that recognizes what kind of "energy state" a market is in at any given moment, and what the right play is for each state. The idea is not new in spirit — every experienced trader knows when a market is healthy, when a big player is dictating the price, when herd panic is unfolding, when liquidity has dried up, when something's being manipulated. What's new is that we can now detect these states automatically, in real time, on live streaming market data, using a method originally developed for something completely different.

## Where the method came from

Greg's prior work on a DARPA project for detecting cyber attacks produced a mathematical operator — call it a "dipole" — that measures the asymmetry between two competing flows in any system. It worked on cyber telemetry: when a network was under attack, the dipole's coefficients moved in characteristic ways before the attack landed. You could literally watch the operator drift in real time and predict where the attack was going.

The same operator also describes four completely unrelated physical phenomena: quantum spin systems, atmospheric turbulence, biochemistry, and seismic activity. Whenever there's a system with conservation laws and bidirectional flow, this dipole shows up.

That's the hypothesis we took into markets. Money is just energy in a different form. Markets are conservation systems — capital flowing in equals capital flowing out, positions sum to zero across all participants. If the dipole works in physics and biology and chemistry and geology and cyber attacks, it should work in markets too. The math doesn't know whether it's looking at buy and sell pressure on Coinbase or coupling strength in a magnet — it captures the same underlying dynamic either way.

## The five universal states

Whatever the system, it's always in one of five states:

| State | What it looks like in a market |
|---|---|
| **Equilibrium** | Two-sided trading. Money flowing both ways, balanced. Healthy. No edge. |
| **Channeled** | One side dominating. A whale buying or selling, and the other side can't push back. Get out of the way, or piggyback. |
| **Cascade** | Mass movement. Panic selling, FOMO buying. Logic out the window. Fade after the overshoot. |
| **Depleted** | Energy drained. Lunchtime, off-hours, the market is asleep. Sit out — no work can be done. |
| **Recirculating** | Activity but no real movement. Wash trades, paired self-deals. Manipulation. Exclude from analysis. |

The transitions between these states are where money is made or lost. The system detects which state we're in, and when it changes.

## What we accomplished in one morning

We ran our first 4-hour live test on Bitcoin (Coinbase) starting at 4:12 AM ET on Monday May 4. The system was given no information about trading hours, news events, time of day, what asset it was looking at, or anything else. Just raw streaming trade data.

Over the four hours, with no human input, it correctly identified in real time:

1. **The London market opening at 4:30 AM ET.** The system detected the regime transition starting around 5:00 AM ET as European institutional desks ramped to full activity.
2. **A volatility event at 6:00 AM ET.** It caught a sudden 4x energy spike in the order flow before we even knew there was an event.
3. **The London lunch lull at 7:00 AM ET.** Exactly as Greg predicted from his trader's intuition, the system saw the activity step down and flow patterns flip back to anti-correlated, marking the regime change to "Depleted."

For a first live test, three independent regime transitions correctly identified in one session is real. We also confirmed the same regime structure showed up on a second venue (Kraken) at the same wall-clock times — the patterns are not venue-specific quirks; they're real market structure.

## Does the dipole actually predict price moves?

This is the central question, and we want to be straight about it. **Detecting regime states is one thing. Making money from them is another.** Those aren't the same problem.

Here's what we've measured so far:

- **Same-window correlation between order flow and price moves is strong.** When we measure flow imbalance and price movement in the same chunk of time, they correlate at roughly 45% on Coinbase and 65% on Kraken — substantially above noise level and statistically significant on both venues. Order flow and price are clearly linked.
- **Next-window prediction is what we still need to prove.** A signal that just describes what's happening right now isn't tradeable — by the time you can read it, the price move has already happened. To actually trade on it, the dipole has to predict the NEXT period's return, not just describe the current one.

In Monday morning's data, the next-period predictive signal was too small to clearly distinguish from noise at our sample size — but a real predictive edge of the size we're hoping for typically needs several days to weeks of data to detect cleanly. That's why we're not declaring victory yet.

What we're hoping the multi-week data shows:

1. **Regime-transition moments predict the direction** the market resolves into. When the system detects a transition from "Equilibrium" to "Cascade-Up," does the price actually keep going up over the next 5–30 minutes more often than not?
2. **Cross-venue agreement is a confidence multiplier.** When both Coinbase and Kraken show the same regime shift at the same wall-clock minute, the resulting price move should follow through more reliably than when only one venue shows it.
3. **Specific regime types have characteristic resolution patterns** we can position ahead of. Whales unwinding inventory eventually exhaust; herds in panic eventually capitulate; depleted markets eventually re-engage. Each has a typical recovery shape.

If the data over the coming weeks shows the dipole has predictive power above the size of trading fees, we have a real product. If it doesn't, we say so honestly and stop. We do not know yet, and that's the bet we're collecting data to settle.

That said, **the early evidence is encouraging.** Several things stood out from the first day:

- The same-window correlation between flow and price (45% on Coinbase, 65% on Kraken) is unusually strong for crypto. Most published academic research on order-flow imbalance reports weaker relationships than what we measured.
- The regime structure replicated cleanly across two independent venues at the same wall-clock minutes — Coinbase and Kraken both caught the volatility spike at 6:00 AM ET with nearly identical magnitudes. Cross-venue agreement on regime transitions is real, not an artifact.
- The system caught three completely independent real-world events in real time without being told what to look for. The London open, the volatility spike, and the lunch lull weren't programmed in — they were detected as state transitions.
- The detection isn't driven by a single noisy feature. Multiple independent measurements of the dipole behavior all moved together at the regime boundaries. That's the signature of real market structure, not a one-dimensional fluke.
- Greg's trader intuition — that the market would slow at London lunch — was confirmed by the system's measurements rather than the other way around. The system independently agreed with experienced human judgment, on a prediction made before the data was collected.

None of these alone proves the predictor works for trading. Together they're real reasons to believe we're looking at genuine market structure, not noise — which is the precondition for a tradeable signal to exist at all. We're moving forward with cautious confidence.

## What we still need

One morning of data is suggestive, not conclusive. Before we'd ever stake real capital on this, we need:

- **More days, more sessions.** Today's data is Monday morning London hours. We need Tuesday-through-Friday confirmation that the same patterns repeat. Friday afternoon especially is a known low-activity test case — the system should detect "Depleted" cleanly.
- **Cross-asset confirmation.** We're now collecting Ethereum data in parallel to confirm the regime detection generalizes beyond Bitcoin (it should — the math is asset-agnostic).
- **3 to 4 weeks of multi-session data** before we'd consider running real money against it.

The good news is the data collection runs itself now. We've set up the system to gather data continuously without anyone needing to babysit it. The waiting is the only hard part.

## Five product structures we considered

Before settling on Option E, here are the five we evaluated in brief:

**Option A — Public signal feed.** A Discord or Telegram channel anyone can subscribe to. Simple, scales easily. But the signal degrades as more people use it, and there are a million signal services already.

**Option B — Pooled-capital LLC.** 5–10 of us pool money into an LLC that runs the strategy on combined capital. Best execution efficiency. But triggers SEC private fund rules, requires a fund administrator and accountant, and someone has to be fiduciary for everyone's money.

**Option C — White-glove personal bots.** Each friend gives trade-only API keys to their exchange accounts; we deploy a bot per account. Each person keeps their capital and control. But API key security is everyone's individual responsibility, and tech support load gets messy with many accounts.

**Option D — Formal LP/GP hedge fund.** Classic small fund structure with performance fees, audited financials, K-1s. Best economic capture per dollar of edge. But six-plus months of legal setup, heaviest regulatory burden, and needs $2M+ to be worth running.

**Option E — Closed signal feed + open-source bot template.** This is the one we chose.

## How Option E works

Two pieces:

1. **A private channel** (probably Discord) with 5–20 of us in it. The system posts when it detects a high-confidence regime alert. An example might read: *"Bitcoin: Channeled-Up signature detected on Coinbase, 8 minutes in, sustained buy-side pressure. Late entry not recommended. Watch for inventory exhaustion around $X."* Each of us decides whether to act on it.
2. **An open-source bot template** that any of us can run on our own exchange account. It reads the signals from the channel and places trades according to your personal risk parameters. Capital and keys stay with you. Some will run it fully automated, some will use it as a research signal and trade manually, some will read alerts and pass.

Why this is the right shape:

- **No pooled capital.** We never touch each other's money. No fiduciary exposure, no SEC issues. The investment-newsletter precedent applies.
- **Edge stays alive longer.** Signal isn't published. Even if 20 of us act on it, that's 20 small independent footprints rather than one big trail.
- **Cheapest to launch.** No legal team, no fund administration. We can be live within 2–3 weeks once the data confirms what we think it confirms.
- **Each person trades what they're comfortable with.** Risk tolerance is yours alone.

**Pricing**: probably free among the friends group at launch. Eventually a token monthly fee ($25–$100 range) once it's stable — just to cover hosting and time. Trading profits stay 100% with each member; we don't take any cut of trading P&L.

## Tier 2 — Where it goes once the friends group works

Once Option E has been running stably with the friends group for a month or two and the signal has earned trust, the natural next step is to point the same system at energy futures markets. That's where Greg's professional background is — he traded energy for seven years and knows the players, the typical regime patterns of natural gas and crude oil and power, the rhythms of expiration days, the storage report cycles.

The plan for Tier 2:

- **Same system, different market.** No major code changes — we just connect it to energy futures data instead of crypto data. The data costs about $125 in trial credits for the major futures vendor, usage-based after.
- **Different audience.** Instead of friends, we'd license the signal feed to professional energy desks at utilities, refineries, prop shops, and energy-focused hedge funds. Pricing scales accordingly: $500 to $5,000 per month per seat. These are professional users with professional budgets.
- **Same product shape.** Closed signal feed. We don't touch their money. They use the alerts to inform their own existing trading.
- **Greg's network is the sales channel.** Instead of cold-call sales, the first paying customer probably comes through a former colleague or someone he knows in the energy community. He's done the work; people remember.

The Tier 2 timeline is 6 to 10 weeks **after** the friends group has demonstrated consistent signal output. We don't pitch this to anyone professional until we have a real track record from the friends group to point at.

## Honest framing

We have something real after one morning of data on one venue, and the early evidence is genuinely encouraging. We do not yet have a guaranteed money-making predictor — those don't exist, and anyone selling you one is lying. What we do have is a methodology with a strong cross-domain track record (four sciences, cyber attacks), measurements from Monday morning that are stronger than published academic baselines, regime detection that successfully identified real events in real time, and cross-venue confirmation that the patterns aren't venue-specific quirks.

The remaining work is replication: gathering enough data over enough days to confirm that what we saw on Monday morning will hold up across different days, different times, and different market conditions. The collection runs itself now; we just need to wait for it to accumulate.

If the multi-week data confirms the patterns, we move forward with Option E. If it doesn't, we'll say so and stop. We'd rather find out we're wrong cheaply than expensively. **But based on what we've seen so far, we think it will hold up.**

We'll keep the group informed as we go.
