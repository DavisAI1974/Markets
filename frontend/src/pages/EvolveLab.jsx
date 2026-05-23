import React, { useEffect, useMemo, useState } from "react";
import { fetchEvolveRequests, postEvolveRequest } from "../api.js";

const MODES = {
  codebase: {
    label: "Codebase",
    target: "markets-watch strategy loop",
    goal: "Find brittle logic, propose a scoped patch, prove it with replay tests.",
  },
  language: {
    label: "Language",
    target: "Nova rule DSL",
    goal: "Promote repeated strategy patterns into reviewed language primitives.",
  },
  runtime: {
    label: "Runtime",
    target: "Python toolchain",
    goal: "Experiment behind flags, benchmark the corpus, and generate migrations.",
  },
};

const STAGES = [
  { key: "observe", label: "Observe", tone: "bg-sky-600", metric: "Signals, tests, traces" },
  { key: "propose", label: "Propose", tone: "bg-violet-600", metric: "Patch or primitive" },
  { key: "verify", label: "Verify", tone: "bg-amber-500", metric: "Tests, replay, audit" },
  { key: "govern", label: "Govern", tone: "bg-emerald-600", metric: "Scope and approval" },
  { key: "learn", label: "Learn", tone: "bg-cyan-600", metric: "Outcome memory" },
];

const BASE_PROPOSALS = [
  {
    id: "EV-018",
    title: "Quarantine continuation trades after dipole conflict",
    surface: "strategy_switcher.py",
    lift: "+7.4bp",
    risk: "medium",
    status: "ready",
    checks: ["unit", "6h replay", "risk caps"],
  },
  {
    id: "EV-019",
    title: "Extract pressure confirmation into a strategy primitive",
    surface: "Nova rule DSL",
    lift: "less duplication",
    risk: "low",
    status: "draft",
    checks: ["syntax", "migration", "readability"],
  },
  {
    id: "EV-020",
    title: "Reject patches that reduce cross-venue disagreement coverage",
    surface: "verification harness",
    lift: "safer merges",
    risk: "low",
    status: "ready",
    checks: ["invariant", "audit", "regression"],
  },
];

const MEMORY = [
  "Learned that profit-first replay improved day-one outcomes but overfit day-three remaining windows.",
  "Recorded failed continuation family where pressure state changed without cross-venue support.",
  "Promoted bucket quarantine smoke test into a required gate for strategy patches.",
];

