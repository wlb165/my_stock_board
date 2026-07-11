from bisect import bisect_right
from calendar import monthrange
from datetime import date, datetime, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen
import json
import re
import time


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
SINA_FINANCE_URL = "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022"
EASTMONEY_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
BAIDU_KLINE_URL = "https://finance.pae.baidu.com/selfselect/getstockquotation"

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


OPERATING_CASH_FLOW_FIELDS = [
    "\u7ecf\u8425\u6d3b\u52a8\u4ea7\u751f\u7684\u73b0\u91d1\u6d41\u91cf\u51c0\u989d",
    "\u7ecf\u8425\u6d3b\u52a8\u73b0\u91d1\u6d41\u91cf\u51c0\u989d",
]
CAPEX_FIELDS = [
    "\u8d2d\u5efa\u56fa\u5b9a\u8d44\u4ea7\u3001\u65e0\u5f62\u8d44\u4ea7\u548c\u5176\u4ed6\u957f\u671f\u8d44\u4ea7\u6240\u652f\u4ed8\u7684\u73b0\u91d1",
    "\u8d2d\u5efa\u56fa\u5b9a\u8d44\u4ea7\u3001\u65e0\u5f62\u8d44\u4ea7\u548c\u5176\u4ed6\u957f\u671f\u8d44\u4ea7\u652f\u4ed8\u7684\u73b0\u91d1",
]
NET_PROFIT_FIELDS = ["净利润", "归属于母公司所有者的净利润"]
EQUITY_FIELDS = ["所有者权益合计", "归属于母公司所有者权益合计"]


def cash_flow_value(items, names):
    return field_value(items, ("first", names))


def report_year(report_date):
    return report_date[:4]


def quarterly_from_cumulative(reports, value_fn):
    ordered = sorted(reports, key=lambda item: item["report_date"])
    previous_by_year = {}
    quarters = []
    for report in ordered:
        date = report["report_date"]
        year = report_year(date)
        cumulative = value_fn(report["items"])
        previous = previous_by_year.get(year, 0.0)
        quarter_value = cumulative - previous
        previous_by_year[year] = cumulative
        quarters.append({"date": date, "value": quarter_value})
    return quarters


def build_ttm_free_cash_flow_points(cash_reports):
    operating_quarters = quarterly_from_cumulative(
        cash_reports,
        lambda items: cash_flow_value(items, OPERATING_CASH_FLOW_FIELDS),
    )
    capex_quarters = quarterly_from_cumulative(
        cash_reports,
        lambda items: cash_flow_value(items, CAPEX_FIELDS),
    )
    quarterly_fcf = []
    for operating, capex in zip(operating_quarters, capex_quarters):
        quarterly_fcf.append({"date": operating["date"], "value": operating["value"] - capex["value"]})

    points = []
    for index in range(3, len(quarterly_fcf)):
        window = quarterly_fcf[index - 3 : index + 1]
        points.append({"date": quarterly_fcf[index]["date"], "ttm_fcf": sum(item["value"] for item in window)})
    return points


def dcf_value(base_fcf, growth_rate, discount_rate, perpetual_growth_rate, forecast_years):
    if discount_rate <= perpetual_growth_rate:
        raise ValueError("discount_rate must be greater than perpetual_growth_rate")
    value = 0.0
    final_fcf = base_fcf
    for year in range(1, forecast_years + 1):
        final_fcf = base_fcf * ((1 + growth_rate) ** year)
        value += final_fcf / ((1 + discount_rate) ** year)
    terminal_value = final_fcf * (1 + perpetual_growth_rate) / (discount_rate - perpetual_growth_rate)
    value += terminal_value / ((1 + discount_rate) ** forecast_years)
    return value


def valuation_zone(price, conservative, neutral, optimistic):
    if price < conservative:
        return "\u4f4e\u4e8e\u4fdd\u5b88\u4f30\u503c"
    if price < neutral:
        return "\u4fdd\u5b88\u533a\u95f4"
    if price <= optimistic:
        return "\u5408\u7406\u533a\u95f4"
    return "\u9ad8\u4e8e\u4e50\u89c2\u4f30\u503c"

