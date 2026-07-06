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

function yuan(value) {
  return `${Number(value || 0).toLocaleString("zh-CN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })} 元`;
}

function setText(selector, text) {
  document.querySelector(selector).textContent = text;
}

function syncStockInputs() {
  state.code = codeInput.value.trim() || "002594";
  state.name = nameInput.value.trim() || state.code;
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
  const revenuePoints = payload.revenue_points || [];
  const pricePoints = payload.price_points || [];
  if (!revenuePoints.length || !pricePoints.length) {
    showError("没有可展示的股价与营收趋势数据");
    return;
  }
  const latestRevenue = revenuePoints[revenuePoints.length - 1];
  const latestPrice = pricePoints[pricePoints.length - 1];
  setText("#trend-heading", `${payload.company.name}股价与年化营收趋势`);
  setText("#latest-revenue", yi(latestRevenue.annualized_revenue_yi));
  setText("#latest-price", yuan(latestPrice.price));
  setText("#latest-trend-date", latestRevenue.date);
  setText("#trend-point-count", `${pricePoints.length} 周`);
  drawTrendChart(revenuePoints, pricePoints);
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

function drawTrendChart(revenuePoints, pricePoints) {
  const width = 1120;
  const height = 520;
  const margin = { top: 48, right: 96, bottom: 72, left: 86 };
  const chartWidth = width - margin.left - margin.right;
  const chartHeight = height - margin.top - margin.bottom;
  const revenueMax = axisMax(revenuePoints.map((item) => item.annualized_revenue_yi));
  const priceMax = axisMax(pricePoints.map((item) => item.price));
  const allTimes = [...revenuePoints, ...pricePoints].map((item) => new Date(item.date).getTime());
  const minTime = Math.min(...allTimes);
  const maxTime = Math.max(...allTimes);
  const timeRange = Math.max(maxTime - minTime, 1);
  const barWidth = Math.min(24, chartWidth / Math.max(revenuePoints.length, 1) * 0.55);
  const yRevenue = (value) => margin.top + chartHeight - (value / revenueMax) * chartHeight;
  const yPrice = (value) => margin.top + chartHeight - (value / priceMax) * chartHeight;
  const xAtDate = (date) => margin.left + ((new Date(date).getTime() - minTime) / timeRange) * chartWidth;
  const grid = [];
  const leftTicks = [];
  const rightTicks = [];

  for (let i = 0; i <= 4; i += 1) {
    const y = margin.top + (chartHeight / 4) * i;
    const leftValue = Math.round(revenueMax - (revenueMax / 4) * i);
    const rightValue = Math.round(priceMax - (priceMax / 4) * i);
    grid.push(`<line x1="${margin.left}" y1="${y}" x2="${width - margin.right}" y2="${y}" class="grid-line" />`);
    leftTicks.push(svgText(34, y + 4, leftValue.toLocaleString("zh-CN"), "revenue-tick"));
    rightTicks.push(svgText(width - margin.right + 18, y + 4, rightValue.toLocaleString("zh-CN"), "price-tick"));
  }

  const barsSvg = revenuePoints.map((point) => {
    const x = xAtDate(point.date) - barWidth / 2;
    const y = yRevenue(point.annualized_revenue_yi);
    const h = margin.top + chartHeight - y;
    return `<rect x="${x}" y="${y}" width="${barWidth}" height="${Math.max(h, 1)}" rx="3" class="trend-bar" />`;
  });
  const linePath = pricePoints.map((point, index) => `${index === 0 ? "M" : "L"} ${xAtDate(point.date)} ${yPrice(point.price)}`).join(" ");
  const latestPoint = pricePoints[pricePoints.length - 1];
  const markerPoints = pricePoints.filter((point, index) => {
    const isLatest = index === pricePoints.length - 1;
    const isYearEnd = point.date.slice(5) >= "12-24" || point.date.slice(5) <= "01-07";
    return isLatest || isYearEnd;
  });
  const pointSvg = markerPoints.map((point, index) => {
    const isLatest = point === latestPoint;
    return `<circle cx="${xAtDate(point.date)}" cy="${yPrice(point.price)}" r="${isLatest ? 5 : 3}" class="trend-point-marker${isLatest ? " latest" : ""}" />`;
  });
  const latestX = xAtDate(latestPoint.date);
  const latestY = yPrice(latestPoint.price);
  const latestLabelX = Math.min(latestX + 12, width - margin.right - 62);
  const latestLabelY = Math.max(latestY - 12, margin.top + 16);
  const latestLabel = `<text x="${latestLabelX}" y="${latestLabelY}" class="latest-price-label">${yuan(latestPoint.price)}</text>`;
  const startYear = new Date(minTime).getFullYear();
  const endYear = new Date(maxTime).getFullYear();
  const xLabels = [];
  const yearGuides = [];
  for (let year = startYear; year <= endYear; year += 1) {
    const x = xAtDate(`${year}-01-01`);
    if (x >= margin.left && x <= width - margin.right) {
      yearGuides.push(`<line x1="${x}" y1="${margin.top}" x2="${x}" y2="${height - margin.bottom}" class="year-guide" />`);
      xLabels.push(svgText(x - 18, height - 30, String(year), "year-label"));
    }
  }

  trendSvg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  trendSvg.innerHTML = [
    ...grid,
    ...yearGuides,
    `<line x1="${margin.left}" y1="${margin.top}" x2="${margin.left}" y2="${height - margin.bottom}" class="axis-line revenue-axis" />`,
    `<line x1="${width - margin.right}" y1="${margin.top}" x2="${width - margin.right}" y2="${height - margin.bottom}" class="axis-line price-axis" />`,
    `<line x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}" class="axis-line" />`,
    svgText(22, 24, "年化营收（亿元）", "revenue-axis-title"),
    svgText(width - margin.right - 28, 24, "前复权股价（元）", "price-axis-title"),
    ...leftTicks,
    ...rightTicks,
    ...barsSvg,
    `<path d="${linePath}" class="trend-line" />`,
    ...pointSvg,
    latestLabel,
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

async function readJsonResponse(response) {
  const contentType = response.headers.get("Content-Type") || "";
  if (!contentType.includes("application/json")) {
    const text = await response.text();
    if (text.trim().toLowerCase().startsWith("<!doctype")) {
      throw new Error("接口返回了页面 HTML，请重启本地服务后刷新");
    }
    throw new Error("接口返回了非 JSON 内容");
  }
  return response.json();
}

async function loadBalanceDashboard() {
  syncStockInputs();
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
    const payload = await readJsonResponse(response);
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
  syncStockInputs();
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
    const response = await fetchWithTimeout(`/api/revenue-price?${params.toString()}`, 30000);
    const payload = await readJsonResponse(response);
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
  syncStockInputs();
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
