import React, { useEffect } from "react";
import { Routes, Route, Link, NavLink } from "react-router-dom";
import { useStore } from "./store.js";
import { fetchStatus, fetchSignals, subscribeToStream } from "./api.js";
import LiveStatus from "./pages/LiveStatus.jsx";
import SignalFeed from "./pages/SignalFeed.jsx";
import SignalDetail from "./pages/SignalDetail.jsx";
import Onboarding from "./pages/Onboarding.jsx";

export default function App() {
  const setStatuses = useStore((s) => s.setStatuses);
  const setSignals = useStore((s) => s.setSignals);
  const prependSignal = useStore((s) => s.prependSignal);
  const setConnected = useStore((s) => s.setConnected);

  useEffect(() => {
    let cancelled = false;
    fetchStatus().then((j) => !cancelled && setStatuses(j.statuses || [])).catch(() => {});
    fetchSignals().then((j) => !cancelled && setSignals(j.signals || [])).catch(() => {});

    const cleanup = subscribeToStream({
      onSnapshot: (d) => setStatuses(d.statuses || []),
      onSignal: (sig) => prependSignal(sig),
      onError: () => setConnected(false),
    });
    setConnected(true);

    // Periodic full-status refresh (defensive against missed SSE events)
    const interval = setInterval(() => {
      fetchStatus().then((j) => setStatuses(j.statuses || [])).catch(() => {});
    }, 30000);

    return () => { cancelled = true; cleanup(); clearInterval(interval); setConnected(false); };
  }, []);

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-slate-800 px-4 py-3 sticky top-0 bg-slate-950/95 backdrop-blur z-10">
        <div className="flex items-center justify-between">
          <Link to="/" className="font-mono text-base font-semibold tracking-tight text-slate-100">
            markets-watch
          </Link>
          <ConnectionDot />
        </div>
        <nav className="mt-2 flex gap-3 text-sm">
          <NavTab to="/">Live</NavTab>
          <NavTab to="/signals">Signals</NavTab>
          <NavTab to="/about">About</NavTab>
        </nav>
      </header>
      <main className="flex-1 p-4 max-w-3xl mx-auto w-full">
        <Routes>
          <Route path="/" element={<LiveStatus />} />
          <Route path="/signals" element={<SignalFeed />} />
          <Route path="/signal/:id" element={<SignalDetail />} />
          <Route path="/about" element={<Onboarding />} />
        </Routes>
      </main>
      <footer className="border-t border-slate-800 px-4 py-2 text-xs text-slate-500 text-center">
        Research signals — not investment advice. Closed group.
      </footer>
    </div>
  );
}

function NavTab({ to, children }) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        `px-2 py-1 rounded ${isActive ? "bg-slate-800 text-slate-100" : "text-slate-400 hover:text-slate-100"}`
      }
    >
      {children}
    </NavLink>
  );
}

function ConnectionDot() {
  const connected = useStore((s) => s.connected);
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${connected ? "bg-green-500" : "bg-red-500"}`}
      title={connected ? "Connected (SSE live)" : "Disconnected"}
    />
  );
}
