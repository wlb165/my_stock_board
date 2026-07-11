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
const workbenchButtons = document.querySelectorAll("[data-workbench-view]");
const workbenchPanels = document.querySelectorAll("[data-workbench-panel]");
const trendSvg = document.querySelector("#trend-svg");
const valuationPanel = document.querySelector("#valuation-panel");
const valuationForm = document.querySelector("#valuation-form");
const valuationSvg = document.querySelector("#valuation-svg");
const multiTrendPanel = document.querySelector("#multi-trend-panel");
const multiStockForm = document.querySelector("#multi-stock-form");
const multiStockCodes = document.querySelector("#multi-stock-codes");
const multiPeriod = document.querySelector("#multi-period");
const multiMode = document.querySelector("#multi-mode");
const multiTrendSvg = document.querySelector("#multi-trend-svg");
const multiLegend = document.querySelector("#multi-legend");
const multiSummary = document.querySelector("#multi-summary");
const multiErrors = document.querySelector("#multi-errors");
let multiTrendPayload = null;

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
  workbenchPanels.forEach((item) => {
    item.hidden = true;
  });
  error.hidden = true;
}

function showError(message) {
  loading.hidden = true;
  workbenchPanels.forEach((item) => {
    item.hidden = true;
  });
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

function pctInputValue(selector) {
  return String((Number(document.querySelector(selector).value || 0) / 100).toFixed(4));
}

function readValuationAssumptions() {
  return {
    forecast_years: document.querySelector("#forecast-years").value,
    growth_conservative: pctInputValue("#growth-conservative"),
    growth_neutral: pctInputValue("#growth-neutral"),
    growth_optimistic: pctInputValue("#growth-optimistic"),
    discount_rate: pctInputValue("#discount-rate"),
    perpetual_growth_rate: pctInputValue("#perpetual-growth-rate"),
    safety_margin: pctInputValue("#safety-margin"),
  };
}

function ratioText(value) {
  return value == null ? "--" : `${Number(value).toLocaleString("zh-CN", { maximumFractionDigits: 2 })}x`;
}

function renderValuation(payload) {
  const summary = payload.summary || {};
  setText("#valuation-current-price", yuan(summary.current_price));
  setText("#valuation-neutral-value", yuan(summary.neutral_value));
  setText("#valuation-discount", summary.discount_to_neutral_pct == null ? "--" : `${summary.discount_to_neutral_pct}%`);
  setText("#valuation-safety-price", yuan(summary.safety_buy_price));
  setText("#valuation-market-cap", yi(summary.market_cap_yi));
  setText("#valuation-pe", ratioText(summary.pe_ttm));
  setText("#valuation-pb", ratioText(summary.pb));
  setText("#valuation-ps", ratioText(summary.ps_ttm));
  drawValuationChart(payload.points || [], payload.price_points || []);
  loading.hidden = true;
  error.hidden = true;
  valuationPanel.hidden = false;
}

function showValuationDashboard() {
  [
    "#valuation-current-price",
    "#valuation-neutral-value",
    "#valuation-discount",
    "#valuation-safety-price",
    "#valuation-market-cap",
    "#valuation-pe",
    "#valuation-pb",
    "#valuation-ps",
  ].forEach((selector) => setText(selector, "--"));
  valuationSvg.innerHTML = "";
  loading.hidden = true;
  error.hidden = true;
  workbenchPanels.forEach((item) => {
    item.hidden = item.dataset.workbenchPanel !== "valuation";
  });
}

function showMultiTrendPlaceholder() {
  loading.hidden = true;
  error.hidden = true;
  workbenchPanels.forEach((item) => {
    item.hidden = item.dataset.workbenchPanel !== "multi-trend";
  });
}

async function loadMultiTrendDashboard() {
  if (window.location.protocol === "file:") {
    showError("请打开 http://127.0.0.1:8765，不要直接打开 static/index.html 文件");
    return;
  }

  setLoading(true);
  try {
    const params = new URLSearchParams({
      codes: multiStockCodes.value.trim(),
      period: multiPeriod.value,
    });
    const response = await fetchWithTimeout(`/api/multi-stock-trend?${params.toString()}`, 45000);
    const payload = await readJsonResponse(response);
    if (payload.error) {
      showError(payload.error);
      return;
    }
    if (!response.ok && !(payload.series || []).length) {
      const firstError = (payload.errors || [])[0];
      showError(firstError ? firstError.message : "没有可展示的多股走势数据");
      return;
    }
    multiTrendPayload = payload;
    renderMultiTrend(payload);
  } catch (err) {
    const message = err.name === "AbortError" ? "接口超时，请确认本地服务和网络可用" : err.message;
    showError(message || "接口请求失败");
  }
}

function renderMultiTrend(payload) {
  const series = payload.series || [];
  const errors = payload.errors || [];
  const mode = multiMode.value || payload.mode_default || "percent";
  if (!series.length) {
    showError("没有可展示的多股走势数据");
    return;
  }

  multiSummary.innerHTML = series.map((item) => {
    const summary = item.summary || {};
    return [
      "<div>",
      `<span>${item.name || item.code}</span>`,
      `<strong>${mode === "price" ? yuan(summary.latest_price) : `${summary.period_change_pct ?? "--"}%`}</strong>`,
      `<span>${summary.point_count || 0} 个采样点</span>`,
      "</div>",
    ].join("");
  }).join("");

  multiErrors.hidden = !errors.length;
  multiErrors.innerHTML = errors.map((item) => {
    const code = item.code ? `${item.code}: ` : "";
    return `<p>${code}${item.message}</p>`;
  }).join("");

  multiLegend.innerHTML = series.map((item, index) => (
    `<span><i style="background:${multiColors[index % multiColors.length]}"></i>${item.name || item.code}</span>`
  )).join("");

  drawMultiTrendChart(series, mode);
  loading.hidden = true;
  error.hidden = true;
  multiTrendPanel.hidden = false;
}

const multiColors = ["#d92d20", "#2563eb", "#16a34a", "#9333ea", "#ea580c", "#0891b2"];

function drawMultiTrendChart(series, mode) {
  const field = mode === "price" ? "price" : "change_pct";
  const allPoints = series.flatMap((item) => item.points || []);
  if (!allPoints.length) {
    multiTrendSvg.innerHTML = "";
    return;
  }

  const width = 1120;
  const height = 520;
  const margin = { top: 44, right: 38, bottom: 64, left: 82 };
  const chartWidth = width - margin.left - margin.right;
  const chartHeight = height - margin.top - margin.bottom;
  const values = allPoints.map((point) => Number(point[field])).filter(Number.isFinite);
  const minValue = Math.min(...values, 0);
  const maxValue = Math.max(...values, 1);
  const valueRange = Math.max(maxValue - minValue, 1);
  const times = allPoints.map((point) => new Date(point.date).getTime());
  const minTime = Math.min(...times);
  const maxTime = Math.max(...times);
  const timeRange = Math.max(maxTime - minTime, 1);
  const xAtDate = (date) => margin.left + ((new Date(date).getTime() - minTime) / timeRange) * chartWidth;
  const yAtValue = (value) => margin.top + chartHeight - ((value - minValue) / valueRange) * chartHeight;
  const grid = [];
  const xLabels = [];
  const yearGuides = [];

  for (let i = 0; i <= 4; i += 1) {
    const y = margin.top + (chartHeight / 4) * i;
    const value = maxValue - (valueRange / 4) * i;
    const label = mode === "price"
      ? value.toLocaleString("zh-CN", { maximumFractionDigits: 2 })
      : `${value.toLocaleString("zh-CN", { maximumFractionDigits: 1 })}%`;
    grid.push(`<line x1="${margin.left}" y1="${y}" x2="${width - margin.right}" y2="${y}" class="grid-line" />`);
    grid.push(svgText(20, y + 4, label, "multi-trend-tick"));
  }

  if (minValue < 0 && maxValue > 0) {
    const zeroY = yAtValue(0);
    grid.push(`<line x1="${margin.left}" y1="${zeroY}" x2="${width - margin.right}" y2="${zeroY}" class="multi-zero-line" />`);
  }

  const startYear = new Date(minTime).getFullYear();
  const endYear = new Date(maxTime).getFullYear();
  for (let year = startYear; year <= endYear; year += 1) {
    const x = xAtDate(`${year}-01-01`);
    if (x >= margin.left && x <= width - margin.right) {
      yearGuides.push(`<line x1="${x}" y1="${margin.top}" x2="${x}" y2="${height - margin.bottom}" class="year-guide" />`);
      xLabels.push(svgText(x - 18, height - 30, String(year), "year-label"));
    }
  }

  const lines = series.map((item, index) => {
    const points = (item.points || []).filter((point) => Number.isFinite(Number(point[field])));
    const path = points.map((point, pointIndex) => {
      const command = pointIndex === 0 ? "M" : "L";
      return `${command} ${xAtDate(point.date)} ${yAtValue(Number(point[field]))}`;
    }).join(" ");
    const latest = points[points.length - 1];
    const marker = latest
      ? `<circle cx="${xAtDate(latest.date)}" cy="${yAtValue(Number(latest[field]))}" r="4" fill="${multiColors[index % multiColors.length]}" class="multi-trend-marker" />`
      : "";
    return `<path d="${path}" class="multi-trend-line" stroke="${multiColors[index % multiColors.length]}" />${marker}`;
  });

  multiTrendSvg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  multiTrendSvg.innerHTML = [
    ...grid,
    ...yearGuides,
    `<line x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}" class="axis-line" />`,
    svgText(22, 24, mode === "price" ? "前复权收盘价（元）" : "区间涨跌幅（%）", "multi-axis-title"),
    ...lines,
    ...xLabels,
  ].join("");
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

function drawValuationChart(points, pricePoints) {
  if (!points.length && !pricePoints.length) {
    valuationSvg.innerHTML = "";
    return;
  }
  const width = 1120;
  const height = 520;
  const margin = { top: 42, right: 52, bottom: 64, left: 78 };
  const chartWidth = width - margin.left - margin.right;
  const chartHeight = height - margin.top - margin.bottom;
  const values = [
    ...pricePoints.map((item) => item.price),
    ...points.flatMap((item) => [
    item.conservative_value,
    item.neutral_value,
    item.optimistic_value,
    item.safety_buy_price,
    ]),
  ].filter((value) => Number(value) > 0);
  const maxValue = axisMax(values);
  const allTimes = [...points, ...pricePoints].map((item) => new Date(item.date).getTime());
  const minTime = Math.min(...allTimes);
  const maxTime = Math.max(...allTimes);
  const timeRange = Math.max(maxTime - minTime, 1);
  const xAtDate = (date) => margin.left + ((new Date(date).getTime() - minTime) / timeRange) * chartWidth;
  const yAtValue = (value) => margin.top + chartHeight - (value / maxValue) * chartHeight;
  const pricePath = pricePoints
    .filter((item) => Number(item.price) > 0)
    .map((item, index) => `${index === 0 ? "M" : "L"} ${xAtDate(item.date)} ${yAtValue(item.price)}`)
    .join(" ");
  const extendedLinePathFor = (field) => {
    const usable = points.filter((item) => Number(item[field]) > 0);
    const segments = usable.map((item, index) => {
      const x = xAtDate(item.date);
      const y = yAtValue(item[field]);
      return `${index === 0 ? "M" : "L"} ${x} ${y}`;
    });
    const latest = usable[usable.length - 1];
    if (latest && Number(latest[field]) > 0) {
      segments.push(`L ${width - margin.right} ${yAtValue(latest[field])}`);
    }
    return segments.join(" ");
  };
  const negativeFcfMarkers = points
    .filter((item) => Number(item.ttm_fcf) < 0 || [
      item.conservative_value,
      item.neutral_value,
      item.optimistic_value,
      item.safety_buy_price,
    ].some((value) => Number(value) < 0))
    .map((item) => {
      const x = xAtDate(item.date);
      const y = height - margin.bottom - 12;
      return [
        `<g class="valuation-negative-marker">`,
        `<title>${item.date}: 该报告期 TTM FCF < 0</title>`,
        `<line x1="${x}" y1="${y - 10}" x2="${x}" y2="${y + 10}" />`,
        `<circle cx="${x}" cy="${y}" r="5" />`,
        `</g>`,
      ].join("");
    });
  const negativeFcfNote = negativeFcfMarkers.length
    ? svgText(width - margin.right - 180, margin.top - 14, "橙色标记：TTM FCF < 0", "valuation-negative-note")
    : "";
  const grid = [];
  const xLabels = [];
  const yearGuides = [];
  for (let i = 0; i <= 4; i += 1) {
    const y = margin.top + (chartHeight / 4) * i;
    const value = Math.round(maxValue - (maxValue / 4) * i);
    grid.push(`<line x1="${margin.left}" y1="${y}" x2="${width - margin.right}" y2="${y}" class="grid-line" />`);
    grid.push(svgText(24, y + 4, value.toLocaleString("zh-CN"), "valuation-tick"));
  }
  const startYear = new Date(minTime).getFullYear();
  const endYear = new Date(maxTime).getFullYear();
  for (let year = startYear; year <= endYear; year += 1) {
    const x = xAtDate(`${year}-01-01`);
    if (x >= margin.left && x <= width - margin.right) {
      yearGuides.push(`<line x1="${x}" y1="${margin.top}" x2="${x}" y2="${height - margin.bottom}" class="year-guide" />`);
      xLabels.push(svgText(x - 18, height - 30, String(year), "year-label"));
    }
  }
  valuationSvg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  valuationSvg.innerHTML = [
    ...grid,
    ...yearGuides,
    `<line x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}" class="axis-line" />`,
    `<path d="${extendedLinePathFor("optimistic_value")}" class="valuation-line optimistic" />`,
    `<path d="${extendedLinePathFor("neutral_value")}" class="valuation-line neutral" />`,
    `<path d="${extendedLinePathFor("conservative_value")}" class="valuation-line conservative" />`,
    `<path d="${extendedLinePathFor("safety_buy_price")}" class="valuation-line safety" />`,
    `<path d="${pricePath}" class="valuation-line price" />`,
    ...negativeFcfMarkers,
    negativeFcfNote,
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

async function loadValuationDashboard() {
  syncStockInputs();
  if (window.location.protocol === "file:") {
    showError("Open http://127.0.0.1:8765 instead of static/index.html");
    return;
  }

  setLoading(true);
  try {
    const params = new URLSearchParams({
      code: state.code,
      name: state.name,
      ...readValuationAssumptions(),
    });
    const response = await fetchWithTimeout(`/api/valuation?${params.toString()}`, 30000);
    const payload = await readJsonResponse(response);
    if (!response.ok || payload.error) {
      showError(payload.error || "Empty API response");
      return;
    }
    renderValuation(payload);
  } catch (err) {
    const message = err.name === "AbortError" ? "API timeout; confirm the local service and network are available" : err.message;
    showError(message || "API request failed");
  }
}

function loadActiveDashboard() {
  periodActions.hidden = state.view !== "balance";
  form.hidden = state.view === "multi-trend";
  if (state.view === "multi-trend") {
    loadMultiTrendDashboard();
    return;
  }
  if (state.view === "valuation") {
    showValuationDashboard();
    return;
  }
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
  workbenchButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.workbenchView === view);
  });
  loadActiveDashboard();
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  syncStockInputs();
  state.index = 0;
  loadActiveDashboard();
});

valuationForm.addEventListener("submit", (event) => {
  event.preventDefault();
  loadValuationDashboard();
});

multiStockForm.addEventListener("submit", (event) => {
  event.preventDefault();
  loadMultiTrendDashboard();
});

multiMode.addEventListener("change", () => {
  if (multiTrendPayload) {
    renderMultiTrend(multiTrendPayload);
  }
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

workbenchButtons.forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.workbenchView));
});

loadActiveDashboard();
