(() => {
  "use strict";

  const opportunities = [
    { id: "ng-lag", title: "NGQ6 → Kalshi $3.55+", route: "NYMEX leader · 5/8 brackets stale", clock: 11.2, edge: 3260, size: 9400, play: "flow_nowcast", mode: "AUTO", urgency: "high", symbol: "NGQ6", price: 3.492, move: 0.034, direction: "LONG", status: "ORDER WORKING", subtitle: "Strong buy flow; upper brackets remain stale", stale: "5 / 8 strikes", confidence: 0.87 },
    { id: "weather-dfw", title: "DFW max ≥ 101°F", route: "Kalshi + Poly · operator upper tail", clock: 46.8, edge: 2180, size: 6800, play: "MOS first appearance", mode: "AUTO", urgency: "high", symbol: "KDFW", price: 0.410, move: 0.082, direction: "YES", status: "ROUTING", subtitle: "12z cycle added heat; market remains below calibrated tail", stale: "2 venues", confidence: 0.78 },
    { id: "cl-lag", title: "CLQ6 → event $84.50+", route: "WTI leader · fastest strike unchanged", clock: 8.4, edge: 1910, size: 7200, play: "flow_nowcast", mode: "AUTO", urgency: "high", symbol: "CLQ6", price: 83.640, move: 0.410, direction: "LONG", status: "INTENT READY", subtitle: "Leader leg confirmed; event contract still at pre-move probability", stale: "3 / 6 strikes", confidence: 0.83 },
    { id: "ng-hedge", title: "Heat thesis delta hedge", route: "Kalshi event → NG futures package", clock: 72.0, edge: 2380, size: 12600, play: "risk coordinator", mode: "APPROVAL", urgency: "medium", symbol: "NGQ6", price: 3.492, move: 0.034, direction: "HEDGE", status: "AWAITING APPROVAL", subtitle: "Preserve event edge while reducing aggregate heat-to-NG concentration", stale: "package TTL 90s", confidence: 0.68 },
    { id: "storage", title: "Storage > 72 Bcf", route: "Kalshi · running chain vs print sign", clock: 184.0, edge: 860, size: 3900, play: "storage Thursday", mode: "SIGNAL", urgency: "medium", symbol: "NGU6", price: 3.574, move: 0.018, direction: "LONG", status: "SIGNAL ONLY", subtitle: "Running-chain context conflicts with headline print sign", stale: "closes 18m", confidence: 0.70 },
    { id: "reversal", title: "NG leg reversal candidate", route: "NYMEX · far-ladder recruitment", clock: 4.1, edge: 0, size: 0, play: "recruitment reversal", mode: "SHADOW", urgency: "low", symbol: "NGQ6", price: 3.492, move: 0.034, direction: "SHORT", status: "ARMED · SHADOW", subtitle: "Counterfactual reversal awaiting fine-resolution confirmation", stale: "no authority", confidence: 0.45 }
  ];

  const deltaEvents = [
    ["15:17:04.084", "dip_imb_level crossed strong-flow threshold", "Flow +0.84", "flow_nowcast"],
    ["15:17:04.091", "flow_nowcast became eligible LONG", "Requirements 5/5", "PLAY"],
    ["15:17:04.104", "Kalshi upper bracket remained unchanged", "Quote age 10.8s", "LAG"],
    ["15:17:04.110", "Lag opportunity created", "Net taker edge $3,260", "ACTION"],
    ["15:17:04.119", "Hard risk gates approved", "$12.6K reserved", "RISK"],
    ["15:17:04.132", "Order transmitted to follower venue", "Leader→send 41.8ms", "ORDER"],
    ["15:17:04.206", "Partial fill received", "780 / 1,250", "FILL"]
  ];

  const weatherRows = [
    ["≥ 99°F", "62 / 64¢", "61 / 65¢", 68, 75, 73, 9.0, "$31.2K"],
    ["≥ 100°F", "49 / 52¢", "48 / 53¢", 56, 66, 64, 12.0, "$24.7K"],
    ["≥ 101°F", "38 / 41¢", "37 / 43¢", 43, 55, 53, 12.0, "$18.1K"],
    ["≥ 102°F", "24 / 28¢", "23 / 29¢", 31, 43, 41, 13.0, "$11.8K"],
    ["≥ 103°F", "13 / 17¢", "12 / 18¢", 19, 31, 29, 12.0, "$6.4K"],
    ["≥ 104°F", "6 / 9¢", "5 / 10¢", 10, 19, 17, 8.0, "$2.6K"]
  ];

  const packages = [
    { status: "AWAITING APPROVAL", statusClass: "warning-bg", title: "Preserve lag edge; hedge NG delta", subtitle: "S100-NG-0719-0042 · 90s TTL", urgent: true, economics: [["Net edge", "$2,380"],["Max leg loss", "$1,120"],["Capital", "$16,600"]], legs: [["Keep Kalshi YES", "470 working; cancel at 47.8% fair", "LIVE"],["Sell 2 NGQ6", "Arm on follower fill completion", "ARMED"]], risks: ["Timing basis", "Partial-fill recovery", "Exact event mapping"], action: "Review package" },
    { status: "AUTO ELIGIBLE", statusClass: "positive-bg", title: "CL leader → Kalshi strike sweep", subtitle: "Fastest 3 strikes · 8.4s edge clock", urgent: true, economics: [["Net edge", "$1,910"],["Capacity", "$7,200"],["Edge half-life", "5.1s"]], legs: [["Buy YES 84.5", "IOC up to 43.0¢", "READY"],["Buy YES 85.0", "Passive remainder", "READY"],["Cancel together", "On fair-value convergence", "POLICY"]], risks: ["Follower repricing", "Cross-strike overlap", "Fee curve"], action: "Inspect live" },
    { status: "SIGNAL", statusClass: "", title: "Poly weather complete-set anomaly", subtitle: "Dallas outcomes · definition-matched", urgent: false, economics: [["Gross edge", "$1,140"],["Net edge", "$670"],["Capital", "$22,400"]], legs: [["Buy 3 underpriced outcomes", "Mutually exclusive event", "SIGNAL"],["Sell overvalued tail", "Liquidity thin", "OPTIONAL"]], risks: ["Onchain settlement", "Outcome completeness", "Thin liquidity"], action: "Compose intent" },
    { status: "SHADOW", statusClass: "", title: "Recruitment reversal hedge", subtitle: "NGQ6 · provisional trigger", urgent: false, economics: [["Counterfactual EV", "$520"],["Max risk", "$2,100"],["Sample", "Live only"]], legs: [["Sell 1 NGQ6", "After fine-resolution turn", "BLOCKED"],["Reduce event YES", "Only if divergence confirms", "BLOCKED"]], risks: ["Provisional rule", "Confirmation missing", "No production authority"], action: "Open evidence" },
    { status: "AUTO ELIGIBLE", statusClass: "positive-bg", title: "Upper-tail venue split", subtitle: "KDFW ≥ 102°F · Kalshi vs Poly", urgent: false, economics: [["Net edge", "$1,260"],["Capacity", "$9,100"],["Match", "Exact"]], legs: [["Buy Kalshi YES", "Ask 28¢", "READY"],["Sell Poly YES", "Bid 34¢ equivalent", "READY"]], risks: ["Cross-venue legging", "Collateral fragmentation", "Resolution snapshot"], action: "Review package" },
    { status: "MONITOR", statusClass: "", title: "Options-implied energy threshold", subtitle: "NG calls vs event probability", urgent: false, economics: [["Divergence", "7.4 pts"],["Net edge", "TBD"],["Match", "Related"]], legs: [["Buy event YES", "If definition basis clears", "MONITOR"],["Buy NG call spread", "Hedge candidate", "MONITOR"]], risks: ["Risk-neutral vs physical P", "Date mismatch", "Volatility basis"], action: "Open analysis" }
  ];

  const connectors = [
    ["Databento CME market data", "MBO · definitions · status", "7.7 ms", "0.3 ms", "LIVE", "positive"],
    ["CME order router", "Broker / FCM adapter", "18.4 ms", "0 open gaps", "LIVE", "positive"],
    ["Kalshi market data", "Books · events · rules", "46 ms", "seq current", "LIVE", "positive"],
    ["Kalshi execution", "Orders · fills · groups", "49 ms", "0 unknown", "LIVE", "positive"],
    ["Polymarket data/execution", "CLOB + settlement lane", "81 ms", "wallet healthy", "LIVE", "positive"],
    ["Weather ingestion", "MOS cycles · observations", "2.1 s", "12z current", "LIVE", "positive"],
    ["AWS evidence store", "Raw · normalized · derived", "—", "append healthy", "LIVE", "positive"]
  ];

  const state = {
    activeView: "mission",
    activeOpportunity: opportunities[0],
    mode: "AUTO",
    paused: false,
    replayTimer: null,
    chartSeries: {
      leader: generateSeries(64, 0.3, 0.08),
      follower: generateSeries(64, 0.18, 0.035),
      flow: generateFlow(64)
    }
  };

  function generateSeries(length, drift, noise) {
    let v = 35;
    return Array.from({ length }, (_, i) => {
      v += (i > length * 0.45 ? drift : drift * 0.15) + (Math.random() - 0.47) * noise * 7;
      return v;
    });
  }

  function generateFlow(length) {
    return Array.from({ length }, (_, i) => Math.max(-1, Math.min(1, (i / length - .35) * 1.8 + (Math.random() - .5) * .35)));
  }

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  function formatMoney(value) {
    return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);
  }

  function renderOpportunities() {
    const tbody = $("#opportunityRows");
    tbody.innerHTML = opportunities.map(o => `
      <tr data-id="${o.id}" class="${o.id === state.activeOpportunity.id ? "selected" : ""}">
        <td><div class="event-cell"><strong>${o.title}</strong><small>${o.route}</small></div></td>
        <td><span class="clock-cell"><i class="urgency-dot ${o.urgency === "high" ? "high" : ""}"></i>${o.clock < 60 ? o.clock.toFixed(1) + "s" : Math.floor(o.clock / 60) + "m"}</span></td>
        <td class="${o.edge > 0 ? "positive" : "neutral"}">${o.edge > 0 ? formatMoney(o.edge) : "—"}</td>
        <td>${o.size > 0 ? formatMoney(o.size) : "—"}</td>
        <td><span class="play-tag">${o.play}</span></td>
        <td><span class="mode-tag ${o.mode.toLowerCase()}">${o.mode}</span></td>
      </tr>`).join("");

    $$("tr[data-id]", tbody).forEach(row => row.addEventListener("click", () => selectOpportunity(row.dataset.id)));
  }

  function selectOpportunity(id) {
    const opportunity = opportunities.find(o => o.id === id);
    if (!opportunity) return;
    state.activeOpportunity = opportunity;
    renderOpportunities();
    $("#episodeTitle").textContent = opportunity.title;
    $("#episodeSubtitle").textContent = opportunity.subtitle;
    $("#leaderSymbol").textContent = opportunity.symbol;
    $("#leaderPrice").textContent = opportunity.price < 1 ? `${(opportunity.price * 100).toFixed(1)}¢` : opportunity.price.toFixed(3);
    $("#leaderMove").textContent = `${opportunity.move >= 0 ? "+" : ""}${opportunity.price < 1 ? (opportunity.move * 100).toFixed(1) + " pts" : opportunity.move.toFixed(3)}`;
    $("#leaderMove").className = opportunity.move >= 0 ? "positive" : "negative";
    $("#episodeDirection").textContent = opportunity.direction;
    $("#episodeStatus").textContent = opportunity.status;
    $("#episodeNetEdge").textContent = opportunity.edge ? formatMoney(opportunity.edge) : "Shadow";
    $("#episodeCapacity").textContent = opportunity.size ? formatMoney(opportunity.size) : "No authority";
    $("#staleStrikes").textContent = opportunity.stale;
    if (window.__REAL_WINDOW__) return void (window.__REAL_CHART__ || drawAllCharts());
    $("#edgeClockValue").textContent = `${opportunity.clock.toFixed(1)}s elapsed`;
    const progress = Math.min(100, (opportunity.clock / 30) * 100);
    $("#edgeProgress").style.width = `${progress}%`;
    $("#edgeNow").style.left = `${progress}%`;
    $("#edgeClockState").textContent = opportunity.clock <= 20 ? "Inside expected 7–20s repricing window" : "Outside standard window; policy-specific handling";
    $("#edgeClockState").className = opportunity.clock <= 20 ? "positive" : "warning";
    state.chartSeries = {
      leader: generateSeries(64, opportunity.direction === "SHORT" ? -0.25 : 0.3, 0.09),
      follower: generateSeries(64, opportunity.clock < 20 ? 0.11 : 0.24, 0.045),
      flow: generateFlow(64).map(v => opportunity.direction === "SHORT" ? -v : v)
    };
    drawAllCharts();
  }

  function renderDeltaTape() {
    $("#deltaTape").innerHTML = deltaEvents.map((e, i) => `
      <div class="delta-row"><time>${e[0]}</time><span class="delta-node"></span><div><strong>${e[1]}</strong><small>${e[2]}</small></div><em>${e[3]}</em></div>
    `).join("");
  }

  function renderWeatherRows() {
    $("#weatherRows").innerHTML = weatherRows.map((r, index) => `
      <tr class="${index === 2 || index === 3 ? "best-edge" : ""}">
        <td>${r[0]}</td><td>${r[1]}</td><td>${r[2]}</td><td>${r[3].toFixed(1)}%</td><td class="positive">${r[4].toFixed(1)}%</td><td>${r[5].toFixed(1)}%</td><td class="positive">+${r[6].toFixed(1)} pts</td><td>${r[7]}</td>
      </tr>`).join("");
  }

  function renderPackages() {
    $("#packageBoard").innerHTML = packages.map((p, idx) => `
      <article class="package-card ${p.urgent ? "urgent" : ""}">
        <div class="package-card-header"><div><span class="panel-kicker">PACKAGE ${String(idx + 1).padStart(2, "0")}</span><h3>${p.title}</h3><p>${p.subtitle}</p></div><span class="badge ${p.statusClass}">${p.status}</span></div>
        <div class="package-economics">${p.economics.map(e => `<div><span>${e[0]}</span><strong class="${e[0].includes("edge") && !e[1].includes("TBD") ? "positive" : ""}">${e[1]}</strong></div>`).join("")}</div>
        <div class="package-legs">${p.legs.map((leg, i) => `<div class="package-leg"><span>${i + 1}</span><div><strong>${leg[0]}</strong><small>${leg[1]}</small></div><em>${leg[2]}</em></div>`).join("")}</div>
        <div class="package-risks">${p.risks.map(r => `<span class="risk-pill">${r}</span>`).join("")}</div>
        <div class="package-actions"><button class="primary-button package-action" data-package="${idx}">${p.action}</button><button class="secondary-button">Dismiss</button></div>
      </article>`).join("");
    $$(".package-action").forEach(button => button.addEventListener("click", openDrawer));
  }

  function renderConnectors() {
    $("#connectorList").innerHTML = connectors.map(c => `
      <div class="connector-row"><div><strong>${c[0]}</strong><small>${c[1]}</small></div><span>${c[2]}</span><span>${c[3]}</span><span class="connector-state"><i class="status-dot ${c[5]}"></i>${c[4]}</span></div>
    `).join("");
  }

  function renderReplayRequirements(value = 42) {
    const requirements = [
      ["CME market data is current", value > 4, "Last event lag 0.7 ms"],
      ["Strong signed flow threshold crossed", value > 18, "dip_imb_level +0.84"],
      ["Follower quote remains stale", value > 25, "Quote age 10.8s"],
      ["Exact event mapping and rule snapshot", value > 8, "Mapping v7 · no mismatch"],
      ["Hard risk and capacity gates", value > 38, "$12.6K reserved"]
    ];
    $("#replayRequirements").innerHTML = requirements.map(r => `
      <div class="requirement-row"><div><strong>${r[0]}</strong><small>${r[2]}</small></div><span class="${r[1] ? "" : "warning"}">${r[1] ? "PASS" : "WAIT"}</span></div>
    `).join("");
  }

  function drawMarketChart(element, leader, follower, flow) {
    if (!element) return;
    const w = Math.max(500, element.clientWidth || 800);
    const h = Math.max(170, element.clientHeight || 220);
    const pad = { l: 36, r: 44, t: 18, b: 22 };
    const innerW = w - pad.l - pad.r;
    const innerH = h - pad.t - pad.b;
    const all = [...leader, ...follower];
    const min = Math.min(...all) - 1;
    const max = Math.max(...all) + 1;
    const x = i => pad.l + (i / (leader.length - 1)) * innerW;
    const y = v => pad.t + (1 - (v - min) / (max - min)) * innerH;
    const points = series => series.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
    const flowBase = pad.t + innerH * .82;
    const flowPath = flow.map((v, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${(flowBase - v * innerH * .13).toFixed(1)}`).join(" ") + ` L ${x(flow.length - 1)} ${flowBase} L ${x(0)} ${flowBase} Z`;
    const grid = [0, .25, .5, .75, 1].map(p => `<line x1="${pad.l}" y1="${pad.t + innerH * p}" x2="${w - pad.r}" y2="${pad.t + innerH * p}"/>`).join("") + [0,.2,.4,.6,.8,1].map(p => `<line x1="${pad.l + innerW*p}" y1="${pad.t}" x2="${pad.l+innerW*p}" y2="${h-pad.b}"/>`).join("");
    const labels = [0,.5,1].map(p => `<text class="chart-label" x="${pad.l + innerW*p}" y="${h-6}" text-anchor="middle">${Math.round(p*60)}s</text>`).join("");
    element.innerHTML = `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="Leader price, follower probability, and signed flow">
      <g class="chart-grid">${grid}</g>
      <line class="chart-baseline" x1="${pad.l}" y1="${flowBase}" x2="${w-pad.r}" y2="${flowBase}" />
      <path class="chart-area" d="${flowPath}" />
      <polyline class="chart-price" points="${points(leader)}" />
      <polyline class="chart-follower" points="${points(follower)}" />
      <circle class="chart-last" cx="${x(leader.length-1)}" cy="${y(leader.at(-1))}" r="3" />
      <circle class="chart-follower-last" cx="${x(follower.length-1)}" cy="${y(follower.at(-1))}" r="3" />
      ${labels}
      <text class="chart-label" x="${w-5}" y="${y(leader.at(-1))+3}" text-anchor="end">leader</text>
      <text class="chart-label" x="${w-5}" y="${y(follower.at(-1))+3}" text-anchor="end">follower</text>
    </svg>`;
  }

  function drawWeatherDistribution() {
    const el = $("#weatherDistribution");
    if (!el) return;
    const w = Math.max(340, el.clientWidth || 430), h = Math.max(240, el.clientHeight || 278);
    const pad = { l: 34, r: 16, t: 18, b: 30 };
    const temps = Array.from({length: 15}, (_,i) => 94 + i);
    const gaussian = (x, mu, sigma) => Math.exp(-.5 * ((x-mu)/sigma)**2);
    const desk = temps.map(t => gaussian(t, 101.2, 2.0));
    const market = temps.map(t => gaussian(t, 99.5, 2.25) * .92);
    const max = Math.max(...desk, ...market);
    const x = i => pad.l + (i/(temps.length-1))*(w-pad.l-pad.r);
    const y = v => pad.t + (1-v/max)*(h-pad.t-pad.b);
    const area = series => `M ${x(0)} ${h-pad.b} ` + series.map((v,i)=>`L ${x(i)} ${y(v)}`).join(" ") + ` L ${x(series.length-1)} ${h-pad.b} Z`;
    const path = series => series.map((v,i)=>`${i?"L":"M"} ${x(i)} ${y(v)}`).join(" ");
    const grid = [0,.25,.5,.75,1].map(p=>`<line x1="${pad.l}" y1="${pad.t+(h-pad.t-pad.b)*p}" x2="${w-pad.r}" y2="${pad.t+(h-pad.t-pad.b)*p}"/>`).join("");
    const labels = temps.filter((_,i)=>i%2===0).map((t,i)=>`<text class="chart-label" x="${x(i*2)}" y="${h-8}" text-anchor="middle">${t}°</text>`).join("");
    el.innerHTML = `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><g class="chart-grid">${grid}</g><path d="${area(desk)}" fill="rgba(106,174,255,.09)"/><path d="${area(market)}" fill="rgba(243,199,102,.05)"/><path d="${path(desk)}" class="chart-price"/><path d="${path(market)}" class="chart-follower"/>${labels}</svg>`;
  }

  function drawReliabilityChart() {
    const el = $("#reliabilityChart");
    if (!el) return;
    const w = Math.max(500, el.clientWidth || 900), h = Math.max(120, el.clientHeight || 145);
    const pad = {l:35,r:18,t:12,b:24};
    const pts = [[.1,.08],[.2,.21],[.3,.32],[.4,.41],[.5,.52],[.6,.63],[.7,.72],[.8,.82],[.9,.88]];
    const x = v => pad.l + v*(w-pad.l-pad.r), y = v => h-pad.b-v*(h-pad.t-pad.b);
    const line = pts.map((p,i)=>`${i?"L":"M"} ${x(p[0])} ${y(p[1])}`).join(" ");
    el.innerHTML = `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><g class="chart-grid"><line x1="${pad.l}" y1="${h-pad.b}" x2="${w-pad.r}" y2="${pad.t}"/><line x1="${pad.l}" y1="${y(.5)}" x2="${w-pad.r}" y2="${y(.5)}"/></g><path d="${line}" class="chart-price"/>${pts.map(p=>`<circle cx="${x(p[0])}" cy="${y(p[1])}" r="3" fill="var(--accent)"/>`).join("")}<text class="chart-label" x="${pad.l}" y="${h-6}">0%</text><text class="chart-label" x="${w-pad.r}" y="${h-6}" text-anchor="end">100% forecast</text><text class="chart-label" x="${pad.l+3}" y="${pad.t+8}">observed</text></svg>`;
  }

  function drawAllCharts() {
    if (!window.__REAL_CHART__) drawMarketChart($("#missionChart"), state.chartSeries.leader, state.chartSeries.follower, state.chartSeries.flow);
    drawMarketChart($("#episodeChart"), state.chartSeries.leader, state.chartSeries.follower, state.chartSeries.flow);
    drawMarketChart($("#replayChart"), state.chartSeries.leader.slice(0, 45), state.chartSeries.follower.slice(0,45), state.chartSeries.flow.slice(0,45));
    drawWeatherDistribution();
    drawReliabilityChart();
  }

  function setView(view) {
    state.activeView = view;
    $$(".view").forEach(v => v.classList.toggle("active", v.id === `view-${view}`));
    $$(".nav-item[data-view]").forEach(button => button.classList.toggle("active", button.dataset.view === view));
    const current = $(`#view-${view}`);
    $("#viewTitle").textContent = current?.dataset.title || "DavisAI Markets";
    $(".view-container").scrollTop = 0;
    closeCommand();
    requestAnimationFrame(drawAllCharts);
  }

  function setMode(mode) {
    state.mode = mode;
    $$(".mode-button").forEach(b => b.classList.toggle("active", b.dataset.mode === mode));
    $("#currentPolicy").textContent = mode;
    toast("Automation mode updated", `New default mode: ${mode}. Existing episode authority remains versioned.`);
  }

  function updateClock() {
    const now = new Date();
    const time = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(now);
    $("#clock").textContent = `${time} ET`;
  }

  function simulateTick() {
    const leader = state.chartSeries.leader;
    const follower = state.chartSeries.follower;
    const flow = state.chartSeries.flow;
    leader.push(leader.at(-1) + .08 + (Math.random()-.48)*.5);
    follower.push(follower.at(-1) + .035 + (Math.random()-.5)*.35);
    flow.push(Math.max(-1, Math.min(1, flow.at(-1) + (Math.random()-.46)*.12)));
    if (leader.length > 64) { leader.shift(); follower.shift(); flow.shift(); }
    const active = state.activeOpportunity;
    if (active.id === "ng-lag" && !window.__REAL_WINDOW__ && !window.__REAL_CHART__) {
      active.price += (Math.random()-.43)*.002;
      active.clock = Math.min(30, active.clock + 1.2);
      $("#leaderPrice").textContent = active.price.toFixed(3);
      $("#edgeClockValue").textContent = `${active.clock.toFixed(1)}s elapsed`;
      const progress = Math.min(100, active.clock / 30 * 100);
      $("#edgeProgress").style.width = `${progress}%`;
      $("#edgeNow").style.left = `${progress}%`;
      if (active.clock > 20) {
        $("#edgeClockState").textContent = "Expected window exceeded; do not chase without policy permission";
        $("#edgeClockState").className = "warning";
      }
    }
    if (!window.__REAL_HEALTH__) {
      const cme = $("#cmeLatency"), kal = $("#kalshiLatency"), poly = $("#polyLatency"), dec = $("#decisionLatency");
      if (cme) cme.textContent = `${(7.3 + Math.random()*1.0).toFixed(1)} ms`;
      if (kal) kal.textContent = `${Math.round(42 + Math.random()*10)} ms`;
      if (poly) poly.textContent = `${Math.round(76 + Math.random()*13)} ms`;
      if (dec) dec.textContent = `${(39 + Math.random()*6).toFixed(1)} ms`;
    }
    if (state.activeView === "mission" || state.activeView === "episode") drawAllCharts();
  }

  function openCommand() {
    $("#commandModal").classList.remove("hidden");
    setTimeout(() => $("#commandInput").focus(), 30);
  }
  function closeCommand() { $("#commandModal").classList.add("hidden"); }

  function openDrawer() {
    $("#drawerBackdrop").classList.remove("hidden");
    $("#actionDrawer").classList.add("open");
  }
  function closeDrawer() {
    $("#drawerBackdrop").classList.add("hidden");
    $("#actionDrawer").classList.remove("open");
  }

  function openKill() { $("#killModal").classList.remove("hidden"); }
  function closeKill() { $("#killModal").classList.add("hidden"); }

  function toast(title, detail) {
    const el = document.createElement("div");
    el.className = "toast";
    el.innerHTML = `<strong>${title}</strong><span>${detail}</span>`;
    $("#toastStack").appendChild(el);
    setTimeout(() => el.remove(), 4200);
  }

  function togglePause() {
    state.paused = !state.paused;
    $("#pauseSystem").textContent = state.paused ? "▶" : "Ⅱ";
    $("#pauseSystem").title = state.paused ? "Resume new autonomous entries" : "Pause new autonomous entries";
    const banner = $("#systemBanner");
    banner.classList.toggle("hidden", !state.paused);
    banner.textContent = state.paused ? "NEW AUTONOMOUS ENTRIES PAUSED — market data, monitoring, open-position management, and hard exits remain active in this prototype." : "";
    toast(state.paused ? "New entries paused" : "New entries resumed", state.paused ? "Existing management policies remain active." : "Default episode authority restored.");
  }

  function updateReplay(value) {
    const v = Number(value);
    const baseMs = 15 * 3600000 + 17 * 60000 + 3800 + Math.round(v * 10.5);
    const h = Math.floor(baseMs / 3600000) % 24;
    const m = Math.floor(baseMs / 60000) % 60;
    const s = Math.floor(baseMs / 1000) % 60;
    const ms = baseMs % 1000;
    $("#replayTime").textContent = `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}.${String(ms).padStart(3,"0")} ET`;
    renderReplayRequirements(v);
    const count = Math.max(8, Math.round(state.chartSeries.leader.length * v / 100));
    drawMarketChart($("#replayChart"), state.chartSeries.leader.slice(0,count), state.chartSeries.follower.slice(0,count), state.chartSeries.flow.slice(0,count));
  }

  function toggleReplay() {
    const button = $("#replayPlay");
    if (state.replayTimer) {
      clearInterval(state.replayTimer); state.replayTimer = null; button.textContent = "▶ Play"; return;
    }
    button.textContent = "Ⅱ Pause";
    state.replayTimer = setInterval(() => {
      const slider = $("#replaySlider");
      let next = Number(slider.value) + 1;
      if (next > 100) { next = 0; }
      slider.value = next;
      updateReplay(next);
    }, 120);
  }

  function bindEvents() {
    $$(".nav-item[data-view]").forEach(button => button.addEventListener("click", () => setView(button.dataset.view)));
    $$(".mode-button").forEach(button => button.addEventListener("click", () => setMode(button.dataset.mode)));
    $("#openCommand").addEventListener("click", openCommand);
    $("#commandModal").addEventListener("click", e => { if (e.target === $("#commandModal")) closeCommand(); });
    $$("[data-command-view]").forEach(button => button.addEventListener("click", () => setView(button.dataset.commandView)));
    $("#commandStageHedge").addEventListener("click", () => { closeCommand(); openDrawer(); });
    $("#commandPause").addEventListener("click", () => { closeCommand(); togglePause(); });
    $("#pauseSystem").addEventListener("click", togglePause);
    $("#killButton").addEventListener("click", openKill);
    $("#riskKillButton").addEventListener("click", openKill);
    $("#closeKillModal").addEventListener("click", closeKill);
    $("#killModal").addEventListener("click", e => { if (e.target === $("#killModal")) closeKill(); });
    $$("[data-kill-action]").forEach(button => button.addEventListener("click", () => { toast("Emergency action staged", `${button.dataset.killAction} requires typed production confirmation and dual authorization.`); closeKill(); }));
    ["#stageHedgeButton", "#manualIntentButton", "#episodeHedgeButton", "#newPackageButton"].forEach(id => $(id)?.addEventListener("click", openDrawer));
    $("#openEpisodeButton").addEventListener("click", () => setView("episode"));
    $("#closeDrawer").addEventListener("click", closeDrawer);
    $("#rejectDrawer").addEventListener("click", closeDrawer);
    $("#drawerBackdrop").addEventListener("click", closeDrawer);
    $("#approveDrawer").addEventListener("click", () => { closeDrawer(); toast("Intent submitted", "The orchestrator received a structured hedge intent; no direct venue command was issued by the UI."); });
    $("#replaySlider").addEventListener("input", e => updateReplay(e.target.value));
    $("#replayPlay").addEventListener("click", toggleReplay);
    window.addEventListener("resize", () => requestAnimationFrame(drawAllCharts));
    document.addEventListener("keydown", e => {
      if (e.key === "/" && !["INPUT","TEXTAREA","SELECT"].includes(document.activeElement.tagName)) { e.preventDefault(); openCommand(); }
      if (e.key === "Escape") { closeCommand(); closeDrawer(); closeKill(); }
    });
  }

  function init() {
    renderOpportunities();
    renderDeltaTape();
    renderWeatherRows();
    renderPackages();
    renderConnectors();
    renderReplayRequirements();
    bindEvents();
    updateClock();
    updateReplay(42);
    requestAnimationFrame(drawAllCharts);
    setInterval(updateClock, 1000);
    setInterval(simulateTick, 1200);
  }

  document.addEventListener("DOMContentLoaded", init);
})();