def closest_close_on_or_before(prices, report_date):
    ordered = sorted(prices, key=lambda item: item["date"])
    dates = [item["date"] for item in ordered]
    index = bisect_right(dates, report_date) - 1
    if index < 0:
        return 0.0
    return parse_number(ordered[index].get("close"))


def sample_weekly_prices(prices):
    weekly = {}
    for item in sorted(prices, key=lambda row: row["date"]):
        close = parse_number(item.get("close"))
        if not close:
            continue
        date = item["date"]
        week_key = datetime.strptime(date, "%Y-%m-%d").isocalendar()[:2]
        weekly[week_key] = {"date": date, "price": round(close, 2)}
    return list(weekly.values())


MAX_COMPARISON_STOCKS = 6
COMPARISON_PERIOD_DAYS = {"6m": 181, "1y": 365, "3y": 365 * 3, "5y": 365 * 5}


def parse_stock_codes(raw_codes, limit=MAX_COMPARISON_STOCKS):
    codes = []
    errors = []
    for code in re.split(r"[,\s]+", raw_codes or ""):
        if not code:
            continue
        if not re.fullmatch(r"\d{6}", code):
            errors.append({"code": code, "message": "Invalid stock code"})
            continue
        if code in codes:
            continue
        if len(codes) >= limit:
            errors.append({"code": code, "message": f"Only the first {limit} stock codes are used"})
            continue
        codes.append(code)
    return codes, errors


def normalize_comparison_period(period):
    return period if period in COMPARISON_PERIOD_DAYS else "1y"


def calendar_months_before(current, months):
    target_month = current.month - months
    target_year = current.year + (target_month - 1) // 12
    target_month = (target_month - 1) % 12 + 1
    target_day = min(current.day, monthrange(target_year, target_month)[1])
    return date(target_year, target_month, target_day)


def period_start_date(period, today=None):
    current = today or date.today()
    period = normalize_comparison_period(period)
    months = {"6m": 6, "1y": 12, "3y": 36, "5y": 60}[period]
    return calendar_months_before(current, months).isoformat()


def filter_prices_from(prices, start_date):
    return [item for item in prices if item.get("date", "") >= start_date]


def build_comparison_series(code, name, weekly_prices):
    prices = []
    for item in sorted(weekly_prices, key=lambda row: row["date"]):
        price = parse_number(item.get("price"))
        if price > 0:
            prices.append({"date": item["date"], "price": round(price, 2)})
    if not prices:
        raise ValueError("No price data")

    first_price = prices[0]["price"]
    points = []
    for item in prices:
        change_pct = (item["price"] - first_price) / first_price * 100
        points.append({"date": item["date"], "price": item["price"], "change_pct": round(change_pct, 2)})
    return {
        "code": code,
        "name": name,
        "points": points,
        "summary": {
            "latest_price": prices[-1]["price"],
            "period_change_pct": round((prices[-1]["price"] - first_price) / first_price * 100, 2),
            "period_high": max(item["price"] for item in prices),
            "period_low": min(item["price"] for item in prices),
            "point_count": len(prices),
        },
    }


def build_revenue_price_payload(code, name, reports, prices):
    revenue_points = []
    for report in sorted(reports, key=lambda item: item["report_date"]):
        revenue = revenue_value(report["items"])
        if not revenue:
            continue
        revenue_points.append(
            {
                "date": report["report_date"],
                "annualized_revenue_yi": round(to_yi(revenue) * annualization_factor(report["report_date"]), 2),
            }
        )
    return {
        "company": {"code": code, "name": name or code},
        "revenue_points": revenue_points,
        "price_points": sample_weekly_prices(prices),
        "price_source": "eastmoney_qfq",
        "price_adjustment": "front_adjusted",
    }


def is_valuation_path(path):
    return path == "/api/valuation"


def parse_rate(params, key, default):
    return float(params.get(key, [str(default)])[0] or default)


