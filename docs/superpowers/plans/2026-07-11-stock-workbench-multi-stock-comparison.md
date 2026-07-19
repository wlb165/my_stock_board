# Stock Workbench Multi-Stock Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first stock analysis workbench layout with a sidebar and a multi-stock trend comparison chart.

**Architecture:** Keep the current single-file Python backend and no-build static frontend. Add a backend multi-stock trend endpoint that returns weekly front-adjusted price series and computed percentage changes; update the frontend shell to separate single-stock analysis from multi-stock comparison.

**Tech Stack:** Python standard library HTTP server, `unittest`, static HTML/CSS/JavaScript, SVG charts, `node --check`.

## Global Constraints

- Keep the existing no-build static frontend.
- Do not add login, saved portfolios, databases, drag-and-drop navigation, complex routing, or persistent preferences.
- Use a left sidebar with a main content area.
- Multi-stock comparison defaults to `002594, 600519, 300750`.
- Multi-stock comparison supports at most 6 stocks in the first version.
- Supported periods are `6m`, `1y`, `3y`, and `5y`; unsupported periods fall back to `1y`.
- Default display mode is percentage change, with absolute price as the alternate mode.
- Reuse the existing Eastmoney front-adjusted K-line data path.
- If one stock fails, show that stock as an error without blocking successful stocks.

---

## File Structure

- Modify `app.py`: add multi-stock parsing, period filtering, percent-change helpers, payload builder, fetch wrapper, path matcher, and request handler.
- Modify `static/index.html`: replace top tab navigation with a sidebar and add the multi-stock comparison panel.
- Modify `static/app.js`: add workbench view state, multi-stock form state, fetch/render functions, and SVG multi-line chart drawing.
- Modify `static/styles.css`: add sidebar shell layout, sidebar navigation styles, comparison controls, chart legend, and summary grid styles.
- Modify `tests/test_balance_sheet.py`: add backend unit tests for helpers, payloads, and handler output.
- Modify `tests/test_static_assets.py`: add static asset checks for sidebar navigation and multi-stock UI hooks.

---

### Task 1: Backend Multi-Stock Data Helpers

**Files:**
- Modify: `app.py`
- Test: `tests/test_balance_sheet.py`

**Interfaces:**
- Produces: `parse_stock_codes(raw_codes: str, limit: int = 6) -> tuple[list[str], list[dict]]`
- Produces: `normalize_comparison_period(period: str | None) -> str`
- Produces: `period_start_date(period: str, today: date | None = None) -> str`
- Produces: `filter_prices_from(prices: list[dict], start_date: str) -> list[dict]`
- Produces: `build_comparison_series(code: str, name: str, weekly_prices: list[dict]) -> dict`

- [ ] **Step 1: Write failing helper tests**

Add imports at the top of `tests/test_balance_sheet.py`:

```python
from datetime import date
import app
```

Add tests inside `BalanceSheetDashboardTest`:

```python

    def test_parse_stock_codes_deduplicates_and_limits(self):
        codes, errors = app.parse_stock_codes("002594, 600519, bad, 002594, 300750, 000333, 601318, 000858, 600000")
        self.assertEqual(codes, ["002594", "600519", "300750", "000333", "601318", "000858"])
        self.assertEqual(errors, [
            {"code": "bad", "message": "Invalid stock code"},
            {"code": "600000", "message": "Only the first 6 stock codes are used"},
        ])

    def test_period_helpers_fall_back_to_one_year(self):
        today = date(2026, 7, 11)
        self.assertEqual(app.normalize_comparison_period("bad"), "1y")
        self.assertEqual(app.period_start_date("6m", today), "2026-01-11")
        self.assertEqual(app.period_start_date("1y", today), "2025-07-11")
        self.assertEqual(app.period_start_date("3y", today), "2023-07-11")
        self.assertEqual(app.period_start_date("5y", today), "2021-07-11")

    def test_build_comparison_series_computes_change_and_summary(self):
        series = app.build_comparison_series(
            "002594",
            "BYD",
            [
                {"date": "2026-01-02", "price": 100.0},
                {"date": "2026-01-09", "price": 110.0},
                {"date": "2026-01-16", "price": 90.0},
            ],
        )
        self.assertEqual(series["code"], "002594")
        self.assertEqual(series["points"][1]["change_pct"], 10.0)
        self.assertEqual(series["summary"], {
            "latest_price": 90.0,
            "period_change_pct": -10.0,
            "period_high": 110.0,
            "period_low": 90.0,
            "point_count": 3,
        })
```

