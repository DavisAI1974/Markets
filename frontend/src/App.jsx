import React, { useEffect } from "react";
import { Routes, Route, Link, NavLink } from "react-router-dom";
import { useStore } from "./store.js";
import { fetchStatus, fetchSignals, fetchDriftAlerts, subscribeToStream } from "./api.js";
import LiveStatus from "./pages/LiveStatus.jsx";
import SignalFeed from "./pages/SignalFeed.jsx";
import SignalDetail from "./pages/SignalDetail.jsx";
import Onboarding from "./pages/Onboarding.jsx";
import Stats from "./pages/Stats.jsx";
import RegimeHistory from "./pages/RegimeHistory.jsx";
import PracticeFeed from "./pages/PracticeFeed.jsx";
import DriftBanner from "./components/DriftBanner.jsx";
import SignalDetailSheet from "./components/SignalDetailSheet.jsx";

export default function App() {
  const setStatuses = useStore((s) => s.setStatuses);
  const setSignals = useStore((s) => s.setSignals);
  const prependSignal = useStore((s) => s.prependSignal);
  const setDriftAlerts = useStore((s) => s.setDriftAlerts);
  const prependDriftAlert = useStore((s) => s.prependDriftAlert);
  const setConnected = useStore((s) => s.setConnected);

  useEffect(() => {
    let cancelled = false;
    fetchStatus().then((j) => !cancelled && setStatuses(j.statuses || [])).catch(() => {});
    fetchSignals().then((j) => !cancelled && setSignals(j.signals || [])).catch(() => {});
    fetchDriftAlerts().then((j) => !cancelled && setDriftAlerts(j.alerts || [])).catch(() => {});

    const cleanup = subscribeToStream({
      onSnapshot: (d) => setStatuses(d.statuses || []),
      onSignal: (sig) => prependSignal(sig),
      onDriftAlert: (a) => prependDriftAlert(a),
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
          <div className="flex items-center gap-3">
            <ModeToggle />
            <ConnectionDot />
          </div>
        </div>
        <nav className="mt-2 flex gap-3 text-sm overflow-x-auto">
          <NavTab to="/">Live</NavTab>
          <NavTab to="/signals">Signals</NavTab>
          <NavTab to="/practice">Practice</NavTab>
          <NavTab to="/history">History</NavTab>
          <NavTab to="/stats">Stats</NavTab>
          <NavTab to="/about">About</NavTab>
        </nav>
      </header>
      <main className="flex-1 p-4 max-w-3xl mx-auto w-full">
        <DriftBanner />
        <Routes>
          <Route path="/" element={<LiveStatus />} />
          <Route path="/signals" element={<SignalFeed />} />
          <Route path="/signal/:id" element={<SignalDetail />} />
          <Route path="/history" element={<RegimeHistory />} />
          <Route path="/practice" element={<PracticeFeed />} />
          <Route path="/stats" element={<Stats />} />
          <Route path="/about" element={<Onboarding />} />
        </Routes>
      </main>
      <footer className="border-t border-slate-800 px-4 py-2 text-xs text-slate-500 text-center">
        Research signals — not investment advice. Closed group.
      </footer>
      <SignalDetailSheet />
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

/**
 * Header mode toggle. Practice mode is default-ON for new users — users
 * have to deliberately switch to live to put real money at risk.
 */
function ModeToggle() {
  const practiceMode = useStore((s) => s.practiceMode);
  const setPracticeMode = useStore((s) => s.setPracticeMode);
  return (
    <button
      onClick={() => {
        if (practiceMode) {
          // Going live requires explicit confirmation
          if (window.confirm("Switch to LIVE mode? Trades you confirm will be sent as real-money intents to your local executor / exchange. Make sure your executor is set up.")) {
            setPracticeMode(false);
          }
        } else {
          setPracticeMode(true);
        }
      }}
      className={`text-[10px] uppercase tracking-wider font-bold rounded px-2 py-1
                    ${practiceMode
                      ? "bg-sky-700 text-sky-50 hover:bg-sky-600"
                      : "bg-amber-700 text-amber-50 hover:bg-amber-600"}`}
      title="Tap to toggle practice / live"
    >
      {practiceMode ? "🎯 Practice" : "⚠️ Live"}
    </button>
  );
}
