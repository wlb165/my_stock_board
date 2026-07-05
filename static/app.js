const state = {
  code: "002594",
  name: "比亚迪",
  index: 0,
  period: null,
  view: "balance",
};

const form = document.querySelector("#stock-form");
const codeInput = document.querySelector("#stock-code");
const nameInput = document.querySelector("#stock-name");
const loading = document.querySelector("#loading");
const error = document.querySelector("#error");
const panel = document.querySelector("#chart-panel");
const trendPanel = document.querySelector("#trend-panel");
const bars = document.querySelector("#bars");
const yAxis = document.querySelector("#y-axis");
const periodActions = document.querySelector("#period-actions");
const currentButton = document.querySelector("#current-period");
const prevButton = document.querySelector("#prev-period");
const nextButton = document.querySelector("#next-period");
const tabButtons = document.querySelectorAll(".tab[data-view]");
const trendSvg = document.querySelector("#trend-svg");

function yi(value) {
  return `${Number(value || 0).toLocaleString("zh-CN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })} 亿`;
}

function setText(selector, text) {
  document.querySelector(selector).textContent = text;
}

function setLoading(isLoading) {
  loading.hidden = !isLoading;
  panel.hidden = true;
  trendPanel.hidden = true;
  error.hidden = true;
}

function showError(message) {
  loading.hidden = true;
  panel.hidden = true;
  trendPanel.hidden = true;
  error.hidden = false;
  error.textContent = `读取失败：${message}`;
}

function niceChartMax(items) {
  const maxValue = Math.max(...items.map((item) => item.value), 1);
  const targetTop = maxValue * 1.12;
  const roughStep = targetTop / 4;
  const exponent = Math.floor(Math.log10(roughStep));
  const base = 10 ** exponent;
  const niceSteps = [1, 1.5, 2, 2.5, 5, 10];
  const step = niceSteps.find((item) => item * base >= roughStep) * base;
  return step * 4;
}

function renderYAxis(maxValue) {
  yAxis.innerHTML = "";
  for (let i = 4; i >= 0; i -= 1) {
    const tick = document.createElement("span");
    tick.textContent = Math.round((maxValue / 4) * i).toLocaleString("zh-CN");
    yAxis.appendChild(tick);
  }
}

function renderBars(payload) {
  const items = [
    ...payload.assets.map((item) => ({ ...item, type: "asset" })),
    ...payload.liabilities.map((item) => ({ ...item, type: "liability" })),
  ];
  const maxValue = niceChartMax(items);
  renderYAxis(maxValue);
  bars.innerHTML = "";

  for (const item of items) {
    const wrap = document.createElement("div");
    wrap.className = "bar-item";

    const stack = document.createElement("div");
    stack.className = "bar-stack";

    const bar = document.createElement("div");
    bar.className = `bar ${item.type}`;
    bar.style.height = `${Math.max((item.value / maxValue) * 100, 1)}%`;

    const value = document.createElement("span");
    value.className = "bar-value";
    value.textContent = item.value ? item.value.toLocaleString("zh-CN") : "0";
    bar.appendChild(value);
    stack.appendChild(bar);

    const label = document.createElement("div");
    label.className = "bar-label";
    label.innerHTML = item.label.replace("&", "<br>&<br>");

    wrap.append(stack, label);
    bars.appendChild(wrap);
  }
}

function renderBalance(payload) {
  state.period = payload.period;
  setText("#chart-heading", `${payload.company.name}资产负债表`);
  setText("#report-date", payload.period.current);
  setText("#total-assets", yi(payload.summary.total_assets_yi));
  setText("#total-liabilities", yi(payload.summary.total_liabilities_yi));
  setText("#equity", yi(payload.summary.equity_yi));
  setText("#debt-ratio", `${payload.summary.debt_ratio_pct}%`);
  prevButton.disabled = !payload.period.has_previous;
  nextButton.disabled = !payload.period.has_next;
  renderBars(payload);
  loading.hidden = true;
  error.hidden = true;
  panel.hidden = false;
}

function renderTrend(payload) {
  const points = payload.points || [];
  if (!points.length) {
    showError("没有可展示的市值与营收趋势数据");
    return;
  }
  const latest = points[points.length - 1];
  setText("#trend-heading", `${payload.company.name}市值与年化营收趋势`);
  setText("#latest-revenue", yi(latest.annualized_revenue_yi));
  setText("#latest-market-cap", yi(latest.market_cap_yi));
  setText("#latest-trend-date", latest.date);
  setText("#trend-point-count", `${points.length} 个`);
  drawTrendChart(points);
  loading.hidden = true;
  error.hidden = true;
  trendPanel.hidden = false;
}

function axisMax(values) {
  return niceChartMax(values.map((value) => ({ value })));
}

function svgText(x, y, text, extra = "") {
  return `<text x="${x}" y="${y}" class="axis-text ${extra}">${text}</text>`;
}