def parse_valuation_assumptions(params):
    assumptions = {
        "cash_flow_basis": "ttm_fcf",
        "forecast_years": int(params.get("forecast_years", ["5"])[0] or 5),
        "growth_conservative": parse_rate(params, "growth_conservative", 0.05),
        "growth_neutral": parse_rate(params, "growth_neutral", 0.10),
        "growth_optimistic": parse_rate(params, "growth_optimistic", 0.15),
        "discount_rate": parse_rate(params, "discount_rate", 0.10),
        "perpetual_growth_rate": parse_rate(params, "perpetual_growth_rate", 0.025),
        "safety_margin": parse_rate(params, "safety_margin", 0.25),
        "alignment": "latest_share_count",
    }
    dcf_value(
        1.0,
        assumptions["growth_neutral"],
        assumptions["discount_rate"],
        assumptions["perpetual_growth_rate"],
        assumptions["forecast_years"],
    )
    return assumptions


SHARE_CAPITAL_FIELDS = ["实收资本（或股本）", "实收资本(或股本)", "股本"]


def build_share_points_from_balance_reports(balance_reports):
    share_points = []
    for report in sorted(balance_reports, key=lambda item: item["report_date"]):
        total_shares = field_value(report["items"], ("first", SHARE_CAPITAL_FIELDS))
        if total_shares:
            share_points.append(
                {
                    "date": report["report_date"],
                    "total_shares": total_shares,
                    "share_count_source": "balance_sheet_share_capital",
                }
            )
    return share_points


def closest_share_on_or_before(share_points, report_date):
    ordered = sorted(share_points, key=lambda item: item["date"])
    dates = [item["date"] for item in ordered]
    index = bisect_right(dates, report_date) - 1
    if index < 0:
        return None
    return ordered[index]


def closest_report_on_or_before(reports, report_date):
    ordered = sorted(reports, key=lambda item: item["report_date"])
    dates = [item["report_date"] for item in ordered]
    index = bisect_right(dates, report_date) - 1
    if index < 0:
        return None
    return ordered[index]


def latest_share_point(share_points):
    if not share_points:
        return None
    return sorted(share_points, key=lambda item: item["date"])[-1]


def ttm_value_by_date(reports, value_fn):
    quarters = quarterly_from_cumulative(reports, value_fn)
    values = {}
    for index in range(3, len(quarters)):
        window = quarters[index - 3 : index + 1]
        values[quarters[index]["date"]] = sum(item["value"] for item in window)
    return values


def metric_ratio(numerator, denominator):
    return round(numerator / denominator, 2) if numerator is not None and denominator else None


def net_profit_value(items):
    return field_value(items, ("first", NET_PROFIT_FIELDS))


def equity_value(items):
    return field_value(items, ("first", EQUITY_FIELDS))


