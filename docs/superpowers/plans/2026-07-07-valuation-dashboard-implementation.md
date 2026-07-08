# Valuation Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a third `估值` dashboard where users set DCF assumptions, click `生成估值`, and see a dynamic DCF valuation band overlaid with stock price plus PE/PB/PS helper metrics.

**Architecture:** Keep the current local `http.server` + static frontend architecture. Add valuation calculation helpers in `app.py`, expose `/api/valuation`, then wire a new static tab/panel that renders controls, summary metrics, and an SVG chart without adding dependencies.

**Tech Stack:** Python standard library HTTP server and unittest, browser `fetch`, vanilla JavaScript, SVG, existing CSS.

## Global Constraints

- V1 uses TTM free cash flow as the default DCF base.
- V1 aligns by report period date, not disclosure date.
- V1 does not add automatic WACC, peer-company comparison, analyst forecasts, terminal multiple, or trading recommendations.
- Historical DCF per-share values must use report-period total shares or the closest available share count on or before that period.
- Daily prices continue to use Eastmoney front-adjusted K-line data.
- The main chart uses the existing SVG pattern; do not add a charting library.
- Keep changes surgical and match existing file style.

---

## File Structure

- Modify `app.py`: add valuation field helpers, TTM FCF calculation, DCF calculation, route detection, `/api/valuation` handler, and data fetch orchestration.
- Modify `tests/test_balance_sheet.py`: add focused unit tests for DCF math, TTM FCF, period-specific shares, route wiring, invalid assumptions, and payload shape.
- Modify `static/index.html`: add the `估值` tab and valuation panel markup.
- Modify `static/app.js`: add valuation state, control reading, API call, summary rendering, SVG chart renderer, and tab routing.
- Modify `static/styles.css`: style valuation controls, summary, chart, and helper metrics using existing visual language.
- Modify `tests/test_static_assets.py`: assert valuation tab, controls, endpoint call, and renderer are wired.

---

### Task 1: Backend Valuation Math

**Files:**
- Modify: `app.py`
- Test: `tests/test_balance_sheet.py`

**Interfaces:**
- Consumes: existing `parse_number`, `to_yi`, `field_value`, and `closest_close_on_or_before`.
- Produces:
  - `cash_flow_value(items: dict, names: list[str]) -> float`
  - `quarterly_from_cumulative(reports: list[dict], value_fn: Callable[[dict], float]) -> list[dict]`
  - `build_ttm_free_cash_flow_points(cash_reports: list[dict]) -> list[dict]`
  - `dcf_value(base_fcf: float, growth_rate: float, discount_rate: float, perpetual_growth_rate: float, forecast_years: int) -> float`
  - `valuation_zone(price: float, conservative: float, neutral: float, optimistic: float) -> str`

- [ ] **Step 1: Write failing tests for DCF and TTM FCF**

Add these imports in `tests/test_balance_sheet.py`:

```python
from app import (
    build_ttm_free_cash_flow_points,
    dcf_value,
    valuation_zone,
)
```

Add these tests:

