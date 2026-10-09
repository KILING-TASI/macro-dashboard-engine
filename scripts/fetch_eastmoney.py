#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_eastmoney.py — 东方财富宏观数据抓取

数据源: https://datacenter-web.eastmoney.com/api/data/v1/get
必须携带 Referer: https://data.eastmoney.com/

用法:
    python3 fetch_eastmoney.py --out data.json            # 抓取全部指标
    python3 fetch_eastmoney.py --indicator cpi --out x.json

输出: JSON 结构
{
  "source": "eastmoney",
  "as_of": "2026-08",
  "indicators": {
     "cpi": {"name":"CPI同比", "unit":"%", "dates":[...], "values":[...],
             "latest": 0.8, "prev": 0.5, "yoy": null, "mom": 0.3}
     ...
  },
  "errors": ["..."]
}
"""
import argparse
import json
import sys
import urllib.request
import urllib.parse
from datetime import datetime

BASE = "https://datacenter-web.eastmoney.com/api/data/v1/get"
HEADERS = {
    "Referer": "https://data.eastmoney.com/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
}

# 指标配置: key -> (reportName, {输出字段: 原始字段}, 名称, 单位, 取样条数)
INDICATORS = {
    "gdp":   ("RPT_ECONOMY_GDP", {"value": "DOMESTICL_PRODUCT_BASE", "yoy": "SUM_SAME"},
              "GDP总量", "亿元", 20),
    "cpi":   ("RPT_ECONOMY_CPI", {"value": "NATIONAL_SAME", "mom": "NATIONAL_SEQUENTIAL"},
              "CPI同比", "%", 36),
    "ppi":   ("RPT_ECONOMY_PPI", {"value": "BASE_SAME"}, "PPI同比", "%", 36),
    "pmi":   ("RPT_ECONOMY_PMI", {"value": "MAKE_INDEX", "non_mfg": "NMAKE_INDEX"},
              "制造业PMI", "指数", 36),
    "retail": ("RPT_ECONOMY_TOTAL_RETAIL", {"value": "RETAIL_TOTAL", "yoy": "RETAIL_TOTAL_SAME"},
               "社会消费品零售总额", "亿元", 36),
    "m0":    ("RPT_ECONOMY_CURRENCY_SUPPLY", {"value": "BASIC_CURRENCY", "yoy": "BASIC_CURRENCY_SAME"},
              "M0", "亿元", 36),
    "m1":    ("RPT_ECONOMY_CURRENCY_SUPPLY", {"value": "CURRENCY", "yoy": "CURRENCY_SAME"},
              "M1", "亿元", 36),
    "m2":    ("RPT_ECONOMY_CURRENCY_SUPPLY", {"value": "FREE_CASH", "yoy": "FREE_CASH_SAME"},
              "M2", "亿元", 36),
    "house": ("RPT_ECONOMY_HOUSE_PRICE", {"value": "FIRST_COMHOUSE_SAME"},
              "70城新房价格同比", "指数", 36),
}


def _http_get(url, timeout=20):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_report(report_name, page_size=40):
    """调用东财接口，返回 data 列表（按时间倒序）。"""
    params = {
        "reportName": report_name,
        "columns": "ALL",
        "pageSize": str(page_size),
        "pageNumber": "1",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
    }
    url = BASE + "?" + urllib.parse.urlencode(params)
    payload = _http_get(url)
    if not payload.get("success"):
        raise RuntimeError(payload.get("message", "eastmoney api error"))
    return (payload.get("result") or {}).get("data") or []


def _num(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def build_series(rows, field_map, limit):
    """从原始行构建时间序列（升序）。"""
    dates, series = [], {k: [] for k in field_map}
    for row in reversed(rows[:limit]):
        rd = row.get("REPORT_DATE", "")
        if not rd:
            continue
        dates.append(rd[:7])  # YYYY-MM
        for key, src in field_map.items():
            series[key].append(_num(row.get(src)))
    return dates, series


def fetch_house_price(limit=36):
    """房价专项：原始数据按城市分行，需按月份聚合为全国均值。"""
    rows = fetch_report("RPT_ECONOMY_HOUSE_PRICE", page_size=2000)
    by_month = {}
    for row in rows:
        rd = (row.get("REPORT_DATE") or "")[:7]
        if not rd:
            continue
        for field, key in (("FIRST_COMHOUSE_SAME", "new"), ("SECOND_HOUSE_SAME", "second")):
            v = _num(row.get(field))
            if v is not None:
                by_month.setdefault(rd, {"new": [], "second": []})[key].append(v)

    months = sorted(by_month.keys())[-limit:]
    dates = months
    new_avg, second_avg = [], []
    for m in months:
        n = by_month[m]["new"]; s = by_month[m]["second"]
        # 房价指数以 100 为基准，同比为指数形式；均值依然是指数口径
        new_avg.append(round(sum(n) / len(n), 2) if n else None)
        second_avg.append(round(sum(s) / len(s), 2) if s else None)

    def _m(vals):
        vv = [v for v in vals if v is not None]
        return (vv[-1], vv[-2] if len(vv) >= 2 else None) if vv else (None, None)
    ln, lp = _m(new_avg)
    return {
        "name": "70城房价指数(均值)", "unit": "指数(100=持平)",
        "dates": dates, "series": {"new": new_avg, "second": second_avg},
        "latest": ln, "prev": lp,
        "mom": round(ln - lp, 3) if (ln is not None and lp is not None) else None,
        "yoy": None,
    }


def fetch_indicator(key, limit=36):
    if key == "house":
        return fetch_house_price(limit)
    report_name, field_map, name, unit, _ = INDICATORS[key]
    rows = fetch_report(report_name, page_size=max(limit + 5, 40))
    dates, series = build_series(rows, field_map, limit)
    value_key = "value" if "value" in series else next(iter(series))
    vals = [v for v in series.get(value_key, []) if v is not None]
    latest = vals[-1] if vals else None
    prev = vals[-2] if len(vals) >= 2 else None
    mom = round(latest - prev, 4) if (latest is not None and prev is not None) else None

    out = {
        "name": name,
        "unit": unit,
        "dates": dates,
        "series": series,
        "latest": latest,
        "prev": prev,
        "mom": mom,
        "yoy": (series.get("yoy") or [None])[-1] if "yoy" in series else None,
    }
    # 去除非 None 的 None
    return out


def fetch_all(indicators=None):
    indicators = indicators or list(INDICATORS.keys())
    result = {"source": "eastmoney", "as_of": None, "indicators": {}, "errors": []}
    for key in indicators:
        try:
            indicator = fetch_indicator(key)
            if not indicator.get("dates") or not any(
                    v is not None for values in indicator.get("series", {}).values() for v in values):
                raise ValueError("指标没有有效数据")
            result["indicators"][key] = indicator
        except Exception as e:  # noqa: BLE001
            result["errors"].append(f"{key}: {e}")
    # as_of = CPI 最新日期
    cpi = result["indicators"].get("cpi")
    if cpi and cpi.get("dates"):
        result["as_of"] = cpi["dates"][-1]
    return result


def main():
    ap = argparse.ArgumentParser(description="抓取东方财富宏观数据")
    ap.add_argument("--indicator", action="append", help="指定指标 key，可多次；缺省抓全部")
    ap.add_argument("--out", default="eastmoney_data.json", help="输出 JSON 路径")
    args = ap.parse_args()

    data = fetch_all(args.indicator)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    ok = list(data["indicators"].keys())
    print(f"[eastmoney] 成功 {len(ok)} 项: {', '.join(ok)}")
    if data["errors"]:
        print(f"[eastmoney] 失败 {len(data['errors'])} 项:", file=sys.stderr)
        for e in data["errors"]:
            print("  -", e, file=sys.stderr)
    print(f"[eastmoney] 已写入 {args.out} (as_of={data['as_of']})")
    if not data["indicators"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