- [ ] **Step 2: Run helper tests and confirm they fail**

Run:

```bash
python -B -m unittest tests.test_balance_sheet.BalanceSheetDashboardTest.test_parse_stock_codes_deduplicates_and_limits tests.test_balance_sheet.BalanceSheetDashboardTest.test_period_helpers_fall_back_to_one_year tests.test_balance_sheet.BalanceSheetDashboardTest.test_build_comparison_series_computes_change_and_summary
```

Expected: fail because helper functions do not exist yet.

- [ ] **Step 3: Implement helpers in `app.py`**

Add imports and constants:

```python
from datetime import date, datetime, timedelta
import re

MAX_COMPARISON_STOCKS = 6
COMPARISON_PERIOD_DAYS = {
    "6m": 182,
    "1y": 365,
    "3y": 365 * 3,
    "5y": 365 * 5,
}
```

Add helper functions near the existing price helpers:

```python
def parse_stock_codes(raw_codes, limit=MAX_COMPARISON_STOCKS):
    seen = set()
    codes = []
    errors = []
    for raw_code in re.split(r"[,，\s]+", raw_codes or ""):
        code = raw_code.strip()
        if not code:
            continue
        if not re.fullmatch(r"\d{6}", code):
            errors.append({"code": code, "message": "Invalid stock code"})
            continue
        if code in seen:
            continue
        seen.add(code)
        if len(codes) >= limit:
            errors.append({"code": code, "message": f"Only the first {limit} stock codes are used"})
            continue
        codes.append(code)
    return codes, errors


def normalize_comparison_period(period):
    return period if period in COMPARISON_PERIOD_DAYS else "1y"


def period_start_date(period, today=None):
    current = today or date.today()
    return (current - timedelta(days=COMPARISON_PERIOD_DAYS[normalize_comparison_period(period)])).isoformat()


def filter_prices_from(prices, start_date):
    return [item for item in prices if item.get("date", "") >= start_date]


def build_comparison_series(code, name, weekly_prices):
    usable = [item for item in weekly_prices if parse_number(item.get("price")) > 0]
    if not usable:
        raise ValueError("No price data")
    first_price = parse_number(usable[0]["price"])
    points = []
    prices = []
    for item in usable:
        price = round(parse_number(item["price"]), 2)
        prices.append(price)
        points.append({
            "date": item["date"],
            "price": price,
            "change_pct": round((price - first_price) / first_price * 100, 2),
        })
    return {
        "code": code,
        "name": name or code,
        "points": points,
        "summary": {
            "latest_price": points[-1]["price"],
            "period_change_pct": points[-1]["change_pct"],
            "period_high": round(max(prices), 2),
            "period_low": round(min(prices), 2),
            "point_count": len(points),
        },
    }
```

- [ ] **Step 4: Run helper tests and confirm they pass**

Run the same command from Step 2.

- [ ] **Step 5: Commit Task 1**

```bash
git add app.py tests/test_balance_sheet.py
git commit -m "Add multi-stock comparison data helpers"
```

---

### Task 2: Backend Multi-Stock Endpoint

**Files:**
- Modify: `app.py`
- Test: `tests/test_balance_sheet.py`

**Interfaces:**
- Consumes: helpers from Task 1.
- Produces: `is_multi_stock_trend_path(path: str) -> bool`
- Produces: `fetch_multi_stock_trend(codes_raw: str, period: str, today: date | None = None) -> dict`
- Produces: `StockBoardHandler.handle_multi_stock_trend(self, query: str) -> None`

- [ ] **Step 1: Write failing endpoint tests**

Add tests inside `BalanceSheetDashboardTest`:

```python
    def test_fetch_multi_stock_trend_returns_series_and_errors(self):
        original_fetch = app.fetch_front_adjusted_daily_closes
        try:
            def fake_fetch(code, start_date, end_date):
                if code == "600519":
                    raise ValueError("network failed")
                return [
                    {"date": "2026-01-02", "close": 10.0},
                    {"date": "2026-01-09", "close": 11.0},
                ]
            app.fetch_front_adjusted_daily_closes = fake_fetch
            payload = app.fetch_multi_stock_trend("002594,600519", "1y", today=date(2026, 7, 11))
        finally:
            app.fetch_front_adjusted_daily_closes = original_fetch

        self.assertEqual(payload["period"], "1y")
        self.assertEqual(payload["mode_default"], "percent")
        self.assertEqual(payload["series"][0]["code"], "002594")
        self.assertEqual(payload["series"][0]["points"][-1]["change_pct"], 10.0)
        self.assertEqual(payload["errors"], [{"code": "600519", "message": "network failed"}])

    def test_multi_stock_trend_path(self):
        self.assertTrue(app.is_multi_stock_trend_path("/api/multi-stock-trend"))
        self.assertFalse(app.is_multi_stock_trend_path("/api/revenue-price"))
```

- [ ] **Step 2: Run endpoint tests and confirm they fail**

Run:

```bash
python -B -m unittest tests.test_balance_sheet.BalanceSheetDashboardTest.test_fetch_multi_stock_trend_returns_series_and_errors tests.test_balance_sheet.BalanceSheetDashboardTest.test_multi_stock_trend_path
```

Expected: fail because endpoint functions do not exist yet.

- [ ] **Step 3: Implement endpoint functions and handler routing**

Add near existing path helpers:

```python
def is_multi_stock_trend_path(path):
    return path == "/api/multi-stock-trend"
```

Add fetch builder near `fetch_revenue_price`:

```python
def fetch_multi_stock_trend(codes_raw, period, today=None):
    normalized_period = normalize_comparison_period(period)
    current = today or date.today()
    start_date = period_start_date(normalized_period, current)
    end_date = current.isoformat()
    codes, errors = parse_stock_codes(codes_raw)
    series = []

    if not codes:
        return {
            "period": normalized_period,
            "mode_default": "percent",
            "series": [],
            "errors": errors or [{"code": "", "message": "No stock codes"}],
        }

    for code in codes:
        try:
            daily_prices = fetch_front_adjusted_daily_closes(code, start_date, end_date)
            weekly_prices = sample_weekly_prices(filter_prices_from(daily_prices, start_date))
            series.append(build_comparison_series(code, code, weekly_prices))
        except Exception as exc:
            errors.append({"code": code, "message": str(exc) or exc.__class__.__name__})

    return {
        "period": normalized_period,
        "mode_default": "percent",
        "series": series,
        "errors": errors,
    }
```

Update `StockBoardHandler.do_GET`:

```python
        if is_multi_stock_trend_path(parsed.path):
            self.handle_multi_stock_trend(parsed.query)
            return
```

Add handler method:

```python
    def handle_multi_stock_trend(self, query):
        params = parse_qs(query)
        codes = params.get("codes", ["002594,600519,300750"])[0]
        period = params.get("period", ["1y"])[0]
        try:
            payload = fetch_multi_stock_trend(codes, period)
            status = 200 if payload.get("series") else 502
            self.write_json(payload, status=status)
        except Exception as exc:
            self.write_json({"error": str(exc) or exc.__class__.__name__}, status=502)
```

- [ ] **Step 4: Run endpoint tests and full backend tests**

Run:

```bash
python -B -m unittest tests.test_balance_sheet
```

Expected: all backend tests pass.

- [ ] **Step 5: Commit Task 2**

```bash
git add app.py tests/test_balance_sheet.py
git commit -m "Add multi-stock trend endpoint"
```

---

### Task 3: Sidebar Workbench Layout

**Files:**
- Modify: `static/index.html`
- Modify: `static/app.js`
- Modify: `static/styles.css`
- Test: `tests/test_static_assets.py`

**Interfaces:**
- Produces: sidebar buttons with `data-workbench-view`.
- Produces: panels with `data-workbench-panel`.
- Existing single-stock view values remain `balance`, `trend`, and `valuation`.

