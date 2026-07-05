from bisect import bisect_right
from datetime import datetime, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen
import json
import socket
import time

try:
    from mootdx.quotes import Quotes
except Exception:
    Quotes = None


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
SINA_FINANCE_URL = "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022"
SINA_KLINE_URL = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
EASTMONEY_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q="
TDX_SERVERS = [
    ("119.97.185.59", 7709),
    ("124.70.133.119", 7709),
    ("116.205.183.150", 7709),
    ("123.60.73.44", 7709),
    ("116.205.163.254", 7709),
    ("121.36.225.169", 7709),
    ("123.60.70.228", 7709),
    ("124.71.9.153", 7709),
    ("110.41.147.114", 7709),
    ("124.71.187.122", 7709),
]


ASSET_GROUPS = [
    ("现金", ["货币资金"]),
    ("应收款", ["应收账款", "应收票据", "应收款项融资"]),
    ("预付款", ["预付款项"]),
    ("存货", ["存货"]),
    ("其它流动", ["其他流动资产"]),
    ("长期投资", ["长期股权投资", "其他权益工具投资", "其他非流动金融资产"]),
    ("固定资产", [("first", ["固定资产净额", "固定资产及清理合计", "固定资产净值", "固定资产"]), "在建工程"]),
    ("无形&商誉", ["无形资产", "商誉"]),
    ("其它固定", ["其他非流动资产"]),
]

LIABILITY_GROUPS = [
    ("短期借款", ["短期借款"]),
    ("应付款", ["应付账款", "应付票据"]),
    ("预收款", ["预收款项", "合同负债"]),
    ("薪酬&税", ["应付职工薪酬", "应交税费"]),
    ("其它流动", ["其他流动负债"]),
    ("长期借款", ["长期借款"]),
    ("其它非流动", ["应付债券", "租赁负债", "长期应付款", "其他非流动负债"]),
]


def parse_number(value):
    if value in (None, ""):
        return 0.0
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return 0.0


def to_yi(value):
    return round(parse_number(value) / 100000000, 2)


def read_url(request, timeout=15, retries=2, encoding="utf-8"):
    last_error = None
    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.read().decode(encoding, errors="ignore")
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.3 * (attempt + 1))
    raise last_error


def field_value(items, field):
    if isinstance(field, tuple) and field[0] == "first":
        for name in field[1]:
            value = parse_number(items.get(name))
            if value:
                return value
        return 0.0
    return parse_number(items.get(field))


def sum_fields(items, names):
    return sum(field_value(items, name) for name in names)


def grouped_items(items, groups):
    return [{"label": label, "value": to_yi(sum_fields(items, names))} for label, names in groups]


def normalize_sina_reports(data, limit):
    report_list = (
        data.get("result", {})
        .get("data", {})
        .get("report_list", {})
        or {}
    )
    reports = []
    for period in sorted(report_list.keys(), reverse=True)[:limit]:
        rows = report_list[period].get("data", []) or []
        items = {
            row.get("item_title"): parse_number(row.get("item_value"))
            for row in rows
            if row.get("item_title") and row.get("item_value") not in (None, "")
        }
        reports.append(
            {
                "report_date": f"{period[:4]}-{period[4:6]}-{period[6:8]}",
                "items": items,
            }
        )
    return reports


def annualization_factor(report_date):
    month_day = report_date[5:]
    if month_day == "03-31":
        return 4
    if month_day == "06-30":
        return 2
    if month_day == "09-30":
        return 4 / 3
    return 1


def revenue_value(items):
    return field_value(items, ("first", ["营业总收入", "营业收入"]))


def closest_close_on_or_before(prices, report_date):
    ordered = sorted(prices, key=lambda item: item["date"])
    dates = [item["date"] for item in ordered]
    index = bisect_right(dates, report_date) - 1
    if index < 0:
        return 0.0
    return parse_number(ordered[index].get("close"))


def build_revenue_market_cap_payload(code, name, reports, prices, total_shares_yi):
    points = []
    for report in sorted(reports, key=lambda item: item["report_date"]):
        revenue = revenue_value(report["items"])
        if not revenue:
            continue
        close = closest_close_on_or_before(prices, report["report_date"])
        points.append(
            {
                "date": report["report_date"],
                "annualized_revenue_yi": round(to_yi(revenue) * annualization_factor(report["report_date"]), 2),
                "market_cap_yi": round(close * total_shares_yi, 2) if close and total_shares_yi else 0.0,
            }
        )
    return {"company": {"code": code, "name": name or code}, "points": points}


