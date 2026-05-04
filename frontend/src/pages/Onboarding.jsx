import React from "react";

export default function Onboarding() {
  return (
    <article className="prose prose-invert max-w-none text-slate-300 leading-relaxed">
      <h2 className="text-xl font-semibold text-slate-100">What this is</h2>
      <p>
        markets-watch detects what kind of <strong>energy state</strong> a market is in at any moment, in real time,
        on streaming order-flow data. Every market is in one of five universal states. The dipole formula —{" "}
        <code className="font-mono text-sm">(buy − sell) / (buy + sell)</code> — measures the asymmetry, the same operator
        that emerged across physics, biology, chemistry, and geology.
      </p>

      <h3 className="text-base font-semibold mt-6 text-slate-100">The five regime states</h3>
      <ul className="space-y-1">
        <li><strong className="text-blue-400">Equilibrium</strong> — healthy two-sided exchange, no edge. (most of the time)</li>
        <li><strong className="text-green-400">Whale ↑ / ↓</strong> — one big actor dominating; piggyback if early, get out of way if late.</li>
        <li><strong className="text-orange-400">Herd ↑ / ↓</strong> — panic / FOMO; logic out the window. Fade after overshoot.</li>
        <li><strong className="text-yellow-500">Wash ⚠</strong> — paired self-trades; do not trade.</li>
        <li><strong className="text-gray-400">Depleted</strong> — market asleep (lunch, off-hours). Sit out.</li>
      </ul>

      <h3 className="text-base font-semibold mt-6 text-slate-100">How to use this</h3>
      <ol className="space-y-2">
        <li>
          <strong>Live status</strong> shows the current regime per asset/venue. Most of the time it'll say
          Equilibrium — that's normal. The interesting moments are the transitions.
        </li>
        <li>
          <strong>Signals</strong> auto-fires when a regime changes to an actionable state. Each signal includes
          a playbook (what to do) and a confidence number (how sure the system is).
        </li>
        <li>
          <strong>Cross-venue confirmation</strong>: when both Coinbase and Kraken see the same regime at the same
          minute, confidence multiplier is 1.5×. When they disagree (single-venue signature), 0.5×.
        </li>
      </ol>

      <h3 className="text-base font-semibold mt-6 text-slate-100">Important caveats</h3>
      <ul className="space-y-1 text-slate-400 text-sm">
        <li>This is research, not investment advice.</li>
        <li>Signal validation requires multi-week data. We are still accumulating.</li>
        <li>Don't share signals or screenshots outside the closed group.</li>
        <li>Each member trades on their own exchange accounts; capital and keys stay with you.</li>
      </ul>

      <h3 className="text-base font-semibold mt-6 text-slate-100">Executor (optional)</h3>
      <p className="text-sm">
        If you want to auto-trade signals, the executor template is in the GitHub repo:
      </p>
      <pre className="bg-slate-950 rounded p-3 text-xs font-mono overflow-x-auto">
{`git clone https://github.com/davisai1974/markets.git
cd markets
git checkout claude/new-session-o3vnm
# follow the README in /executor (coming soon)`}
      </pre>
      <p className="text-sm">
        The executor reads from this app's <code>/api/signals</code> stream and places orders on
        your exchange account using your own API keys. It never leaves your machine.
      </p>
    </article>
  );
}