- [ ] **Step 1: Write failing static asset tests**

Add tests to `tests/test_static_assets.py`:

```python
    def test_sidebar_workbench_navigation_exists(self):
        html = INDEX.read_text(encoding="utf-8")
        script = SCRIPT.read_text(encoding="utf-8")
        styles = STYLES.read_text(encoding="utf-8")

        self.assertIn('class="sidebar"', html)
        self.assertIn('data-workbench-view="balance"', html)
        self.assertIn('data-workbench-view="trend"', html)
        self.assertIn('data-workbench-view="valuation"', html)
        self.assertIn('data-workbench-view="multi-trend"', html)
        self.assertIn('data-workbench-panel="multi-trend"', html)
        self.assertIn("workbenchButtons", script)
        self.assertIn(".app-shell", styles)
        self.assertIn(".sidebar", styles)
```

- [ ] **Step 2: Run static test and confirm it fails**

Run:

```bash
python -B -m unittest tests.test_static_assets.StaticAssetsTest.test_sidebar_workbench_navigation_exists
```

Expected: fail because sidebar elements do not exist yet.

- [ ] **Step 3: Update `static/index.html` shell**

Replace the top-level `<main class="shell">` layout with:

```html
<main class="app-shell">
  <aside class="sidebar" aria-label="功能导航">
    <div class="sidebar-brand">
      <p class="eyebrow">股票分析工作台</p>
      <h1>A 股看板</h1>
    </div>
    <nav class="sidebar-nav">
      <p class="sidebar-group">个股分析</p>
      <button class="nav-item active" type="button" data-workbench-view="balance">资产负债表</button>
      <button class="nav-item" type="button" data-workbench-view="trend">股价与营收</button>
      <button class="nav-item" type="button" data-workbench-view="valuation">估值</button>
      <p class="sidebar-group">多股对比</p>
      <button class="nav-item" type="button" data-workbench-view="multi-trend">走势对比</button>
    </nav>
  </aside>

  <section class="workspace">
    <header class="topbar single-stock-controls">
      <!-- keep existing single-stock form here -->
    </header>
    <!-- keep existing board/panels here -->
  </section>
</main>
```

Keep the existing single-stock panels and form. Remove the old top `<nav class="tabs">` once the sidebar buttons replace it.

- [ ] **Step 4: Update `static/app.js` view switching**

Replace `tabButtons` with:

```javascript
const workbenchButtons = document.querySelectorAll("[data-workbench-view]");
const workbenchPanels = document.querySelectorAll("[data-workbench-panel]");
```

Update view switching:

```javascript
function setView(view) {
  state.view = view;
  workbenchButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.workbenchView === view);
  });
  loadActiveDashboard();
}

workbenchButtons.forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.workbenchView));
});
```

Ensure existing single-stock panel visibility still happens in `setLoading`, `showError`, `renderBalance`, `renderTrend`, and `renderValuation`.

- [ ] **Step 5: Add sidebar CSS**

Add to `static/styles.css`:

```css
.app-shell {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  min-height: 100vh;
}

.sidebar {
  background: #101827;
  color: #f8fafc;
  padding: 24px 18px;
}

.sidebar-brand h1 {
  margin: 4px 0 28px;
  font-size: 24px;
}

.sidebar-group {
  margin: 22px 0 8px;
  color: #94a3b8;
  font-size: 13px;
}

.nav-item {
  width: 100%;
  display: block;
  margin: 4px 0;
  padding: 10px 12px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #cbd5e1;
  text-align: left;
  cursor: pointer;
}

.nav-item.active,
.nav-item:hover {
  background: #1f2937;
  color: #ffffff;
}

.workspace {
  min-width: 0;
  padding: 28px;
}

@media (max-width: 820px) {
  .app-shell {
    grid-template-columns: 1fr;
  }

  .sidebar {
    position: static;
  }
}
```

- [ ] **Step 6: Run static tests and JS syntax check**

Run:

```bash
python -B -m unittest tests.test_static_assets
node --check static/app.js
```

Expected: all static tests pass and JS syntax check passes.

- [ ] **Step 7: Commit Task 3**