def build_valuation_payload(code, name, income_reports, balance_reports, cash_reports, prices, share_points, assumptions):
    fcf_points = build_ttm_free_cash_flow_points(cash_reports)
    revenue_ttm = ttm_value_by_date(income_reports, revenue_value)
    net_profit_ttm = ttm_value_by_date(income_reports, net_profit_value)
    share_point = latest_share_point(share_points)
    total_shares = parse_number(share_point.get("total_shares")) if share_point else None
    points = []

    for fcf_point in fcf_points:
        date = fcf_point["date"]
        if not total_shares:
            continue
        price = closest_close_on_or_before(prices, date)
        ttm_fcf = fcf_point["ttm_fcf"]
        conservative = dcf_value(
            ttm_fcf,
            assumptions["growth_conservative"],
            assumptions["discount_rate"],
            assumptions["perpetual_growth_rate"],
            assumptions["forecast_years"],
        ) / total_shares
        neutral = dcf_value(
            ttm_fcf,
            assumptions["growth_neutral"],
            assumptions["discount_rate"],
            assumptions["perpetual_growth_rate"],
            assumptions["forecast_years"],
        ) / total_shares
        optimistic = dcf_value(
            ttm_fcf,
            assumptions["growth_optimistic"],
            assumptions["discount_rate"],
            assumptions["perpetual_growth_rate"],
            assumptions["forecast_years"],
        ) / total_shares
        market_cap = price * total_shares if price else None
        balance_report = closest_report_on_or_before(balance_reports, date)
        equity = equity_value(balance_report["items"]) if balance_report else 0.0

        points.append(
            {
                "date": date,
                "price": round(price, 2) if price else None,
                "market_cap_yi": round(market_cap / 100000000, 2) if market_cap is not None else None,
                "ttm_fcf": round(ttm_fcf, 2),
                "total_shares": total_shares,
                "share_count_date": share_point.get("date"),
                "share_count_source": share_point.get(
                    "share_count_source",
                    share_point.get("source", "provided_share_points"),
                ),
                "conservative_value": round(conservative, 2),
                "neutral_value": round(neutral, 2),
                "optimistic_value": round(optimistic, 2),
                "safety_buy_price": round(neutral * (1 - assumptions["safety_margin"]), 2),
                "safety_price": round(neutral * (1 - assumptions["safety_margin"]), 2),
                "zone": valuation_zone(price, conservative, neutral, optimistic) if price else None,
                "pe_ttm": metric_ratio(market_cap, net_profit_ttm.get(date)),
                "pb": metric_ratio(market_cap, equity),
                "ps_ttm": metric_ratio(market_cap, revenue_ttm.get(date)),
            }
        )

    price_points = sample_weekly_prices(prices)
    latest = points[-1] if points else {}
    latest_price = price_points[-1] if price_points else {}
    current_price = latest_price.get("price", latest.get("price"))
    latest_total_shares = parse_number(latest.get("total_shares"))
    market_cap_yi = (
        round(current_price * latest_total_shares / 100000000, 2)
        if current_price and latest_total_shares
        else latest.get("market_cap_yi")
    )
    neutral_value = latest.get("neutral_value")
    discount_to_neutral_pct = (
        round((neutral_value - current_price) / neutral_value * 100, 2)
        if current_price and neutral_value
        else None
    )
    return {
        "company": {"code": code, "name": name or code},
        "assumptions": assumptions,
        "points": points,
        "price_points": price_points,
        "summary": {
            "date": latest.get("date"),
            "price": current_price,
            "current_price": current_price,
            "current_price_date": latest_price.get("date", latest.get("date")),
            "market_cap_yi": market_cap_yi,
            "neutral_value": latest.get("neutral_value"),
            "safety_buy_price": latest.get("safety_buy_price"),
            "discount_to_neutral_pct": discount_to_neutral_pct,
            "pe_ttm": latest.get("pe_ttm"),
            "pb": latest.get("pb"),
            "ps_ttm": latest.get("ps_ttm"),
        },
        "share_count_source": latest.get("share_count_source", "unavailable"),
        "share_count_date": latest.get("share_count_date"),
        "share_count_basis": "latest_share_count",
        "price_adjustment": "front_adjusted",
        "cash_flow_basis": assumptions["cash_flow_basis"],
        "alignment": assumptions["alignment"],
    }


def derive_share_points_from_market_cap(prices):
    share_points = []
    for item in prices:
        close = parse_number(item.get("close"))
        market_cap = parse_number(item.get("market_cap") or item.get("total_market_cap"))
        if close and market_cap:
            share_points.append(
                {
                    "date": item["date"],
                    "total_shares": market_cap / close,
                    "source": "market_cap_divided_by_close",
                }
            )
    return share_points


def stock_prefix(code):
    return "sh" if code.startswith(("6", "9")) else "sz"


def should_redirect_to_static_index(path):
    return path == "/"


def is_revenue_price_path(path):
    return path in ("/api/revenue-price", "/api/revenue-market-cap")


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


def fetch_cash_flow_reports(code, limit=32):
    return fetch_sina_financial_report(code, "llb", limit)


