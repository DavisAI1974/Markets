import React, { useEffect, useState } from "react";
import {
  fetchCouplingMatrix, fetchLeadLag, fetchDipoleSignals, fetchStrength, fetchDecoupling,
} from "../api.js";
import CouplingMatrix from "../components/CouplingMatrix.jsx";
import LeadLag from "../components/LeadLag.jsx";
import StrengthOverTime from "../components/StrengthOverTime.jsx";
import DecouplingFeed from "../components/DecouplingFeed.jsx";

const ASSETS = ["BTC", "ETH"];

/**
 * Coupling — the Operator-Discovery layer view: cross-source coupling matrix,
 * cross-venue lead-lag, per-source algebraic dipole, rolling strength, and the
 * decoupling-event feed. All backed by the real collector bins.
 */
export default function Coupling() {
  const [matrix, setMatrix] = useState(null);
  const [leadlag, setLeadlag] = useState({});
  const [dipoles, setDipoles] = useState(null);
  const [decoupling, setDecoupling] = useState(null);
  const [strengthSel, setStrengthSel] = useState(null);   // {asset, venue}
  const [strength, setStrength] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      fetchCouplingMatrix().then((d) => !cancelled && setMatrix(d)).catch(() => {});
      fetchDipoleSignals().then((d) => !cancelled && setDipoles(d)).catch(() => {});
      fetchDecoupling().then((d) => !cancelled && setDecoupling(d)).catch(() => {});
      ASSETS.forEach((a) =>
        fetchLeadLag(a).then((d) => !cancelled && setLeadlag((p) => ({ ...p, [a]: d }))).catch(() => {}));
    };
    load();
    const t = setInterval(load, 60000);
    return () => { cancelled = true; clearInterval(t); };
  }, []);

  // Default the strength selection to the first dipole source once it arrives.
  useEffect(() => {
    if (!strengthSel && dipoles?.signals?.length) {
      const s = dipoles.signals[0];
      setStrengthSel({ asset: s.asset, venue: s.venue });
    }
  }, [dipoles, strengthSel]);

  useEffect(() => {
    if (!strengthSel) return;
    let cancelled = false;
    fetchStrength(strengthSel.asset, strengthSel.venue)
      .then((d) => !cancelled && setStrength(d)).catch(() => setStrength(null));
    return () => { cancelled = true; };
  }, [strengthSel]);

  const ready = matrix?.ready;
  const computedAt = matrix?.computed_utc
    ? new Date(matrix.computed_utc * 1000).toLocaleTimeString("en-US", { hour12: false })
    : null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xs uppercase tracking-wider text-slate-500">Operator-Discovery coupling layer</h2>
        {computedAt && <span className="text-[10px] text-slate-500">computed {computedAt}</span>}
      </div>

      {!ready && (
        <div className="text-slate-500 text-sm py-4 text-center border border-slate-800 rounded">
          OD layer is computing from the real bins (first pass ~1-2 min after startup)…
        </div>
      )}

      <Section title="Coupling matrix">
        <CouplingMatrix data={matrix} />
      </Section>

      <Section title="Lead-lag (cross-venue)">
        <div className="space-y-4">
          {ASSETS.map((a) => (
            <div key={a}>
              <h4 className="font-mono text-xs text-slate-400 mb-1">{a}</h4>
              <LeadLag asset={a} data={leadlag[a]} />
            </div>
          ))}
        </div>
      </Section>

      <Section title="Algebraic dipole (per source)">
        <DipoleTable data={dipoles} onSelect={setStrengthSel} selected={strengthSel} />
      </Section>

      <Section title={`Coupling strength over time${strengthSel ? ` — ${strengthSel.asset}/${strengthSel.venue}` : ""}`}>
        <StrengthOverTime data={strength} />
      </Section>

      <Section title="Decoupling events">
        <DecouplingFeed data={decoupling} />
      </Section>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <section>
      <h3 className="text-[11px] uppercase tracking-wider text-slate-500 mb-1.5">{title}</h3>
      {children}
    </section>
  );
}

function DipoleTable({ data, onSelect, selected }) {
  if (!data) return <div className="text-slate-500 text-xs italic">loading…</div>;
  const sigs = data.signals || [];
  if (sigs.length === 0) return <div className="text-slate-500 text-xs italic">no dipole fits yet</div>;
  return (
    <div className="bg-slate-900 rounded p-2 border border-slate-800 overflow-x-auto">
      <table className="text-[11px] font-mono w-full">
        <thead className="text-slate-500">
          <tr className="text-left">
            <th className="p-1">source</th><th className="p-1">a</th><th className="p-1">b</th>
            <th className="p-1">c (quad)</th><th className="p-1">R²</th><th className="p-1">dir</th>
          </tr>
        </thead>
        <tbody>
          {sigs.map((s, i) => {
            const key = `${s.asset}/${s.venue}`;
            const sel = selected && `${selected.asset}/${selected.venue}` === key;
            return (
              <tr key={i}
                  onClick={() => onSelect({ asset: s.asset, venue: s.venue })}
                  className={`cursor-pointer ${sel ? "bg-slate-800" : "hover:bg-slate-800/50"}`}>
                <td className="p-1 text-slate-300">{key}</td>
                <td className="p-1 text-slate-400">{s.a.toFixed(3)}</td>
                <td className="p-1 text-slate-400">{s.b.toFixed(3)}</td>
                <td className="p-1 text-slate-400">{s.c.toFixed(4)}</td>
                <td className="p-1 text-slate-400">{s.r2.toFixed(3)}</td>
                <td className={`p-1 ${s.direction > 0 ? "text-emerald-400" : "text-rose-400"}`}>
                  {s.direction > 0 ? "H_a>H_b ↑" : "H_a<H_b ↓"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="text-[10px] text-slate-500 mt-1 px-1">
        H_a² = a + b·(H_a·H_b) + c·(H_a·H_b)². The quadratic c is the chem-dipole signature;
        c≈0 on these reconstructed channels (the exact construction is pending from Basic_equations).
        Click a row to see its strength series.
      </div>
    </div>
  );
}
