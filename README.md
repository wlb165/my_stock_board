# A Stock Balance Sheet Dashboard

## Revenue and Stock Price Trend

- The trend board shows annualized revenue and front-adjusted stock price.
- Annualized revenue uses quarterly reports:
  - Q1 revenue x 4
  - Half-year revenue x 2
  - Q3 revenue x 4 / 3
  - Annual revenue x 1
- Historical stock price is sampled weekly through the latest complete trading day, using the last available trading close in each week.
- Daily close source: Eastmoney front-adjusted K-line (`fqt=1`) only, so the trend never mixes adjusted and unadjusted prices.

## Stock Analysis Workbench

- Single-stock analysis keeps the existing balance sheet, revenue and price, and valuation views.
- Multi-stock comparison shows up to 6 stocks in one chart.
- The comparison chart defaults to percentage change and can switch to absolute price.
- Supported comparison ranges: 6 months, 1 year, 3 years, 5 years.


本项目是一个本地 A 股上市公司资产负债表看板。

## 功能

- 输入股票代码查看上市公司资产负债表
- 使用新浪财报三表接口抓取资产负债表数据
- 将资产、负债科目按看板口径汇总为柱状图
- 支持当期、上一期、下一期切换

## 运行

```bash
python app.py
```

然后打开：

```text
http://127.0.0.1:8765
```

## 测试

```bash
python -B -m unittest tests.test_balance_sheet tests.test_static_assets
node --check static/app.js
```
