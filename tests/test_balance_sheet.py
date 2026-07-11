import sys
from datetime import date, timedelta
import types
import unittest
import app

from app import (
    annualization_factor,
    build_dashboard_payload,
    build_revenue_price_payload,
    build_ttm_free_cash_flow_points,
    build_valuation_payload,
    closest_close_on_or_before,
    dcf_value,
    fetch_front_adjusted_daily_closes,
    fetch_revenue_price,
    is_revenue_price_path,
    is_valuation_path,
    parse_valuation_assumptions,
    sample_weekly_prices,
    should_redirect_to_static_index,
    valuation_zone,
)


class BalanceSheetDashboardTest(unittest.TestCase):
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

    def test_period_helpers_use_month_end_for_invalid_leap_day_targets(self):
        today = date(2024, 2, 29)
        self.assertEqual(app.period_start_date("1y", today), "2023-02-28")
        self.assertEqual(app.period_start_date("3y", today), "2021-02-28")
        self.assertEqual(app.period_start_date("5y", today), "2019-02-28")

    def test_build_comparison_series_computes_change_and_summary(self):
        series = app.build_comparison_series("002594", "BYD", [
            {"date": "2026-01-02", "price": 100.0},
            {"date": "2026-01-09", "price": 110.0},
            {"date": "2026-01-16", "price": 90.0},
        ])
        self.assertEqual(series["code"], "002594")
        self.assertEqual(series["points"][1]["change_pct"], 10.0)
        self.assertEqual(series["summary"], {
            "latest_price": 90.0, "period_change_pct": -10.0,
            "period_high": 110.0, "period_low": 90.0, "point_count": 3,
        })

    def test_stock_search_matches_code_and_name(self):
        self.assertEqual(
            app.search_stock_directory("比亚迪"),
            [{"code": "002594", "name": "比亚迪"}],
        )
        self.assertEqual(
            app.search_stock_directory("600519"),
            [{"code": "600519", "name": "贵州茅台"}],
        )

    def test_multi_stock_trend_uses_directory_names(self):
        original_fetch = app.fetch_resilient_daily_closes
        try:
            app.fetch_resilient_daily_closes = lambda code, start, end: [
                {"date": "2026-01-02", "close": 100.0},
                {"date": "2026-01-09", "close": 110.0},
            ]
            payload = app.fetch_multi_stock_trend("002594,600519", "1y", today=date(2026, 7, 11))
        finally:
            app.fetch_resilient_daily_closes = original_fetch

        self.assertEqual(
            [(series["code"], series["name"]) for series in payload["series"]],
            [("002594", "比亚迪"), ("600519", "贵州茅台")],
        )

    def test_multi_stock_trend_keeps_successful_series_when_one_fetch_fails(self):
        original_fetch = app.fetch_resilient_daily_closes
        try:
            def fake_fetch(code, start_date, end_date):
                if code == "600519":
                    raise RuntimeError("source unavailable")
                return [
                    {"date": "2026-01-02", "close": 100.0},
                    {"date": "2026-01-09", "close": 110.0},
                ]

            app.fetch_resilient_daily_closes = fake_fetch
            payload = app.fetch_multi_stock_trend(
                "002594,600519,300750", "1y", today=date(2026, 7, 11)
            )
        finally:
            app.fetch_resilient_daily_closes = original_fetch

        self.assertEqual(payload["period"], "1y")
        self.assertEqual(payload["mode_default"], "percent")
        self.assertEqual([series["code"] for series in payload["series"]], ["002594", "300750"])
        self.assertEqual(payload["errors"], [{"code": "600519", "message": "source unavailable"}])

    def test_multi_stock_trend_uses_resilient_price_fallbacks(self):
        original_eastmoney = app.fetch_front_adjusted_daily_closes
        original_resilient = app.fetch_resilient_daily_closes
        calls = []
        try:
            def fail_eastmoney(code, start_date, end_date):
                calls.append("eastmoney")
                raise RuntimeError("eastmoney unavailable")

            def fake_resilient(code, start_date, end_date):
                calls.append("resilient")
                return [
                    {"date": "2026-01-02", "close": 100.0},
                    {"date": "2026-01-09", "close": 110.0},
                ]

            app.fetch_front_adjusted_daily_closes = fail_eastmoney
            app.fetch_resilient_daily_closes = fake_resilient
            payload = app.fetch_multi_stock_trend("002594", "1y", today=date(2026, 7, 11))
        finally:
            app.fetch_front_adjusted_daily_closes = original_eastmoney
            app.fetch_resilient_daily_closes = original_resilient

        self.assertEqual(calls, ["resilient"])
        self.assertEqual(payload["series"][0]["code"], "002594")
        self.assertEqual(payload["series"][0]["points"][-1]["change_pct"], 10.0)
        self.assertEqual(payload["errors"], [])

    def test_multi_stock_trend_uses_dense_comparison_sampling(self):
        original_fetch = app.fetch_resilient_daily_closes
        prices = [
            {"date": (date(2026, 1, 1) + timedelta(days=index)).isoformat(), "close": 100.0 + index}
            for index in range(10)
        ]
        try:
            app.fetch_resilient_daily_closes = lambda code, start_date, end_date: prices
            payload = app.fetch_multi_stock_trend("002594", "1y", today=date(2026, 7, 11))
        finally:
            app.fetch_resilient_daily_closes = original_fetch

        self.assertEqual(len(payload["series"][0]["points"]), 10)
        self.assertEqual(payload["series"][0]["summary"]["point_count"], 10)

    def test_multi_stock_trend_route_matches_only_exact_path(self):
        self.assertTrue(app.is_multi_stock_trend_path("/api/multi-stock-trend"))
        self.assertFalse(app.is_multi_stock_trend_path("/api/multi-stock-trend/"))
        self.assertFalse(app.is_multi_stock_trend_path("/api/valuation"))

    def test_multi_stock_trend_handler_preserves_explicit_blank_codes(self):
        calls = []
        responses = []
        original_fetch = app.fetch_multi_stock_trend
        handler = object.__new__(app.StockBoardHandler)
        try:
            def fake_fetch(codes, period):
                calls.append((codes, period))
                return {
                    "period": period,
                    "mode_default": "percent",
                    "series": [],
                    "errors": [{"code": "", "message": "No stock codes"}],
                }

            app.fetch_multi_stock_trend = fake_fetch
            handler.write_json = lambda payload, status=200: responses.append((payload, status))
            handler.handle_multi_stock_trend("codes=")
            handler.handle_multi_stock_trend("")
        finally:
            app.fetch_multi_stock_trend = original_fetch

        self.assertEqual(calls, [("", "1y"), ("002594,600519,300750", "1y")])
        self.assertEqual([status for _, status in responses], [502, 502])

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
        self.assertEqual(assumptions["alignment"], "latest_share_count")

    def test_parse_valuation_assumptions_rejects_invalid_discount_rate(self):
        params = {"discount_rate": ["0.02"], "perpetual_growth_rate": ["0.03"]}

        with self.assertRaisesRegex(ValueError, "discount_rate"):
            parse_valuation_assumptions(params)

    def test_build_share_points_from_balance_reports_reads_share_capital(self):
        import app

        balance_reports = [
            {"report_date": "2024-12-31", "items": {"实收资本（或股本）": 3039068554}},
            {"report_date": "2025-03-31", "items": {"实收资本(或股本)": "3050000000"}},
            {"report_date": "2025-06-30", "items": {"股本": 3060000000}},
        ]

        points = app.build_share_points_from_balance_reports(balance_reports)

        self.assertEqual(points, [
            {
                "date": "2024-12-31",
                "total_shares": 3039068554,
                "share_count_source": "balance_sheet_share_capital",
            },
            {
                "date": "2025-03-31",
                "total_shares": 3050000000,
                "share_count_source": "balance_sheet_share_capital",
            },
            {
                "date": "2025-06-30",
                "total_shares": 3060000000,
                "share_count_source": "balance_sheet_share_capital",
            },
        ])

    def test_build_valuation_payload_uses_balance_sheet_share_points_with_close_only_prices(self):
        import app

        assumptions = {
            "cash_flow_basis": "ttm_fcf",
            "forecast_years": 5,
            "growth_conservative": 0.0,
            "growth_neutral": 0.0,
            "growth_optimistic": 0.0,
            "discount_rate": 0.10,
            "perpetual_growth_rate": 0.02,
            "safety_margin": 0.25,
            "alignment": "latest_share_count",
        }
        dates = ["2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31"]
        cash_reports = [
            {
                "report_date": date,
                "items": {
                    app.OPERATING_CASH_FLOW_FIELDS[0]: (index + 1) * 100000000,
                    app.CAPEX_FIELDS[0]: 0,
                },
            }
            for index, date in enumerate(dates)
        ]
        income_reports = [
            {
                "report_date": date,
                "items": {
                    "营业总收入": (index + 1) * 200000000,
                    app.NET_PROFIT_FIELDS[0]: (index + 1) * 10000000,
                },
            }
            for index, date in enumerate(dates)
        ]
        balance_reports = [
            {
                "report_date": "2024-12-31",
                "items": {
                    "实收资本（或股本）": 100000000,
                    app.EQUITY_FIELDS[0]: 1000000000,
                },
            },
        ]
        prices = [{"date": "2024-12-31", "close": 12.0}]
        share_points = app.build_share_points_from_balance_reports(balance_reports)

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

        self.assertEqual(len(payload["points"]), 1)
        self.assertEqual(payload["points"][0]["total_shares"], 100000000)
        self.assertEqual(payload["points"][0]["share_count_source"], "balance_sheet_share_capital")
        self.assertEqual(payload["summary"]["market_cap_yi"], 12.0)
        self.assertEqual(
            payload["points"][0]["safety_buy_price"],
            round(payload["points"][0]["neutral_value"] * (1 - assumptions["safety_margin"]), 2),
        )
        self.assertEqual(payload["summary"]["safety_buy_price"], payload["points"][0]["safety_buy_price"])
        self.assertEqual(
            payload["summary"]["discount_to_neutral_pct"],
            round((payload["points"][0]["neutral_value"] - 12.0) / payload["points"][0]["neutral_value"] * 100, 2),
        )

    def test_build_valuation_payload_uses_latest_total_shares_for_all_periods(self):
        assumptions = {
            "cash_flow_basis": "ttm_fcf",
            "forecast_years": 5,
            "growth_conservative": 0.0,
            "growth_neutral": 0.0,
            "growth_optimistic": 0.0,
            "discount_rate": 0.10,
            "perpetual_growth_rate": 0.02,
            "safety_margin": 0.25,
            "alignment": "latest_share_count",
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

        self.assertEqual(payload["points"][0]["total_shares"], 200000000)
        self.assertEqual(payload["points"][1]["total_shares"], 200000000)
        self.assertEqual(payload["points"][0]["share_count_date"], "2025-03-31")
        self.assertEqual(payload["points"][1]["share_count_date"], "2025-03-31")
        self.assertEqual(payload["share_count_basis"], "latest_share_count")
        self.assertEqual(payload["price_adjustment"], "front_adjusted")
        self.assertIn("pe_ttm", payload["summary"])
        self.assertIn("pb", payload["summary"])
        self.assertIn("ps_ttm", payload["summary"])

    def test_build_valuation_payload_uses_none_for_missing_price_metrics(self):
        import app

        assumptions = {
            "cash_flow_basis": "ttm_fcf",
            "forecast_years": 5,
            "growth_conservative": 0.0,
            "growth_neutral": 0.0,
            "growth_optimistic": 0.0,
            "discount_rate": 0.10,
            "perpetual_growth_rate": 0.02,
            "safety_margin": 0.25,
            "alignment": "latest_share_count",
        }
        dates = ["2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31"]
        cash_reports = [
            {
                "report_date": date,
                "items": {
                    app.OPERATING_CASH_FLOW_FIELDS[0]: (index + 1) * 100000000,
                    app.CAPEX_FIELDS[0]: 0,
                },
            }
            for index, date in enumerate(dates)
        ]
        income_reports = [
            {
                "report_date": date,
                "items": {
                    "钀ヤ笟鎬绘敹鍏?": (index + 1) * 200000000,
                    app.NET_PROFIT_FIELDS[0]: (index + 1) * 10000000,
                },
            }
            for index, date in enumerate(dates)
        ]
        balance_reports = [
            {"report_date": "2024-12-31", "items": {app.EQUITY_FIELDS[0]: 1000000000}},
        ]
        share_points = [{"date": "2024-12-31", "total_shares": 100000000}]
        prices = [{"date": "2024-12-31", "close": ""}]

        payload = build_valuation_payload(
            "002594",
            "BYD",
            income_reports,
            balance_reports,
            cash_reports,
            prices,
            share_points,
            assumptions,
        )

        summary = payload["summary"]
        self.assertIsNone(summary["pe_ttm"])
        self.assertIsNone(summary["pb"])
        self.assertIsNone(summary["ps_ttm"])
        self.assertIsNone(summary["market_cap_yi"])
        self.assertIsNone(summary["current_price"])
        self.assertIsNone(summary["discount_to_neutral_pct"])

    def test_valuation_payload_keeps_weekly_prices_through_latest_close(self):
        import app

        assumptions = {
            "cash_flow_basis": "ttm_fcf",
            "forecast_years": 5,
            "growth_conservative": 0.0,
            "growth_neutral": 0.0,
            "growth_optimistic": 0.0,
            "discount_rate": 0.10,
            "perpetual_growth_rate": 0.02,
            "safety_margin": 0.25,
            "alignment": "latest_share_count",
        }
        cash_reports = [
            {
                "report_date": date,
                "items": {
                    app.OPERATING_CASH_FLOW_FIELDS[0]: 100000000,
                    app.CAPEX_FIELDS[0]: 0,
                },
            }
            for date in ["2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31"]
        ]
        balance_reports = [
            {
                "report_date": "2026-03-31",
                "items": {
                    app.SHARE_CAPITAL_FIELDS[0]: 100000000,
                    app.EQUITY_FIELDS[0]: 1000000000,
                },
            }
        ]
        income_reports = [
            {"report_date": "2026-03-31", "items": {app.NET_PROFIT_FIELDS[0]: 50000000}},
        ]
        prices = [
            {"date": "2026-03-31", "close": 10.0},
            {"date": "2026-04-03", "close": 11.0},
            {"date": "2026-04-10", "close": 12.0},
        ]
        share_points = app.build_share_points_from_balance_reports(balance_reports)

        payload = build_valuation_payload(
            "002245",
            "蔚蓝锂芯",
            income_reports,
            balance_reports,
            cash_reports,
            prices,
            share_points,
            assumptions,
        )

        self.assertEqual(payload["points"][-1]["date"], "2026-03-31")
        self.assertEqual(payload["price_points"][-1], {"date": "2026-04-10", "price": 12.0})
        self.assertEqual(payload["summary"]["current_price"], 12.0)
        self.assertEqual(payload["summary"]["market_cap_yi"], 12.0)

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

    def test_ttm_free_cash_flow_subtracts_sina_capex_field_with_suo(self):
        import app

        reports = [
            {
                "report_date": "2025-06-30",
                "items": {
                    app.OPERATING_CASH_FLOW_FIELDS[0]: 410000000,
                    "购建固定资产、无形资产和其他长期资产所支付的现金": 213000000,
                },
            },
            {
                "report_date": "2025-09-30",
                "items": {
                    app.OPERATING_CASH_FLOW_FIELDS[0]: 717000000,
                    "购建固定资产、无形资产和其他长期资产所支付的现金": 315000000,
                },
            },
            {
                "report_date": "2025-12-31",
                "items": {
                    app.OPERATING_CASH_FLOW_FIELDS[0]: 1256000000,
                    "购建固定资产、无形资产和其他长期资产所支付的现金": 692000000,
                },
            },
            {
                "report_date": "2026-03-31",
                "items": {
                    app.OPERATING_CASH_FLOW_FIELDS[0]: 193000000,
                    "购建固定资产、无形资产和其他长期资产所支付的现金": 213000000,
                },
            },
        ]

        points = build_ttm_free_cash_flow_points(reports)

        self.assertEqual(points[-1], {"date": "2026-03-31", "ttm_fcf": 544000000})

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

    def test_comparison_price_sampling_keeps_daily_density_with_cap(self):
        prices = [
            {"date": (date(2026, 1, 1) + timedelta(days=index)).isoformat(), "close": 100.0 + index}
            for index in range(240)
        ]

        sampled = app.sample_comparison_prices(prices, max_points=180)

        self.assertEqual(len(sampled), 180)
        self.assertEqual(sampled[0], {"date": "2026-01-01", "price": 100.0})
        self.assertEqual(sampled[-1], {"date": "2026-08-28", "price": 339.0})
        self.assertGreater(len(sampled), len(sample_weekly_prices(prices)))

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

    def test_baidu_daily_closes_parses_market_data_rows(self):
        import app

        response = {
            "Result": {
                "newMarketData": {
                    "keys": ["timestamp", "time", "open", "close"],
                    "marketData": (
                        "1704067200,2024-01-01,10.00,11.00;"
                        "1704153600,2024-01-02,11.00,12.00;"
                        "1704240000,2024-01-03,12.00,--"
                    ),
                }
            }
        }
        original_read_url = app.read_url
        try:
            app.read_url = lambda request, timeout=15: __import__("json").dumps(response)

            prices = app.fetch_baidu_daily_closes("002594", "2024-01-02", "2024-01-31")
        finally:
            app.read_url = original_read_url

        self.assertEqual(prices, [{"date": "2024-01-02", "close": 12.0}])

    def test_mootdx_daily_closes_parses_daily_bars(self):
        import app

        quotes_module = types.ModuleType("mootdx.quotes")
        mootdx_module = types.ModuleType("mootdx")

        class FakeClient:
            def bars(self, symbol, category, start=0, offset=800):
                self.call = {"symbol": symbol, "category": category, "start": start, "offset": offset}
                return [
                    {"datetime": "2024-01-01", "close": 11.0},
                    {"datetime": "2024-01-02 15:00", "close": 12.0},
                    {"datetime": "2024-01-03", "close": 0},
                ]

        fake_client = FakeClient()

        class FakeQuotes:
            @staticmethod
            def factory(market="std", **kwargs):
                return fake_client

        quotes_module.Quotes = FakeQuotes
        original_mootdx = sys.modules.get("mootdx")
        original_quotes = sys.modules.get("mootdx.quotes")
        try:
            sys.modules["mootdx"] = mootdx_module
            sys.modules["mootdx.quotes"] = quotes_module

            prices = app.fetch_mootdx_daily_closes("002594", "2024-01-02", "2024-01-31")
        finally:
            if original_mootdx is None:
                sys.modules.pop("mootdx", None)
            else:
                sys.modules["mootdx"] = original_mootdx
            if original_quotes is None:
                sys.modules.pop("mootdx.quotes", None)
            else:
                sys.modules["mootdx.quotes"] = original_quotes

        self.assertEqual(fake_client.call["symbol"], "002594")
        self.assertEqual(fake_client.call["category"], 4)
        self.assertEqual(prices, [{"date": "2024-01-02", "close": 12.0}])

    def test_revenue_price_daily_closes_falls_back_to_mootdx_when_eastmoney_fails(self):
        import app

        calls = []
        original_eastmoney = app.fetch_front_adjusted_daily_closes
        original_mootdx = app.fetch_mootdx_daily_closes
        original_baidu = app.fetch_baidu_daily_closes
        try:
            def fail_eastmoney(code, start, end):
                calls.append("eastmoney")
                raise RuntimeError("eastmoney unavailable")

            def fake_mootdx(code, start, end):
                calls.append("mootdx")
                return [{"date": "2024-12-31", "close": 40.0}]

            def fake_baidu(code, start, end):
                calls.append("baidu")
                return [{"date": "2024-12-31", "close": 41.0}]

            app.fetch_front_adjusted_daily_closes = fail_eastmoney
            app.fetch_mootdx_daily_closes = fake_mootdx
            app.fetch_baidu_daily_closes = fake_baidu

            prices = app.fetch_resilient_daily_closes("002594", "2024-01-01", "2024-12-31")
        finally:
            app.fetch_front_adjusted_daily_closes = original_eastmoney
            app.fetch_mootdx_daily_closes = original_mootdx
            app.fetch_baidu_daily_closes = original_baidu

        self.assertEqual(calls, ["eastmoney", "mootdx"])
        self.assertEqual(prices, [{"date": "2024-12-31", "close": 40.0}])

    def test_valuation_daily_closes_uses_front_adjusted_eastmoney_before_fallbacks(self):
        import app

        calls = []
        original_eastmoney = app.fetch_front_adjusted_daily_closes
        original_mootdx = app.fetch_mootdx_daily_closes
        original_baidu = app.fetch_baidu_daily_closes
        try:
            def fake_eastmoney(code, start, end):
                calls.append("eastmoney_qfq")
                return [{"date": "2024-12-31", "close": 39.0}]

            def fake_baidu(code, start, end):
                calls.append("baidu")
                return [{"date": "2024-12-31", "close": 40.0}]

            app.fetch_front_adjusted_daily_closes = fake_eastmoney
            app.fetch_mootdx_daily_closes = lambda code, start, end: calls.append("mootdx") or []
            app.fetch_baidu_daily_closes = fake_baidu

            prices = app.fetch_valuation_daily_closes("002594", "2024-01-01", "2024-12-31")
        finally:
            app.fetch_front_adjusted_daily_closes = original_eastmoney
            app.fetch_mootdx_daily_closes = original_mootdx
            app.fetch_baidu_daily_closes = original_baidu

        self.assertEqual(calls, ["eastmoney_qfq"])
        self.assertEqual(prices, [{"date": "2024-12-31", "close": 39.0}])

        self.assertEqual(calls, ["eastmoney_qfq"])

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
        original_prices = app.fetch_resilient_daily_closes
        try:
            app.fetch_income_reports = lambda code, limit: reports

            def fake_prices(code, start, end):
                calls.append({"start": start, "end": end})
                return prices

            app.fetch_resilient_daily_closes = fake_prices

            payload = fetch_revenue_price("002245", "\u851a\u84dd\u9502\u82af", today="2026-07-06")
        finally:
            app.fetch_income_reports = original_reports
            app.fetch_resilient_daily_closes = original_prices

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
