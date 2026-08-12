/* Visible rule-scan diagnostic for the rank-1 duplicate-wrapper candidate. */
(() => {
  "use strict";

  const API = "/api/v1/novel/candidates";
  let latest = null;
  let timer = null;

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function installStyle() {
    if (document.querySelector("#novelDiagnosticStyle")) return;
    const style = document.createElement("style");
    style.id = "novelDiagnosticStyle";
    style.textContent = `
      .novel-live-diagnostic {
        display:grid; grid-template-columns: minmax(0,1fr) repeat(3, minmax(70px,.45fr));
        gap:8px; align-items:center; margin:0 12px 11px; padding:9px 10px;
        border:1px solid var(--border-subtle); border-radius:8px; background:rgba(8,13,19,.62);
      }
      .novel-live-diagnostic.available { border-color:rgba(73,214,163,.25); }
      .novel-live-diagnostic.awaiting { border-color:rgba(244,180,94,.22); }
      .novel-diagnostic-copy span, .novel-diagnostic-copy strong, .novel-diagnostic-copy small,
      .novel-diagnostic-stat span, .novel-diagnostic-stat strong { display:block; }
      .novel-diagnostic-copy span, .novel-diagnostic-stat span {
        color:var(--muted); font-size:7px; text-transform:uppercase; letter-spacing:.04em;
      }
      .novel-diagnostic-copy strong { margin-top:3px; font-size:8px; line-height:1.45; }
      .novel-diagnostic-copy small { margin-top:3px; color:var(--muted-2); font-size:7px; line-height:1.45; }
      .novel-diagnostic-stat { min-width:0; padding-left:8px; border-left:1px solid var(--border-subtle); }
      .novel-diagnostic-stat strong { margin-top:4px; font:800 12px var(--mono); }
      .novel-diagnostic-stat .positive { color:var(--positive); }
      @media (max-width:900px) {
        .novel-live-diagnostic { grid-template-columns:1fr; }
        .novel-diagnostic-stat { padding:7px 0 0; border-left:0; border-top:1px solid var(--border-subtle); }
      }
    `;
    document.head.appendChild(style);
  }

  function rankOneCard() {
    return Array.from(document.querySelectorAll(".novel-card")).find(card =>
      card.querySelector(".novel-rank")?.textContent.trim() === "RANK 1"
    );
  }

  function attach() {
    if (!latest) return;
    const card = rankOneCard();
    if (!card) return;
    const candidate = latest.candidates?.find(c => c.id === "KALSHI_DUPLICATE_WRAPPER_PARITY");
    const diagnostic = candidate?.live_diagnostic;
    if (!diagnostic) return;

    let node = card.querySelector(".novel-live-diagnostic");
    if (!node) {
      node = document.createElement("div");
      node.className = "novel-live-diagnostic";
      const details = card.querySelector(".novel-details");
      card.insertBefore(node, details || null);
    }

    if (!diagnostic.available) {
      node.className = "novel-live-diagnostic awaiting";
      node.innerHTML = `
        <div class="novel-diagnostic-copy">
          <span>Live rule scan</span>
          <strong>AWAITING CURRENT MARKET JSON</strong>
          <small>${escapeHtml(diagnostic.reason)} · output: ${escapeHtml(diagnostic.path)}</small>
        </div>
        <div class="novel-diagnostic-stat"><span>Exact groups</span><strong>—</strong></div>
        <div class="novel-diagnostic-stat"><span>Near matches</span><strong>—</strong></div>
        <div class="novel-diagnostic-stat"><span>Gross positive</span><strong>—</strong></div>`;
      return;
    }

    node.className = "novel-live-diagnostic available";
    node.innerHTML = `
      <div class="novel-diagnostic-copy">
        <span>Live rule scan</span>
        <strong>${escapeHtml(diagnostic.canonical_markets)} canonical markets from ${escapeHtml(diagnostic.input_markets)} inputs</strong>
        <small>${escapeHtml(diagnostic.note)} · ${escapeHtml(diagnostic.path)}</small>
      </div>
      <div class="novel-diagnostic-stat"><span>Exact groups</span><strong>${escapeHtml(diagnostic.exact_normalized_rule_groups)}</strong></div>
      <div class="novel-diagnostic-stat"><span>Near matches</span><strong>${escapeHtml(diagnostic.semantic_near_match_groups)}</strong></div>
      <div class="novel-diagnostic-stat"><span>Gross positive</span><strong class="${diagnostic.positive_gross_pairs_before_fees > 0 ? "positive" : ""}">${escapeHtml(diagnostic.positive_gross_pairs_before_fees)}</strong></div>`;
  }

  async function refresh() {
    try {
      const response = await fetch(API, { cache: "no-store" });
      if (!response.ok) return;
      latest = await response.json();
      attach();
    } catch {
      // The primary Novel module owns API error display; this enhancer stays silent.
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    installStyle();
    const root = document.querySelector(".view-container") || document.body;
    const observer = new MutationObserver(() => attach());
    observer.observe(root, { childList: true, subtree: true });
    refresh();
    timer = window.setInterval(refresh, 60000);
    window.addEventListener("beforeunload", () => window.clearInterval(timer), { once: true });
  });
})();
