#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_fred.py — FRED（圣路易斯联储）宏观数据抓取

数据源（无需 API key）: https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES_ID>

用法:
    python3 fetch_fred.py --out data.json
    python3 fetch_fred.py --series DGS10 --series FEDFUNDS --out x.json

输出: JSON 结构同 fetch_eastmoney.py
"""
import argparse
import csv
import io
import json
import sys
import urllib.request

BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"
# 注意：FRED 对带自定义 User-Agent 的请求会拒绝/超时，必须不带 UA 头。
HEADERS = {}

# key -> (series_id, 显示名, 单位, 是否按年同比转换, 取样条数, 频率)
# 频率: Q 季频 / M 月频 / W 周频 / D 日频（用于日期截断与长周期计算）
SERIES = {
    "us_cpi":     ("CPIAUCSL",  "美国CPI",      "指数", True,  60,  "M"),
    "us_unrate":  ("UNRATE",    "美国失业率",    "%",    False, 60,  "M"),
    "fedfunds":   ("FEDFUNDS",  "联邦基金利率",  "%",    False, 60,  "M"),
    "us10y":      ("DGS10",     "10Y美债收益率", "%",    False, 1300, "D"),
    "usdcny":     ("DEXCHUS",   "美元兑人民币",  "汇率",  False, 1300, "D"),
    "usd_index":  ("DTWEXBGS",  "美元指数(广义)", "指数", False, 1300, "D"),
    "wti":        ("DCOILWTICO", "WTI原油",     "美元/桶", False, 1300, "D"),
    # ---- P1 新增 ----
    "cn_rate":    ("IR3TIB01CNM156N", "中国3月期银行间利率", "%", False, 60, "M"),
    "copper":     ("PCOPPUSDM", "铜价(月)",     "美元/吨", False, 60,  "M"),
    "gold":       ("IQ12260",   "金价(月)",     "指数",  False, 60,  "M"),
    "us10y_real": ("DFII10",    "10Y美债实际利率", "%",   False, 260, "D"),
    "vix":        ("VIXCLS",    "VIX恐慌指数",  "指数",  False, 260, "D"),
    "us_curve":   ("T10Y2Y",    "美债10Y-2Y利差", "%",   False, 260, "D"),
    # ---- P2 新增（盈利周期代理）----
    "us_indpro":  ("INDPRO",    "美国工业生产指数", "指数", True, 60, "M"),
    "us_retail":  ("RSAFS",     "美国零售销售",  "百万美元", True, 60, "M"),
    "us_payems":  ("PAYEMS",    "美国非农就业",  "千人", True, 60,  "M"),

    # ---- P3 长周期（全历史，用于带通滤波提取 7-11 年 / 15-25 年分量）----
    # 朱格拉周期：设备投资 / 固定资产投资
    "lj_equip":   ("Y033RC1Q027SBEA", "美国设备投资(季同比)", "同比%", True, 320, "Q"),
    "lj_gfcf":    ("GPDIC1",          "美国私人固定资产投资(季同比)", "同比%", True, 320, "Q"),
    "lj_gdp":     ("GDPC1",           "美国实际GDP(季同比)", "同比%", True, 320, "Q"),
    # 库兹涅茨周期：地产 / 建筑
    "lj_house":   ("Y033RC1Q027SBEA", "美国设备投资(季同比,库兹涅茨备用)", "同比%", True, 320, "Q"),
    "lj_houst":   ("HOUST",           "美国新屋开工(月)", "千套", False, 820, "M"),
    "lj_cs":      ("CSUSHPINSA",      "美国Case-Shiller房价(月同比)", "同比%", True, 480, "M"),
    "lj_mortg":   ("MORTGAGE30US",    "美国30年房贷利率(周)", "%", False, 2900, "W"),
    # 债务周期（Dalio 长债代理）
    "lj_debtgdp": ("GFDEGDQ188S",     "美国非金融部门债务/GDP(季)", "%", False, 245, "Q"),
    "lj_credit":  ("TOTBKCR",         "美国银行总信贷(周)", "十亿美元", False, 2810, "W"),
    "lj_lev":     ("BOGZ1FL073164003Q", "美国非金融企业债务(季)", "百万美元", False, 325, "Q"),
    # NBER 衰退标记（对齐长周期峰谷用）
    "lj_rec":     ("USREC",           "NBER衰退区间", "0/1", False, 2070, "M"),
}


def fetch_series(series_id, timeout=30, retries=2):
    """下载 FRED CSV，返回 [(date, value), ...] 升序（已剔除缺失值）。"""
    url = f"{BASE}?id={series_id}"
    last_err = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                text = resp.read().decode("utf-8", errors="ignore")
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < retries:
                continue
            raise RuntimeError(f"FRED 请求失败({series_id}): {last_err}") from e
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []
    out = []
    for row in rows[1:]:  # 跳过 header
        if len(row) < 2:
            continue
        d, v = row[0].strip(), row[1].strip()
        if v in ("", ".", "NA"):
            continue
        try:
            out.append((d, float(v)))
        except ValueError:
            continue
    out.sort(key=lambda x: x[0])
    return out


def _yoy(series):
    """把指数型月度序列转成同比 %（12 期前比较）。"""
    out = []
    for i in range(len(series)):
        if i >= 12 and series[i - 12][1]:
            yoy = (series[i][1] / series[i - 12][1] - 1) * 100
            out.append((series[i][0], round(yoy, 3)))
    return out


def _yoy_quarterly(series):
    """把指数型季度序列转成同比 %（4 期前比较）。"""
    out = []
    for i in range(len(series)):
        if i >= 4 and series[i - 4][1]:
            yoy = (series[i][1] / series[i - 4][1] - 1) * 100
            out.append((series[i][0], round(yoy, 3)))
    return out


def build(key, limit=None):
    series_id, name, unit, to_yoy, n_default, freq = SERIES[key]
    limit = limit or n_default
    raw = fetch_series(series_id)
    if to_yoy:
        if freq == "Q":
            raw = _yoy_quarterly(raw)
        else:
            raw = _yoy(raw)
    raw = raw[-limit:]
    # 日期截断：日频/周频保留完整日期 YYYY-MM-DD，月频 YYYY-MM，季频 YYYY-MM
    keep_day = freq in ("D", "W")
    dates = [(d[:10] if keep_day else d[:7]) for d, _ in raw]
    values = [v for _, v in raw]
    return {
        "name": name,
        "series_id": series_id,
        "unit": unit,
        "freq": freq,
        "dates": dates,
        "values": values,
        "latest": values[-1] if values else None,
        "prev": values[-2] if len(values) >= 2 else None,
        "mom": round(values[-1] - values[-2], 4) if len(values) >= 2 else None,
    }


def _derive_ratio(num_key, den_key, name, unit, limit=60, operation="ratio"):
    """由两条序列按日期对齐计算比值（如铜金比 = 铜价 / 金价）。"""
    a = {d[:7] if len(d) > 7 else d: v for d, v in fetch_series(SERIES[num_key][0])}
    b = {d[:7] if len(d) > 7 else d: v for d, v in fetch_series(SERIES[den_key][0])}
    common = sorted(set(a) & set(b))
    raw = ([(d, a[d] - b[d]) for d in common] if operation == "spread"
           else [(d, a[d] / b[d]) for d in common if b[d]])
    raw = raw[-limit:]
    dates = [d for d, _ in raw]
    values = [round(v, 4) for _, v in raw]
    latest = values[-1] if values else None
    prev = values[-2] if len(values) >= 2 else None
    return {
        "name": name, "series_id": f"{SERIES[num_key][0]}{'-' if operation == 'spread' else '/'}{SERIES[den_key][0]}",
        "unit": unit, "freq": "M", "dates": dates, "values": values,
        "latest": latest, "prev": prev,
        "mom": round(latest - prev, 4) if (latest is not None and prev is not None) else None,
    }


# 派生指标：key -> (分子key, 分母key, 名称, 单位)
DERIVED = {
    "copper_gold": ("copper", "gold", "铜金比", "比值"),
    "cn_us_spread": ("cn_rate", "fedfunds", "中国利率-美国利率(利差)", "pct"),
}


def fetch_all(keys=None):
    keys = keys or list(SERIES.keys())
    result = {"source": "fred", "as_of": None, "indicators": {}, "errors": []}
    for key in keys:
        if key in DERIVED:
            continue          # 派生指标单独处理，跳过 SERIES 查询
        try:
            indicator = build(key)
            if not indicator["dates"]:
                raise ValueError("序列没有有效数据")
            result["indicators"][key] = indicator
        except Exception as e:  # noqa: BLE001
            result["errors"].append(f"{key}: {e}")
    # 派生指标：默认全部计算；若显式指定 keys，则只算被请求的那些
    explicit = set(keys) & set(DERIVED)
    derived_keys = explicit if explicit else set(DERIVED)
    for key in derived_keys:
        nk, dk, name, unit = DERIVED[key]
        try:
            indicator = _derive_ratio(nk, dk, name, unit,
                                      operation="spread" if key == "cn_us_spread" else "ratio")
            if not indicator["dates"]:
                raise ValueError("派生序列没有共同日期")
            result["indicators"][key] = indicator
        except Exception as e:  # noqa: BLE001
            result["errors"].append(f"{key}(派生): {e}")
    us10y = result["indicators"].get("us10y")
    if us10y and us10y.get("dates"):
        result["as_of"] = us10y["dates"][-1]
    # 单指标/派生模式下，as_of 可能仍为空 → 用任一序列兜底
    if not result["as_of"]:
        for v in result["indicators"].values():
            if v.get("dates"):
                result["as_of"] = v["dates"][-1]
                break
    return result


def main():
    ap = argparse.ArgumentParser(description="抓取 FRED 海外宏观数据")
    ap.add_argument("--series", action="append", help="指定指标 key，可多次；缺省全部")
    ap.add_argument("--out", default="fred_data.json")
    args = ap.parse_args()

    data = fetch_all(args.series)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[fred] 成功 {len(data['indicators'])} 项: {', '.join(data['indicators'].keys())}")
    for e in data["errors"]:
        print("  [err]", e, file=sys.stderr)
    print(f"[fred] 已写入 {args.out} (as_of={data['as_of']})")
    if not data["indicators"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