def stock_prefix(code):
    return "sh" if code.startswith(("6", "9")) else "sz"


def should_redirect_to_static_index(path):
    return path == "/"


def fetch_balance_sheet(code, limit=8):
    paper_code = f"{stock_prefix(code)}{code}"
    params = urlencode(
        {
            "paperCode": paper_code,
            "source": "fzb",
            "type": "0",
            "page": "1",
            "num": str(limit),
        }
    )
    request = Request(f"{SINA_FINANCE_URL}?{params}", headers={"User-Agent": UA})
    data = json.loads(read_url(request, timeout=15))
    reports = normalize_sina_reports(data, limit)
    if not reports:
        raise ValueError("未取到资产负债表数据")
    return reports


def fetch_sina_financial_report(code, report_type, limit=8):
    paper_code = f"{stock_prefix(code)}{code}"
    params = urlencode(
        {
            "paperCode": paper_code,
            "source": report_type,
            "type": "0",
            "page": "1",
            "num": str(limit),
        }
    )
    request = Request(f"{SINA_FINANCE_URL}?{params}", headers={"User-Agent": UA})
    data = json.loads(read_url(request, timeout=15))
    reports = normalize_sina_reports(data, limit)
    if not reports:
        raise ValueError("未取到财报数据")
    return reports


def fetch_income_reports(code, limit=32):
    return fetch_sina_financial_report(code, "lrb", limit)


def fetch_current_quote(code):
    prefixed = f"{stock_prefix(code)}{code}"
    request = Request(TENCENT_QUOTE_URL + prefixed, headers={"User-Agent": UA})
    data = read_url(request, timeout=10, encoding="gbk")
    if '"' not in data:
        raise ValueError("未取到腾讯行情数据")
    vals = data.split('"')[1].split("~")
    price = parse_number(vals[3]) if len(vals) > 3 else 0.0
    mcap_yi = parse_number(vals[44]) if len(vals) > 44 else 0.0
    return {"price": price, "mcap_yi": mcap_yi, "total_shares_yi": (mcap_yi / price) if price else 0.0}


def probe_tdx_server(ip, port, timeout=2.0):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def tdx_client():
    if Quotes is None:
        raise RuntimeError("mootdx is not installed")
    for server in TDX_SERVERS:
        if probe_tdx_server(*server):
            return Quotes.factory(market="std", server=server)
    return Quotes.factory(market="std", bestip=True)


def normalize_trade_date(value):
    text = str(value)[:10]
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text


def fetch_tdx_daily_closes(code, start_date, end_date):
    client = tdx_client()
    rows = client.bars(symbol=code, frequency=9, offset=3000)
    prices = []
    for _, row in rows.iterrows():
        date = normalize_trade_date(row.get("date") or row.get("datetime"))
        close = parse_number(row.get("close"))
        if start_date <= date <= end_date and close:
            prices.append({"date": date, "close": close})
    return prices


def fetch_sina_daily_closes(code, start_date, end_date):
    params = urlencode(
        {
            "symbol": f"{stock_prefix(code)}{code}",
            "scale": "240",
            "ma": "no",
            "datalen": "3000",
        }
    )
    request = Request(
        f"{SINA_KLINE_URL}?{params}",
        headers={"User-Agent": UA, "Referer": "https://finance.sina.com.cn/"},
    )
    rows = json.loads(read_url(request, timeout=15))
    return [
        {"date": row["day"], "close": parse_number(row.get("close"))}
        for row in rows
        if start_date <= row.get("day", "") <= end_date and parse_number(row.get("close"))
    ]


def fetch_eastmoney_daily_closes(code, start_date, end_date):
    market = "1" if code.startswith(("6", "9")) else "0"
    params = urlencode(
        {
            "secid": f"{market}.{code}",
            "klt": "101",
            "fqt": "1",
            "beg": start_date.replace("-", ""),
            "end": end_date.replace("-", ""),
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        }
    )
    request = Request(
        f"{EASTMONEY_KLINE_URL}?{params}",
        headers={"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"},
    )
    data = json.loads(read_url(request, timeout=15))
    klines = (data.get("data") or {}).get("klines") or []
    prices = []
    for line in klines:
        parts = line.split(",")
        if len(parts) >= 3:
            prices.append({"date": parts[0], "close": parse_number(parts[2])})
    return prices


