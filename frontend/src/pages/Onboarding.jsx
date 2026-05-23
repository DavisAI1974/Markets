import React from "react";
import PushNotifyButton from "../components/PushNotifyButton.jsx";

export default function Onboarding() {
  return (
    <article className="prose prose-invert max-w-none text-slate-300 leading-relaxed">
      <h2 className="text-xl font-semibold text-slate-100">What is markets-watch?</h2>
      <p>
        markets-watch tells you, in real time, what kind of activity is happening in a market —
        whether one big actor is dominating, whether a crowd is piling on, whether trading is
        balanced and healthy, or whether something looks artificial. It watches the live order
        flow on multiple exchanges at once and posts a signal whenever it detects something
        worth your attention.
      </p>

      <p className="text-sm text-slate-400">
        Tap any market read on the Live tab to drill into the live bid/ask cells and the
        rolling minute-by-minute tape for that pair.
      </p>

      <div className="not-prose my-4 rounded border border-emerald-900/60 bg-emerald-950/30 p-3">
        <h3 className="text-sm font-semibold text-emerald-200 mb-2">
          Get pushed when a clean market read fires
        </h3>
        <p className="text-xs text-emerald-200/70 mb-2">
          Subscribe to push notifications: every detected event (whale buyer / whale seller /
          herd buying or selling / cross-venue cascade) shows up as a system notification
          within seconds. Works on Android Chrome and on iOS Safari (after you install the
          app via Share → Add to Home Screen).
        </p>
        <PushNotifyButton />
      </div>

      <h2 className="text-xl font-semibold text-slate-100 mt-8">What you'll see in a signal</h2>
      <p className="text-sm">
        Every signal comes with the same anatomy:
      </p>
      <ul className="text-sm space-y-1">
        <li><strong>Event:</strong> plain-language description — "Whale buyer detected", "Herd selling", etc.</li>
        <li><strong>Asset · Venue:</strong> which coin and which exchange.</li>
        <li><strong>Price:</strong> last trade.</li>
        <li><strong>Bid / Ask:</strong> current top-of-book quote. Whichever side was last
            hit by a trade flashes red — bid red means someone just sold, ask red means
            someone just bought.</li>
        <li><strong>Buy / Sell volume:</strong> how much volume traded on the buy side
            versus the sell side over the chunk window, in absolute coin units, plus a
            stacked bar so it's visible at a glance.</li>
        <li><strong>Trades:</strong> total number of individual trades over the chunk window.</li>
        <li><strong>Read quality:</strong> whether the tape is clean, mixed, noisy, thin,
            or still incomplete.</li>
        <li><strong>Cross-venue:</strong> whether the same event is visible on the second venue
            — confirmation makes the signal much higher conviction.</li>
        <li><strong>Playbook:</strong> the suggested action for this event type.</li>
      </ul>

      {/* ----------------------------------------------------------------- */}
      <h2 className="text-xl font-semibold text-slate-100 mt-8">Event types</h2>
      <p className="text-sm">
        Every chunk of market data (a flow-aware window of 10–30 one-minute bars) is
        classified into one of these. Most of the time markets are in healthy two-sided
        trading — the interesting moments are the transitions.
      </p>

      <Term color="blue" name="Equilibrium" formal="EQUILIBRIUM_TWO_SIDED">
        <p><strong>Buyers and sellers actively pushing back against each other.</strong> Volume
        flows both ways, balanced. This is normal market behavior most of the time.</p>
        <p className="text-xs text-slate-400 mt-1"><em>Playbook:</em> sit out — no edge here unless
        the flow becomes extremely one-sided within the chunk.</p>
      </Term>

      <Term color="green" name="Whale buyer detected" formal="WHALE_UP">
        <p><strong>One whale buyer dominating</strong>, sustained over multiple minutes. Sellers
        can't push back fast enough. Could be a position cover, accumulation, or institutional
        rotation.</p>
        <p className="text-xs text-slate-400 mt-1"><em>Playbook:</em> piggyback if you catch it
        early. Get out of the way if late — whale buyers eventually finish. Watch for the buying
        to exhaust near round-number price levels.</p>
      </Term>

      <Term color="red" name="Whale seller detected" formal="WHALE_DOWN">
        <p><strong>One whale seller dominating.</strong> Mirror image of the whale-buyer case.</p>
        <p className="text-xs text-slate-400 mt-1"><em>Playbook:</em> piggyback short if early.
        Watch for the seller's inventory to run out — that's typically the bottom.</p>
      </Term>

      <Term color="orange" name="Herd buying" formal="HERD_UP">
        <p><strong>FOMO / panic buy.</strong> Many actors aligned on the buy side at the same
        time. Volume and volatility both spike.</p>
        <p className="text-xs text-slate-400 mt-1"><em>Playbook:</em> follow with tight stops if
        you catch it on the way up. Fade after overshoot — these usually retrace.</p>
      </Term>

      <Term color="rose" name="Herd selling" formal="HERD_DOWN">
        <p><strong>Panic sell / capitulation.</strong> Multi-actor selling.</p>
        <p className="text-xs text-slate-400 mt-1"><em>Playbook:</em> do <strong>not</strong>
        catch the falling knife. Wait for the sell pressure to peak and exhaust, then fade
        once the worst is over.</p>
      </Term>

      <Term color="amber" name="Whale → Herd cascade" formal="WHALE_TO_HERD_*">
        <p><strong>A big actor's flow tripped a crowd-style cascade in the same direction.</strong> The
        first chunk classifies as a whale, the very next chunk classifies as a cascade with
        no quiet in between. This is a cleaner read because two independent signal types align.</p>
        <p className="text-xs text-slate-400 mt-1"><em>Playbook:</em> ride the cascade with a
        tight stop. Exit on first sign of exhaustion (volume drops, buy/sell pressure flips).</p>
      </Term>

      <Term color="amber" name="Cross-venue cascade" formal="CROSS_VENUE_WHALE_HERD_*">
        <p><strong>Same direction, both venues, two different signal types simultaneously.</strong>
        One exchange shows a whale, the other shows a cascade, same direction, same wall-clock
        window. This is the strongest event we emit.</p>
        <p className="text-xs text-slate-400 mt-1"><em>Playbook:</em> independent confirmation
        across venues. Size accordingly. Tight stop.</p>
      </Term>

      <Term color="yellow" name="Wash pattern — skip" formal="WASH_PAIRED">
        <p><strong>Paired self-trades.</strong> Tight price range, low volatility, suspicious
        flow signature. Manipulation, not real price discovery.</p>
        <p className="text-xs text-slate-400 mt-1"><em>Playbook:</em> exclude. Do not trade.</p>
      </Term>

      <Term color="gray" name="Quiet" formal="DEPLETED">
        <p><strong>Market is asleep.</strong> Off-hours, lunch lulls, weekends. There's no flow
        worth riding.</p>
        <p className="text-xs text-slate-400 mt-1"><em>Playbook:</em> sit out. Wait for
        activity to return.</p>
      </Term>

      {/* ----------------------------------------------------------------- */}
      <h2 className="text-xl font-semibold text-slate-100 mt-8">Other terms in the app</h2>

      <Glossary term="Bid / Ask">
        The current top-of-book quote on the exchange. Bid = highest price someone is willing
        to pay; Ask = lowest price someone is willing to sell at. Whichever side was just
        traded against flashes red on the card.
      </Glossary>

      <Glossary term="Cross-venue confirmation">
        We track the same asset on multiple venues (Coinbase, Kraken). When both venues
        report the same kind of activity at the same wall-clock minute, the read quality
        improves. When they disagree, the read is treated as thinner. Disagreement often
        means a single-venue event (e.g., a whale on one exchange) rather than a global
        market move.
      </Glossary>

      <Glossary term="Read quality">
        A plain-language description of the tape: Clean buyer/seller means directional
        participation is easy to read, Two-sided means buyers and sellers are pushing back,
        Noisy means the flow may be artificial, Thin means there is not enough flow, and
        Incomplete means the app is still waiting for a usable market read.
      </Glossary>

      <Glossary term="Buy / Sell volume">
        On every signal you'll see the absolute coin volume that traded on the aggressor-buy
        side versus the aggressor-sell side over the chunk window, plus a stacked-bar visual.
        High one-side share is the cleanest confirmation after the headline market read.
      </Glossary>

      <Glossary term="Trades">
        The count of individual trades that hit the tape over the chunk window, regardless of
        size. High trade count + low one-side share suggests many small actors (cascade);
        low trade count + high one-side share suggests one or two big actors (whale).
      </Glossary>

      {/* ----------------------------------------------------------------- */}
      <h2 className="text-xl font-semibold text-slate-100 mt-8">FAQ</h2>

      <FAQ q="Why is the signal feed quiet most of the time?">
        Most market activity is healthy two-sided trading — that's the baseline. Real big-actor
        events and cascades are rare, which is exactly why they're worth flagging when they
        happen.
      </FAQ>

      <FAQ q="Should I trade every signal?">
        No. The signals are research; your executor's risk gates filter them by your personal
        thresholds (minimum signal strength, asset whitelist, daily trade cap, etc.). For the first
        weeks you should run the executor in <code>--dry-run</code> mode and just verify the
        gates fire as you'd expect. Real-money trading requires a real-exchange adapter you
        write yourself, not the paper adapter we ship.
      </FAQ>

      <FAQ q="What if Coinbase says one thing and Kraken says another?">
        That's a <em>single-venue event</em>, and it's actually one of the most informative
        situations. Cross-venue disagreement at the same wall-clock minute often means a big
        actor specifically on one exchange. The system flags these as thinner reads; consider
        raising your minimum signal-strength gate if you want to skip them entirely.
      </FAQ>

      <FAQ q="Why are different coins on the same venue treated differently?">
        Each coin has its own fingerprint — different liquidity, different actor mix, different
        baseline volatility. The executor's risk config supports per-(asset, venue) overrides
        on top of the default settings.
      </FAQ>

      <FAQ q="How do I know if it's working?">
        Open the Stats tab. It shows the rolling 24-hour (or 7d / 30d) signal counts, regime
        distribution, cross-venue confirmation rate, average read score, and (once enough
        signals resolve) realized hit rate and total P&L.
      </FAQ>

      <FAQ q="Can I run my own executor?">
        Yes. Clone the repo, edit <code>my_config.json</code>, run{" "}
        <code>python -m executor.executor --config my_config.json --dry-run</code>. The repo
        ships a paper-trading adapter; for real money, write your own Exchange adapter (see
        <code>executor/exchanges/base.py</code>). Your API keys never leave your machine.
      </FAQ>

      {/* ----------------------------------------------------------------- */}
      <h2 className="text-xl font-semibold text-slate-100 mt-8">House rules</h2>
      <ul className="text-slate-300 space-y-1 text-sm">
        <li>This is research, not investment advice. Your money, your risk.</li>
        <li>Closed group only. Don't share signals, screenshots, or links outside.</li>
        <li>Each member trades on their own exchange accounts; no pooled capital.</li>
        <li>Discord is the primary channel; this app is the visual companion.</li>
        <li>If you find a bug, post in <code>#data-health</code>; if you want to discuss a
            signal interpretation, use the threaded reply on the signal post in Discord.</li>
      </ul>

      <p className="text-slate-500 text-xs italic mt-8">
        Multi-week validation of the underlying signal is still in progress. We're collecting
        data 24/7 via GitHub Actions; decisions to scale up position sizes or onboard more
        members depend on what that data shows.
      </p>
    </article>
  );
}

