/* adapter.js - wires the prototype UI to the real read plane (/api/v1).
 *
 * Doctrine (DASHBOARD_HANDOFF_S100): every panel is badged with its truth level -
 *   REAL DATA      backed by an actual store on this machine
 *   AWAITING DATA  the store exists on S3 but is not in the local cache (or creds absent)
 *   SIMULATED      prototype placeholder; no real counterpart exists yet (executor lane is last)
 * Probabilities/confidences keep provenance labels; per-event rows, never pooled headlines;
 * maker-first economics; expected windows come from the lag map, never a fixed constant.
 */
(() => {
  "use strict";

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const API = "/api/v1";

  const state = { day: null, snapshot: null };

  /* ---------- badges ---------- */

  function badge(panelSel, level, note) {
    const panel = $(panelSel);
    if (!panel) return;
    const header = panel.querySelector(".panel-header");
    if (!header) return;
    let b = header.querySelector(".data-badge");
    if (!b) {
      b = document.createElement("span");
      b.className = "data-badge";
      header.appendChild(b);
    }
    b.classList.remove("real", "awaiting", "sim");
    b.classList.add(level);
    b.textContent = level === "real" ? "REAL DATA" : level === "awaiting" ? "AWAITING DATA" : "SIMULATED";
    if (note) b.title = note;
  }

  const SIMULATED_PANELS = [
    ".opportunities-panel", ".coach-panel", ".ledger-panel",
    ".wide-chart-panel", ".perception-panel", ".staircase-panel", ".od-panel", ".order-life-panel",
    ".weather-table-panel", ".distribution-panel", ".contribution-panel", ".calibration-panel",
    ".replay-control-panel", ".replay-chart-panel",
    ".exposure-panel", ".scenario-panel", ".limits-panel", ".audit-panel",
  ];

  /* ---------- helpers ---------- */

  async function get(path) {
    const r = await fetch(API + path);
    if (!r.ok) throw new Error(`${path} -> ${r.status}`);
    return r.json();
  }

  function fmt(v) {
    if (v === null || v === undefined) return "—";
    if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(2);
    return String(v);
  }

  function blockHeadline(name, block) {
    if (block === null || block === undefined) return "awaiting data";
    if (typeof block !== "object") return fmt(block);
    const skip = new Set(["note"]);
    const parts = [];
    for (const [k, v] of Object.entries(block)) {
      if (skip.has(k) || v === null || typeof v === "object") continue;
      parts.push(`${k} ${fmt(v)}`);
      if (parts.length >= 4) break;
    }
    return parts.join(" · ") || "present";
  }

  /* ---------- topbar: day picker + environment pill ---------- */

  function installDayPicker() {
    const actions = $(".topbar-actions");
    if (!actions || $("#asofDay")) return;
    const wrap = document.createElement("label");
    wrap.className = "asof-picker";
    wrap.innerHTML = `<span>AS-OF</span><input type="date" id="asofDay" />`;
    actions.insertBefore(wrap, actions.firstChild);
    $("#asofDay").addEventListener("change", e => {
      const v = e.target.value;
      if (v) loadSnapshot(v.replace(/-/g, ""));
    });
  }

  function setEnvironmentPill(snap) {
    const pill = $(".environment-pill");
    if (!pill) return;
    const h = snap.health;
    const creds = h.aws_credentials.resolved;
    const n = snap.decision_state.n_blocks_fed ?? 0;
    const total = snap.decision_state.n_blocks_total ?? 22;
    pill.innerHTML = creds
      ? `<span class="status-dot positive"></span>READ PLANE · ${n}/${total} BLOCKS FED`
      : `<span class="status-dot warning"></span>READ PLANE · AWAITING AWS CREDENTIALS · ${n}/${total} BLOCKS`;
    pill.title = creds ? "" : h.aws_credentials.note || "";
  }

  /* ---------- health chips: repurposed as data-plane truth ---------- */

  function setHealthChips(snap) {
    window.__REAL_HEALTH__ = true;   // stops app.js from writing fake latencies
    const h = snap.health;
    const chips = [
      ["cme", "NYMEX tape", h.nymex_days_local > 0 ? `${h.nymex_days_local} days` : "awaiting", h.nymex_days_local > 0],
      ["kalshi", "Kalshi raw", h.kalshi_raw_present ? "local" : "awaiting", h.kalshi_raw_present],
      ["poly", "Lag map", h.lag_map_present ? "local" : "awaiting", h.lag_map_present],
      ["weather", "Stores", `${h.stores_present}/${h.stores_total}`, h.stores_present > 0],
    ];
    $$(".health-chip").forEach((chip, i) => {
      if (!chips[i]) return;
      const [, label, value, ok] = chips[i];
      chip.innerHTML = `<span class="status-dot ${ok ? "positive" : "warning"}"></span><span>${label}</span><strong>${value}</strong>`;
      chip.title = "data-plane availability on this machine (not venue latency - no live feed here)";
    });
  }

  /* ---------- mission metric cards ---------- */

  function setMetricCards(snap) {
    const cards = $$("#view-mission .metric-card");
    if (cards.length < 4) return;
    const ds = snap.decision_state, br = snap.brain, lm = snap.lag_map, h = snap.health;
    const atm = lm.available ? lm.response_rate_by_band?.ATM : null;
    const defs = [
      ["Decision state (as-of)", `${ds.n_blocks_fed ?? 0}/${ds.n_blocks_total ?? 22}`,
       ds.available ? "blocks fed" : "error",
       `day ${snap.as_of_day} · ${ds.mode || ""} · missing = awaiting store pull`, ds.n_blocks_fed > 0],
      ["Brain (signal core)", br.version || "?", `${br.n_plays} plays`,
       `targets: ${(br.targets || []).join(", ")} · inventory, not calls`, true],
      ["Lag map (feed M)", lm.available ? `${lm.n_event_days} days` : "—",
       lm.available ? `${lm.n_rows.toLocaleString()} rows` : "awaiting data",
       lm.available ? `ATM response ${atm ? (atm.rate * 100).toFixed(0) + "%" : "?"} · per-cell windows drive the edge clock` : (lm.reason || ""), lm.available],
      ["Data plane", `${h.stores_present}/${h.stores_total}`,
       h.aws_credentials.resolved ? "stores local" : "no AWS creds",
       h.aws_credentials.resolved ? "platform_sync pulls fill the rest" : (h.aws_credentials.note || ""), h.aws_credentials.resolved],
    ];
    cards.forEach((card, i) => {
      const [label, big, delta, small, ok] = defs[i];
      card.innerHTML = `<span class="metric-label">${label}</span>
        <div class="metric-value"><strong>${big}</strong><span class="metric-delta ${ok ? "positive" : "neutral"}">${delta}</span></div>
        <small>${small}</small>`;
    });
  }

  /* ---------- edge clock: lag-map per-cell window ---------- */

  async function setEdgeClock() {
    const stateEl = $("#edgeClockState");
    const ticks = $(".edge-ticks");
    const valueEl = $("#edgeClockValue");
    if (!stateEl) return;
    try {
      const w = await get("/lag-map/window?band=ATM");
      if (w.available && w.n > 0) {
        window.__REAL_WINDOW__ = true;  // stops app.js fake clock churn
        valueEl.textContent = `ATM cell · n=${w.n}`;
        stateEl.textContent = `Measured window (this regime): min ${w.delay_min_s}s · med ${w.delay_med_s}s · p90 ${w.delay_p90_s}s`;
        stateEl.className = "positive";
        stateEl.title = w.note || "";
        if (ticks) ticks.innerHTML = `<span>0s</span><span>min ${w.delay_min_s}s</span><span>med ${w.delay_med_s}s</span><span>p90 ${w.delay_p90_s}s</span>`;
        const prog = $("#edgeProgress"), now = $("#edgeNow");
        if (prog) prog.style.width = "0%";
        if (now) now.style.left = "0%";
      } else {
        stateEl.textContent = "Expected window awaits the lag map store (per-cell, never a fixed constant)";
        stateEl.className = "warning";
      }
    } catch {
      stateEl.textContent = "Expected window awaits the lag map store";
      stateEl.className = "warning";
    }
  }

  /* ---------- state delta tape -> decision-state block table ---------- */

  function setDeltaTape(snap) {
    const el = $("#deltaTape");
    if (!el) return;
    const ds = snap.decision_state;
    const panel = $(".delta-panel");
    if (panel) {
      const kicker = panel.querySelector(".panel-kicker");
      const h2 = panel.querySelector("h2");
      const countBtn = panel.querySelector(".panel-header .text-button");
      if (kicker) kicker.textContent = "AS-OF DECISION STATE";
      if (h2) h2.textContent = `Blocks · ${snap.as_of_day}`;
      if (countBtn) countBtn.textContent = `${ds.n_blocks_fed ?? 0}/${ds.n_blocks_total ?? 22} fed`;
    }
    if (!ds.available) {
      el.innerHTML = `<div class="delta-row"><div><strong>decision_state unavailable</strong><small>${(ds.error || "").slice(0, 200)}</small></div></div>`;
      return;
    }
    const s = ds.state || {};
    const scalarRow = `<div class="delta-row"><time>day</time><span class="delta-node"></span><div><strong>${s.dow || "?"} · surprise ${fmt(s.stor_surprise)} ${s.stor_surprise_sign || ""} · curve ${s.curve_regime || "?"}</strong><small>day scalars</small></div><em>SCALARS</em></div>`;
    const keys = (ds.blocks_fed || []).concat(ds.blocks_awaiting_data || []);
    el.innerHTML = scalarRow + keys.map(k => {
      const fed = (ds.blocks_fed || []).includes(k);
      const b = s[k];
      const noteTitle = b && typeof b === "object" && b.note ? String(b.note).replace(/"/g, "&quot;") : "";
      return `<div class="delta-row" title="${noteTitle}"><time>${fed ? "fed" : "—"}</time><span class="delta-node ${fed ? "" : "pending"}"></span>
        <div><strong>${k}</strong><small>${fed ? blockHeadline(k, b) : "awaiting data (store not local / no coverage)"}</small></div>
        <em class="${fed ? "" : "muted"}">${fed ? "FED" : "AWAITING"}</em></div>`;
    }).join("");
    el.title = ds.note || "";
  }

  /* ---------- ledgers: doctrine relabel ---------- */

  function relabelLedgers() {
    const cards = $$(".ledger-card");
    cards.forEach(card => {
      const strongs = card.querySelectorAll(".ledger-metrics strong");
      strongs.forEach(s => { s.textContent = "—"; s.classList.remove("positive"); });
      const rule = card.querySelector(".ledger-rule strong");
      if (rule) { rule.textContent = "NO LEDGER YET"; rule.classList.remove("positive"); }
      const b = card.querySelector(".badge");
      if (b) { b.textContent = "NOT BUILT"; b.className = "badge"; }
    });
    const poly = cards[2];
    if (poly) {
      const rule = poly.querySelector(".ledger-rule strong");
      if (rule) rule.textContent = "CONTEXT-ONLY (doctrine)";
      const b = poly.querySelector(".badge");
      if (b) b.textContent = "CONTEXT-ONLY";
    }
  }

  /* ---------- episode: play stack from the brain ---------- */

  function setPlayStack(snap) {
    const wrap = $(".play-groups");
    if (!wrap) return;
    const br = snap.brain;
    const groups = Object.entries(br.plays_by_target || {}).map(([target, plays]) => {
      const rows = plays.map(p => {
        const conf = p.confidence !== null && p.confidence !== undefined ? p.confidence.toFixed(2) : "—";
        const fe = String(p.forward_evidence || "");
        const prov = fe.startsWith("FORWARD-CONFIRMED") ? "FWD-CONFIRMED" : (p.status || "PROVISIONAL");
        const req = Array.isArray(p.requires) ? p.requires.join(", ") : (p.requires || "");
        const tip = `${p.read || ""}\n\nforward_evidence: ${fe}`.replace(/"/g, "&quot;");
        return `<div class="play-row" title="${tip}">
          <span>${p.id}</span><strong>${conf}</strong>
          <small>${req ? "requires: " + String(req).slice(0, 60) : (p.trigger || "").slice(0, 60)}</small>
          <em>${String(prov).toUpperCase().slice(0, 14)}</em></div>`;
      }).join("");
      return `<div class="play-group"><h3>${target.toUpperCase()}</h3>${rows}</div>`;
    }).join("");
    wrap.innerHTML = groups;
    const panel = $(".play-stack-panel");
    if (panel) {
      const h2 = panel.querySelector("h2");
      if (h2) h2.textContent = `Play Inventory · brain ${br.version}`;
      const btn = panel.querySelector(".panel-header .text-button");
      if (btn) { btn.textContent = "confidence = brain value, provenance labeled"; btn.disabled = true; }
      badge(".play-stack-panel", "real", br.provenance_note);
    }
  }

  /* ---------- weather view ---------- */

  function setWeather(snap) {
    const s = (snap.decision_state && snap.decision_state.state) || {};
    const strip = $(".weather-summary-strip");
    if (strip) {
      const wx = s.weather, wf = s.weather_forecast, fr = s.freeze_risk;
      strip.innerHTML = [
        ["Realized regime", wx ? blockHeadline("weather", wx) : "awaiting data"],
        ["Forecast (MOS as-of)", wf ? blockHeadline("weather_forecast", wf) : "awaiting data"],
        ["Freeze risk (feed E)", fr ? blockHeadline("freeze_risk", fr) : "awaiting data"],
        ["Model disagreement", s.model_disagreement ? blockHeadline("md", s.model_disagreement) : "awaiting data"],
        ["Doctrine", "forecaster = Greg's spec · HANDS OFF"],
      ].map(([k, v]) => `<div><span>${k}</span><strong>${v}</strong></div>`).join("");
    }
    const cyc = $(".cycle-timeline");
    if (cyc) {
      const c = s.weather_forecast_cycle;
      if (c && typeof c === "object") {
        const rows = Object.entries(c).filter(([k, v]) => k !== "note" && v !== null && typeof v !== "object")
          .slice(0, 6)
          .map(([k, v]) => `<div class="cycle-row"><time>·</time><span class="cycle-line"></span><div><strong>${k}: ${fmt(v)}</strong></div></div>`)
          .join("");
        cyc.innerHTML = rows || cyc.innerHTML;
        badge(".cycle-panel", "real", c.note || "cycle-level MOS as-of");
      } else {
        badge(".cycle-panel", "awaiting", "weather_forecast_cycle block absent - pull the MOS cycle store");
      }
    }
  }

  /* ---------- replay view: as-of inspector ---------- */

  function setReplay(snap) {
    const ds = snap.decision_state;
    const dl = $(".snapshot-list");
    if (dl) {
      dl.innerHTML = [
        ["As-of day", snap.as_of_day],
        ["Assembly mode", ds.mode || "—"],
        ["Blocks fed", `${ds.n_blocks_fed ?? 0} / ${ds.n_blocks_total ?? 22}`],
        ["Brain", snap.brain.version],
        ["Generated (UTC)", snap.generated_at_utc],
        ["Doctrine", "as-of only; nothing revised, nothing interpolated"],
      ].map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("");
      badge(".snapshot-panel", "real");
    }
    const req = $("#replayRequirements");
    if (req && snap.brain.plays_by_target) {
      const rows = [];
      for (const [target, plays] of Object.entries(snap.brain.plays_by_target)) {
        for (const p of plays) {
          if (!p.requires) continue;
          const r = Array.isArray(p.requires) ? p.requires.join(", ") : String(p.requires);
          rows.push(`<div class="requirement-row"><div><strong>${p.id}</strong><small>${r.slice(0, 110)}</small></div><span>${target.toUpperCase()}</span></div>`);
        }
      }
      req.innerHTML = rows.join("") || "<div class='requirement-row'><div><strong>no requires fields</strong></div></div>";
      badge(".requirements-panel", "real", "each play's `requires` from the brain - the invocation gate contract");
      const reqBadge = $(".requirements-panel .panel-header .badge");
      if (reqBadge) reqBadge.remove();
    }
    const lineage = $(".lineage-panel");
    if (lineage) {
      const flow = lineage.querySelector(".lineage-flow");
      const note = lineage.querySelector(".lineage-note");
      if (flow) flow.remove();
      if (note) {
        note.innerHTML = `<pre class="asof-json">${JSON.stringify(ds.state || ds, null, 1)
          .replace(/&/g, "&amp;").replace(/</g, "&lt;")}</pre>`;
      }
      const h2 = lineage.querySelector("h2");
      if (h2) h2.textContent = "Raw as-of decision_state JSON";
      badge(".lineage-panel", "real", "verbatim decision_state output for the selected day");
    }
  }

  /* ---------- risk/ops connectors: store truth ---------- */

  function setConnectors(snap) {
    const el = $("#connectorList");
    if (!el) return;
    const h = snap.health;
    const rows = [];
    rows.push(`<div class="connector-row"><div><strong>AWS credentials</strong><small>explicit pair only; container placeholders ignored</small></div><span>${h.aws_credentials.resolved ? "resolved" : "absent"}</span><span></span><span class="connector-state"><i class="status-dot ${h.aws_credentials.resolved ? "positive" : "warning"}"></i>${h.aws_credentials.resolved ? "OK" : "AWAITING"}</span></div>`);
    rows.push(`<div class="connector-row"><div><strong>Live GLBX feed</strong><small>${h.live_feed.note.slice(0, 90)}…</small></div><span>AWS box only</span><span></span><span class="connector-state"><i class="status-dot warning"></i>NOT HERE</span></div>`);
    rows.push(`<div class="connector-row"><div><strong>Execution lane</strong><small>${h.execution.note.slice(0, 90)}…</small></div><span>not built</span><span></span><span class="connector-state"><i class="status-dot"></i>BY DESIGN</span></div>`);
    for (const s of h.stores) {
      const ok = s.present;
      const detail = s.files !== undefined ? `${s.files} files` : (s.bytes !== undefined ? `${(s.bytes / 1e6).toFixed(1)} MB` : "");
      rows.push(`<div class="connector-row"><div><strong>${s.label}</strong><small>${s.feeds}</small></div><span>${s.s3_prefix}</span><span>${detail}</span><span class="connector-state"><i class="status-dot ${ok ? "positive" : "warning"}"></i>${ok ? "LOCAL" : "AWAITING"}</span></div>`);
    }
    el.innerHTML = rows.join("");
    badge(".connector-panel", "real", "data-plane truth for this machine");
    const panel = $(".connector-panel");
    if (panel) {
      const h2 = panel.querySelector("h2");
      if (h2) h2.textContent = "Store and feed availability";
    }
  }

  /* ---------- mission chart: real leader/follower when local ---------- */

  async function setMissionChart(snap) {
    const day = snap.as_of_day;
    const chartPanel = ".active-episode-panel";
    try {
      const ny = await get(`/nymex/minute-bars/${day}`);
      if (!ny.available) {
        badge(chartPanel, "awaiting", ny.reason || "tape not local");
        return;
      }
      // leader series: minute closes (follower overlay = future Kalshi candle join)
      const leader = ny.bars.map(b => b[1]);
      const el = $("#missionChart");
      if (el && leader.length > 8) {
        window.__REAL_CHART__ = true;
        drawRealChart(el, leader);
        const sym = $("#leaderSymbol"), px = $("#leaderPrice"), mv = $("#leaderMove");
        if (sym) sym.textContent = "NG cont";
        if (px) px.textContent = leader[leader.length - 1].toFixed(3);
        if (mv) {
          const d = leader[leader.length - 1] - leader[0];
          mv.textContent = `${d >= 0 ? "+" : ""}${d.toFixed(3)}`;
          mv.className = d >= 0 ? "positive" : "negative";
        }
        const title = $("#episodeTitle"), sub = $("#episodeSubtitle");
        if (title) title.textContent = `NG leader · ${day}`;
        if (sub) sub.textContent = `${ny.n_ticks.toLocaleString()} ticks · ${ny.n_minutes} minutes · S3 nymex_cont (as-of replay, not live)`;
        badge(chartPanel, "real", "leader = real minute bars; follower overlay awaits Kalshi candle join");
      }
    } catch {
      badge(chartPanel, "awaiting", "tape not local");
    }
  }

  function drawRealChart(el, leader) {
    const w = Math.max(500, el.clientWidth || 800);
    const h = Math.max(170, el.clientHeight || 220);
    const pad = { l: 42, r: 44, t: 18, b: 22 };
    const innerW = w - pad.l - pad.r, innerH = h - pad.t - pad.b;
    const min = Math.min(...leader), max = Math.max(...leader);
    const span = (max - min) || 1;
    const x = i => pad.l + (i / (leader.length - 1)) * innerW;
    const y = v => pad.t + (1 - (v - min) / span) * innerH;
    const pts = leader.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
    const grid = [0, .25, .5, .75, 1].map(p => `<line x1="${pad.l}" y1="${pad.t + innerH * p}" x2="${w - pad.r}" y2="${pad.t + innerH * p}"/>`).join("");
    const labels = [[0, min + span], [1, min]].map(([p, v]) =>
      `<text class="chart-label" x="${pad.l - 6}" y="${pad.t + innerH * p + 3}" text-anchor="end">${(p === 0 ? max : min).toFixed(2)}</text>`).join("");
    el.innerHTML = `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="NG continuous minute bars (real)">
      <g class="chart-grid">${grid}</g>
      <polyline class="chart-price" points="${pts}" />
      <circle class="chart-last" cx="${x(leader.length - 1)}" cy="${y(leader[leader.length - 1])}" r="3" />
      ${labels}
      <text class="chart-label" x="${w - 5}" y="${y(leader[leader.length - 1]) + 3}" text-anchor="end">leader</text>
    </svg>`;
  }

  /* ---------- load + orchestrate ---------- */

  async function loadSnapshot(day8) {
    let snap;
    try {
      snap = await get(`/desk/snapshot${day8 ? `?day=${day8}` : ""}`);
    } catch (e) {
      const pill = $(".environment-pill");
      if (pill) pill.innerHTML = `<span class="status-dot warning"></span>API UNREACHABLE (open via the server, not file://)`;
      return;
    }
    state.day = snap.as_of_day;
    state.snapshot = snap;
    const dp = $("#asofDay");
    if (dp && !dp.value) dp.value = `${snap.as_of_day.slice(0, 4)}-${snap.as_of_day.slice(4, 6)}-${snap.as_of_day.slice(6)}`;
    setEnvironmentPill(snap);
    setHealthChips(snap);
    setMetricCards(snap);
    setDeltaTape(snap);
    relabelLedgers();
    setPlayStack(snap);
    setWeather(snap);
    setReplay(snap);
    setConnectors(snap);
    setEdgeClock();
    setMissionChart(snap);
    SIMULATED_PANELS.forEach(sel => badge(sel, "sim",
      "prototype placeholder - no real counterpart yet (executor/coach emit lanes come later)"));
    badge(".delta-panel", (snap.decision_state.n_blocks_fed ?? 0) > 0 ? "real" : "awaiting",
      snap.decision_state.note || "");
  }

  document.addEventListener("DOMContentLoaded", () => {
    installDayPicker();
    loadSnapshot();
    setInterval(() => loadSnapshot(state.day), 60000);
  });
})();
