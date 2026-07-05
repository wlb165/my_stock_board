const state = {
  code: "002594",
  name: "比亚迪",
  index: 0,
  period: null,
};

const form = document.querySelector("#stock-form");
const codeInput = document.querySelector("#stock-code");
const nameInput = document.querySelector("#stock-name");
const loading = document.querySelector("#loading");
const error = document.querySelector("#error");
const panel = document.querySelector("#chart-panel");
const bars = document.querySelector("#bars");
const yAxis = document.querySelector("#y-axis");
const currentButton = document.querySelector("#current-period");
const prevButton = document.querySelector("#prev-period");
const nextButton = document.querySelector("#next-period");

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
  panel.hidden = isLoading;
  error.hidden = true;
}

function showError(message) {
  loading.hidden = true;
  panel.hidden = true;
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

function render(payload) {
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

async function fetchWithTimeout(url, timeoutMs = 20000) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { signal: controller.signal });
  } finally {
    window.clearTimeout(timer);
  }
}

async function loadDashboard() {
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
    render(payload);
  } catch (err) {
    const message = err.name === "AbortError" ? "接口超时，请确认本地服务和网络可用" : err.message;
    showError(message || "接口请求失败");
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  state.code = codeInput.value.trim() || "002594";
  state.name = nameInput.value.trim() || state.code;
  state.index = 0;
  loadDashboard();
});

currentButton.addEventListener("click", () => {
  state.index = 0;
  loadDashboard();
});

prevButton.addEventListener("click", () => {
  if (!state.period?.has_previous) return;
  state.index += 1;
  loadDashboard();
});

nextButton.addEventListener("click", () => {
  if (!state.period?.has_next) return;
  state.index -= 1;
  loadDashboard();
});

loadDashboard();
