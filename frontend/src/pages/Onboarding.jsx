import React from "react";

export default function Onboarding() {
  return (
    <article className="prose prose-invert max-w-none text-slate-300 leading-relaxed">
      <h2 className="text-xl font-semibold text-slate-100">What is markets-watch?</h2>
      <p>
        It's a system that detects what kind of <strong>energy state</strong> a market is in at any moment,
        in real time, on streaming order-flow data. Every market is in one of five universal states.
        We tell you which one and what to do about it.
      </p>
      <p>
        The math behind it (the <strong>dipole</strong>) is the same operator that emerged across physics,
        biology, chemistry, and geology. It works on markets because money is just energy in a different
        form, and markets are conservation systems — capital flowing in equals capital flowing out.
      </p>

      {/* ----------------------------------------------------------------- */}
      <h2 className="text-xl font-semibold text-slate-100 mt-8">What the regime labels mean</h2>
      <p className="text-sm">
        Every chunk of market data (a regime-aware window of 10–30 one-minute bars) gets classified
        into one of these states. Most chunks are equilibrium — that's normal market behavior.
        The interesting moments are the transitions.
      </p>

      <Term color="blue" name="Equilibrium" formal="EQUILIBRIUM_TWO_SIDED">
        <p><strong>Healthy two-sided trading.</strong> Money flowing both ways, balanced. Buyers and
        sellers actively pushing back against each other.</p>
        <p className="text-xs text-slate-400 mt-1"><em>Playbook:</em> sit out — no edge to extract.
        Unless we detect an extreme dipole within equilibrium (see "EQUILIBRIUM_EXTREME_DEMO" below),
        in which case it's a mean-reversion candidate.</p>
      </Term>

      <Term color="green" name="Whale ↑" formal="WHALE_UP">
        <p><strong>One big buyer dominating</strong>, sustained over multiple minutes. Counter-flow
        from sellers can't push back fast enough. Could be position cover, accumulation, or institutional
        rotation.</p>
        <p className="text-xs text-slate-400 mt-1"><em>Playbook:</em> piggyback if you catch it early
        (their flow keeps pushing price up). Get out of the way if late — whales eventually exhaust.
        Watch for round-number price magnets where the whale's order may finish.</p>
      </Term>

      <Term color="red" name="Whale ↓" formal="WHALE_DOWN">
        <p><strong>One big seller dominating.</strong> Mirror image of Whale ↑.</p>
        <p className="text-xs text-slate-400 mt-1"><em>Playbook:</em> piggyback short if early.
        Watch for capitulation bottom — whales' inventory eventually depletes.</p>
      </Term>

      <Term color="orange" name="Herd ↑" formal="HERD_UP">
        <p><strong>FOMO / panic buy.</strong> Mass aligned movement — many actors buying at the same
        time. Logic out the window. Volume spikes, realized vol spikes, dipole goes very positive.</p>
        <p className="text-xs text-slate-400 mt-1"><em>Playbook:</em> follow with tight stops if you
        catch it on the way up. Fade after overshoot — herd events usually retrace.</p>
      </Term>

      <Term color="rose" name="Herd ↓" formal="HERD_DOWN">
        <p><strong>Panic sell / capitulation.</strong> Multi-actor selling cascade.</p>
        <p className="text-xs text-slate-400 mt-1"><em>Playbook:</em> do <strong>not</strong> catch
        the falling knife. Wait for capitulation (volume + dipole peak), then fade after the worst
        is over.</p>
      </Term>

      <Term color="yellow" name="Wash ⚠" formal="WASH_PAIRED">
        <p><strong>Paired self-trades.</strong> Detected by anti-correlated H_a/H_b within tight
        price range and low realized volatility. Manipulation, not real price discovery.</p>
        <p className="text-xs text-slate-400 mt-1"><em>Playbook:</em> exclude. Do not trade.</p>
      </Term>

      <Term color="gray" name="Depleted" formal="DEPLETED">
        <p><strong>Market is asleep.</strong> Realized vol below activity floor or session-specific
        baseline. Lunchtime lull, off-hours, weekends. The system can't do work — there's no flow
        to ride.</p>
        <p className="text-xs text-slate-400 mt-1"><em>Playbook:</em> sit out. Wait for re-engagement.</p>
      </Term>

      <Term color="blue" name="Equilibrium-Extreme (demo)" formal="EQUILIBRIUM_EXTREME_DEMO">
        <p><strong>Mean-reversion candidate within equilibrium.</strong> The market is in a healthy
        two-sided state, but the dipole has spiked extreme (|dipole| {">"} 0.3) and volume is elevated
        (vol_z {">"} 0.5). Per our autoresearch finding, these chunks tend to mean-revert at the next
        chunk close.</p>
        <p className="text-xs text-slate-400 mt-1"><em>Playbook:</em> fade the dipole — go opposite
        direction, hold one chunk (~30 minutes), exit at chunk close.</p>
        <p className="text-xs text-yellow-400/70 italic mt-1">
          NB: currently flagged "DEMO" because we're using it to populate the signal feed before
          multi-day regime-transition data accumulates. Reverts to non-demo once production signals
          flow naturally.
        </p>
      </Term>

      {/* ----------------------------------------------------------------- */}
      <h2 className="text-xl font-semibold text-slate-100 mt-8">Other terms in the app</h2>

      <Glossary term="Dipole">
        The asymmetry between taker buy volume (H_a) and taker sell volume (H_b) within a chunk:
        <code className="block font-mono text-sm bg-slate-950 p-2 rounded my-2">
          dipole = (H_a − H_b) / (H_a + H_b)
        </code>
        Range −1 to +1. Positive means buyers were aggressive; negative means sellers were aggressive.
        Same operator structure as in physics, biology, chemistry, geology.
      </Glossary>

      <Glossary term="Cross-venue confirmation">
        We track the same asset on multiple venues (Coinbase, Kraken). When both venues' classifiers
        report the <em>same</em> regime at the same wall-clock minute, the signal's confidence is
        multiplied by 1.5×. When they disagree, multiplied by 0.5×. Disagreement often means a
        single-venue event (e.g., a whale on one exchange) rather than a global market move.
      </Glossary>

      <Glossary term="Confidence">
        A 0–1 score combining (a) how strongly the classifier rules fired, and (b) the cross-venue
        multiplier. Below 0.5 = weak signal, skip. 0.5–0.7 = moderate. Above 0.7 = strong.
        Configure your minimum confidence threshold in the executor config.
      </Glossary>

      <Glossary term="PELT chunk">
        We don't use fixed time bins. Instead, PELT (Pruned Exact Linear Time) change-point detection
        finds natural regime boundaries in the price + flow series and chunks the data along those
        boundaries. Chunks are typically 10–30 minutes long. Each chunk gets one regime label.
      </Glossary>

      <Glossary term="Realized vol (rv)">
        Standard deviation of log returns within a chunk. Reported in basis points (bp). Baseline
        on BTC during quiet periods is around 4–5 bp per chunk; during volatile events it can
        spike to 100+ bp.
      </Glossary>

      <Glossary term="Adjusted confidence">
        confidence × cross_venue_multiplier, capped at [0, 1]. This is the number the executor's
        risk gate compares against your `min_confidence` setting. Use this for thresholding.
      </Glossary>

      {/* ----------------------------------------------------------------- */}
      <h2 className="text-xl font-semibold text-slate-100 mt-8">FAQ</h2>

      <FAQ q="Why is the signal feed empty most of the time?">
        Most chunks are equilibrium — that's normal market behavior. Real WHALE / HERD / WASH transitions
        are rare. The DEMO mode also emits signals for extreme-dipole equilibrium chunks
        (mean-reversion candidates) so the feed has actionable content while we accumulate real
        transitions across multiple days.
      </FAQ>

      <FAQ q="Should I trade every signal?">
        No. The signals are research; the executor's risk gates filter them by your personal
        thresholds (min confidence, asset whitelist, daily trade cap, etc.). For the first weeks
        you should run the executor in <code>--dry-run</code> mode and just verify the gates fire
        as you'd expect. Real-money trading requires a real-exchange adapter you write yourself,
        not the paper adapter we ship.
      </FAQ>

      <FAQ q="What if Coinbase says one thing and Kraken says another?">
        That's a <em>single-venue event</em>, and it's actually one of the most informative signals.
        Cross-venue disagreement at the same wall-clock minute often means a whale specifically on
        one exchange, or a venue-local technical anomaly. The system flags these with a 0.5× confidence
        multiplier; consider raising your `min_confidence` if you want to skip them entirely.
      </FAQ>

      <FAQ q="Why are different coins on the same venue treated differently?">
        Each coin has its own fingerprint — different liquidity, different actor mix, different
        baseline volatility. The executor's risk config supports per-(asset, venue) overrides
        on top of the default settings. The operator-discovery system also tracks which formula
        predicts best for each (asset, venue) independently. ETH on Coinbase and ETH on Kraken
        may end up using different operators.
      </FAQ>

      <FAQ q="How do I know if it's working?">
        Open the Stats tab. It shows the rolling 24-hour (or 7d / 30d) signal counts, regime
        distribution, cross-venue confirmation rate, and average confidence. Once we have multi-week
        data, we'll add realized hit rate and P&L tracking too. Until then, the right bar is
        "are the regime transitions matching things you know happened in the market?" — e.g., did
        the system flag the volatility spike when CPI came out? When London opened?
      </FAQ>

      <FAQ q="Can I run my own executor?">
        Yes. Clone the repo, edit <code>my_config.json</code>, run{" "}
        <code>python -m executor.executor --config my_config.json --dry-run</code>. The repo
        ships a paper-trading adapter; for real-money, write your own Exchange adapter (see
        <code>executor/exchanges/base.py</code>). Your API keys never leave your machine.
      </FAQ>

      {/* ----------------------------------------------------------------- */}
      <h2 className="text-xl font-semibold text-slate-100 mt-8">House rules</h2>
      <ul className="text-slate-300 space-y-1 text-sm">
        <li>This is research, not investment advice. Your money, your risk.</li>
        <li>Closed group only. Don't share signals, screenshots, or links outside.</li>
        <li>Each member trades on their own exchange accounts; no pooled capital.</li>
        <li>Discord is the primary channel; this app is the visual companion.</li>
        <li>If you find a bug, post in <code>#data-health</code>; if you want to discuss a signal
            interpretation, use the threaded reply on the signal post in Discord.</li>
      </ul>

      <p className="text-slate-500 text-xs italic mt-8">
        Multi-week validation of the underlying signal is still in progress. We're collecting data
        24/7 via GitHub Actions; decisions to scale up position sizes or onboard more friends
        depend on what that data shows.
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
