/* Novel Edge Lab — injects a read-only preregistration panel into Mission Control. */
(() => {
  "use strict";

  const API = "/api/v1/novel/candidates";
  const state = { payload: null, filter: "all" };
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function installNav() {
    const nav = $(".rail-nav");
    if (!nav || $("[data-view='novel']")) return;
    const button = document.createElement("button");
    button.className = "nav-item";
    button.dataset.view = "novel";
    button.setAttribute("aria-label", "Novel Edge Lab");
    button.title = "Novel Edge Lab";
    button.innerHTML = `<span class="nav-icon novel-nav-icon">N+</span><span class="nav-label">Novel</span>`;
    const replay = $("[data-view='replay']", nav);
    nav.insertBefore(button, replay || null);
    button.addEventListener("click", openNovel);
  }

  function installCommand() {
    const results = $(".command-results");
    if (!results || $("#commandNovel")) return;
    const button = document.createElement("button");
    button.id = "commandNovel";
    button.innerHTML = `<span>Open</span><strong>Novel Edge Lab</strong><kbd>G N</kbd>`;
    button.addEventListener("click", openNovel);
    const replay = $("[data-command-view='replay']", results);
    results.insertBefore(button, replay || null);
  }

  function installView() {
    const container = $(".view-container");
    if (!container || $("#view-novel")) return;
    const section = document.createElement("section");
    section.className = "view";
    section.id = "view-novel";
    section.dataset.title = "Novel Edge Lab";
    section.innerHTML = `
      <div class="novel-page">
        <div class="page-heading">
          <div>
            <span class="panel-kicker">PREREGISTERED · READ-ONLY · NO ROUTING AUTHORITY</span>
            <h2>Novel Edge Lab</h2>
            <p>Contract seams, causal clocks, cross-market structures, revision vintages, and interaction candidates. Each card remains separate until untouched-forward evidence says otherwise.</p>
          </div>
          <div class="page-actions">
            <span class="badge warning-bg">WATCH / SHADOW ONLY</span>
            <button class="secondary-button" id="novelRefresh">Refresh readiness</button>
          </div>
        </div>

        <div class="novel-summary-row" id="novelSummary"></div>

        <article class="panel novel-watch-panel">
          <div class="panel-header">
            <div><span class="panel-kicker">NEXT 48 HOURS</span><h2>Strike-watch windows</h2><p>Windows are calendar and rule checks, not trade instructions.</p></div>
            <span class="data-badge awaiting" id="novelGenerated">LOADING</span>
          </div>
          <div class="novel-watch-list" id="novelWatchList"><div class="novel-empty">Loading watch windows…</div></div>
        </article>

        <article class="panel novel-registry-panel">
          <div class="panel-header">
            <div><span class="panel-kicker">ONE BOX PER CANDIDATE</span><h2>Preregistered candidate registry</h2></div>
            <span class="data-badge sim">NO EXECUTION</span>
          </div>
          <div class="novel-toolbar">
            <div class="novel-filter-group" id="novelFilters">
              <button class="novel-filter active" data-filter="all">All</button>
              <button class="novel-filter" data-filter="immediate">Next 48h</button>
              <button class="novel-filter" data-filter="structural">Structural seams</button>
              <button class="novel-filter" data-filter="wired">Wired inputs</button>
              <button class="novel-filter" data-filter="awaiting">Awaiting data</button>
            </div>
            <span class="novel-registry-note">Scores are ordinal research rankings, not fitted weights.</span>
          </div>
          <div class="novel-card-grid" id="novelCards"><div class="novel-empty">Loading candidate registry…</div></div>
        </article>

        <article class="panel novel-balance-panel">
          <div class="panel-header">
            <div><span class="panel-kicker">RISK, NOT COSMETIC SYMMETRY</span><h2>Balance conventions</h2><p>Equal contracts, equal dollars, and equal displayed size are not interchangeable.</p></div>
            <span class="data-badge real">DOCTRINE</span>
          </div>
          <div class="novel-balance-grid" id="novelBalanceGrid"></div>
        </article>
      </div>`;
    const replay = $("#view-replay", container);
    container.insertBefore(section, replay || null);
    $("#novelRefresh")?.addEventListener("click", load);
    $$("#novelFilters .novel-filter").forEach(button => button.addEventListener("click", () => {
      state.filter = button.dataset.filter;
      $$("#novelFilters .novel-filter").forEach(b => b.classList.toggle("active", b === button));
      renderCards();
    }));
  }

  function openNovel() {
    $$(".view").forEach(view => view.classList.toggle("active", view.id === "view-novel"));
    $$(".nav-item[data-view]").forEach(button => button.classList.toggle("active", button.dataset.view === "novel"));
    const title = $("#viewTitle");
    if (title) title.textContent = "Novel Edge Lab";
    const vc = $(".view-container");
    if (vc) vc.scrollTop = 0;
    $("#commandModal")?.classList.add("hidden");
  }

  function score(value) {
    return `${Number(value || 0)}/5`;
  }

  function truthLabel(readiness) {
    if (readiness.level === "WIRED_INPUTS") return "WIRED INPUTS";
    if (readiness.level === "PARTIAL_INPUTS") return "PARTIAL INPUTS";
    return "AWAITING DATA";
  }

  function filteredCandidates() {
    if (!state.payload) return [];
    return state.payload.candidates.filter(candidate => {
      if (state.filter === "immediate") return candidate.next_48h_window_active;
      if (state.filter === "structural") return /STRUCTURAL|CONFIRMED/.test(candidate.verdict);
      if (state.filter === "wired") return candidate.readiness.level === "WIRED_INPUTS";
      if (state.filter === "awaiting") return candidate.readiness.level === "AWAITING_DATA";
      return true;
    });
  }

  function renderSummary() {
    const el = $("#novelSummary");
    if (!el || !state.payload) return;
    const s = state.payload.summary;
    const cards = [
      ["Candidates", s.candidates, "Separate preregistrations"],
      ["Wired inputs", s.wired_inputs, "All required local paths present"],
      ["Partial inputs", s.partial_inputs, "Some local seams available"],
      ["Awaiting data", s.awaiting_data, "Missing required local stores"],
      ["Next 48h windows", s.next_48h_watch_windows, "Watch or shadow only"],
    ];
    el.innerHTML = cards.map(([label, value, note]) => `
      <article class="novel-summary-card"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(note)}</small></article>
    `).join("");
  }

  function renderSchedule() {
    const el = $("#novelWatchList");
    const stamp = $("#novelGenerated");
    if (!el || !state.payload) return;
    const rows = state.payload.immediate_schedule || [];
    if (stamp) {
      stamp.textContent = state.payload.generated_at_et.replace("T", " ") + " ET";
      stamp.className = "data-badge real";
    }
    if (!rows.length) {
      el.innerHTML = `<div class="novel-empty">No preregistered watch windows fall inside the next 48 hours. This does not mean no market opportunity exists.</div>`;
      return;
    }
    el.innerHTML = rows.map(row => {
      const when = new Date(row.starts_at_et);
      const label = new Intl.DateTimeFormat("en-US", {
        timeZone: "America/New_York", weekday: "short", month: "short", day: "numeric",
        hour: "2-digit", minute: "2-digit", hour12: false,
      }).format(when);
      return `<div class="novel-watch-row">
        <time class="novel-watch-time">${escapeHtml(label)} ET</time>
        <div class="novel-watch-copy"><strong>${escapeHtml(row.label)}</strong><small>${escapeHtml(row.requires)}</small></div>
        <span class="novel-watch-mode">${escapeHtml(row.authority)}</span>
      </div>`;
    }).join("");
  }

  function pathTags(items) {
    return (items || []).map(item => `<span class="novel-path ${item.present ? "present" : ""}" title="${item.present ? "present" : "missing"}">${item.present ? "●" : "○"} ${escapeHtml(item.path)}</span>`).join("");
  }

  function renderCards() {
    const el = $("#novelCards");
    if (!el || !state.payload) return;
    const items = filteredCandidates();
    if (!items.length) {
      el.innerHTML = `<div class="novel-empty">No candidates match this filter.</div>`;
      return;
    }
    el.innerHTML = items.map(candidate => {
      const r = candidate.readiness;
      const instruments = (candidate.instruments || []).join(" · ");
      const immediate = candidate.next_48h_window_active;
      return `<article class="novel-card" data-immediate="${immediate}">
        <div class="novel-card-head">
          <div class="novel-card-heading">
            <div class="novel-rank-line">
              <span class="novel-rank">RANK ${candidate.rank}</span>
              <span class="novel-family">${escapeHtml(candidate.family)}</span>
              ${immediate ? `<span class="novel-verdict">48H WATCH</span>` : ""}
            </div>
            <h3>${escapeHtml(candidate.title)}</h3>
            <p>${escapeHtml(candidate.why)}</p>
          </div>
          <div class="novel-card-badges">
            <span class="novel-verdict">${escapeHtml(candidate.verdict)}</span>
            <span class="novel-truth ${escapeHtml(r.truth_level)}">${truthLabel(r)}</span>
            <span class="novel-authority">${escapeHtml(candidate.authority)}</span>
          </div>
        </div>

        <div class="novel-score-grid">
          <div><span>Potential</span><strong>${score(candidate.potential_value)}</strong></div>
          <div><span>Causal</span><strong>${score(candidate.causal_defensibility)}</strong></div>
          <div><span>Data</span><strong>${r.required_present}/${r.required_total}</strong></div>
          <div><span>Testability</span><strong>${score(candidate.testability)}</strong></div>
        </div>

        <div class="novel-meta">
          <div><span>Instruments</span><strong>${escapeHtml(instruments)}</strong></div>
          <div><span>Causal clock</span><strong>${escapeHtml(candidate.clock)}</strong></div>
          <div><span>Balance mode</span><span class="novel-balance">${escapeHtml(candidate.balance_mode)}</span></div>
          <div><span>Provenance</span><strong>${escapeHtml(candidate.provenance)}</strong><small>execution_enabled = false</small></div>
        </div>

        ${immediate ? `<div class="novel-immediate-note"><strong>Immediate watch:</strong> ${escapeHtml(candidate.watch_window)}</div>` : ""}

        <details class="novel-details">
          <summary>Mechanism, use window, kill test, and wiring</summary>
          <div class="novel-detail-body">
            <div class="novel-detail-row"><span>Use only when</span><strong>${escapeHtml(candidate.use_when)}</strong></div>
            <div class="novel-detail-row"><span>Kill test</span><strong>${escapeHtml(candidate.kill_test)}</strong></div>
            <div class="novel-detail-row"><span>Status discipline</span><small>${escapeHtml(candidate.status_note)}</small></div>
            <div class="novel-detail-row"><span>Required local inputs</span><div class="novel-path-list">${pathTags(r.required)}</div></div>
            <div class="novel-detail-row"><span>Existing supporting code/docs</span><div class="novel-path-list">${pathTags(r.supporting)}</div></div>
          </div>
        </details>
      </article>`;
    }).join("");
  }

  function renderBalanceModes() {
    const el = $("#novelBalanceGrid");
    if (!el || !state.payload) return;
    el.innerHTML = Object.entries(state.payload.balance_modes || {}).map(([mode, description]) => `
      <div class="novel-balance-cell"><strong>${escapeHtml(mode)}</strong><small>${escapeHtml(description)}</small></div>
    `).join("");
  }

  function renderError(error) {
    const summary = $("#novelSummary");
    const cards = $("#novelCards");
    const watch = $("#novelWatchList");
    if (summary) summary.innerHTML = "";
    if (cards) cards.innerHTML = `<div class="novel-empty">Novel API unavailable: ${escapeHtml(error.message || error)}</div>`;
    if (watch) watch.innerHTML = `<div class="novel-empty">Watch schedule unavailable.</div>`;
  }

  async function load() {
    try {
      const response = await fetch(API, { cache: "no-store" });
      if (!response.ok) throw new Error(`${API} returned ${response.status}`);
      state.payload = await response.json();
      renderSummary();
      renderSchedule();
      renderCards();
      renderBalanceModes();
    } catch (error) {
      renderError(error);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    installNav();
    installView();
    installCommand();
    load();
    setInterval(load, 60000);
  });
})();
