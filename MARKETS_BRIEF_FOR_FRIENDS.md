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

We have something real after one morning of data on one venue. We do not have a guaranteed money-making predictor — those don't exist, and anyone selling you one is lying. What we have is a methodology and early evidence that it works on markets the way it worked across the four sciences and on cyber attacks. The remaining work is replication: gathering enough data over enough days to confirm that what we saw on Monday morning wasn't a fluke.

If the multi-week data confirms the patterns, we move forward with Option E. If it doesn't, we'll say so and stop. We'd rather find out we're wrong cheaply than expensively.

We'll keep the group informed as we go.
