/* global Chart */

let DATA = null;
let pieChart = null;
let barChart = null;
let metricView = "combined";

const $ = (sel) => document.querySelector(sel);

function pct(x, digits = 1) {
  return `${(x * 100).toFixed(digits)}%`;
}

function cny(n) {
  if (n >= 1e6) return `¥${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `¥${Math.round(n / 1e3)}K`;
  return `¥${Math.round(n)}`;
}

function localGmv(n, currency) {
  if (currency === "CLP" || currency === "JPY") {
    if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M ${currency}`;
    if (n >= 1e3) return `${Math.round(n / 1e3)}K ${currency}`;
  }
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M ${currency}`;
  if (n >= 1e3) return `${Math.round(n / 1e3)}K ${currency}`;
  return `${Math.round(n)} ${currency}`;
}

function dualGmv(local, currency, cnyVal) {
  return `${localGmv(local, currency)} / ${cny(cnyVal)}`;
}

function pickMetrics(row, view) {
  if (view === "campaign") return row.campaign;
  if (view === "flow") return row.flow;
  const c = row.campaign;
  const f = row.flow;
  const delivered = c.delivered + f.delivered || 1;
  return {
    openRate: (c.openRate * c.delivered + f.openRate * f.delivered) / delivered,
    clickRate: (c.clickRate * c.delivered + f.clickRate * f.delivered) / delivered,
    convRate: (c.conversions + f.conversions) / delivered,
    delivered,
  };
}

function viewGmv(row, view) {
  if (view === "campaign") {
    return { local: row.campaign.gmv, cny: row.campaignGmvCny, campLocal: row.campaign.gmv, campCny: row.campaignGmvCny, flowLocal: 0, flowCny: 0 };
  }
  if (view === "flow") {
    return { local: row.flow.gmv, cny: row.flowGmvCny, campLocal: 0, campCny: 0, flowLocal: row.flow.gmv, flowCny: row.flowGmvCny };
  }
  return {
    local: row.campaign.gmv + row.flow.gmv,
    cny: row.totalGmvCny,
    campLocal: row.campaign.gmv,
    campCny: row.campaignGmvCny,
    flowLocal: row.flow.gmv,
    flowCny: row.flowGmvCny,
  };
}

function aggregateView(view) {
  let delivered = 0;
  let openW = 0;
  let clickW = 0;
  let conv = 0;
  let gmvCny = 0;
  let campaignCny = 0;
  let flowCny = 0;

  for (const row of DATA.rows) {
    const c = row.campaign;
    const f = row.flow;
    if (view === "campaign" || view === "combined") {
      delivered += c.delivered;
      openW += c.openRate * c.delivered;
      clickW += c.clickRate * c.delivered;
      conv += c.conversions;
      campaignCny += row.campaignGmvCny;
    }
    if (view === "flow" || view === "combined") {
      delivered += f.delivered;
      openW += f.openRate * f.delivered;
      clickW += f.clickRate * f.delivered;
      conv += f.conversions;
      flowCny += row.flowGmvCny;
    }
  }

  if (view === "campaign") {
    gmvCny = campaignCny;
  } else if (view === "flow") {
    gmvCny = flowCny;
  } else {
    gmvCny = campaignCny + flowCny;
  }

  const d = delivered || 1;
  const totalParts = campaignCny + flowCny || 1;
  return {
    gmvCny,
    campaignCny,
    flowCny,
    campaignShare: view === "flow" ? 0 : campaignCny / totalParts,
    flowShare: view === "campaign" ? 0 : flowCny / totalParts,
    openRate: openW / d,
    clickRate: clickW / d,
    convRate: conv / d,
  };
}

function rowTone(row, totalGmv, view) {
  const share = viewGmv(row, view).cny / totalGmv;
  if (share >= 0.15) return "tone-top";
  return "";
}

function alertTone(priority) {
  if (priority === "P0") return "tone-p0";
  if (priority === "P1") return "tone-p1";
  return "tone-warn";
}

async function loadData() {
  const res = await fetch("data/dashboard.json");
  if (!res.ok) throw new Error(`无法加载 dashboard.json (${res.status})`);
  return res.json();
}

function renderMeta() {
  const m = DATA.meta;
  const seed = m.seed ? " · 快照预览" : "";
  const errs = m.errors?.length ? ` · ${m.errors.length} 站同步失败` : "";
  $("#meta-line").textContent =
    `${m.period} · 更新 ${m.updatedAt.replace("T", " ").replace("Z", " UTC")} · ${m.siteCount} 站${seed}${errs}`;
}

function renderKpis() {
  const agg = aggregateView(metricView);
  const viewLabel = metricView === "combined" ? "合计" : metricView === "campaign" ? "Campaign" : "Flow";
  $("#kpi-grid").innerHTML = [
    { label: `${viewLabel} GMV (CNY)`, value: cny(agg.gmvCny), cls: "info" },
    { label: "Campaign 占比", value: pct(agg.campaignShare), cls: "", hide: metricView === "flow" },
    { label: "Flow 占比", value: pct(agg.flowShare), cls: "success", hide: metricView === "campaign" },
    { label: "打开率", value: pct(agg.openRate), cls: "" },
    { label: "点击率", value: pct(agg.clickRate, 2), cls: "" },
    { label: "转化率", value: pct(agg.convRate, 2), cls: "" },
  ]
    .filter((k) => !k.hide)
    .map(
      (k) => `
    <div class="kpi">
      <div class="kpi-label">${k.label}</div>
      <div class="kpi-value ${k.cls}">${k.value}</div>
    </div>`
    )
    .join("");
}

function renderCharts() {
  const agg = aggregateView(metricView);
  const pieCtx = $("#pie-chart");
  if (pieChart) pieChart.destroy();

  if (metricView === "combined") {
    pieChart = new Chart(pieCtx, {
      type: "doughnut",
      data: {
        labels: ["Campaign", "Flow"],
        datasets: [{ data: [agg.campaignCny, agg.flowCny], backgroundColor: ["#3b82f6", "#22c55e"], borderWidth: 0 }],
      },
      options: { plugins: { legend: { display: false } }, cutout: "55%" },
    });
    $("#pie-legend").innerHTML = `
      <div class="total">合计 ${cny(agg.gmvCny)}</div>
      <div class="legend-item"><span class="legend-dot" style="background:#3b82f6"></span>Campaign ${cny(agg.campaignCny)} (${pct(agg.campaignShare)})</div>
      <div class="legend-item"><span class="legend-dot" style="background:#22c55e"></span>Flow ${cny(agg.flowCny)} (${pct(agg.flowShare)})</div>`;
  } else {
    const label = metricView === "campaign" ? "Campaign" : "Flow";
    const val = metricView === "campaign" ? agg.campaignCny : agg.flowCny;
    pieChart = new Chart(pieCtx, {
      type: "doughnut",
      data: {
        labels: [label],
        datasets: [{ data: [val], backgroundColor: [metricView === "campaign" ? "#3b82f6" : "#22c55e"], borderWidth: 0 }],
      },
      options: { plugins: { legend: { display: false } }, cutout: "55%" },
    });
    $("#pie-legend").innerHTML = `<div class="total">${label} ${cny(val)}</div>`;
  }

  const rows = DATA.rows.slice().sort((a, b) => viewGmv(b, metricView).cny - viewGmv(a, metricView).cny);
  const barCtx = $("#bar-chart");
  if (barChart) barChart.destroy();

  const chartTitle = $("#bar-chart-title");
  if (chartTitle) chartTitle.textContent = metricView === "combined" ? "各站 GMV（本位币 / CNY）" : `各站 ${metricView === "campaign" ? "Campaign" : "Flow"} GMV（CNY）`;

  if (metricView === "combined") {
    barChart = new Chart(barCtx, {
      type: "bar",
      data: {
        labels: rows.map((r) => r.region),
        datasets: [
          { label: "Campaign CNY", data: rows.map((r) => r.campaignGmvCny), backgroundColor: "#3b82f6" },
          { label: "Flow CNY", data: rows.map((r) => r.flowGmvCny), backgroundColor: "#22c55e" },
        ],
      },
      options: chartOptions(),
    });
  } else {
    const key = metricView === "campaign" ? "campaignGmvCny" : "flowGmvCny";
    barChart = new Chart(barCtx, {
      type: "bar",
      data: {
        labels: rows.map((r) => r.region),
        datasets: [{ label: "GMV CNY", data: rows.map((r) => r[key]), backgroundColor: metricView === "campaign" ? "#3b82f6" : "#22c55e" }],
      },
      options: chartOptions(),
    });
  }
}

function chartOptions() {
  return {
    indexAxis: "y",
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: { stacked: metricView === "combined", ticks: { callback: (v) => cny(v) }, grid: { color: "#2d3a4f" } },
      y: { stacked: metricView === "combined", grid: { display: false } },
    },
    plugins: { legend: { position: "bottom", labels: { color: "#8b9cb3" } } },
  };
}

function renderOverviewTable() {
  const agg = aggregateView(metricView);
  const totalGmv = agg.gmvCny;
  const tbody = $("#overview-table tbody");
  const showCamp = metricView !== "flow";
  const showFlow = metricView !== "campaign";

  $("#overview-table thead tr").innerHTML = `
    <th class="col-site">站点</th>
    ${showCamp ? '<th class="col-num">Campaign GMV</th>' : ""}
    ${showFlow ? '<th class="col-num">Flow GMV</th>' : ""}
    <th class="col-num">合计 GMV</th>
    <th class="col-num">打开率</th>
    <th class="col-num">转化率</th>
    <th class="col-num">占比</th>`;

  tbody.innerHTML = DATA.rows
    .map((row) => {
      const m = pickMetrics(row, metricView);
      const g = viewGmv(row, metricView);
      const cells = [
        `<td class="col-site">${row.region}</td>`,
        showCamp
          ? `<td class="col-num dual">${dualGmv(g.campLocal, row.currency, g.campCny)}</td>`
          : "",
        showFlow ? `<td class="col-num dual">${dualGmv(g.flowLocal, row.currency, g.flowCny)}</td>` : "",
        `<td class="col-num dual"><strong>${dualGmv(g.local, row.currency, g.cny)}</strong></td>`,
        `<td class="col-num">${pct(m.openRate)}</td>`,
        `<td class="col-num">${pct(m.convRate, 2)}</td>`,
        `<td class="col-num">${pct(g.cny / totalGmv, 1)}</td>`,
      ].join("");
      return `<tr class="${rowTone(row, totalGmv, metricView)}">${cells}</tr>`;
    })
    .join("");
}

function renderEmailList(items, kind) {
  if (!items?.length) return `<p class="hint">暂无数据</p>`;
  return items
    .map((item) => {
      const m = item.metrics || {};
      const metricsLine = m.recipients
        ? `<div class="email-metrics">发送 ${m.recipients.toLocaleString()} · 打开 ${pct(m.openRate)} · 点击 ${pct(m.clickRate, 2)} · GMV ${Math.round(m.gmv || 0).toLocaleString()}</div>`
        : "";
      return `
      <div class="email-card ${kind}">
        <div class="email-name">${escapeHtml(item.name)}</div>
        <div class="email-subject">Subject：${escapeHtml(item.subject || "—")}</div>
        <div class="email-audience">受众：${escapeHtml(item.audience || "—")}</div>
        ${metricsLine}
        <ul class="email-reasons">${(item.reasons || []).map((r) => `<li>${escapeHtml(r)}</li>`).join("")}</ul>
      </div>`;
    })
    .join("");
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderSites() {
  const container = $("#sites-container");
  const order = DATA.siteOrder || DATA.rows.map((r) => r.region);
  container.innerHTML = order
    .map((code) => {
      const why = DATA.siteWhy[code];
      if (!why) return "";
      return `
      <div class="site-block" data-site="${code}">
        <button type="button" class="site-header" aria-expanded="false">
          <span>${code}</span>
          <span class="chevron">›</span>
        </button>
        <div class="site-body">
          <p class="site-summary">${escapeHtml(why.summary || "")}</p>
          <div class="sub-block open">
            <button type="button" class="sub-header">Campaign 最佳 / 待优化 <span class="chevron">›</span></button>
            <div class="sub-body">
              <p class="hint">最佳</p>
              ${renderEmailList(why.campaignBest, "best")}
              <p class="hint" style="margin-top:0.75rem">待优化</p>
              ${renderEmailList(why.campaignWorst, "worst")}
            </div>
          </div>
          <div class="sub-block open">
            <button type="button" class="sub-header">Flow 最佳 / 待优化 <span class="chevron">›</span></button>
            <div class="sub-body">
              <p class="hint">最佳</p>
              ${renderEmailList(why.flowBest, "best")}
              <p class="hint" style="margin-top:0.75rem">待优化</p>
              ${renderEmailList(why.flowWorst, "worst")}
            </div>
          </div>
        </div>
      </div>`;
    })
    .join("");

  container.querySelectorAll(".site-header").forEach((btn) => {
    btn.addEventListener("click", () => {
      const block = btn.closest(".site-block");
      block.classList.toggle("open");
      btn.setAttribute("aria-expanded", block.classList.contains("open"));
    });
  });
  container.querySelectorAll(".sub-header").forEach((btn) => {
    btn.addEventListener("click", () => btn.closest(".sub-block").classList.toggle("open"));
  });
}

function renderFlow() {
  const tbody = $("#flow-table tbody");
  const alerts = DATA.flowAlerts || [];
  tbody.innerHTML = alerts.length
    ? alerts
        .map(
          (a) => `<tr class="${alertTone(a.priority)}">
      <td>${a.priority}</td>
      <td>${a.region}</td>
      <td>${escapeHtml(a.flow)}</td>
      <td>${a.category}</td>
      <td>${escapeHtml(a.issue)}</td>
      <td>${escapeHtml(a.action)}</td>
    </tr>`
        )
        .join("")
    : `<tr><td colspan="6" class="hint">暂无待关注项</td></tr>`;
}

function renderPlaybook() {
  const order = DATA.siteOrder || DATA.rows.map((r) => r.region);
  const playbooks = DATA.sitePlaybook || {};
  $("#playbook-grid").innerHTML = order
    .map((code) => {
      const pb = playbooks[code];
      if (!pb) return "";
      const list = (title, items) =>
        `<div class="playbook-section"><h4>${title}</h4><ul>${(items || []).map((x) => `<li>${escapeHtml(x)}</li>`).join("")}</ul></div>`;
      return `
      <div class="card playbook-card site-playbook">
        <h3>${code} · Playbook</h3>
        <p class="site-summary">${escapeHtml(pb.summary || "")}</p>
        ${list("Campaign 可复制", pb.successCampaign)}
        ${list("Campaign 待避免", pb.avoidCampaign)}
        ${list("Flow 可复制", pb.successFlow)}
        ${list("Flow 待避免", pb.avoidFlow)}
      </div>`;
    })
    .join("");
}

function refreshOverview() {
  renderKpis();
  renderCharts();
  renderOverviewTable();
}

function showSection(name) {
  document.querySelectorAll(".view").forEach((el) => el.classList.add("hidden"));
  $(`#view-${name}`).classList.remove("hidden");
  $("#metric-filter-wrap").classList.toggle("hidden", name !== "overview");
  if (name === "overview") refreshOverview();
}

async function init() {
  try {
    DATA = await loadData();
    metricView = $("#metric-view").value;
    $("#loading").classList.add("hidden");
    renderMeta();
    renderSites();
    renderFlow();
    renderPlaybook();
    showSection($("#section-select").value);

    $("#section-select").addEventListener("change", (e) => showSection(e.target.value));
    $("#metric-view").addEventListener("change", (e) => {
      metricView = e.target.value;
      refreshOverview();
    });
  } catch (err) {
    $("#loading").classList.add("hidden");
    const el = $("#error");
    el.textContent = err.message;
    el.classList.remove("hidden");
  }
}

document.addEventListener("DOMContentLoaded", init);
