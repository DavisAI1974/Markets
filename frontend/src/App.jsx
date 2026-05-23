import React, { useEffect, useState } from "react";
import { Routes, Route, Link, NavLink, useLocation } from "react-router-dom";
import { useStore } from "./store.js";
import { fetchStatus, fetchSignals, fetchDriftAlerts, fetchAutoTradeSettings, postAutoTradeSettings, subscribeToStream } from "./api.js";
import LiveStatus from "./pages/LiveStatus.jsx";
import SignalFeed from "./pages/SignalFeed.jsx";
import SignalDetail from "./pages/SignalDetail.jsx";
import TapeDetail from "./pages/TapeDetail.jsx";
import Onboarding from "./pages/Onboarding.jsx";
import Stats from "./pages/Stats.jsx";
import RegimeHistory from "./pages/RegimeHistory.jsx";
import PracticeFeed from "./pages/PracticeFeed.jsx";
import EvolveLab from "./pages/EvolveLab.jsx";
import DriftBanner from "./components/DriftBanner.jsx";
import SignalDetailSheet from "./components/SignalDetailSheet.jsx";
import RouteErrorBoundary from "./components/RouteErrorBoundary.jsx";

const PRIVATE_TAB_PASSWORD = import.meta.env.VITE_MARKETS_PRIVATE_PASS || "markets-only";
const PRIVATE_UNLOCK_KEY = "markets_watch_private_tabs_unlocked";

export default function App() {
  const location = useLocation();
  const [privateTabsUnlocked, setPrivateTabsUnlocked] = useState(() => {
    try {
      return sessionStorage.getItem(PRIVATE_UNLOCK_KEY) === "1";
    } catch {
      return false;
    }
  });
  const setStatuses = useStore((s) => s.setStatuses);
  const setSignals = useStore((s) => s.setSignals);
  const prependSignal = useStore((s) => s.prependSignal);
  const setDriftAlerts = useStore((s) => s.setDriftAlerts);
  const prependDriftAlert = useStore((s) => s.prependDriftAlert);
  const setConnected = useStore((s) => s.setConnected);
  const setError = useStore((s) => s.setError);
  const setAutoTradeSettings = useStore((s) => s.setAutoTradeSettings);

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [location.pathname]);

  useEffect(() => {
    let cancelled = false;
    if (window.__MW_LIVE__?.statuses?.length) {
      setStatuses(window.__MW_LIVE__.statuses);
      setError(null);
    }
    const refreshStatus = () => {
      setError("loading live reads...");
      fetchStatus().then((j) => {
        if (cancelled) return;
        const statuses = j.statuses || [];
        if (statuses.length > 0) {
          setStatuses(statuses);
          setError(null);
        }
      }).catch((e) => setError(`market reads: ${String(e?.message || e)}`));
    };

    refreshStatus();
    fetchSignals().then((j) => !cancelled && setSignals(j.signals || [])).catch((e) => setError(`signals: ${String(e?.message || e)}`));
    fetchDriftAlerts().then((j) => !cancelled && setDriftAlerts(j.alerts || [])).catch((e) => setError(`drift alerts: ${String(e?.message || e)}`));
    fetchAutoTradeSettings().then((j) => !cancelled && setAutoTradeSettings(j)).catch((e) => setError(`auto trade: ${String(e?.message || e)}`));

    const cleanup = subscribeToStream({
      onSnapshot: (d) => {
        const statuses = d.statuses || [];
        if (statuses.length > 0) setStatuses(statuses);
      },
      onSignal: (sig) => prependSignal(sig),
      onDriftAlert: (a) => prependDriftAlert(a),
      onError: () => {
        setConnected(false);
        setError("stream disconnected");
      },
    });
    setConnected(true);

    const earlyRefresh = setTimeout(refreshStatus, 1500);

    // Periodic full-status refresh (defensive against missed SSE events)
    const interval = setInterval(refreshStatus, 10000);

    return () => {
      cancelled = true;
      cleanup();
      clearTimeout(earlyRefresh);
      clearInterval(interval);
      setConnected(false);
    };
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
            <AutoTradeToggle />
            <ConnectionDot />
          </div>
        </div>
        <nav className="mt-2 flex flex-wrap gap-1 text-xs sm:gap-2 sm:text-sm">
          <NavTab to="/">Live</NavTab>
          <NavTab to="/signals">Signals</NavTab>
          <NavTab to="/practice">Practice</NavTab>
          {privateTabsUnlocked && <NavTab to="/evolve">Evolve</NavTab>}
          <NavTab to="/history">History</NavTab>
          <NavTab to="/stats">Stats</NavTab>
          <NavTab to="/about">About</NavTab>
        </nav>
      </header>
      <main className="flex-1 p-4 max-w-3xl mx-auto w-full">
        <DriftBanner />
        <RouteErrorBoundary resetKey={location.pathname}>
          <Routes>
            <Route path="/" element={<LiveStatus />} />
            <Route path="/signals" element={<SignalFeed />} />
            <Route path="/signal/:id" element={<SignalDetail />} />
            <Route path="/tape/:asset/:venue" element={<TapeDetail />} />
            <Route path="/history" element={<RegimeHistory />} />
            <Route path="/practice" element={<PracticeFeed />} />
            <Route
              path="/evolve"
              element={
                <PasswordGate
                  title="Evolve locked"
                  storageKey="markets_watch_evolve_unlocked"
                  onUnlock={() => setPrivateTabsUnlocked(true)}
                >
                  <EvolveLab />
                </PasswordGate>
              }
            />
            <Route path="/stats" element={<Stats />} />
            <Route path="/about" element={<Onboarding />} />
          </Routes>
        </RouteErrorBoundary>
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
        `px-2 py-1 rounded whitespace-nowrap sm:px-2.5 ${isActive ? "bg-slate-800 text-slate-100" : "text-slate-400 hover:text-slate-100"}`
      }
    >
      {children}
    </NavLink>
  );
}

