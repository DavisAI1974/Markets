import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchSignalDetail } from "../api.js";
import DipoleChart from "../components/DipoleChart.jsx";

export default function SignalDetail() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchSignalDetail(id).then(setData).catch((e) => setError(e.message));
  }, [id]);

  if (error) return <div className="text-red-400 text-sm">Error: {error}</div>;
  if (!data) return <div className="text-slate-500 text-sm">Loading…</div>;

  const sig = data.signal;
  const time = new Date(sig.timestamp_utc * 1000).toLocaleString();
  const conf = sig.adjusted_confidence ?? sig.confidence ?? 0;
  const cvm = sig.cross_venue_multiplier ?? 1.0;

  return (
    <div className="space-y-4">
      <Link to="/signals" className="text-xs text-slate-400 hover:text-slate-200">← back to feed</Link>

      <div className="bg-slate-900 rounded-lg p-4 border border-slate-800">
        <div className="flex items-start justify-between mb-2">
          <div>
            <div className="font-mono text-lg font-semibold">{sig.regime.replace(/_/g, " ")}</div>
            <div className="text-sm text-slate-400">{sig.asset}-USD · {sig.venue}</div>
          </div>
          <div className="text-right text-xs text-slate-500 font-mono">
            {time}
            <div className="mt-1">conf {(conf * 100).toFixed(0)}%</div>
          </div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3 text-xs">
          <Metric label="mean dipole" value={sig.mean_dipole?.toFixed(3)} />
          <Metric label="realized vol" value={(sig.realized_vol * 1e4).toFixed(1) + " bp"} />
          <Metric label="chunk volume" value={sig.chunk_volume?.toFixed(2)} />
          <Metric label="cross-venue mult" value={cvm.toFixed(2)} />
        </div>
        <div className="mt-3 p-3 bg-slate-950 rounded text-sm">
          <div className="text-slate-400 text-xs uppercase tracking-wider mb-1">Playbook</div>
          {sig.playbook}
        </div>
        {sig.notes && sig.notes.length > 0 && (
          <details className="mt-3 text-xs">
            <summary className="text-slate-400 cursor-pointer">Why this fired</summary>
            <ul className="mt-2 text-slate-300 list-disc pl-5 space-y-1">
              {sig.notes.map((n, i) => <li key={i} className="font-mono">{n}</li>)}
            </ul>
          </details>
        )}
      </div>

      <div className="bg-slate-900 rounded-lg p-4 border border-slate-800">
        <DipoleChart data={data.chart} />
      </div>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="bg-slate-950 rounded px-2 py-1.5">
      <div className="text-slate-500 text-[10px] uppercase tracking-wide">{label}</div>
      <div className="font-mono text-sm mt-0.5">{value ?? "—"}</div>
    </div>
  );
}