function drawTrendChart(points) {
  const width = Math.max(980, points.length * 36 + 130);
  const height = 430;
  const margin = { top: 24, right: 74, bottom: 62, left: 74 };
  const chartWidth = width - margin.left - margin.right;
  const chartHeight = height - margin.top - margin.bottom;
  const revenueMax = axisMax(points.map((item) => item.annualized_revenue_yi));
  const marketMax = axisMax(points.map((item) => item.market_cap_yi));
  const xStep = chartWidth / Math.max(points.length - 1, 1);
  const barWidth = Math.min(18, xStep * 0.5);
  const yRevenue = (value) => margin.top + chartHeight - (value / revenueMax) * chartHeight;
  const yMarket = (value) => margin.top + chartHeight - (value / marketMax) * chartHeight;
  const xAt = (index) => margin.left + index * xStep;
  const grid = [];
  const leftTicks = [];
  const rightTicks = [];

  for (let i = 0; i <= 4; i += 1) {
    const y = margin.top + (chartHeight / 4) * i;
    const leftValue = Math.round(revenueMax - (revenueMax / 4) * i);
    const rightValue = Math.round(marketMax - (marketMax / 4) * i);
    grid.push(`<line x1="${margin.left}" y1="${y}" x2="${width - margin.right}" y2="${y}" class="grid-line" />`);
    leftTicks.push(svgText(28, y + 4, leftValue.toLocaleString("zh-CN")));
    rightTicks.push(svgText(width - margin.right + 14, y + 4, rightValue.toLocaleString("zh-CN")));
  }

  const barsSvg = points.map((point, index) => {
    const x = xAt(index) - barWidth / 2;
    const y = yRevenue(point.annualized_revenue_yi);
    const h = margin.top + chartHeight - y;
    return `<rect x="${x}" y="${y}" width="${barWidth}" height="${Math.max(h, 1)}" rx="2" class="trend-bar" />`;
  });
  const linePath = points.map((point, index) => `${index === 0 ? "M" : "L"} ${xAt(index)} ${yMarket(point.market_cap_yi)}`).join(" ");
  const pointSvg = points.map((point, index) => `<circle cx="${xAt(index)}" cy="${yMarket(point.market_cap_yi)}" r="3" class="trend-point" />`);
  const xLabels = points.map((point, index) => {
    const isYearEnd = point.date.endsWith("12-31");
    const isEdge = index === 0 || index === points.length - 1;
    if (!isYearEnd && !isEdge) return "";
    return svgText(xAt(index) - 18, height - 26, point.date.slice(0, 4));
  });

  trendSvg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  trendSvg.innerHTML = [
    ...grid,
    `<line x1="${margin.left}" y1="${margin.top}" x2="${margin.left}" y2="${height - margin.bottom}" class="axis-line" />`,
    `<line x1="${width - margin.right}" y1="${margin.top}" x2="${width - margin.right}" y2="${height - margin.bottom}" class="axis-line" />`,
    `<line x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}" class="axis-line" />`,
    svgText(20, 18, "年化营收"),
    svgText(width - margin.right + 8, 18, "总市值"),
    ...leftTicks,
    ...rightTicks,
    ...barsSvg,
    `<path d="${linePath}" class="trend-line" />`,
    ...pointSvg,
    ...xLabels,
  ].join("");
}

async function fetchWithTimeout(url, timeoutMs = 20000) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { signal: controller.signal });
  } finally {
    window.clearTimeout(timer);
  }
}

async function loadBalanceDashboard() {
  state.name = nameInput.value.trim() || state.name;
  if (window.location.protocol === "file:") {
    showError("请打开 http://127.0.0.1:8765，不要直接打开 static/index.html 文件");
    return;
  }

  setLoading(true);
  try {
    const params = new URLSearchParams({
      code: state.code,
      name: state.name,
      index: String(state.index),
    });
    const response = await fetchWithTimeout(`/api/balance-sheet?${params.toString()}`);
    const payload = await response.json();
    if (!response.ok || payload.error) {
      showError(payload.error || "接口无返回");
      return;
    }
    renderBalance(payload);
  } catch (err) {
    const message = err.name === "AbortError" ? "接口超时，请确认本地服务和网络可用" : err.message;
    showError(message || "接口请求失败");
  }
}

async function loadTrendDashboard() {
  state.name = nameInput.value.trim() || state.name;
  if (window.location.protocol === "file:") {
    showError("请打开 http://127.0.0.1:8765，不要直接打开 static/index.html 文件");
    return;
  }

  setLoading(true);
  try {
    const params = new URLSearchParams({
      code: state.code,
      name: state.name,
    });
    const response = await fetchWithTimeout(`/api/revenue-market-cap?${params.toString()}`, 30000);
    const payload = await response.json();
    if (!response.ok || payload.error) {
      showError(payload.error || "接口无返回");
      return;
    }
    renderTrend(payload);
  } catch (err) {
    const message = err.name === "AbortError" ? "接口超时，请确认本地服务和网络可用" : err.message;
    showError(message || "接口请求失败");
  }
}

function loadActiveDashboard() {
  periodActions.hidden = state.view !== "balance";
  if (state.view === "trend") {
    loadTrendDashboard();
    return;
  }
  if (state.view === "balance") {
    loadBalanceDashboard();
  }
}

function setView(view) {
  if (view === "basic") return;
  state.view = view;
  tabButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  loadActiveDashboard();
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  state.code = codeInput.value.trim() || "002594";
  state.name = nameInput.value.trim() || state.code;
  state.index = 0;
  loadActiveDashboard();
});

currentButton.addEventListener("click", () => {
  state.index = 0;
  loadBalanceDashboard();
});

prevButton.addEventListener("click", () => {
  if (!state.period?.has_previous) return;
  state.index += 1;
  loadBalanceDashboard();
});

nextButton.addEventListener("click", () => {
  if (!state.period?.has_next) return;
  state.index -= 1;
  loadBalanceDashboard();
});

tabButtons.forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.view));
});

loadActiveDashboard();
