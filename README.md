# A Stock Balance Sheet Dashboard

## Revenue and Market Cap Trend

- The trend board shows annualized revenue and estimated market cap.
- Annualized revenue uses quarterly reports:
  - Q1 revenue x 4
  - Half-year revenue x 2
  - Q3 revenue x 4 / 3
  - Annual revenue x 1
- Historical market cap is estimated from daily close price and current total shares.
- Daily close source priority: Tongdaxin/mootdx, Sina K-line, Eastmoney K-line.

Tongdaxin data needs `mootdx`. Without it, the app falls back to HTTP K-line sources.

```bash
pip install mootdx
```

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
