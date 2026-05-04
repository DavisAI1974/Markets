import React from "react";
import { useStore } from "../store.js";
import SignalCard from "../components/SignalCard.jsx";

export default function SignalFeed() {
  const signals = useStore((s) => s.signals);

  if (!signals || signals.length === 0) {
    return (
      <div className="text-slate-500 text-sm py-8 text-center">
        No signals yet. Signal events fire on regime transitions to actionable states (Whale, Herd, Wash).
        <br />
        Most chunks are Equilibrium — that's normal market behavior.
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-xs uppercase tracking-wider text-slate-500 mb-2 px-1">
        Recent signals · {signals.length}
      </h2>
      {signals.map((sig) => (
        <SignalCard key={sig.signal_id} sig={sig} />
      ))}
    </div>
  );
}
