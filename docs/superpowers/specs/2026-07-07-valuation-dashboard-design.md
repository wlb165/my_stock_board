# Valuation Dashboard Design

## Summary

Add a third independent dashboard tab named `估值`. The dashboard is a DCF-first valuation workspace. Users choose valuation assumptions, click `生成估值`, and the app renders a dynamic DCF valuation band over time with the stock price overlaid. PE, PB, PS, market cap, and valuation-position metrics act as secondary checks.

This is not a replacement for the existing `资产负债表` or `股价与营收` dashboards.

## Goals

- Add a standalone valuation dashboard.
- Use TTM free cash flow as the default DCF base.
- Recalculate DCF value at each reporting period, so the valuation band changes as fundamentals change.
- Let users set the main DCF assumptions before generating the valuation.
- Overlay historical stock price with conservative, neutral, and optimistic DCF value lines.
- Show PE, PB, PS, current market cap, and discount or premium versus neutral DCF value.

## Non-Goals

- No automatic WACC model in V1.
- No peer-company comparison in V1.
- No research-report consensus forecast integration in V1.
- No disclosure-date alignment in V1. The first version aligns by report period date.
- No trading recommendation or buy/sell signal.

## Assumptions

- The existing local HTTP server and static frontend remain the app architecture.
- The new dashboard follows the existing tab-based UI pattern.
- Financial statements are still fetched from Sina's finance report API.
- Daily prices continue to use Eastmoney front-adjusted K-line data, matching the current trend dashboard.
- Report-period alignment is acceptable for V1, with clear labeling.
- DCF output is an estimate for analysis, not an investment recommendation.

## User Flow

1. User enters a stock code and optional company name.
2. User switches to the `估值` tab.
3. The dashboard shows DCF controls with sensible defaults.
4. User adjusts assumptions.
5. User clicks `生成估值`.
6. The app fetches valuation data and renders the valuation dashboard.

## DCF Inputs

V1 exposes these common inputs:

- `现金流口径`: default `TTM 自由现金流`.
- `预测年限`: `3`, `5`, or `10` years. Default `5`.
- `保守增长率`: default `5%`.
- `中性增长率`: default `10%`.
- `乐观增长率`: default `15%`.
- `折现率`: default `10%`.
- `永续增长率`: default `2.5%`.
- `安全边际`: default `25%`.

V1 keeps advanced controls out of scope unless needed during implementation. The interface can leave room for later additions such as net cash adjustment, terminal multiple, and disclosure-date alignment.

## Financial Definitions

TTM free cash flow is the sum of the latest four quarterly free cash flow values:

```text
Free Cash Flow = Net Cash Flow From Operating Activities - Capital Expenditure
```

The cash flow statement field names can vary, so the implementation should use a small candidate-field helper similar to the existing revenue field fallback.

DCF enterprise value for each scenario:

```text
Year N FCF = Base TTM FCF * (1 + growth_rate) ^ N
Present Value = Sum(Year N FCF / (1 + discount_rate) ^ N)
Terminal Value = Year Final FCF * (1 + perpetual_growth_rate) / (discount_rate - perpetual_growth_rate)
DCF Value = Present Value + Terminal Value / (1 + discount_rate) ^ forecast_years
```

Per-share DCF value:

```text
DCF Per Share = DCF Value / Total Shares
```

Safety-buy price:

```text
Safety Buy Price = Neutral DCF Per Share * (1 - Safety Margin)
```

## Dynamic Valuation Band

For each report period with enough data:

1. Calculate TTM free cash flow from the latest four quarters ending at that report period.
2. Calculate conservative, neutral, and optimistic DCF values from the user's assumptions.
3. Convert each value to per-share value.
4. Find the latest front-adjusted close on or before the report period.
5. Add a chart point:

```json
{
  "date": "2025-12-31",
  "price": 88.5,
  "conservative_value": 62.1,
  "neutral_value": 84.3,
  "optimistic_value": 113.8,
  "safety_buy_price": 63.2,
  "ttm_fcf_yi": 120.5
}
```