function PasswordGate({ title, storageKey, onUnlock, children }) {
  const [unlocked, setUnlocked] = useState(() => {
    try {
      return sessionStorage.getItem(PRIVATE_UNLOCK_KEY) === "1" || sessionStorage.getItem(storageKey) === "1";
    } catch {
      return false;
    }
  });
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  function unlock(event) {
    event.preventDefault();
    if (password.trim() !== PRIVATE_TAB_PASSWORD) {
      setError("That password did not match.");
      return;
    }
    try {
      sessionStorage.setItem(PRIVATE_UNLOCK_KEY, "1");
      sessionStorage.setItem(storageKey, "1");
    } catch {
      // Private browsing can block storage; still unlock for this render.
    }
    setUnlocked(true);
    onUnlock?.();
    setError("");
    setPassword("");
  }

  if (unlocked) return children;

  return (
    <section className="mx-auto mt-10 max-w-sm rounded border border-slate-800 bg-slate-900/80 p-5 shadow-lg shadow-black/20">
      <div className="mb-4">
        <h1 className="text-base font-semibold text-slate-100">{title}</h1>
        <p className="mt-1 text-sm leading-5 text-slate-400">
          Enter the private markets password to view this tab on this device.
        </p>
      </div>
      <form onSubmit={unlock} className="space-y-3">
        <label className="block">
          <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            Password
          </span>
          <input
            type="password"
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
              setError("");
            }}
            autoComplete="current-password"
            className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500"
          />
        </label>
        {error && <div className="text-xs font-medium text-rose-300">{error}</div>}
        <button
          type="submit"
          className="w-full rounded bg-sky-700 px-3 py-2 text-sm font-semibold text-sky-50 hover:bg-sky-600"
        >
          Unlock
        </button>
      </form>
      <p className="mt-3 text-xs leading-5 text-slate-500">
        Unlock lasts for this browser session only.
      </p>
    </section>
  );
}

function ConnectionDot() {
  const connected = useStore((s) => s.connected);
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-1.5 py-1 text-[10px] uppercase tracking-wide text-slate-300`}
      title={connected ? "Connected (SSE live)" : "Disconnected"}
    >
      <span className={`inline-block h-2 w-2 rounded-full ${connected ? "bg-green-500" : "bg-red-500"}`} />
      <span className="hidden sm:inline">{connected ? "Live data" : "Offline"}</span>
    </span>
  );
}

function AutoTradeToggle() {
  const settings = useStore((s) => s.autoTradeSettings);
  const setAutoTradeSettings = useStore((s) => s.setAutoTradeSettings);
  const enabled = !!settings?.enabled;
  const tolerance = settings?.tolerance || "balanced";

  async function saveAuto(next, errorLabel = "Auto settings failed") {
    try {
      const saved = await postAutoTradeSettings(next);
      setAutoTradeSettings(saved);
    } catch (e) {
      window.alert(`${errorLabel}: ${String(e?.message || e)}`);
    }
  }

  async function toggle() {
    if (!enabled) {
      const ok = window.confirm(
        "Turn on AUTO practice trading? This opens simulated practice trades using the selected tolerance. Live auto requires a separate server-side safety flag."
      );
      if (!ok) return;
    }
    const next = {
      ...(settings || {}),
      enabled: !enabled,
      practice: true,
      tolerance,
      apply_preset: !enabled,
    };
    await saveAuto(next, "Auto toggle failed");
  }

  async function changeTolerance(nextTolerance) {
    await saveAuto({
      ...(settings || {}),
      enabled,
      practice: true,
      tolerance: nextTolerance,
      apply_preset: true,
    }, "Tolerance update failed");
  }

  return (
    <div className="flex items-center gap-1 rounded bg-slate-900/90 p-1 ring-1 ring-slate-700/80">
      <button
        onClick={toggle}
        className={`text-[10px] uppercase tracking-wider font-bold rounded px-2 py-1 whitespace-nowrap
                      ${enabled
                        ? "bg-emerald-700 text-emerald-50 hover:bg-emerald-600"
                        : "bg-slate-800 text-slate-300 hover:bg-slate-700"}`}
        title="Auto practice trading for eligible pressure setups"
      >
        {enabled ? "Auto on" : "Manual"}
      </button>
      <select
        value={tolerance}
        onChange={(e) => changeTolerance(e.target.value)}
        className="h-6 rounded bg-slate-950 px-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-200 outline-none ring-1 ring-slate-700 hover:ring-slate-500"
        title="Auto tolerance"
      >
        <option value="conservative">Conservative</option>
        <option value="balanced">Balanced</option>
        <option value="aggressive">Aggressive</option>
      </select>
    </div>
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