def fetch_daily_closes(code, start_date, end_date):
    errors = []
    for fetcher in (fetch_tdx_daily_closes, fetch_sina_daily_closes, fetch_eastmoney_daily_closes):
        try:
            prices = fetcher(code, start_date, end_date)
            if prices:
                return prices
        except Exception as exc:
            errors.append(f"{fetcher.__name__}: {exc}")
    raise RuntimeError("; ".join(errors) or "No daily close data")


def fetch_revenue_market_cap(code, name, limit=32):
    try:
        reports = fetch_income_reports(code, limit)
    except Exception as exc:
        raise RuntimeError(f"income report source failed: {exc}") from exc
    if not reports:
        raise ValueError("未取到利润表数据")
    first_report_date = min(report["report_date"] for report in reports)
    start_date = (datetime.strptime(first_report_date, "%Y-%m-%d") - timedelta(days=10)).strftime("%Y-%m-%d")
    end_date = max(report["report_date"] for report in reports)
    try:
        quote = fetch_current_quote(code)
    except Exception as exc:
        raise RuntimeError(f"current quote source failed: {exc}") from exc
    try:
        prices = fetch_daily_closes(code, start_date, end_date)
    except Exception as exc:
        raise RuntimeError(f"daily close source failed: {exc}") from exc
    return build_revenue_market_cap_payload(code, name, reports, prices, quote["total_shares_yi"])


def build_dashboard_payload(code, name, reports, index):
    safe_index = max(0, min(index, len(reports) - 1))
    current = reports[safe_index]
    items = current["items"]
    assets_total = parse_number(items.get("资产总计"))
    liabilities_total = parse_number(items.get("负债合计"))
    equity_total = parse_number(items.get("所有者权益合计"))
    if not equity_total and assets_total and liabilities_total:
        equity_total = assets_total - liabilities_total
    debt_ratio = (liabilities_total / assets_total * 100) if assets_total else 0

    return {
        "company": {"code": code, "name": name or code},
        "period": {
            "current": current["report_date"],
            "index": safe_index,
            "total": len(reports),
            "has_previous": safe_index + 1 < len(reports),
            "has_next": safe_index > 0,
        },
        "assets": grouped_items(items, ASSET_GROUPS),
        "liabilities": grouped_items(items, LIABILITY_GROUPS),
        "summary": {
            "total_assets_yi": to_yi(assets_total),
            "total_liabilities_yi": to_yi(liabilities_total),
            "equity_yi": to_yi(equity_total),
            "debt_ratio_pct": round(debt_ratio, 2),
        },
    }


class StockBoardHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/balance-sheet":
            self.handle_balance_sheet(parsed.query)
            return
        if parsed.path == "/api/revenue-market-cap":
            self.handle_revenue_market_cap(parsed.query)
            return
        if should_redirect_to_static_index(parsed.path):
            self.send_response(302)
            self.send_header("Location", "/static/index.html")
            self.end_headers()
            return
        super().do_GET()

    def translate_path(self, path):
        if path.startswith("/static/"):
            return str(ROOT / path.lstrip("/"))
        return str(STATIC_DIR / "index.html")

    def handle_balance_sheet(self, query):
        params = parse_qs(query)
        code = params.get("code", ["002594"])[0].strip()
        name = params.get("name", ["比亚迪"])[0].strip()
        index = int(params.get("index", ["0"])[0] or 0)
        try:
            reports = fetch_balance_sheet(code)
            payload = build_dashboard_payload(code, name, reports, index)
            self.write_json(payload)
        except Exception as exc:
            self.write_json({"error": str(exc) or exc.__class__.__name__}, status=502)

    def handle_revenue_market_cap(self, query):
        params = parse_qs(query)
        code = params.get("code", ["002594"])[0].strip()
        name = params.get("name", ["比亚迪"])[0].strip()
        try:
            payload = fetch_revenue_market_cap(code, name)
            self.write_json(payload)
        except Exception as exc:
            self.write_json({"error": str(exc) or exc.__class__.__name__}, status=502)

    def write_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 8765), StockBoardHandler)
    print("资产负债表看板: http://127.0.0.1:8765")
    server.serve_forever()


if __name__ == "__main__":
    main()