```python
    def test_builds_ttm_free_cash_flow_from_cumulative_cash_flow_reports(self):
        reports = [
            {
                "report_date": "2024-03-31",
                "items": {
                    "经营活动产生的现金流量净额": 1000000000,
                    "购建固定资产、无形资产和其他长期资产支付的现金": 200000000,
                },
            },
            {
                "report_date": "2024-06-30",
                "items": {
                    "经营活动产生的现金流量净额": 2500000000,
                    "购建固定资产、无形资产和其他长期资产支付的现金": 700000000,
                },
            },
            {
                "report_date": "2024-09-30",
                "items": {
                    "经营活动产生的现金流量净额": 4300000000,
                    "购建固定资产、无形资产和其他长期资产支付的现金": 1200000000,
                },
            },
            {
                "report_date": "2024-12-31",
                "items": {
                    "经营活动产生的现金流量净额": 7000000000,
                    "购建固定资产、无形资产和其他长期资产支付的现金": 2000000000,
                },
            },
            {
                "report_date": "2025-03-31",
                "items": {
                    "经营活动产生的现金流量净额": 1300000000,
                    "购建固定资产、无形资产和其他长期资产支付的现金": 300000000,
                },
            },
        ]

        points = build_ttm_free_cash_flow_points(reports)

        self.assertEqual(points[0], {"date": "2024-12-31", "ttm_fcf": 5000000000})
        self.assertEqual(points[1], {"date": "2025-03-31", "ttm_fcf": 5200000000})

    def test_dcf_value_uses_growth_discount_and_terminal_value(self):
        value = dcf_value(
            base_fcf=100000000,
            growth_rate=0.10,
            discount_rate=0.10,
            perpetual_growth_rate=0.025,
            forecast_years=5,
        )

        self.assertEqual(round(value, 0), 1866666667)

    def test_dcf_value_rejects_terminal_growth_at_or_above_discount_rate(self):
        with self.assertRaisesRegex(ValueError, "discount_rate"):
            dcf_value(100000000, 0.10, 0.025, 0.025, 5)

    def test_valuation_zone_describes_price_position(self):
        self.assertEqual(valuation_zone(50, 70, 100, 130), "低于保守估值")
        self.assertEqual(valuation_zone(80, 70, 100, 130), "保守区间")
        self.assertEqual(valuation_zone(110, 70, 100, 130), "合理区间")
        self.assertEqual(valuation_zone(150, 70, 100, 130), "高于乐观估值")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
& "C:\Users\10122\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -B -m unittest tests.test_balance_sheet
```

Expected: failure because the imported valuation helpers do not exist.

- [ ] **Step 3: Implement minimal valuation helpers**

Add near the existing revenue helpers in `app.py`:

```python
OPERATING_CASH_FLOW_FIELDS = ["经营活动产生的现金流量净额", "经营活动现金流量净额"]
CAPEX_FIELDS = ["购建固定资产、无形资产和其他长期资产支付的现金"]


def cash_flow_value(items, names):
    return field_value(items, ("first", names))


def report_year(report_date):
    return report_date[:4]


def quarterly_from_cumulative(reports, value_fn):
    ordered = sorted(reports, key=lambda item: item["report_date"])
    previous_by_year = {}
    quarters = []
    for report in ordered:
        date = report["report_date"]
        year = report_year(date)
        cumulative = value_fn(report["items"])
        previous = previous_by_year.get(year, 0.0)
        quarter_value = cumulative - previous
        previous_by_year[year] = cumulative
        quarters.append({"date": date, "value": quarter_value})
    return quarters


def build_ttm_free_cash_flow_points(cash_reports):
    operating_quarters = quarterly_from_cumulative(
        cash_reports,
        lambda items: cash_flow_value(items, OPERATING_CASH_FLOW_FIELDS),
    )
    capex_quarters = quarterly_from_cumulative(
        cash_reports,
        lambda items: cash_flow_value(items, CAPEX_FIELDS),
    )
    quarterly_fcf = []
    for operating, capex in zip(operating_quarters, capex_quarters):
        quarterly_fcf.append({"date": operating["date"], "value": operating["value"] - capex["value"]})

    points = []
    for index in range(3, len(quarterly_fcf)):
        window = quarterly_fcf[index - 3 : index + 1]
        points.append({"date": quarterly_fcf[index]["date"], "ttm_fcf": sum(item["value"] for item in window)})
    return points


def dcf_value(base_fcf, growth_rate, discount_rate, perpetual_growth_rate, forecast_years):
    if discount_rate <= perpetual_growth_rate:
        raise ValueError("discount_rate must be greater than perpetual_growth_rate")
    value = 0.0
    final_fcf = base_fcf
    for year in range(1, forecast_years + 1):
        final_fcf = base_fcf * ((1 + growth_rate) ** year)
        value += final_fcf / ((1 + discount_rate) ** year)
    terminal_value = final_fcf * (1 + perpetual_growth_rate) / (discount_rate - perpetual_growth_rate)
    value += terminal_value / ((1 + discount_rate) ** forecast_years)
    return value


def valuation_zone(price, conservative, neutral, optimistic):
    if price < conservative:
        return "低于保守估值"
    if price < neutral:
        return "保守区间"
    if price <= optimistic:
        return "合理区间"
    return "高于乐观估值"
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
& "C:\Users\10122\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -B -m unittest tests.test_balance_sheet
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add app.py tests/test_balance_sheet.py
git commit -m "Add valuation math helpers"
```

