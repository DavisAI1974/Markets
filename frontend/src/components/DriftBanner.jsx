import React, { useState } from "react";
import { useStore } from "../store.js";

/**
 * Top banner that surfaces recent drift alerts. Pulls from the store's
 * driftAlerts (populated via /api/drift-alerts on load + drift_alert SSE
 * events as they arrive). Collapsible — shows the latest by default,
 * expand to see the rest.
 *
 * The whole point of this is to make sure users see "the sand has shifted"
 * the moment it's detectable, not after their P&L tells them.
 */

const TYPE_STYLES = {
  direction_flip:               { color: "amber",  icon: "⚠", title: "Direction flip" },
  edge_decay:                    { color: "amber",  icon: "↓", title: "Edge decaying" },
  edge_strengthen:               { color: "emerald",icon: "↑", title: "Edge strengthening" },
  sample_milestone:              { color: "sky",    icon: "✓", title: "Sample milestone" },
  outcome_contradiction_streak:  { color: "rose",   icon: "⚠", title: "Outcome contradiction streak" },
  pressure_watch_high_priority:  { color: "amber",  icon: "⚠", title: "Pressure forming" },
};

const COLOR_CLS = {
  amber:   "border-amber-700 bg-amber-950/40 text-amber-200",
  emerald: "border-emerald-700 bg-emerald-950/40 text-emerald-200",
  sky:     "border-sky-700 bg-sky-950/40 text-sky-200",
  rose:    "border-rose-700 bg-rose-950/40 text-rose-200",
};

function _short(alert) {
  const t = alert.type;
  const key = alert.key || "?";
  if (t === "direction_flip") {
    return `${key}: ${alert.from} → ${alert.to} (r ${alert.prev_r ?? "?"}→${alert.cur_r ?? "?"})`;
  }
  if (t === "edge_decay") {
    return `${key}: |r| ${(alert.abs_r_trend || []).join(" → ")}`;
  }
  if (t === "edge_strengthen") {
    return `${key}: |r| ${(alert.abs_r_trend || []).join(" → ")}`;
  }
  if (t === "sample_milestone") {
    return `${key}: crossed ${alert.milestone}`;
  }
  if (t === "outcome_contradiction_streak") {
    return alert.summary || `${key}: ${alert.streak} in a row`;
  }
  if (t === "pressure_watch_high_priority") {
    return alert.summary || `${alert.asset || "Market"} pressure forming`;
  }
  return alert.summary || key;
}

export default function DriftBanner() {
  const driftAlerts = useStore((s) => s.driftAlerts);
  const [expanded, setExpanded] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  if (!driftAlerts || driftAlerts.length === 0 || dismissed) return null;

  const latest = driftAlerts[0];
  const tStyle = TYPE_STYLES[latest.type] || { color: "amber", icon: "⚠", title: "Drift" };
  const cls = COLOR_CLS[tStyle.color] || COLOR_CLS.amber;

  const ts = latest.ts_utc
    ? new Date(latest.ts_utc * 1000).toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit" })
    : "—";

  return (
    <div className={`border-l-4 rounded-r ${cls} px-3 py-2 mb-3`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-xs font-bold uppercase tracking-wider mb-1">
            {tStyle.icon} {tStyle.title}  <span className="opacity-60 font-mono">{ts} UTC</span>
          </div>
          <div className="text-xs font-mono break-words">{_short(latest)}</div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {driftAlerts.length > 1 && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-[10px] underline opacity-80 hover:opacity-100"
            >
              {expanded ? "hide" : `+${driftAlerts.length - 1} more`}
            </button>
          )}
          <button
            onClick={() => setDismissed(true)}
            className="text-[10px] opacity-60 hover:opacity-100"
            aria-label="dismiss"
          >
            ×
          </button>
        </div>
      </div>
      {expanded && driftAlerts.length > 1 && (
        <div className="mt-2 space-y-1 text-[11px] font-mono opacity-90 max-h-48 overflow-y-auto">
          {driftAlerts.slice(1).map((a, i) => {
            const sub = TYPE_STYLES[a.type] || TYPE_STYLES.direction_flip;
            const subTs = a.ts_utc
              ? new Date(a.ts_utc * 1000).toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit" })
              : "—";
            return (
              <div key={a.id || i} className="border-t border-current/20 pt-1">
                {sub.icon} {sub.title} · <span className="opacity-60">{subTs}</span>
                <div className="opacity-90 break-words">{_short(a)}</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