```bash
git add static/index.html static/app.js static/styles.css tests/test_static_assets.py
git commit -m "Add stock workbench sidebar layout"
```

---

### Task 4: Frontend Multi-Stock Comparison UI and Chart

**Files:**
- Modify: `static/index.html`
- Modify: `static/app.js`
- Modify: `static/styles.css`
- Test: `tests/test_static_assets.py`

**Interfaces:**
- Consumes: `/api/multi-stock-trend?codes=...&period=...` from Task 2.
- Produces: `loadMultiTrendDashboard()`, `renderMultiTrend(payload)`, `drawMultiTrendChart(series, mode)`.

- [ ] **Step 1: Write failing static checks for multi-stock hooks**

Add to `tests/test_static_assets.py`:

```python
    def test_multi_stock_comparison_ui_hooks_exist(self):
        html = INDEX.read_text(encoding="utf-8")
        script = SCRIPT.read_text(encoding="utf-8")

        self.assertIn('id="multi-stock-form"', html)
        self.assertIn('id="multi-stock-codes"', html)
        self.assertIn('id="multi-period"', html)
        self.assertIn('id="multi-mode"', html)
        self.assertIn('id="multi-trend-svg"', html)
        self.assertIn('id="multi-summary"', html)
        self.assertIn("loadMultiTrendDashboard", script)
        self.assertIn("renderMultiTrend", script)
        self.assertIn("drawMultiTrendChart", script)
        self.assertIn("/api/multi-stock-trend", script)
```

- [ ] **Step 2: Run static check and confirm it fails**

Run:

```bash
python -B -m unittest tests.test_static_assets.StaticAssetsTest.test_multi_stock_comparison_ui_hooks_exist
```

Expected: fail because multi-stock UI does not exist yet.

- [ ] **Step 3: Add multi-stock HTML panel**

Add inside the main board:

```html
<section id="multi-trend-panel" class="multi-trend-panel" data-workbench-panel="multi-trend" hidden>
  <div class="chart-title">
    <h2>多股走势对比</h2>
    <p>同一时间范围内比较多家公司走势，默认按区间涨跌幅归一化。</p>
  </div>

  <form id="multi-stock-form" class="multi-stock-form">
    <label>股票代码
      <input id="multi-stock-codes" value="002594, 600519, 300750" aria-label="多股股票代码" />
    </label>
    <label>时间范围
      <select id="multi-period">
        <option value="6m">6 个月</option>
        <option value="1y" selected>1 年</option>
        <option value="3y">3 年</option>
        <option value="5y">5 年</option>
      </select>
    </label>
    <label>显示方式
      <select id="multi-mode">
        <option value="percent" selected>涨跌幅</option>
        <option value="price">股价</option>
      </select>
    </label>
    <button type="submit">生成对比</button>
  </form>

  <div class="trend-chart-wrap">
    <svg id="multi-trend-svg" role="img" aria-label="多股走势对比图"></svg>
  </div>
  <div id="multi-legend" class="multi-legend"></div>
  <div id="multi-summary" class="multi-summary"></div>
  <div id="multi-errors" class="multi-errors"></div>
</section>
```

- [ ] **Step 4: Add JavaScript state and loading**

Add selectors:

```javascript
const multiTrendPanel = document.querySelector("#multi-trend-panel");
const multiStockForm = document.querySelector("#multi-stock-form");
const multiStockCodes = document.querySelector("#multi-stock-codes");
const multiPeriod = document.querySelector("#multi-period");
const multiMode = document.querySelector("#multi-mode");
const multiTrendSvg = document.querySelector("#multi-trend-svg");
const multiLegend = document.querySelector("#multi-legend");
const multiSummary = document.querySelector("#multi-summary");
const multiErrors = document.querySelector("#multi-errors");
```

Update `setLoading` and `showError` to hide `multiTrendPanel`.

Add loader:

```javascript
async function loadMultiTrendDashboard() {
  if (window.location.protocol === "file:") {
    showError("Open http://127.0.0.1:8765 instead of static/index.html");
    return;
  }
  setLoading(true);
  try {
    const params = new URLSearchParams({
      codes: multiStockCodes.value.trim() || "002594,600519,300750",
      period: multiPeriod.value || "1y",
    });
    const response = await fetchWithTimeout(`/api/multi-stock-trend?${params.toString()}`, 45000);
    const payload = await readJsonResponse(response);
    if (!response.ok && !(payload.series || []).length) {
      showError((payload.errors || []).map((item) => item.message).join("; ") || payload.error || "接口无返回");
      return;
    }
    renderMultiTrend(payload);
  } catch (err) {
    const message = err.name === "AbortError" ? "接口超时，请减少股票数量或稍后重试" : err.message;
    showError(message || "接口请求失败");
  }
}
```

Update `loadActiveDashboard`:

```javascript
  if (state.view === "multi-trend") {
    periodActions.hidden = true;
    form.hidden = true;
    loadMultiTrendDashboard();
    return;
  }
  form.hidden = false;
```

- [ ] **Step 5: Add render and chart functions**

Add:

```javascript
const multiColors = ["#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2"];

function pct(value) {
  const number = Number(value || 0);
  return `${number > 0 ? "+" : ""}${number.toLocaleString("zh-CN", { maximumFractionDigits: 2 })}%`;
}

function renderMultiTrend(payload) {
  const series = payload.series || [];
  if (!series.length) {
    showError("没有可展示的多股走势数据");
    return;
  }
  drawMultiTrendChart(series, multiMode.value);
  multiLegend.innerHTML = series.map((item, index) => (
    `<span><i style="background:${multiColors[index % multiColors.length]}"></i>${item.name || item.code}</span>`
  )).join("");
  multiSummary.innerHTML = series.map((item) => (
    `<div class="multi-summary-card">
      <span>${item.name || item.code}</span>
      <strong>${pct(item.summary.period_change_pct)}</strong>
      <p>最新价 ${yuan(item.summary.latest_price)} · 高 ${yuan(item.summary.period_high)} · 低 ${yuan(item.summary.period_low)} · ${item.summary.point_count} 点</p>
    </div>`
  )).join("");
  multiErrors.innerHTML = (payload.errors || []).map((item) => (
    `<p>${item.code || "输入"}：${item.message}</p>`
  )).join("");
  loading.hidden = true;
  error.hidden = true;
  panel.hidden = true;
  trendPanel.hidden = true;
  valuationPanel.hidden = true;
  multiTrendPanel.hidden = false;
}
```

Implement `drawMultiTrendChart(series, mode)` with a single SVG:

```javascript
function drawMultiTrendChart(series, mode) {
  const width = 1120;
  const height = 520;
  const margin = { top: 42, right: 48, bottom: 64, left: 78 };
  const chartWidth = width - margin.left - margin.right;
  const chartHeight = height - margin.top - margin.bottom;
  const allPoints = series.flatMap((item) => item.points || []);
  const valueKey = mode === "price" ? "price" : "change_pct";
  const values = allPoints.map((item) => Number(item[valueKey])).filter(Number.isFinite);
  const minValue = Math.min(...values, 0);
  const maxValue = Math.max(...values, 1);
  const valueRange = Math.max(maxValue - minValue, 1);
  const times = allPoints.map((item) => new Date(item.date).getTime());
  const minTime = Math.min(...times);
  const maxTime = Math.max(...times);
  const timeRange = Math.max(maxTime - minTime, 1);
  const xAtDate = (date) => margin.left + ((new Date(date).getTime() - minTime) / timeRange) * chartWidth;
  const yAtValue = (value) => margin.top + chartHeight - ((value - minValue) / valueRange) * chartHeight;
  const grid = [];
  for (let i = 0; i <= 4; i += 1) {
    const y = margin.top + (chartHeight / 4) * i;
    const value = maxValue - (valueRange / 4) * i;
    const label = mode === "price" ? yuan(value) : pct(value);
    grid.push(`<line x1="${margin.left}" y1="${y}" x2="${width - margin.right}" y2="${y}" class="grid-line" />`);
    grid.push(svgText(18, y + 4, label, "valuation-tick"));
  }
  const startYear = new Date(minTime).getFullYear();
  const endYear = new Date(maxTime).getFullYear();
  const xLabels = [];
  for (let year = startYear; year <= endYear; year += 1) {
    const x = xAtDate(`${year}-01-01`);
    if (x >= margin.left && x <= width - margin.right) {
      xLabels.push(svgText(x - 18, height - 30, String(year), "year-label"));
    }
  }
  const paths = series.map((item, index) => {
    const path = (item.points || []).map((point, pointIndex) => (
      `${pointIndex === 0 ? "M" : "L"} ${xAtDate(point.date)} ${yAtValue(Number(point[valueKey]))}`
    )).join(" ");
    return `<path d="${path}" class="multi-trend-line" stroke="${multiColors[index % multiColors.length]}" />`;
  });
  multiTrendSvg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  multiTrendSvg.innerHTML = [
    ...grid,
    `<line x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}" class="axis-line" />`,
    ...paths,
    ...xLabels,
  ].join("");
}
```

Add form events:

```javascript
multiStockForm.addEventListener("submit", (event) => {
  event.preventDefault();
  loadMultiTrendDashboard();
});