---

### Task 2: Backend Valuation Payload and Route

**Files:**
- Modify: `app.py`
- Test: `tests/test_balance_sheet.py`

**Interfaces:**
- Consumes Task 1 helpers.
- Produces:
  - `is_valuation_path(path: str) -> bool`
  - `parse_valuation_assumptions(params: dict) -> dict`
  - `build_valuation_payload(code: str, name: str, income_reports: list[dict], balance_reports: list[dict], cash_reports: list[dict], prices: list[dict], share_points: list[dict], assumptions: dict) -> dict`
  - `fetch_cash_flow_reports(code: str, limit: int = 32) -> list[dict]`
  - `fetch_valuation(code: str, name: str, assumptions: dict, limit: int = 32, today: str | None = None) -> dict`

- [ ] **Step 1: Write failing backend payload tests**

Add these imports:

```python
from app import (
    build_valuation_payload,
    is_valuation_path,
    parse_valuation_assumptions,
)
```

Add these tests:

```python
    def test_valuation_route_is_wired(self):
        self.assertTrue(is_valuation_path("/api/valuation"))
        self.assertFalse(is_valuation_path("/api/revenue-price"))

    def test_parse_valuation_assumptions_validates_terminal_growth(self):
        params = {
            "forecast_years": ["5"],
            "growth_conservative": ["0.05"],
            "growth_neutral": ["0.10"],
            "growth_optimistic": ["0.15"],
            "discount_rate": ["0.10"],
            "perpetual_growth_rate": ["0.025"],
            "safety_margin": ["0.25"],
        }

        assumptions = parse_valuation_assumptions(params)

        self.assertEqual(assumptions["forecast_years"], 5)
        self.assertEqual(assumptions["cash_flow_basis"], "ttm_fcf")
        self.assertEqual(assumptions["alignment"], "report_period")

    def test_parse_valuation_assumptions_rejects_invalid_discount_rate(self):
        params = {"discount_rate": ["0.02"], "perpetual_growth_rate": ["0.03"]}

        with self.assertRaisesRegex(ValueError, "discount_rate"):
            parse_valuation_assumptions(params)

    def test_build_valuation_payload_uses_period_specific_total_shares(self):
        assumptions = {
            "cash_flow_basis": "ttm_fcf",
            "forecast_years": 5,
            "growth_conservative": 0.0,
            "growth_neutral": 0.0,
            "growth_optimistic": 0.0,
            "discount_rate": 0.10,
            "perpetual_growth_rate": 0.02,
            "safety_margin": 0.25,
            "alignment": "report_period",
        }
        cash_reports = [
            {"report_date": "2024-03-31", "items": {"经营活动产生的现金流量净额": 100000000, "购建固定资产、无形资产和其他长期资产支付的现金": 0}},
            {"report_date": "2024-06-30", "items": {"经营活动产生的现金流量净额": 200000000, "购建固定资产、无形资产和其他长期资产支付的现金": 0}},
            {"report_date": "2024-09-30", "items": {"经营活动产生的现金流量净额": 300000000, "购建固定资产、无形资产和其他长期资产支付的现金": 0}},
            {"report_date": "2024-12-31", "items": {"经营活动产生的现金流量净额": 400000000, "购建固定资产、无形资产和其他长期资产支付的现金": 0}},
            {"report_date": "2025-03-31", "items": {"经营活动产生的现金流量净额": 150000000, "购建固定资产、无形资产和其他长期资产支付的现金": 0}},
        ]
        income_reports = [
            {"report_date": "2024-12-31", "items": {"营业总收入": 800000000, "净利润": 100000000}},
            {"report_date": "2025-03-31", "items": {"营业总收入": 220000000, "净利润": 25000000}},
        ]
        balance_reports = [
            {"report_date": "2024-12-31", "items": {"所有者权益合计": 1000000000}},
            {"report_date": "2025-03-31", "items": {"所有者权益合计": 1100000000}},
        ]
        share_points = [
            {"date": "2024-12-31", "total_shares": 100000000},
            {"date": "2025-03-31", "total_shares": 200000000},
        ]
        prices = [
            {"date": "2024-12-31", "close": 12.0},
            {"date": "2025-03-31", "close": 10.0},
        ]

        payload = build_valuation_payload(
            "002594",
            "比亚迪",
            income_reports,
            balance_reports,
            cash_reports,
            prices,
            share_points,
            assumptions,
        )

        self.assertEqual(payload["points"][0]["total_shares"], 100000000)
        self.assertEqual(payload["points"][1]["total_shares"], 200000000)
        self.assertGreater(payload["points"][0]["neutral_value"], payload["points"][1]["neutral_value"])
        self.assertIn("pe_ttm", payload["summary"])
        self.assertIn("pb", payload["summary"])
        self.assertIn("ps_ttm", payload["summary"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
& "C:\Users\10122\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -B -m unittest tests.test_balance_sheet
```

