/* signals_demo.js - demo-first dashboard wiring.
 *
 * Loaded by dashboard.server after app.js and adapter.js. The original prototype data remains
 * available as a visual fallback, but this layer replaces the opportunity queue and state tape
 * with the versioned demo feed plus the real SIGNALS_IN_USE registry joined to the selected
 * decision_state. It cannot submit, amend, cancel, or route an order.
 */
(() => {
  "use strict";

  const API = "/api/v1";
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  let renderingSignals = false;
  let latest = null;

  function esc(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function fmt(value) {
    if (value === null || value === undefined) return "awaiting";
    if (typeof value === "boolean") return value ? "true" : "false";
    if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(3);
    return String(value);
  }

  function money(value) {
    if (!value) return "demo only";
    return new Intl.NumberFormat("en-US", {
      style: "currency", currency: "USD", maximumFractionDigits: 0
    }).format(value);
  }

  function selectedDay() {
    const picker = $("#asofDay");
    if (picker?.value) return picker.value.replace(/-/g, "");
    return null;
  }

  async function get(path) {
    const response = await fetch(API + path);
    if (!response.ok) throw new Error(`${path} -> ${response.status}`);
    return response.json();
  }

  function ensureBadge(panel, text, title) {
    const header = panel?.querySelector(".panel-header");
    if (!header) return;
    let badge = header.querySelector(".data-badge.demo-feed-badge");
    if (!badge) {
      badge = document.createElement("span");
      badge.className = "data-badge sim demo-feed-badge";
      header.appendChild(badge);
    }
    badge.textContent = text;
    badge.title = title || "";
  }

  function renderOpportunities(feed) {
    const tbody = $("#opportunityRows");
    const panel = $(".opportunities-panel");
    if (!tbody || !panel) return;
    const rows = feed.opportunities || [];
    tbody.innerHTML = rows.map((row, index) => `
      <tr data-demo-id="${esc(row.id)}" class="${index === 0 ? "selected" : ""}">
        <td><div class="event-cell"><strong>${esc(row.title)}</strong>
          <small>${esc(row.route)} · ${esc(row.signal_path)} = ${esc(fmt(row.signal_value))}</small></div></td>
        <td><span class="clock-cell"><i class="urgency-dot ${row.urgency === "high" ? "high" : ""}"></i>${Number(row.clock_s).toFixed(0)}s demo</span></td>
        <td class="${row.demo_edge_usd > 0 ? "positive" : "neutral"}">${esc(money(row.demo_edge_usd))}</td>
        <td>${esc(money(row.demo_size_usd))}</td>
        <td><span class="play-tag">${esc(row.play)}</span></td>
        <td><span class="mode-tag signal">DEMO</span></td>
      </tr>`).join("");

    const kicker = panel.querySelector(".panel-kicker");
    const h2 = panel.querySelector("h2");
    if (kicker) kicker.textContent = "VERSIONED DEMONSTRATION FEED";
    if (h2) h2.textContent = "Kalshi Demo Opportunity Queue";
    ensureBadge(panel, "DEMO FEED", feed.note);

    $$("tr[data-demo-id]", tbody).forEach(row => {
      row.addEventListener("click", () => {
        $$("tr[data-demo-id]", tbody).forEach(r => r.classList.remove("selected"));
        row.classList.add("selected");
        const item = rows.find(r => r.id === row.dataset.demoId);
        if (item) renderEpisode(item);
      });
    });
    if (rows[0]) renderEpisode(rows[0]);
  }

  function renderEpisode(item) {
    const set = (id, value) => { const el = $(id); if (el) el.textContent = value; };
    set("#episodeKicker", "DEMO DECISION EPISODE - NO EXECUTION AUTHORITY");
    set("#episodeTitle", item.title);
    set("#episodeSubtitle", `${item.subtitle} Signal value: ${fmt(item.signal_value)}.`);
    set("#episodeDirection", item.direction);
    set("#episodeStatus", item.status);
    set("#leaderSymbol", "KALSHI DEMO");
    set("#episodeNetEdge", item.demo_edge_usd ? `${money(item.demo_edge_usd)} demo` : "No call");
    set("#episodeCapacity", item.demo_size_usd ? `${money(item.demo_size_usd)} demo` : "No authority");
    set("#staleStrikes", item.market_ticker || "market mapping pending");
    set("#edgeClockValue", `${Number(item.clock_s).toFixed(0)}s demo clock`);
    const edgeState = $("#edgeClockState");
    if (edgeState) {
      edgeState.textContent = "Demonstration timing only - firing mechanism not connected";
      edgeState.className = "warning";
    }
    window.__REAL_WINDOW__ = true;
  }

  function renderSignals(snapshot) {
    const tape = $("#deltaTape");
    const panel = $(".delta-panel");
    if (!tape || !panel || renderingSignals) return;
    renderingSignals = true;
    try {
      const signals = (snapshot.signals || []).slice(0, 32);
      const kicker = panel.querySelector(".panel-kicker");
      const h2 = panel.querySelector("h2");
      const count = panel.querySelector(".panel-header .text-button");
      if (kicker) kicker.textContent = "BRAIN-CONSUMED SIGNALS";
      if (h2) h2.textContent = `Signals in Use · ${snapshot.day}`;
      if (count) count.textContent = `${snapshot.resolved_definition_count}/${snapshot.definition_count} definitions resolved`;
      tape.innerHTML = signals.map(signal => {
        const first = (signal.values || []).find(v => v.available) || (signal.values || [])[0] || {};
        const status = signal.status === "resolved" ? "FED" : signal.status.toUpperCase();
        return `<div class="delta-row" title="${esc(signal.example_path)}">
          <time>${esc(signal.block)}</time><span class="delta-node ${signal.status === "awaiting" ? "pending" : ""}"></span>
          <div><strong>${esc(signal.field)}</strong><small>${esc(first.path || signal.example_path)} = ${esc(fmt(first.value))}</small></div>
          <em class="${signal.status === "awaiting" ? "muted" : ""}">${signal.brain_mentions} refs · ${status}</em></div>`;
      }).join("");
      tape.title = snapshot.provenance || "";
      ensureBadge(panel, "REAL REGISTRY", snapshot.note);
    } finally {
      renderingSignals = false;
    }
  }

  function setEnvironment(feed, signals) {
    const pill = $(".environment-pill");
    if (!pill) return;
    const creds = feed.credential_status || {};
    const credentialText = creds.ready_for_authenticated_demo_reads ? "DEMO CREDS READY" : "DEMO CREDS NOT LOADED";
    pill.innerHTML = `<span class="status-dot warning"></span>KALSHI DEMO · NO EXECUTION · ${signals.resolved_definition_count}/${signals.definition_count} SIGNALS · ${credentialText}`;
    pill.title = "Demo environment rehearsal. The browser contains no credentials and no order route.";
  }

  function lockExecutionControls() {
    $$(".mode-button").forEach(button => {
      button.disabled = true;
      button.title = "Demo feed active; firing policy is not connected";
    });
    ["#pauseSystem", "#killButton", "#stageHedgeButton", "#manualIntentButton",
     "#episodeHedgeButton", "#newPackageButton", "#approveDrawer"].forEach(selector => {
      const el = $(selector);
      if (el) {
        el.disabled = true;
        el.title = "Demo feed only - no execution authority";
      }
    });
  }

  async function refresh() {
    const day = selectedDay();
    const suffix = day ? `?day=${day}` : "";
    try {
      const [feed, signals] = await Promise.all([
        get(`/demo/opportunities${suffix}`),
        get(`/signals/in-use${suffix}`),
      ]);
      latest = { feed, signals };
      renderOpportunities(feed);
      renderSignals(signals);
      setEnvironment(feed, signals);
      lockExecutionControls();
    } catch (error) {
      const panel = $(".opportunities-panel");
      ensureBadge(panel, "DEMO AWAITING", String(error));
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    setTimeout(refresh, 800);
    $("#asofDay")?.addEventListener("change", () => setTimeout(refresh, 350));
    const tape = $("#deltaTape");
    if (tape) {
      const observer = new MutationObserver(() => {
        if (!renderingSignals && latest?.signals) setTimeout(() => renderSignals(latest.signals), 50);
      });
      observer.observe(tape, { childList: true });
    }
    setInterval(refresh, 60000);
    setInterval(() => {
      if (latest) setEnvironment(latest.feed, latest.signals);
    }, 3000);
  });
})();
