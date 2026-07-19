# Valuation Chart Latest Price Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the valuation chart use latest weekly stock price data while keeping DCF valuation report-period based.

**Architecture:** Extend the existing `/api/valuation` payload with `price_points`. Keep backend calculations in `app.py` and frontend SVG rendering in `static/app.js`. No new dependencies.

**Tech Stack:** Python stdlib HTTP server, vanilla JavaScript, SVG, `unittest`, `node --check`.

## Global Constraints

- Preserve existing API fields where possible.
- Keep DCF points tied to report periods.
- Use weekly sampled stock prices through the latest complete trading day.
- Latest summary compares latest stock price against latest report-period DCF.
- DCF lines extend horizontally after the latest report period.

---

### Task 1: Backend Payload

**Files:**
- Modify: `app.py`
- Test: `tests/test_balance_sheet.py`

**Interfaces:**
- Consumes: `build_valuation_payload(...)`, `sample_weekly_prices(prices)`
- Produces: payload field `price_points: list[{date: str, price: float}]`

- [ ] Add a failing unit test asserting `price_points` includes weekly prices after the latest report date and summary current price uses the latest price point.
- [ ] Implement `price_points` in `build_valuation_payload`.
- [ ] Update summary market cap and discount to use latest price with latest valuation point.
- [ ] Run `python -B -m unittest tests.test_balance_sheet`.

### Task 2: Frontend Chart

**Files:**
- Modify: `static/app.js`
- Test: `tests/test_static_assets.py`

**Interfaces:**
- Consumes: `payload.points`, `payload.price_points`
- Produces: chart with weekly price line, step DCF lines, year labels.

- [ ] Add/adjust static asset test assertions for `price_points`, step path rendering, and year labels.
- [ ] Update `renderValuation` to pass both series.
- [ ] Update `drawValuationChart(valuationPoints, pricePoints)`.
- [ ] Run `python -B -m unittest tests.test_static_assets` and `node --check static/app.js`.

### Task 3: Verification

**Files:**
- No additional edits expected.

- [ ] Run all tests: `python -B -m unittest tests.test_balance_sheet tests.test_static_assets`.
- [ ] Call `/api/valuation` for `002245` and verify `price_points` extends beyond latest report date.
- [ ] Refresh the local app and visually check the valuation chart.