Expected: failure because route and payload helpers do not exist.

- [ ] **Step 3: Implement payload helpers and route handler**

Add helpers in `app.py`:

```python
NET_PROFIT_FIELDS = ["净利润", "归属于母公司所有者的净利润"]
EQUITY_FIELDS = ["所有者权益合计", "归属于母公司所有者权益合计"]


def is_valuation_path(path):
    return path == "/api/valuation"


def parse_rate(params, key, default):
    return float(params.get(key, [str(default)])[0] or default)


def parse_valuation_assumptions(params):
    assumptions = {
        "cash_flow_basis": "ttm_fcf",
        "forecast_years": int(params.get("forecast_years", ["5"])[0] or 5),
        "growth_conservative": parse_rate(params, "growth_conservative", 0.05),
        "growth_neutral": parse_rate(params, "growth_neutral", 0.10),
        "growth_optimistic": parse_rate(params, "growth_optimistic", 0.15),
        "discount_rate": parse_rate(params, "discount_rate", 0.10),
        "perpetual_growth_rate": parse_rate(params, "perpetual_growth_rate", 0.025),
        "safety_margin": parse_rate(params, "safety_margin", 0.25),
        "alignment": "report_period",
    }
    dcf_value(1.0, assumptions["growth_neutral"], assumptions["discount_rate"], assumptions["perpetual_growth_rate"], assumptions["forecast_years"])
    return assumptions


def closest_share_on_or_before(share_points, report_date):
    ordered = sorted(share_points, key=lambda item: item["date"])
    dates = [item["date"] for item in ordered]
    index = bisect_right(dates, report_date) - 1
    if index < 0:
        return None
    return ordered[index]


def ttm_value_by_date(reports, value_fn):
    quarters = quarterly_from_cumulative(reports, value_fn)
    values = {}
    for index in range(3, len(quarters)):
        window = quarters[index - 3 : index + 1]
        values[quarters[index]["date"]] = sum(item["value"] for item in window)
    return values


def metric_ratio(numerator, denominator):
    return round(numerator / denominator, 2) if denominator else None
```

Then implement `build_valuation_payload` using the Task 1 helpers, and add:

```python
def fetch_cash_flow_reports(code, limit=32):
    return fetch_sina_financial_report(code, "llb", limit)
```

Wire `StockBoardHandler.do_GET`:

```python
        if is_valuation_path(parsed.path):
            self.handle_valuation(parsed.query)
            return
```

Add handler:

```python
    def handle_valuation(self, query):
        params = parse_qs(query)
        code = params.get("code", ["002594"])[0].strip()
        name = params.get("name", ["比亚迪"])[0].strip()
        try:
            assumptions = parse_valuation_assumptions(params)
            payload = fetch_valuation(code, name, assumptions)
            self.write_json(payload)
        except Exception as exc:
            self.write_json({"error": str(exc) or exc.__class__.__name__}, status=502)
```

For `fetch_valuation`, fetch income, balance, cash reports, prices, and share points. In V1, derive share points from market cap divided by close only if period-specific share count is unavailable from a stable source; set `share_count_source` accordingly. Do not silently use the latest share count for older periods.