multiMode.addEventListener("change", () => {
  if (state.view === "multi-trend") {
    loadMultiTrendDashboard();
  }
});
```

- [ ] **Step 6: Add CSS for multi-stock UI**

Add:

```css
.multi-stock-form {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) 140px 140px auto;
  gap: 12px;
  align-items: end;
  margin-bottom: 18px;
}

.multi-stock-form label {
  display: grid;
  gap: 6px;
  color: #475569;
  font-size: 13px;
}

.multi-trend-line {
  fill: none;
  stroke-width: 2.5;
}

.multi-legend,
.multi-summary {
  display: grid;
  gap: 10px;
}

.multi-legend {
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  margin-top: 12px;
}

.multi-legend i {
  display: inline-block;
  width: 10px;
  height: 10px;
  margin-right: 8px;
  border-radius: 50%;
}

.multi-summary {
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  margin-top: 16px;
}

.multi-summary-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px;
  background: #ffffff;
}

.multi-summary-card strong {
  display: block;
  margin: 6px 0;
  font-size: 24px;
}

.multi-errors {
  margin-top: 12px;
  color: #b91c1c;
}
```

- [ ] **Step 7: Run static tests and JS syntax check**

Run:

```bash
python -B -m unittest tests.test_static_assets
node --check static/app.js
```

Expected: all static tests pass and JS syntax check passes.

- [ ] **Step 8: Commit Task 4**

```bash
git add static/index.html static/app.js static/styles.css tests/test_static_assets.py
git commit -m "Add multi-stock comparison chart UI"
```

---

### Task 5: Full Verification and Documentation

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes all prior tasks.
- Produces updated usage notes for the stock workbench and multi-stock comparison.

- [ ] **Step 1: Update README feature summary**

Add a concise section near the existing feature list:

```markdown
## Stock Analysis Workbench

- Single-stock analysis keeps the existing balance sheet, revenue and price, and valuation views.
- Multi-stock comparison shows up to 6 stocks in one chart.
- The comparison chart defaults to percentage change and can switch to absolute price.
- Supported comparison ranges: 6 months, 1 year, 3 years, 5 years.
```

- [ ] **Step 2: Run full verification**

Run:

```bash
python -B -m unittest tests.test_balance_sheet tests.test_static_assets
node --check static/app.js
```

Expected: all tests pass and JavaScript syntax check passes.

- [ ] **Step 3: Manually smoke test local app**

Run:

```bash
python app.py
```

Open:

```text
http://127.0.0.1:8765
```

Check:

- Sidebar appears.
- Single-stock balance sheet still loads.
- Single-stock revenue and price still loads.
- Single-stock valuation form still opens and submits.
- Multi-stock comparison loads default stocks.
- Multi-stock comparison can switch period and mode.
- Entering more than 6 codes returns a visible limit message.

- [ ] **Step 4: Commit Task 5**

```bash
git add README.md
git commit -m "Document stock workbench comparison feature"
```

- [ ] **Step 5: Final status check**

Run:

```bash
git status --short --branch
git log --oneline -5
```

Expected: branch contains the design commit plus task commits; only unrelated pre-existing untracked files remain.