def fetch_eastmoney_daily_closes(code, start_date, end_date, adjustment):
    market = "1" if code.startswith(("6", "9")) else "0"
    params = urlencode(
        {
            "secid": f"{market}.{code}",
            "klt": "101",
            "fqt": adjustment,
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


def fetch_eastmoney_front_adjusted_daily_closes(code, start_date, end_date):
    return fetch_eastmoney_daily_closes(code, start_date, end_date, "1")


def fetch_eastmoney_unadjusted_daily_closes(code, start_date, end_date):
    return fetch_eastmoney_daily_closes(code, start_date, end_date, "0")


def fetch_baidu_daily_closes(code, start_date, end_date):
    params = urlencode(
        {
            "all": "1",
            "isIndex": "false",
            "isBk": "false",
            "isBlock": "false",
            "isFutures": "false",
            "isStock": "true",
            "newFormat": "1",
            "group": "quotation_kline_ab",
            "finClientType": "pc",
            "code": code,
            "start_time": start_date.replace("-", ""),
            "ktype": "1",
        }
    )
    request = Request(
        f"{BAIDU_KLINE_URL}?{params}",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/vnd.finance-web.v1+json",
            "Origin": "https://gushitong.baidu.com",
            "Referer": "https://gushitong.baidu.com/",
        },
    )
    data = json.loads(read_url(request, timeout=15))
    if "ResultCode" in data and str(data.get("ResultCode")) != "0":
        raise RuntimeError(f"baidu_kline source returned ResultCode {data.get('ResultCode')}")
    market_data = ((data.get("Result") or {}).get("newMarketData") or {})
    keys = market_data.get("keys") or []
    rows = (market_data.get("marketData") or "").split(";")
    date_index = keys.index("time") if "time" in keys else 1
    close_index = keys.index("close") if "close" in keys else 3
    prices = []
    for row in rows:
        parts = row.split(",")
        if len(parts) <= max(date_index, close_index):
            continue
        date = parts[date_index]
        close = parse_number(parts[close_index])
        if start_date <= date <= end_date and close:
            prices.append({"date": date, "close": close})
    return prices

def fetch_mootdx_daily_closes(code, start_date, end_date):
    try:
        from mootdx.quotes import Quotes
    except Exception as exc:
        raise RuntimeError(f"mootdx source unavailable: {exc}") from exc

    client = Quotes.factory(market="std", timeout=5)
    bars = client.bars(symbol=code, category=4, offset=3000)
    if hasattr(bars, "reset_index"):
        records = bars.reset_index().to_dict("records")
    elif hasattr(bars, "to_dict"):
        records = bars.to_dict("records")
    else:
        records = list(bars or [])

    prices = []
    for record in records:
        date_value = record.get("datetime") or record.get("date") or record.get("time")
        date = str(date_value)[:10] if date_value else ""
        close = parse_number(record.get("close"))
        if start_date <= date <= end_date and close:
            prices.append({"date": date, "close": close})
    return prices


def fetch_resilient_daily_closes(code, start_date, end_date):
    errors = []
    sources = [
        ("eastmoney_qfq", fetch_front_adjusted_daily_closes),
        ("mootdx", fetch_mootdx_daily_closes),
        ("baidu_kline", fetch_baidu_daily_closes),
    ]
    for source_name, fetcher in sources:
        try:
            prices = fetcher(code, start_date, end_date)
        except Exception as exc:
            errors.append(f"{source_name}: {exc}")
            continue
        if prices:
            return prices
        errors.append(f"{source_name}: returned no daily close data")
    raise RuntimeError("daily close sources failed: " + "; ".join(errors))


def fetch_valuation_daily_closes(code, start_date, end_date):
    errors = []
    sources = [
        ("eastmoney_qfq", fetch_front_adjusted_daily_closes),
        ("mootdx", fetch_mootdx_daily_closes),
        ("baidu_kline", fetch_baidu_daily_closes),
    ]
    for source_name, fetcher in sources:
        try:
            prices = fetcher(code, start_date, end_date)
        except Exception as exc:
            errors.append(f"{source_name}: {exc}")
            continue
        if prices:
            return prices
        errors.append(f"{source_name}: returned no daily close data")
    raise RuntimeError("valuation daily close sources failed: " + "; ".join(errors))

def fetch_front_adjusted_daily_closes(code, start_date, end_date):
    try:
        prices = fetch_eastmoney_front_adjusted_daily_closes(code, start_date, end_date)
    except Exception as exc:
        raise RuntimeError(f"eastmoney_qfq source failed: {exc}") from exc
    if not prices:
        raise RuntimeError("eastmoney_qfq source returned no daily close data")
    return prices


def fetch_unadjusted_daily_closes(code, start_date, end_date):
    try:
        prices = fetch_eastmoney_unadjusted_daily_closes(code, start_date, end_date)
    except Exception as exc:
        raise RuntimeError(f"eastmoney_unadjusted source failed: {exc}") from exc
    if not prices:
        raise RuntimeError("eastmoney_unadjusted source returned no daily close data")
    return prices


def fetch_revenue_price(code, name, limit=32, today=None):
    try:
        reports = fetch_income_reports(code, limit)
    except Exception as exc:
        raise RuntimeError(f"income report source failed: {exc}") from exc
    if not reports:
        raise ValueError("未取到利润表数据")
    first_report_date = min(report["report_date"] for report in reports)
    start_date = (datetime.strptime(first_report_date, "%Y-%m-%d") - timedelta(days=10)).strftime("%Y-%m-%d")
    today = today or datetime.now().strftime("%Y-%m-%d")
    end_date = today
    try:
        prices = fetch_resilient_daily_closes(code, start_date, end_date)
        prices = [item for item in prices if item.get("date", "") < today]
    except Exception as exc:
        raise RuntimeError(f"daily close source failed: {exc}") from exc
    return build_revenue_price_payload(code, name, reports, prices)


def fetch_valuation(code, name, assumptions, limit=32, today=None):
    try:
        income_reports = fetch_income_reports(code, limit)
        balance_reports = fetch_balance_sheet(code, limit)
        cash_reports = fetch_cash_flow_reports(code, limit)
    except Exception as exc:
        raise RuntimeError(f"financial report source failed: {exc}") from exc
    report_dates = [report["report_date"] for report in income_reports + balance_reports + cash_reports]
    if not report_dates:
        raise ValueError("未取到估值所需财报数据")
    start_date = (datetime.strptime(min(report_dates), "%Y-%m-%d") - timedelta(days=10)).strftime("%Y-%m-%d")
    today = today or datetime.now().strftime("%Y-%m-%d")
    try:
        prices = fetch_valuation_daily_closes(code, start_date, today)
        prices = [item for item in prices if item.get("date", "") < today]
    except Exception as exc:
        raise RuntimeError(f"daily close source failed: {exc}") from exc
    balance_share_points = build_share_points_from_balance_reports(balance_reports)
    market_cap_share_points = derive_share_points_from_market_cap(prices)
    share_points = balance_share_points or market_cap_share_points
    payload = build_valuation_payload(
        code,
        name,
        income_reports,
        balance_reports,
        cash_reports,
        prices,
        share_points,
        assumptions,
    )
    if not share_points:
        payload["share_count_source"] = "unavailable"
    return payload


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
        if is_valuation_path(parsed.path):
            self.handle_valuation(parsed.query)
            return
        if is_revenue_price_path(parsed.path):
            self.handle_revenue_price(parsed.query)
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

    def handle_revenue_price(self, query):
        params = parse_qs(query)
        code = params.get("code", ["002594"])[0].strip()
        name = params.get("name", ["比亚迪"])[0].strip()
        try:
            payload = fetch_revenue_price(code, name)
            self.write_json(payload)
        except Exception as exc:
            self.write_json({"error": str(exc) or exc.__class__.__name__}, status=502)

    def handle_valuation(self, query):
        params = parse_qs(query)
        code = params.get("code", ["002594"])[0].strip()
        name = params.get("name", ["比亚迪"])[0].strip()
        try:
            assumptions = parse_valuation_assumptions(params)
            payload = fetch_valuation(code, name, assumptions)
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