export default function EvolveLab() {
  const [mode, setMode] = useState("codebase");
  const [autonomy, setAutonomy] = useState(38);
  const [activeStage, setActiveStage] = useState("observe");
  const [cycle, setCycle] = useState(1);
  const [humanApproval, setHumanApproval] = useState(true);
  const [shadowMode, setShadowMode] = useState(true);
  const [proposals, setProposals] = useState(BASE_PROPOSALS);
  const [requestPrompt, setRequestPrompt] = useState("");
  const [requestStatus, setRequestStatus] = useState("");
  const [requestError, setRequestError] = useState("");
  const [requestSaving, setRequestSaving] = useState(false);
  const [evolveRequests, setEvolveRequests] = useState([]);

  const profile = MODES[mode];
  const approvalGate = humanApproval ? "required" : "disabled";
  const executionMode = shadowMode ? "shadow branch" : "write branch";
  const selectedStage = STAGES.find((stage) => stage.key === activeStage) || STAGES[0];

  useEffect(() => {
    let cancelled = false;
    fetchEvolveRequests(8)
      .then((data) => {
        if (!cancelled) setEvolveRequests(data.requests || []);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const safetyScore = useMemo(() => {
    const approval = humanApproval ? 34 : 0;
    const shadow = shadowMode ? 26 : 8;
    const autonomyPenalty = Math.round(autonomy / 4);
    return Math.max(12, Math.min(98, 48 + approval + shadow - autonomyPenalty));
  }, [autonomy, humanApproval, shadowMode]);

  function runCycle() {
    const nextStageIndex = (STAGES.findIndex((stage) => stage.key === activeStage) + 1) % STAGES.length;
    setActiveStage(STAGES[nextStageIndex].key);
    setCycle((value) => value + 1);
    setProposals((items) => {
      const rotated = items.map((item, index) => {
        if (index !== 0) return item;
        return {
          ...item,
          status: item.status === "ready" ? "verified" : "ready",
        };
      });
      return [...rotated.slice(1), rotated[0]];
    });
  }

  async function submitRequest(event) {
    event.preventDefault();
    const prompt = requestPrompt.trim();
    if (!prompt) {
      setRequestError("Type what you want Evolve to make first.");
      return;
    }
    setRequestSaving(true);
    setRequestError("");
    setRequestStatus("");
    try {
      const data = await postEvolveRequest({ prompt, mode });
      setEvolveRequests((items) => [data.request, ...items].slice(0, 8));
      setRequestPrompt("");
      setRequestStatus("Saved to the evolve request queue.");
    } catch (e) {
      setRequestError(`Could not save: ${String(e?.message || e)}`);
    } finally {
      setRequestSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      <section className="rounded border border-slate-800 bg-slate-950 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500">Self-evolving system</div>
            <h1 className="mt-1 text-2xl font-semibold tracking-normal text-slate-100">{profile.target}</h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-400">{profile.goal}</p>
          </div>
          <div className="grid grid-cols-2 gap-2 text-right sm:min-w-48">
            <Metric label="cycle" value={`#${cycle}`} />
            <Metric label="safety" value={`${safetyScore}%`} intent={safetyScore > 70 ? "good" : "warn"} />
          </div>
        </div>

        <div className="mt-4 flex rounded bg-slate-900 p-1 ring-1 ring-slate-800">
          {Object.entries(MODES).map(([key, item]) => (
            <button
              key={key}
              type="button"
              onClick={() => setMode(key)}
              className={`flex-1 rounded px-2 py-2 text-xs font-semibold uppercase tracking-wider ${
                mode === key ? "bg-slate-700 text-slate-100" : "text-slate-400 hover:bg-slate-800 hover:text-slate-100"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </section>

      <section className="rounded border border-emerald-900/70 bg-emerald-950/20 p-3">
        <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-xs uppercase tracking-wider text-emerald-300">Make request</h2>
            <p className="mt-1 text-xs leading-5 text-slate-400">
              Capture a build idea for the evolution queue from this device.
            </p>
          </div>
          <span className="font-mono text-[10px] uppercase tracking-wider text-slate-500">{profile.label}</span>
        </div>
        <form onSubmit={submitRequest} className="space-y-2">
          <textarea
            value={requestPrompt}
            onChange={(event) => {
              setRequestPrompt(event.target.value);
              setRequestError("");
              setRequestStatus("");
            }}
            rows={5}
            placeholder="Example: add a safer auto-practice rule for whale buyer exhaustion..."
            className="min-h-32 w-full resize-y rounded border border-slate-700 bg-slate-950 px-3 py-2 text-base leading-6 text-slate-100 outline-none placeholder:text-slate-600 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 sm:text-sm"
          />
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-h-5 text-xs">
              {requestError && <span className="text-rose-300">{requestError}</span>}
              {requestStatus && <span className="text-emerald-300">{requestStatus}</span>}
            </div>
            <button
              type="submit"
              disabled={requestSaving}
              className="rounded bg-emerald-700 px-4 py-2 text-sm font-semibold text-emerald-50 hover:bg-emerald-600 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {requestSaving ? "Saving..." : "Send to evolve"}
            </button>
          </div>
        </form>
        {evolveRequests.length > 0 && (
          <div className="mt-3 space-y-2">
            <div className="text-[10px] uppercase tracking-wider text-slate-500">Recent requests</div>
            {evolveRequests.map((request) => (
              <div key={request.id} className="rounded border border-slate-800 bg-slate-950 p-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[10px] text-slate-500">{request.id}</span>
                  <span className="rounded bg-slate-900 px-2 py-0.5 text-[10px] uppercase tracking-wider text-slate-400">
                    {request.status || "new"}
                  </span>
                </div>
                <p className="mt-1 line-clamp-3 text-xs leading-5 text-slate-300">{request.prompt}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="grid gap-3 lg:grid-cols-[1.25fr_0.75fr]">
        <div className="rounded border border-slate-800 bg-slate-900/70 p-3">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="text-xs uppercase tracking-wider text-slate-500">Evolution loop</h2>
            <button
              type="button"
              onClick={runCycle}
              className="rounded bg-emerald-700 px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-emerald-50 hover:bg-emerald-600"
            >
              Run cycle
            </button>
          </div>

          <div className="grid grid-cols-5 gap-2">
            {STAGES.map((stage) => (
              <button
                key={stage.key}
                type="button"
                onClick={() => setActiveStage(stage.key)}
                className={`min-h-24 rounded border p-2 text-left transition ${
                  activeStage === stage.key
                    ? "border-slate-400 bg-slate-800"
                    : "border-slate-800 bg-slate-950 hover:border-slate-600"
                }`}
              >
                <span className={`mb-2 block h-1.5 rounded ${stage.tone}`} />
                <span className="block text-xs font-semibold text-slate-100">{stage.label}</span>
                <span className="mt-1 block text-[10px] leading-4 text-slate-500">{stage.metric}</span>
              </button>
            ))}
          </div>

          <div className="mt-3 rounded border border-slate-800 bg-slate-950 p-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-slate-100">{selectedStage.label} gate</div>
                <p className="mt-1 text-xs leading-5 text-slate-400">
                  The system can move through this stage only when its local evidence is attached to the proposal.
                  Autonomy controls how far it may go before asking for review.
                </p>
              </div>
              <span className={`rounded px-2 py-1 text-[10px] uppercase tracking-wider ${selectedStage.tone} text-white`}>
                active
              </span>
            </div>
          </div>
        </div>

        <div className="rounded border border-slate-800 bg-slate-900/70 p-3">
          <h2 className="mb-3 text-xs uppercase tracking-wider text-slate-500">Governor</h2>
          <label className="block text-xs text-slate-400">
            Autonomy
            <input
              type="range"
              min="0"
              max="100"
              value={autonomy}
              onChange={(e) => setAutonomy(Number(e.target.value))}
              className="mt-2 w-full accent-emerald-600"
            />
          </label>
          <div className="mt-2 flex items-center justify-between font-mono text-xs text-slate-500">
            <span>manual</span>
            <span>{autonomy}%</span>
            <span>agentic</span>
          </div>

          <Toggle checked={shadowMode} onChange={setShadowMode} label="Shadow mode" value={executionMode} />
          <Toggle checked={humanApproval} onChange={setHumanApproval} label="Human approval" value={approvalGate} />

          <div className="mt-4 grid grid-cols-2 gap-2">
            <Metric label="max patch" value={autonomy > 70 ? "medium" : "small"} />
            <Metric label="merge path" value={humanApproval ? "PR" : "blocked"} />
          </div>
        </div>
      </section>

      <section className="rounded border border-slate-800 bg-slate-900/70 p-3">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xs uppercase tracking-wider text-slate-500">Proposal queue</h2>
          <span className="font-mono text-[10px] text-slate-500">{proposals.length} candidates</span>
        </div>
        <div className="space-y-2">
          {proposals.map((proposal) => (
            <article key={proposal.id} className="rounded border border-slate-800 bg-slate-950 p-3">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-wider text-slate-500">{proposal.id} · {proposal.surface}</div>
                  <h3 className="mt-1 text-sm font-semibold text-slate-100">{proposal.title}</h3>
                </div>
                <div className="flex gap-2 text-[10px] uppercase tracking-wider">
                  <Badge tone={proposal.status === "verified" ? "good" : "neutral"}>{proposal.status}</Badge>
                  <Badge tone={proposal.risk === "medium" ? "warn" : "good"}>{proposal.risk}</Badge>
                </div>
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-[7rem_1fr]">
                <div className="rounded bg-slate-900 p-2">
                  <div className="text-[10px] uppercase tracking-wider text-slate-500">expected lift</div>
                  <div className="mt-1 font-mono text-sm text-emerald-300">{proposal.lift}</div>
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                  {proposal.checks.map((check) => (
                    <span key={check} className="rounded bg-slate-900 px-2 py-1 text-[10px] uppercase tracking-wider text-slate-400">
                      {check}
                    </span>
                  ))}
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="grid gap-3 lg:grid-cols-2">
        <div className="rounded border border-slate-800 bg-slate-900/70 p-3">
          <h2 className="mb-3 text-xs uppercase tracking-wider text-slate-500">Memory</h2>
          <div className="space-y-2">
            {MEMORY.map((entry) => (
              <div key={entry} className="rounded border border-slate-800 bg-slate-950 p-2 text-xs leading-5 text-slate-400">
                {entry}
              </div>
            ))}
          </div>
        </div>
        <div className="rounded border border-slate-800 bg-slate-900/70 p-3">
          <h2 className="mb-3 text-xs uppercase tracking-wider text-slate-500">Promotion rules</h2>
          <Rule passed={shadowMode}>Every change starts in a disposable branch with attached evidence.</Rule>
          <Rule passed={humanApproval}>Production merge requires an explicit reviewer decision.</Rule>
          <Rule passed={autonomy < 80}>High-autonomy changes stay below the shared-runtime boundary.</Rule>
          <Rule passed>Failed experiments become negative examples in memory.</Rule>
        </div>
      </section>
    </div>
  );
}

function Metric({ label, value, intent = "neutral" }) {
  const color = intent === "good" ? "text-emerald-300" : intent === "warn" ? "text-amber-300" : "text-slate-100";
  return (
    <div className="rounded border border-slate-800 bg-slate-900 p-2">
      <div className="text-[10px] uppercase tracking-wider text-slate-500">{label}</div>
      <div className={`mt-1 font-mono text-sm ${color}`}>{value}</div>
    </div>
  );
}

function Toggle({ checked, onChange, label, value }) {
  return (
    <label className="mt-4 flex cursor-pointer items-center justify-between gap-3 rounded border border-slate-800 bg-slate-950 p-3">
      <span>
        <span className="block text-xs font-semibold text-slate-100">{label}</span>
        <span className="mt-1 block font-mono text-[10px] uppercase tracking-wider text-slate-500">{value}</span>
      </span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-5 w-5 accent-emerald-600"
      />
    </label>
  );
}

function Badge({ tone, children }) {
  const classes = {
    good: "bg-emerald-950 text-emerald-300 ring-emerald-800",
    warn: "bg-amber-950 text-amber-300 ring-amber-800",
    neutral: "bg-slate-900 text-slate-300 ring-slate-700",
  };
  return (
    <span className={`rounded px-2 py-1 ring-1 ${classes[tone] || classes.neutral}`}>
      {children}
    </span>
  );
}

function Rule({ passed, children }) {
  return (
    <div className="mb-2 flex items-start gap-2 rounded border border-slate-800 bg-slate-950 p-2 text-xs leading-5 text-slate-400">
      <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${passed ? "bg-emerald-500" : "bg-amber-500"}`} />
      <span>{children}</span>
    </div>
  );
}
