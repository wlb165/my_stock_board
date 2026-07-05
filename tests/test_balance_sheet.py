import unittest

from app import build_dashboard_payload, should_redirect_to_static_index


class BalanceSheetDashboardTest(unittest.TestCase):
    def test_root_request_redirects_to_static_index(self):
        self.assertTrue(should_redirect_to_static_index("/"))
        self.assertFalse(should_redirect_to_static_index("/static/index.html"))

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