- [ ] **Step 4: Run backend tests**

Run:

```bash
& "C:\Users\10122\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -B -m unittest tests.test_balance_sheet
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add app.py tests/test_balance_sheet.py
git commit -m "Add valuation API payload"
```

---

### Task 3: Valuation Tab Markup and Static Wiring

**Files:**
- Modify: `static/index.html`
- Modify: `tests/test_static_assets.py`

**Interfaces:**
- Consumes `/api/valuation` from Task 2.
- Produces DOM IDs used by Task 4:
  - `valuation-panel`
  - `valuation-form`
  - `forecast-years`
  - `growth-conservative`
  - `growth-neutral`
  - `growth-optimistic`
  - `discount-rate`
  - `perpetual-growth-rate`
  - `safety-margin`
  - `valuation-svg`

- [ ] **Step 1: Write failing static asset test**

Add to `tests/test_static_assets.py`:

```python
    def test_valuation_view_is_wired(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn('data-view="valuation"', html)
        self.assertIn('id="valuation-panel"', html)
        self.assertIn('id="valuation-form"', html)
        self.assertIn('id="valuation-svg"', html)
        self.assertIn("生成估值", html)
        self.assertIn("/api/valuation", script)
        self.assertIn("loadValuationDashboard", script)
        self.assertIn("drawValuationChart", script)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
& "C:\Users\10122\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -B -m unittest tests.test_static_assets
```

Expected: failure because the valuation tab and script hooks do not exist.

- [ ] **Step 3: Add valuation HTML**

In `static/index.html`, add a new tab after the trend tab:

```html
<button class="tab" type="button" data-view="valuation">估值</button>
```

Add a new section inside `.board` after `trend-panel`:

```html
<section id="valuation-panel" class="valuation-panel" hidden>
  <form id="valuation-form" class="valuation-form">
    <label>预测年限
      <select id="forecast-years">
        <option value="3">3 年</option>
        <option value="5" selected>5 年</option>
        <option value="10">10 年</option>
      </select>
    </label>
    <label>保守增长率
      <input id="growth-conservative" type="number" value="5" step="0.5" />
    </label>
    <label>中性增长率
      <input id="growth-neutral" type="number" value="10" step="0.5" />
    </label>
    <label>乐观增长率
      <input id="growth-optimistic" type="number" value="15" step="0.5" />
    </label>
    <label>折现率
      <input id="discount-rate" type="number" value="10" step="0.5" />
    </label>
    <label>永续增长率
      <input id="perpetual-growth-rate" type="number" value="2.5" step="0.5" />
    </label>
    <label>安全边际
      <input id="safety-margin" type="number" value="25" step="1" />
    </label>
    <button type="submit">生成估值</button>
  </form>

  <div class="summary-grid valuation-summary">
    <div><span>当前股价</span><strong id="valuation-current-price">--</strong></div>
    <div><span>中性 DCF</span><strong id="valuation-neutral-value">--</strong></div>
    <div><span>折价/溢价</span><strong id="valuation-discount">--</strong></div>
    <div><span>安全买入价</span><strong id="valuation-safety-price">--</strong></div>
  </div>

  <div class="valuation-chart-wrap">
    <svg id="valuation-svg" role="img" aria-label="DCF 估值带与股价走势"></svg>
  </div>

  <div class="summary-grid valuation-ratios">
    <div><span>当前市值</span><strong id="valuation-market-cap">--</strong></div>
    <div><span>PE</span><strong id="valuation-pe">--</strong></div>
    <div><span>PB</span><strong id="valuation-pb">--</strong></div>
    <div><span>PS</span><strong id="valuation-ps">--</strong></div>
  </div>
</section>
```

- [ ] **Step 4: Run static test**

Run:

```bash
& "C:\Users\10122\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -B -m unittest tests.test_static_assets
```

Expected: still fails until Task 4 adds JavaScript hooks.

- [ ] **Step 5: Commit after Task 4 instead of here**

Do not commit yet; the static test intentionally depends on Task 4 JavaScript wiring.

---

### Task 4: Valuation Frontend Logic and Chart

