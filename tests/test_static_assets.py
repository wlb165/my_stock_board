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


if __name__ == "__main__":
    unittest.main()
