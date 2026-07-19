# Valuation Chart Latest Price Design

## Goal
Improve the valuation chart so it compares quarterly DCF valuation bands against a denser, latest-available stock price series.

## Design
DCF valuation points remain report-period based because they depend on financial statements. Stock price points become weekly sampled daily closes through the latest complete trading day, matching the revenue/price dashboard style.

After the latest report period, DCF lines stay flat through the latest stock price date. This shows that valuation has not changed without a new report, while the market price has continued moving.

The x-axis shows year labels and vertical year guides. Summary metrics use the latest stock price compared with the latest report-period DCF values.

## Scope
- Add `price_points` to `/api/valuation` payload.
- Keep existing `points` as report-period DCF points.
- Update frontend chart rendering to draw stock price from `price_points` and DCF as step-style horizontal lines.
- Add year labels on the valuation chart.