**Files:**
- Modify: `static/app.js`
- Modify: `static/styles.css`
- Modify: `tests/test_static_assets.py`

**Interfaces:**
- Consumes DOM IDs from Task 3 and `/api/valuation` from Task 2.
- Produces:
  - `readValuationAssumptions() -> URLSearchParams-compatible object`
  - `loadValuationDashboard() -> Promise<void>`
  - `renderValuation(payload: object) -> void`
  - `drawValuationChart(points: object[]) -> void`

- [ ] **Step 1: Add JavaScript wiring**

In `static/app.js`, add selectors:

```javascript
const valuationPanel = document.querySelector("#valuation-panel");
const valuationForm = document.querySelector("#valuation-form");
const valuationSvg = document.querySelector("#valuation-svg");
```

Update `setLoading` to hide `valuationPanel`:

```javascript
  valuationPanel.hidden = true;
```

Add:

```javascript
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
  drawValuationChart(payload.points || []);
  loading.hidden = true;
  error.hidden = true;
  valuationPanel.hidden = false;
}

async function loadValuationDashboard() {
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
      ...readValuationAssumptions(),
    });
    const response = await fetchWithTimeout(`/api/valuation?${params.toString()}`, 30000);
    const payload = await readJsonResponse(response);
    if (!response.ok || payload.error) {
      showError(payload.error || "接口无返回");
      return;
    }
    renderValuation(payload);
  } catch (err) {
    const message = err.name === "AbortError" ? "接口超时，请确认本地服务和网络可用" : err.message;
    showError(message || "接口请求失败");
  }
}
```

Add a simple SVG renderer:

```javascript
function drawValuationChart(points) {
  if (!points.length) {
    valuationSvg.innerHTML = "";
    return;
  }
  const width = 1120;
  const height = 520;
  const margin = { top: 42, right: 52, bottom: 64, left: 78 };
  const chartWidth = width - margin.left - margin.right;
  const chartHeight = height - margin.top - margin.bottom;
  const values = points.flatMap((item) => [
    item.price,
    item.conservative_value,
    item.neutral_value,
    item.optimistic_value,
    item.safety_buy_price,
  ]).filter((value) => Number(value) > 0);
  const maxValue = axisMax(values);
  const minTime = Math.min(...points.map((item) => new Date(item.date).getTime()));
  const maxTime = Math.max(...points.map((item) => new Date(item.date).getTime()));
  const timeRange = Math.max(maxTime - minTime, 1);
  const xAtDate = (date) => margin.left + ((new Date(date).getTime() - minTime) / timeRange) * chartWidth;
  const yAtValue = (value) => margin.top + chartHeight - (value / maxValue) * chartHeight;
  const pathFor = (field) => points
    .filter((item) => Number(item[field]) > 0)
    .map((item, index) => `${index === 0 ? "M" : "L"} ${xAtDate(item.date)} ${yAtValue(item[field])}`)
    .join(" ");
  const grid = [];
  for (let i = 0; i <= 4; i += 1) {
    const y = margin.top + (chartHeight / 4) * i;
    const value = Math.round(maxValue - (maxValue / 4) * i);
    grid.push(`<line x1="${margin.left}" y1="${y}" x2="${width - margin.right}" y2="${y}" class="grid-line" />`);
    grid.push(svgText(24, y + 4, value.toLocaleString("zh-CN"), "valuation-tick"));
  }
  valuationSvg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  valuationSvg.innerHTML = [
    ...grid,
    `<line x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}" class="axis-line" />`,
    `<path d="${pathFor("optimistic_value")}" class="valuation-line optimistic" />`,
    `<path d="${pathFor("neutral_value")}" class="valuation-line neutral" />`,
    `<path d="${pathFor("conservative_value")}" class="valuation-line conservative" />`,
    `<path d="${pathFor("safety_buy_price")}" class="valuation-line safety" />`,
    `<path d="${pathFor("price")}" class="valuation-line price" />`,
  ].join("");
}
```

Update `loadActiveDashboard`:

```javascript
  if (state.view === "valuation") {
    loadValuationDashboard();
    return;
  }
```

Update `setView` to allow `valuation`:

```javascript
  if (view === "basic") return;