// -----------------------------------------------------------------------------

const COLOR_BORDERS = {
  blue: "border-blue-700",
  green: "border-green-700",
  red: "border-red-700",
  orange: "border-orange-600",
  rose: "border-rose-700",
  amber: "border-amber-600",
  yellow: "border-yellow-700",
  gray: "border-gray-600",
};

function Term({ color, name, formal, children }) {
  const borderCls = COLOR_BORDERS[color] || "border-slate-700";
  return (
    <div className={`my-3 border-l-4 ${borderCls} bg-slate-900/50 rounded-r p-3`}>
      <div className="flex items-baseline justify-between gap-2 mb-1">
        <h3 className="text-base font-semibold text-slate-100 m-0 p-0">{name}</h3>
        <code className="text-[10px] text-slate-500 font-mono">{formal}</code>
      </div>
      <div className="text-sm text-slate-300">{children}</div>
    </div>
  );
}

function Glossary({ term, children }) {
  return (
    <div className="my-3">
      <strong className="text-slate-100">{term}</strong>
      <span className="text-slate-300 text-sm"> — {children}</span>
    </div>
  );
}

function FAQ({ q, children }) {
  return (
    <details className="my-2 bg-slate-900/40 rounded p-2 border border-slate-800">
      <summary className="cursor-pointer text-sm font-semibold text-slate-100">{q}</summary>
      <div className="text-sm text-slate-300 mt-2 ml-2">{children}</div>
    </details>
  );
}
