import React from "react";

// Heat color for a |cross-correlation| in [0,1]: slate -> teal -> green.
function ccColor(cc) {
  const v = Math.max(0, Math.min(1, cc));
  if (v < 0.2) return "bg-slate-800 text-slate-400";
  if (v < 0.4) return "bg-teal-900/60 text-teal-200";
  if (v < 0.6) return "bg-teal-700/70 text-teal-50";
  if (v < 0.8) return "bg-emerald-600/80 text-white";
  return "bg-emerald-500 text-white";
}

/**
 * CouplingMatrix — lag-0 |cross-correlation| heatmap across sources, with the
 * OD structured-coupling verdict marked. Reads /api/coupling_matrix.
 */
export default function CouplingMatrix({ data }) {
  if (!data) return <div className="text-slate-500 text-xs italic">loading…</div>;
  const pairs = data.pairs || [];
  if (pairs.length === 0) {
    return <div className="text-slate-500 text-xs italic">no coupling data yet (OD layer still computing)</div>;
  }
  // Build the set of node labels in first-seen order.
  const nodes = [];
  pairs.forEach((p) => { [p.a, p.b].forEach((n) => { if (!nodes.includes(n)) nodes.push(n); }); });
  const cell = {};
  pairs.forEach((p) => { cell[`${p.a}|${p.b}`] = p; cell[`${p.b}|${p.a}`] = p; });

  return (
    <div className="bg-slate-900 rounded p-3 border border-slate-800 overflow-x-auto">
      <table className="text-[10px] font-mono border-collapse">
        <thead>
          <tr>
            <th className="p-1"></th>
            {nodes.map((n) => (
              <th key={n} className="p-1 text-slate-400 align-bottom">
                <div className="rotate-[-45deg] origin-bottom-left whitespace-nowrap h-12 w-5">{n}</div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {nodes.map((rn) => (
            <tr key={rn}>
              <td className="p-1 text-slate-400 whitespace-nowrap pr-2 text-right">{rn}</td>
              {nodes.map((cn) => {
                if (rn === cn) return <td key={cn} className="p-1 bg-slate-950 text-slate-700 text-center">·</td>;
                const p = cell[`${rn}|${cn}`];
                if (!p) return <td key={cn} className="p-1 bg-slate-950"></td>;
                return (
                  <td
                    key={cn}
                    className={`p-1 text-center ${ccColor(p.cc0)} ${p.structured ? "ring-1 ring-inset ring-amber-400" : ""}`}
                    title={`${p.a} <> ${p.b}\n|cc0|=${p.cc0.toFixed(3)} ${p.pair_kind}\n${p.structured ? `STRUCTURED (mi=${p.mi_frac.toFixed(2)}, chem=${p.chem_frac.toFixed(2)})` : "not structured"}`}
                  >
                    {p.cc0.toFixed(2).slice(1)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="text-[10px] text-slate-500 mt-2 flex flex-wrap gap-3">
        <span>cell = lag-0 |cross-correlation| of log returns</span>
        <span><span className="inline-block w-3 h-3 mr-1 rounded ring-1 ring-inset ring-amber-400 align-middle" />amber ring = OD structured coupling (MI / chem residual in the null)</span>
      </div>
    </div>
  );
}