## UI Design

Add a new tab:

```text
资产负债表 | 股价与营收 | 估值 | 基本信息
```

The `估值` panel contains:

- DCF controls at the top.
- A `生成估值` button.
- Summary metrics:
  - Current price
  - Current market cap
  - Neutral DCF value
  - Discount or premium versus neutral DCF value
  - Safety-buy price
  - Current valuation zone
- Main chart:
  - Stock price line
  - Conservative DCF line
  - Neutral DCF line
  - Optimistic DCF line
  - Optional safety-buy line
- Relative valuation section:
  - PE
  - PB
  - PS
  - Latest TTM free cash flow

The chart should use the existing SVG pattern rather than adding a charting library.

## API Design

Add:

```text
GET /api/valuation
```

Query parameters:

- `code`
- `name`
- `forecast_years`
- `growth_conservative`
- `growth_neutral`
- `growth_optimistic`
- `discount_rate`
- `perpetual_growth_rate`
- `safety_margin`

Payload shape:

```json
{
  "company": {
    "code": "002594",
    "name": "比亚迪"
  },
  "assumptions": {
    "cash_flow_basis": "ttm_fcf",
    "forecast_years": 5,
    "growth_conservative": 0.05,
    "growth_neutral": 0.10,
    "growth_optimistic": 0.15,
    "discount_rate": 0.10,
    "perpetual_growth_rate": 0.025,
    "safety_margin": 0.25,
    "alignment": "report_period"
  },
  "summary": {
    "current_price": 88.5,
    "market_cap_yi": 9000.0,
    "neutral_value": 84.3,
    "discount_to_neutral_pct": -4.98,
    "safety_buy_price": 63.2,
    "pe_ttm": 22.5,
    "pb": 4.1,
    "ps_ttm": 2.3,
    "latest_ttm_fcf_yi": 120.5,
    "valuation_zone": "合理区间"
  },
  "points": []
}
```

## Data Flow

Server-side:

1. Fetch income reports for revenue and net profit.
2. Fetch balance sheet reports for shareholder equity.
3. Fetch cash flow reports for operating cash flow and capital expenditure.
4. Fetch daily front-adjusted prices.
5. Fetch or derive total shares and current market cap.
6. Build quarterly records by report date.
7. Calculate TTM values and DCF values.
8. Return a compact payload for the frontend.

Client-side:

1. Read form inputs and DCF controls.
2. Call `/api/valuation`.
3. Render summary metrics.
4. Draw the valuation chart.
5. Render PE, PB, PS helper metrics.

## Error Handling

- If fewer than four cash flow periods exist, show `现金流数据不足，无法计算 TTM 自由现金流`.
- If TTM free cash flow is negative, still show the point but label the DCF result as `现金流为负，DCF 参考意义较弱`.
- If `discount_rate <= perpetual_growth_rate`, reject the request with a clear error.
- If price data is missing, return valuation points without price and show a chart note.
- If PE cannot be calculated because net profit is zero or negative, show `--`.

## Testing

Backend unit tests:

- TTM free cash flow calculation uses the latest four quarters.
- DCF calculation returns expected conservative, neutral, and optimistic values.
- DCF rejects invalid `discount_rate <= perpetual_growth_rate`.
- Valuation payload includes assumptions, summary, and dynamic points.
- PE/PB/PS handle zero or missing denominators.

Static asset tests:

- `估值` tab is wired in `index.html`.
- `生成估值` controls exist.
- Frontend calls `/api/valuation`.
- Chart renderer uses valuation point fields.

Manual verification:

- Run the existing unittest suite.
- Run `node --check static/app.js`.
- Start the local server and verify the three dashboard tabs switch correctly.

## Open Decisions For Later

- Whether to add disclosure-date alignment in V2.
- Whether to add net cash adjustment to convert enterprise value to equity value.
- Whether to add a terminal-multiple method next to perpetual-growth DCF.
- Whether to integrate analyst forecasts or peer comparison.
