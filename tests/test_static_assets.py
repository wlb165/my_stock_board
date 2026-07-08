import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class StaticAssetsTest(unittest.TestCase):
    def test_index_uses_relative_assets_and_valid_default_name(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")

        self.assertIn('href="styles.css"', html)
        self.assertIn('src="app.js"', html)
        self.assertIn('value="比亚迪"', html)

    def test_app_javascript_has_file_mode_guard(self):
        script = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn('name: "比亚迪"', script)
        self.assertIn("window.location.protocol === \"file:\"", script)
        self.assertIn("请打开 http://127.0.0.1:8765", script)


    def test_chart_scale_is_not_locked_to_500_yi_steps(self):
        script = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertNotIn("maxValue / 500", script)
        self.assertIn("niceChartMax", script)

    def test_revenue_price_view_is_wired(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn('data-view="trend"', html)
        self.assertIn('id="trend-svg"', html)
        self.assertIn("\u80a1\u4ef7\u4e0e\u8425\u6536", html)
        self.assertIn("/api/revenue-price", script)
        self.assertIn("price_points", script)
        self.assertIn("revenue_points", script)
        self.assertIn("Content-Type", script)
        self.assertIn("\u6700\u8fd1\u5b8c\u6574\u4ea4\u6613\u65e5", html)
        self.assertIn("drawTrendChart", script)
        self.assertIn("latest-price-label", script)
        self.assertIn("trend-point-marker", script)
        self.assertIn("revenue-axis-title", script)
        self.assertIn("price-axis-title", script)

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

    def test_valuation_view_has_readable_chinese_labels(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")

        for label in (
            "\u4f30\u503c",
            "\u751f\u6210\u4f30\u503c",
            "\u9884\u6d4b\u5e74\u9650",
            "\u4fdd\u5b88\u589e\u957f\u7387",
            "\u4e2d\u6027\u589e\u957f\u7387",
            "\u4e50\u89c2\u589e\u957f\u7387",
            "\u6298\u73b0\u7387",
            "\u6c38\u7eed\u589e\u957f\u7387",
            "\u5b89\u5168\u8fb9\u9645",
            "\u5f53\u524d\u80a1\u4ef7",
            "\u4e2d\u6027 DCF",
            "\u6298\u4ef7/\u6ea2\u4ef7",
            "\u5b89\u5168\u4e70\u5165\u4ef7",
            "\u5f53\u524d\u5e02\u503c",
            "DCF \u4f30\u503c\u5e26\u4e0e\u80a1\u4ef7\u8d70\u52bf",
        ):
            self.assertIn(label, html)

    def test_valuation_fetch_requires_explicit_form_submit(self):
        script = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn("function showValuationDashboard()", script)
        self.assertIn(
            'if (state.view === "valuation") {\n'
            '    showValuationDashboard();\n'
            '    return;\n'
            '  }',
            script,
        )
        self.assertNotIn(
            'if (state.view === "valuation") {\n'
            '    loadValuationDashboard();\n'
            '    return;\n'
            '  }',
            script,
        )
        self.assertIn('valuationForm.addEventListener("submit"', script)
        self.assertIn("loadValuationDashboard();", script)


if __name__ == "__main__":
    unittest.main()
