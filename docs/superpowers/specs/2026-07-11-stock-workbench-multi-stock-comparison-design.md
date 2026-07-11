# Stock Workbench and Multi-Stock Comparison Design

## Goal

Turn the current single-company dashboard into the first version of a long-term stock analysis workbench.

This feature introduces a left sidebar information architecture and a new multi-stock comparison module. The existing single-company analysis remains intact, while the new module focuses on comparing several companies in one chart.

## Product Direction

The workbench has two primary workflows:

- Single-stock analysis: analyze one company in depth.
- Multi-stock comparison: compare several companies over the same time range.

The first version should improve the structure without adding platform features such as login, saved portfolios, databases, drag-and-drop navigation, or complex routing.

## Navigation

Replace the current top-level tab layout with a static left sidebar and a main content area.

Sidebar structure:

- Single-stock analysis
  - Balance sheet
  - Revenue and price
  - Valuation
- Multi-stock comparison
  - Price trend comparison

The existing single-stock input remains scoped to the single-stock analysis pages. The multi-stock comparison page has its own input controls.

## Multi-Stock Comparison Page

The new page compares multiple stocks in one SVG line chart.

Controls:

- Stock code list input, using comma-separated codes.
- Default stock list: `002594, 600519, 300750`.
- Maximum stock count in the first version: 6.
- Time range selector: 6 months, 1 year, 3 years, 5 years.
- Display mode selector:
  - Percentage change, default.
  - Absolute price.

Chart behavior:

- One chart contains all selected stocks.
- Each stock is drawn as a distinct colored line.
- The x-axis is date.
- The y-axis is percentage change in percentage mode, and price in absolute price mode.
- A legend maps line colors to stock codes or names.

Summary behavior:

- Show one summary item per stock below the chart.
- Each item includes latest price, period change, period high, period low, and data point count.
- If one stock fails to load, show that stock as an error item without blocking successful stocks.

## Backend Design

Add a new endpoint:

```text
/api/multi-stock-trend?codes=002594,600519,300750&period=1y
```

Supported periods:

- `6m`
- `1y`
- `3y`
- `5y`

The backend should:

- Parse and validate the code list.
- Limit the number of stocks to 6 in the first version to avoid slow page loads.
- Reuse the existing Eastmoney front-adjusted K-line data path.
- Sample prices weekly, consistent with the existing trend chart.
- Filter data to the selected period.
- Compute percentage change from each stock's first visible price.
- Return successful series and per-stock errors separately.

Response shape:

```json
{
  "period": "1y",
  "mode_default": "percent",
  "series": [
    {
      "code": "002594",
      "name": "002594",
      "points": [
        {
          "date": "2026-01-02",
          "price": 100.0,
          "change_pct": 0.0
        }
      ],
      "summary": {
        "latest_price": 100.0,
        "period_change_pct": 12.3,
        "period_high": 118.0,
        "period_low": 92.0,
        "point_count": 52
      }
    }
  ],
  "errors": [
    {
      "code": "000000",
      "message": "No price data"
    }
  ]
}
```

## Frontend Design

Keep the existing no-build static frontend.

Update `static/index.html`:

- Add sidebar navigation.
- Group existing panels under single-stock analysis.
- Add a new multi-stock comparison panel.
- Add multi-stock input controls and a comparison SVG.

Update `static/app.js`:

- Track the active workbench view separately from the selected single-stock report view.
- Add multi-stock form state.
- Fetch `/api/multi-stock-trend`.
- Draw the comparison SVG with reusable chart helpers where practical.
- Render summary items and per-stock errors.

Update `static/styles.css`:

- Add a two-column app shell with a sidebar and main content area.
- Keep the existing restrained dashboard style.
- Make the comparison chart and controls responsive.

## Error Handling

- Empty stock list shows a validation error.
- Invalid codes are returned as per-stock errors.
- If more than 6 stock codes are entered, only the first 6 valid-looking codes are requested and the response includes an error explaining the limit.
- If all stocks fail, show a page-level error.
- If some stocks succeed, render the chart and show failed stocks below it.
- Unsupported periods fall back to `1y`.

## Testing

Backend tests:

- Code list parsing and trimming.
- Stock limit behavior.
- Period cutoff behavior.
- Percentage change calculation.
- Multi-stock endpoint response with mixed success and failure.

Frontend checks:

- `node --check static/app.js`.
- Existing static asset tests should cover the new panel ids and controls.

Full verification:

```bash
python -B -m unittest tests.test_balance_sheet tests.test_static_assets
node --check static/app.js
```

## Out of Scope

- Saved portfolios.
- User accounts.
- Persistent preferences.
- Database storage.
- Real-time streaming quotes.
- Industry classification.
- Fundamental metric comparison.
- Exporting charts.