```

Keep this line unchanged, because it already allows any non-basic view:

```javascript
state.view = view;
```

Add form listener:

```javascript
valuationForm.addEventListener("submit", (event) => {
  event.preventDefault();
  loadValuationDashboard();
});
```

- [ ] **Step 2: Add CSS**

Add to `static/styles.css`:

```css
.valuation-form {
  display: grid;
  grid-template-columns: repeat(4, minmax(120px, 1fr));
  gap: 12px;
  margin-bottom: 22px;
}

.valuation-form label {
  display: grid;
  gap: 6px;
  color: var(--muted);
  font-size: 13px;
}

.valuation-form input,
.valuation-form select,
.valuation-form button {
  height: 38px;
  border: 1px solid #d6d6d6;
  border-radius: 4px;
  padding: 0 10px;
  font-size: 14px;
}

.valuation-form button {
  cursor: pointer;
  color: #fff;
  border-color: var(--accent);
  background: var(--accent);
}

.valuation-chart-wrap {
  width: 100%;
  min-height: 520px;
  overflow-x: auto;
  border: 1px solid #eef1f4;
  border-radius: 6px;
  background: #fff;
}

#valuation-svg {
  display: block;
  width: 100%;
  min-width: 1120px;
  height: 520px;
}

.valuation-line {
  fill: none;
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.valuation-line.price {
  stroke: var(--red);
  stroke-width: 3.5;
}

.valuation-line.optimistic {
  stroke: #65a30d;
}

.valuation-line.neutral {
  stroke: var(--accent);
}

.valuation-line.conservative {
  stroke: #2563eb;
}

.valuation-line.safety {
  stroke: #8b5cf6;
  stroke-dasharray: 7 7;
}

.valuation-tick {
  fill: #667085;
}

@media (max-width: 820px) {
  .valuation-form {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
```

- [ ] **Step 3: Run static tests and JS syntax check**

Run:

```bash
& "C:\Users\10122\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -B -m unittest tests.test_static_assets
& "C:\Users\10122\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" --check static/app.js
```

Expected: both pass.

- [ ] **Step 4: Commit Tasks 3 and 4 together**

Run:

```bash
git add static/index.html static/app.js static/styles.css tests/test_static_assets.py
git commit -m "Add valuation dashboard UI"
```

---

### Task 5: End-to-End Verification and Cleanup

**Files:**
- Modify only if verification exposes defects: `app.py`, `static/app.js`, `static/index.html`, `static/styles.css`, tests.

**Interfaces:**
- Consumes all previous tasks.
- Produces a verified working valuation dashboard.

- [ ] **Step 1: Run full automated checks**

Run:

```bash
& "C:\Users\10122\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -B -m unittest tests.test_balance_sheet tests.test_static_assets
& "C:\Users\10122\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" --check static/app.js
```

Expected: all tests pass and JS syntax check exits with code 0.

- [ ] **Step 2: Start local server**

Run:

```bash
& "C:\Users\10122\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" app.py
```

Expected: server starts at `http://127.0.0.1:8765`.

- [ ] **Step 3: Manually verify the app**

Open:

```text
http://127.0.0.1:8765/static/index.html
```

Verify:

- `资产负债表` tab still loads.
- `股价与营收` tab still loads.
- `估值` tab shows parameter controls.
- Clicking `生成估值` calls `/api/valuation`.
- The valuation chart renders price and DCF lines when data is available.
- If data is missing, the page shows a readable error instead of a blank panel.

- [ ] **Step 4: Stop the server**

Use `Ctrl+C` in the terminal running `& "C:\Users\10122\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" app.py`.

- [ ] **Step 5: Check final diff and status**

Run:

```bash
git status --short
git diff --stat
```

Expected: no uncommitted changes unless Step 3 found a defect and you fixed it.

- [ ] **Step 6: Commit verification fixes if needed**

If verification required fixes, run:

```bash
git add app.py static/index.html static/app.js static/styles.css tests/test_balance_sheet.py tests/test_static_assets.py
git commit -m "Fix valuation dashboard verification issues"
```

If no fixes were needed, do not create an empty commit.
