import unittest

from app import (
    annualization_factor,
    build_dashboard_payload,
    build_revenue_price_payload,
    build_ttm_free_cash_flow_points,
    closest_close_on_or_before,
    dcf_value,
    fetch_front_adjusted_daily_closes,
    fetch_revenue_price,
    is_revenue_price_path,
    sample_weekly_prices,
    should_redirect_to_static_index,
    valuation_zone,
)


class BalanceSheetDashboardTest(unittest.TestCase):
    def test_builds_ttm_free_cash_flow_from_cumulative_cash_flow_reports(self):
        reports = [
            {
                "report_date": "2024-03-31",
                "items": {
                    "\u7ecf\u8425\u6d3b\u52a8\u4ea7\u751f\u7684\u73b0\u91d1\u6d41\u91cf\u51c0\u989d": 1000000000,
                    "\u8d2d\u5efa\u56fa\u5b9a\u8d44\u4ea7\u3001\u65e0\u5f62\u8d44\u4ea7\u548c\u5176\u4ed6\u957f\u671f\u8d44\u4ea7\u652f\u4ed8\u7684\u73b0\u91d1": 200000000,
                },
            },
            {
                "report_date": "2024-06-30",
                "items": {
                    "\u7ecf\u8425\u6d3b\u52a8\u4ea7\u751f\u7684\u73b0\u91d1\u6d41\u91cf\u51c0\u989d": 2500000000,
                    "\u8d2d\u5efa\u56fa\u5b9a\u8d44\u4ea7\u3001\u65e0\u5f62\u8d44\u4ea7\u548c\u5176\u4ed6\u957f\u671f\u8d44\u4ea7\u652f\u4ed8\u7684\u73b0\u91d1": 700000000,
                },
            },
            {
                "report_date": "2024-09-30",
                "items": {
                    "\u7ecf\u8425\u6d3b\u52a8\u4ea7\u751f\u7684\u73b0\u91d1\u6d41\u91cf\u51c0\u989d": 4300000000,
                    "\u8d2d\u5efa\u56fa\u5b9a\u8d44\u4ea7\u3001\u65e0\u5f62\u8d44\u4ea7\u548c\u5176\u4ed6\u957f\u671f\u8d44\u4ea7\u652f\u4ed8\u7684\u73b0\u91d1": 1200000000,
                },
            },
            {
                "report_date": "2024-12-31",
                "items": {
                    "\u7ecf\u8425\u6d3b\u52a8\u4ea7\u751f\u7684\u73b0\u91d1\u6d41\u91cf\u51c0\u989d": 7000000000,
                    "\u8d2d\u5efa\u56fa\u5b9a\u8d44\u4ea7\u3001\u65e0\u5f62\u8d44\u4ea7\u548c\u5176\u4ed6\u957f\u671f\u8d44\u4ea7\u652f\u4ed8\u7684\u73b0\u91d1": 2000000000,
                },
            },
            {
                "report_date": "2025-03-31",
                "items": {
                    "\u7ecf\u8425\u6d3b\u52a8\u4ea7\u751f\u7684\u73b0\u91d1\u6d41\u91cf\u51c0\u989d": 1300000000,
                    "\u8d2d\u5efa\u56fa\u5b9a\u8d44\u4ea7\u3001\u65e0\u5f62\u8d44\u4ea7\u548c\u5176\u4ed6\u957f\u671f\u8d44\u4ea7\u652f\u4ed8\u7684\u73b0\u91d1": 300000000,
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
        self.assertEqual(valuation_zone(50, 70, 100, 130), "\u4f4e\u4e8e\u4fdd\u5b88\u4f30\u503c")
        self.assertEqual(valuation_zone(80, 70, 100, 130), "\u4fdd\u5b88\u533a\u95f4")
        self.assertEqual(valuation_zone(110, 70, 100, 130), "\u5408\u7406\u533a\u95f4")
        self.assertEqual(valuation_zone(150, 70, 100, 130), "\u9ad8\u4e8e\u4e50\u89c2\u4f30\u503c")

    def test_root_request_redirects_to_static_index(self):
        self.assertTrue(should_redirect_to_static_index("/"))
        self.assertFalse(should_redirect_to_static_index("/static/index.html"))

    def test_revenue_annualization_uses_report_period_factor(self):
        self.assertEqual(annualization_factor("2024-03-31"), 4)
        self.assertEqual(annualization_factor("2024-06-30"), 2)
        self.assertEqual(annualization_factor("2024-09-30"), 4 / 3)
        self.assertEqual(annualization_factor("2024-12-31"), 1)

    def test_closest_close_uses_last_trade_before_report_date(self):
        prices = [
            {"date": "2024-03-28", "close": 10.0},
            {"date": "2024-04-01", "close": 12.0},
        ]

        self.assertEqual(closest_close_on_or_before(prices, "2024-03-31"), 10.0)

    def test_builds_revenue_price_payload(self):
        reports = [
            {
                "report_date": "2024-03-31",
                "items": {"\u8425\u4e1a\u603b\u6536\u5165": 1000000000},
            },
            {
                "report_date": "2024-06-30",
                "items": {"\u8425\u4e1a\u6536\u5165": 3000000000},
            },
            {
                "report_date": "2024-09-30",
                "items": {"\u8425\u4e1a\u603b\u6536\u5165": 6000000000},
            },
            {
                "report_date": "2024-12-31",
                "items": {"\u8425\u4e1a\u603b\u6536\u5165": 10000000000},
            },
        ]
        prices = [
            {"date": "2024-03-29", "close": 10.0},
            {"date": "2024-06-28", "close": 20.0},
            {"date": "2024-09-30", "close": 30.0},
            {"date": "2024-12-31", "close": 40.0},
        ]

        payload = build_revenue_price_payload("002594", "\u6bd4\u4e9a\u8fea", reports, prices)

        self.assertEqual(payload["revenue_points"][0]["annualized_revenue_yi"], 40.0)
        self.assertEqual(payload["revenue_points"][1]["annualized_revenue_yi"], 60.0)
        self.assertEqual(payload["revenue_points"][2]["annualized_revenue_yi"], 80.0)
        self.assertEqual(payload["revenue_points"][3]["annualized_revenue_yi"], 100.0)
        self.assertEqual(payload["price_source"], "eastmoney_qfq")
        self.assertEqual(payload["price_adjustment"], "front_adjusted")
        self.assertEqual(payload["price_points"], [
            {"date": "2024-03-29", "price": 10.0},
            {"date": "2024-06-28", "price": 20.0},
            {"date": "2024-09-30", "price": 30.0},
            {"date": "2024-12-31", "price": 40.0},
        ])
        self.assertNotIn("points", payload)

    def test_weekly_price_sampling_uses_last_trade_in_each_week(self):
        prices = [
            {"date": "2024-01-02", "close": 10.0},
            {"date": "2024-01-03", "close": 11.0},
            {"date": "2024-01-05", "close": 12.0},
            {"date": "2024-01-08", "close": 13.0},
            {"date": "2024-01-10", "close": 14.0},
            {"date": "2024-01-19", "close": 15.0},
        ]

        self.assertEqual(sample_weekly_prices(prices), [
            {"date": "2024-01-05", "price": 12.0},
            {"date": "2024-01-10", "price": 14.0},
            {"date": "2024-01-19", "price": 15.0},
        ])

    def test_front_adjusted_daily_closes_uses_only_eastmoney_qfq_source(self):
        import app

        calls = []
        original_eastmoney = app.fetch_eastmoney_front_adjusted_daily_closes
        try:
            app.fetch_eastmoney_front_adjusted_daily_closes = lambda code, start, end: calls.append("eastmoney") or [{"date": "2024-12-31", "close": 40.0}]

            prices = fetch_front_adjusted_daily_closes("002594", "2024-01-01", "2024-12-31")
        finally:
            app.fetch_eastmoney_front_adjusted_daily_closes = original_eastmoney

        self.assertEqual(calls, ["eastmoney"])
        self.assertEqual(prices, [{"date": "2024-12-31", "close": 40.0}])

    def test_front_adjusted_daily_closes_fails_when_eastmoney_qfq_fails(self):
        import app

        calls = []
        original_eastmoney = app.fetch_eastmoney_front_adjusted_daily_closes
        try:
            def fail_eastmoney(code, start, end):
                calls.append("eastmoney")
                raise RuntimeError("eastmoney unavailable")

            app.fetch_eastmoney_front_adjusted_daily_closes = fail_eastmoney

            with self.assertRaisesRegex(RuntimeError, "eastmoney_qfq"):
                fetch_front_adjusted_daily_closes("002594", "2024-01-01", "2024-12-31")
        finally:
            app.fetch_eastmoney_front_adjusted_daily_closes = original_eastmoney

        self.assertEqual(calls, ["eastmoney"])

    def test_revenue_price_extends_prices_to_latest_complete_trading_day(self):
        import app

        calls = []
        reports = [
            {
                "report_date": "2026-03-31",
                "items": {"\u8425\u4e1a\u603b\u6536\u5165": 2153000000},
            }
        ]
        prices = [
            {"date": "2026-03-27", "close": 11.16},
            {"date": "2026-07-03", "close": 20.34},
            {"date": "2026-07-06", "close": 21.91},
        ]
        original_reports = app.fetch_income_reports
        original_prices = app.fetch_front_adjusted_daily_closes
        try:
            app.fetch_income_reports = lambda code, limit: reports

            def fake_prices(code, start, end):
                calls.append({"start": start, "end": end})
                return prices

            app.fetch_front_adjusted_daily_closes = fake_prices

            payload = fetch_revenue_price("002245", "\u851a\u84dd\u9502\u82af", today="2026-07-06")
        finally:
            app.fetch_income_reports = original_reports
            app.fetch_front_adjusted_daily_closes = original_prices

        self.assertEqual(calls[0]["end"], "2026-07-06")
        self.assertEqual(payload["price_points"][-1], {"date": "2026-07-03", "price": 20.34})
    def test_revenue_price_route_keeps_old_path_compatible(self):
        self.assertTrue(is_revenue_price_path("/api/revenue-price"))
        self.assertTrue(is_revenue_price_path("/api/revenue-market-cap"))
        self.assertFalse(is_revenue_price_path("/api/balance-sheet"))

    def test_fixed_asset_uses_sina_net_amount_and_construction_in_progress(self):
        reports = [
            {
                "report_date": "2024-12-31",
                "items": {
                    "\u56fa\u5b9a\u8d44\u4ea7\u51c0\u989d": 262287000000,
                    "\u56fa\u5b9a\u8d44\u4ea7\u53ca\u6e05\u7406\u5408\u8ba1": 262287000000,
                    "\u5728\u5efa\u5de5\u7a0b": 13170000000,
                    "\u5176\u4ed6\u975e\u6d41\u52a8\u8d44\u4ea7": 22536000000,
                    "\u8d44\u4ea7\u603b\u8ba1": 783356000000,
                    "\u8d1f\u503a\u5408\u8ba1": 584668000000,
                },
            }
        ]

        payload = build_dashboard_payload("002594", "\u6bd4\u4e9a\u8fea", reports, 0)

        self.assertEqual(payload["assets"][6], {"label": "\u56fa\u5b9a\u8d44\u4ea7", "value": 2754.57})
        self.assertEqual(payload["assets"][8], {"label": "\u5176\u5b83\u56fa\u5b9a", "value": 225.36})

    def test_builds_asset_and_liability_chart_items_in_yi(self):
        reports = [
            {
                "report_date": "2025-12-31",
                "items": {
                    "货币资金": 1200000000,
                    "应收账款": 300000000,
                    "预付款项": 50000000,
                    "存货": 900000000,
                    "其他流动资产": 100000000,
                    "长期股权投资": 200000000,
                    "固定资产": 1100000000,
                    "无形资产": 70000000,
                    "商誉": 30000000,
                    "其他非流动资产": 40000000,
                    "短期借款": 80000000,
                    "应付账款": 600000000,
                    "合同负债": 150000000,
                    "应付职工薪酬": 50000000,
                    "应交税费": 30000000,
                    "其他流动负债": 90000000,
                    "长期借款": 200000000,
                    "应付债券": 250000000,
                    "其他非流动负债": 50000000,
                    "资产总计": 3950000000,
                    "负债合计": 1500000000,
                    "所有者权益合计": 2450000000,
                },
            }
        ]

        payload = build_dashboard_payload("002594", "比亚迪", reports, 0)

        self.assertEqual(payload["company"]["code"], "002594")
        self.assertEqual(payload["period"]["current"], "2025-12-31")
        self.assertEqual(payload["summary"]["total_assets_yi"], 39.5)
        self.assertEqual(payload["summary"]["debt_ratio_pct"], 37.97)
        self.assertEqual(payload["assets"][0], {"label": "现金", "value": 12.0})
        self.assertEqual(payload["assets"][7], {"label": "无形&商誉", "value": 1.0})
        self.assertEqual(payload["liabilities"][3], {"label": "薪酬&税", "value": 0.8})
        self.assertEqual(payload["liabilities"][6], {"label": "其它非流动", "value": 3.0})


if __name__ == "__main__":
    unittest.main()
