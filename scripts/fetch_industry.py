#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_industry.py — 行业指数历史行情抓取（新浪财经）

用于「宏观→行业量化归因」：抓取行业指数月线，供回归分析使用。

数据源（无需 key）：
    https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData
    ?symbol=<code>&scale=240&ma=no&datalen=<n>
    scale=240 为日线；datalen 最大约 1023（约 4 年日线）

注意：沙箱环境下东财 push2 行情接口、腾讯 ifzq 接口均被拦截（501/断开），
      新浪行情接口可用，故采用新浪为行情数据源。

用法:
    python3 fetch_industry.py --out industry_data.json
    python3 fetch_industry.py --months 36 --out x.json
"""
import argparse
import json
import sys
import time
import urllib.request

BASE = ("https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
        "CN_MarketData.getKLineData")
HEADERS = {
    "Referer": "https://finance.sina.com.cn/",
    "Accept": "*/*",
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
}

# 中证行业指数 + 主要宽基（新浪代码）
# 注：仅保留经过实测「能返回最新数据」的代码。
# 部分中证行业代码（材料/工业/电信/公用/银行/地产/证券/能源部分）
# 在新浪接口返回陈旧或错误数据，已剔除，避免污染回归结果。
INDICES = {
    # 宽基（基准 + 风格对照）
    "sh000001": "上证指数",
    "sh000300": "沪深300",
    "sh000905": "中证500",
    "sz399006": "创业板指",
    # 中证一级行业（实测数据最新）
    "sh000928": "能源",
    "sh000932": "主要消费",
    "sh000933": "医药卫生",
    "sh000934": "金融",
    "sh000935": "信息技术",
}

# 归因用的「行业篮子」：中证一级行业（不含宽基），用于回归
SECTOR_KEYS = ["sh000928", "sh000932", "sh000933", "sh000934", "sh000935"]


def fetch_kline(symbol, datalen=1023, retries=2):
    """抓取单只指数日线，返回 [(date, close), ...] 升序。"""
    url = f"{BASE}?symbol={symbol}&scale=240&ma=no&datalen={datalen}"
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=25) as r:
                text = r.read().decode("utf-8", errors="ignore")
            break
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < retries:
                time.sleep(1.2)
                continue
            raise RuntimeError(f"新浪行情请求失败({symbol}): {last}") from e
    text = text.strip()
    if not text.startswith("["):
        raise ValueError(f"{symbol} 返回非 JSON: {text[:80]}")
    rows = json.loads(text)
    out = []
    for r in rows:
        d = r.get("day", "")[:10]
        c = r.get("close")
        if d and c not in (None, ""):
            try:
                out.append((d, float(c)))
            except (TypeError, ValueError):
                continue
    out.sort(key=lambda x: x[0])
    return out


def to_monthly(series):
    """日线 → 月末收盘价（取每月最后一个交易日）。"""
    buckets = {}
    for d, v in series:
        buckets[d[:7]] = v
    months = sorted(buckets)
    return months, [buckets[m] for m in months]


def monthly_returns(months, closes):
    """月末收盘 → 月度收益率（%）。"""
    rets = []
    for i in range(1, len(closes)):
        if closes[i - 1]:
            rets.append((months[i], round((closes[i] / closes[i - 1] - 1) * 100, 4)))
    return rets


def fetch_all(months=36):
    """抓取全部指数，返回 {code: {name, months, closes, returns}}。"""
    result = {"source": "sina", "as_of": None, "indices": {}, "errors": []}
    datalen = min(1023, max(120, months * 23))
    for code, name in INDICES.items():
        try:
            daily = fetch_kline(code, datalen=datalen)
            m, closes = to_monthly(daily)
            if len(m) < 2:
                raise ValueError("有效月度数据不足")
            # 只保留最近 months+1 个月（多留 1 个月用于算首月收益率）
            keep = months + 1
            m, closes = m[-keep:], closes[-keep:]
            result["indices"][code] = {
                "name": name,
                "months": m,
                "closes": closes,
                "returns": monthly_returns(m, closes),
            }
            if result["as_of"] is None or m[-1] > result["as_of"]:
                result["as_of"] = m[-1]
        except Exception as e:  # noqa: BLE001
            result["errors"].append(f"{name}({code}): {e}")
        time.sleep(0.2)  # 温和限速
    return result


def main():
    ap = argparse.ArgumentParser(description="抓取行业指数历史行情（新浪）")
    ap.add_argument("--months", type=int, default=36, help="保留月数，默认 36")
    ap.add_argument("--out", default="industry_data.json")
    args = ap.parse_args()

    data = fetch_all(args.months)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    ok = len(data["indices"])
    print(f"[industry] 成功 {ok}/{len(INDICES)} 个指数，as_of={data['as_of']}")
    for code, v in data["indices"].items():
        print(f"  {v['name']:8s} {code} n={len(v['months'])} "
              f"({v['months'][0]}~{v['months'][-1]})")
    for e in data["errors"]:
        print("  [err]", e, file=sys.stderr)
    print(f"[industry] 已写入 {args.out}")
    if not data["indices"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
