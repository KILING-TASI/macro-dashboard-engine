#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
regress_attribution.py — 宏观→行业量化归因（回归替代经验矩阵）

思路：
  用行业指数月度超额收益率，对若干宏观因子的月度变化做多元线性回归，
  得到每个行业对每个因子的【真实 beta】与拟合优度 R²。
  以此替代/校验原本基于经验判断的「因子×行业敏感度矩阵」。

宏观因子（月度）：
  ① 增长（growth）   : PMI 变化（制造业 PMI 环比）
  ② 通胀（inflation）: CPI 同比变化
  ③ 流动性（liquidity）: M1 同比变化（资金活化）
  ④ 汇率（fx）       : 美元兑人民币变化（贬值 → 正）
  ⑤ 海外利率（us_rate）: 10Y 美债收益率变化
  ⑥ 周期品（commodity）: 铜金比变化（顺周期信号）

方法：
  - 数据对齐到月度
  - 行业收益率做「减去市场基准（沪深300）」的超额处理（可选）
  - 逐行业 OLS（最小二乘），标准化系数便于横向比较
  - 输出 beta 矩阵 + R² + 显著性（t 值近似）

用法:
    python3 regress_attribution.py --industry industry.json --eastmoney em.json \
        --fred fred.json --out attribution.json
"""
import argparse
import json
import math
import sys
from dated_series import paired

# 因子定义：key -> (来源, 字段, 中文名, 单位)
# 来源 em=东财数据, fred=FRED 数据
FACTORS = [
    ("growth",     "em",   "pmi",     "增长(PMI变化)",     "pt"),
    ("inflation",  "em",   "cpi",     "通胀(CPI同比变化)", "%"),
    ("liquidity",  "em",   "m1",      "流动性(M1同比变化)", "%"),
    ("fx",         "fred", "usdcny",  "汇率(USDCNY变化)",  "pct"),
    ("us_rate",    "fred", "us10y",   "海外利率(10Y美债变化)", "%"),
    ("commodity",  "fred", "copper_gold", "周期品(铜金比变化)", "ratio"),
]

# 行业代码 -> 展示名（与 fetch_industry 保持一致）
SECTOR_NAMES = {
    "sh000928": "能源", "sh000932": "主要消费", "sh000933": "医药卫生",
    "sh000934": "金融", "sh000935": "信息技术",
}
BENCHMARK = "sh000300"   # 沪深300 作为市场基准（做超额收益）


# ---------------------------------------------------------------- 数据提取

def _em_monthly_series(em, key):
    """东财指标 → {月份: 值}。东财结构：indicators[key].series.value / yoy。"""
    ind = (em.get("indicators") or {}).get(key) or {}
    dates = ind.get("dates") or []
    # 优先取 yoy，其次 value
    series = ind.get("series") or {}
    vals = series.get("yoy") or series.get("value") or ind.get("values") or []
    out = {}
    for d, v in paired(dates, vals):
        if v is not None and len(d) >= 7:
            out[d[:7]] = v
    return out


def _fred_monthly_series(fr, key):
    """FRED 指标 → {月份: 值}（日频取月末值）。"""
    ind = (fr.get("indicators") or {}).get(key) or {}
    dates = ind.get("dates") or []
    vals = ind.get("values") or []
    out = {}
    for d, v in paired(dates, vals):
        if v is None:
            continue
        m = d[:7]
        out[m] = v     # 后者覆盖前者 → 月末值
    return out


def _diff(series):
    """对 {月:值} 做一阶差分 → {月: 变化量}。"""
    months = sorted(series)
    out = {}
    for i in range(1, len(months)):
        if not _adjacent_months(months[i - 1], months[i]):
            continue
        out[months[i]] = series[months[i]] - series[months[i - 1]]
    return out


def _pct_change(series):
    """对 {月:值} 做百分比变化 → {月: %变化}。"""
    months = sorted(series)
    out = {}
    for i in range(1, len(months)):
        if not _adjacent_months(months[i - 1], months[i]):
            continue
        prev = series[months[i - 1]]
        if prev:
            out[months[i]] = (series[months[i]] / prev - 1) * 100
    return out


def _adjacent_months(previous, current):
    def number(month):
        year, month_number = map(int, month.split("-"))
        return year * 12 + month_number
    return number(current) - number(previous) == 1


# ---------------------------------------------------------------- 因子构造

def build_factors(em, fr):
    """构造各因子的月度变化序列，返回 {factor_key: {月: 变化}}。"""
    raw = {
        "growth":     ("em",   "pmi"),
        "inflation":  ("em",   "cpi"),
        "liquidity":  ("em",   "m1"),
        "fx":         ("fred", "usdcny"),
        "us_rate":    ("fred", "us10y"),
    }
    factors = {}
    for fk, (src, key) in raw.items():
        s = _em_monthly_series(em, key) if src == "em" else _fred_monthly_series(fr, key)
        if len(s) >= 6:
            factors[fk] = _pct_change(s) if fk == "fx" else _diff(s)

    # 铜金比：FRED 派生指标（已按月），直接取变化
    cg = _fred_monthly_series(fr, "copper_gold")
    if len(cg) >= 6:
        factors["commodity"] = _pct_change(cg)   # 比值用百分比变化

    return factors


# ---------------------------------------------------------------- OLS

def ols(y, X):
    """
    普通最小二乘（含截距）。X 为 [[x1,x2,...], ...]，y 为 [y1,...]。
    返回 (coefs[含截距], r2, tvals)。
    用正态方程 + 高斯消元，避免 numpy 依赖。
    """
    n = len(y)
    if n == 0 or not X:
        return None, 0.0, []
    k = len(X[0])
    # 设计矩阵加截距列
    A = [[1.0] + list(row) for row in X]
    p = k + 1
    if n <= p:
        return None, 0.0, []   # 样本不足

    # X'X
    XtX = [[sum(A[i][a] * A[i][b] for i in range(n)) for b in range(p)]
           for a in range(p)]
    # X'y
    Xty = [sum(A[i][a] * y[i] for i in range(n)) for a in range(p)]

    # 高斯消元解 (X'X) b = X'y
    M = [XtX[i][:] + [Xty[i]] for i in range(p)]
    for c in range(p):
        # 选主元
        piv = max(range(c, p), key=lambda r: abs(M[r][c]))
        if abs(M[piv][c]) < 1e-12:
            return None, 0.0, []
        M[c], M[piv] = M[piv], M[c]
        for r in range(p):
            if r != c and M[c][c]:
                f = M[r][c] / M[c][c]
                for cc in range(c, p + 1):
                    M[r][cc] -= f * M[c][cc]
    beta = [M[i][p] / M[i][i] for i in range(p)]

    # 残差与 R²
    yhat = [sum(beta[a] * A[i][a] for a in range(p)) for i in range(n)]
    ybar = sum(y) / n
    ss_res = sum((y[i] - yhat[i]) ** 2 for i in range(n))
    ss_tot = sum((y[i] - ybar) ** 2 for i in range(n))
    r2 = 1 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0

    # t 值近似：se(b) = sqrt(σ² * (X'X)^-1_ii)
    dof = n - p
    sigma2 = ss_res / dof if dof > 0 else 0.0
    # 求 (X'X)^-1 对角（再做一次消元求逆的对角）
    inv_diag = []
    for i in range(p):
        e = [1.0 if j == i else 0.0 for j in range(p)]
        MM = [XtX[r][:] + [e[r]] for r in range(p)]
        for c in range(p):
            piv = max(range(c, p), key=lambda r: abs(MM[r][c]))
            if abs(MM[piv][c]) < 1e-12:
                inv_diag.append(0.0); break
            MM[c], MM[piv] = MM[piv], MM[c]
            for r in range(p):
                if r != c and MM[c][c]:
                    f = MM[r][c] / MM[c][c]
                    for cc in range(c, p + 1):
                        MM[r][cc] -= f * MM[c][cc]
        else:
            inv_diag.append(MM[i][p] / MM[i][i])
    tvals = []
    for i in range(p):
        se = math.sqrt(sigma2 * inv_diag[i]) if inv_diag[i] > 0 else 0.0
        tvals.append(beta[i] / se if se > 1e-12 else 0.0)

    return beta, r2, tvals


# ---------------------------------------------------------------- 主流程

def compute(industry, em, fr, use_excess=True):
    """返回归因结果 dict。"""
    idx = industry.get("indices") or {}
    factors = build_factors(em, fr)
    factor_keys = [f[0] for f in FACTORS if f[0] in factors]

    # 基准收益率（用于超额）
    bench_rets = {}
    if BENCHMARK in idx:
        bench_rets = {m: v for m, v in idx[BENCHMARK]["returns"]}

    result = {
        "factors": [{"key": f[0], "name": f[3], "unit": f[4]}
                    for f in FACTORS if f[0] in factors],
        "sectors": [],
        "n_obs": 0,
        "use_excess": use_excess,
        "point_in_time": False,
        "timing_note": "未取得逐期首次发布日期与修订版本；仅作事后历史关联，不能解释为当时可用预测。",
        "note": ("行业超额收益对宏观因子月度变化的 OLS 回归；"
                 "beta 为标准ized 系数，正值=因子上行利好该行业"),
    }

    for code, meta in idx.items():
        if code not in SECTOR_NAMES:
            continue
        rets = {m: v for m, v in meta["returns"]}
        # 构造 y（超额收益）：取「行业收益率」与「全部因子」都有的月份
        if not factor_keys:
            continue
        common = set(rets)
        for k in factor_keys:
            common &= set(factors[k])
        y_months = sorted(common)
        if use_excess:
            y_months = sorted(common & set(bench_rets))
        if len(y_months) < 12:
            continue
        y = []
        for m in y_months:
            r = rets[m]
            if use_excess and m in bench_rets:
                r = r - bench_rets[m]
            y.append(r)
        X = [[factors[k][m] for k in factor_keys] for m in y_months]

        # 同时标准化收益和因子，得到无量纲 beta；常量列无法估计。
        def standardize(values):
            mean = sum(values) / len(values)
            sd = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
            return [(v - mean) / sd for v in values] if sd > 1e-12 else None

        columns = [standardize([row[i] for row in X]) for i in range(len(factor_keys))]
        y = standardize(y)
        if y is None or any(column is None for column in columns):
            continue
        X = [list(row) for row in zip(*columns)]

        beta, r2, tvals = ols(y, X)
        if beta is None:
            continue
        result["sectors"].append({
            "code": code,
            "name": SECTOR_NAMES[code],
            "beta": {k: round(beta[i + 1], 4) for i, k in enumerate(factor_keys)},
            "t": {k: round(tvals[i + 1], 2) for i, k in enumerate(factor_keys)},
            "r2": round(r2, 4),
            "n": len(y_months),
            "start_month": y_months[0],
            "end_month": y_months[-1],
        })
        result["n_obs"] = len(y_months)

    return result


def main():
    ap = argparse.ArgumentParser(description="宏观→行业量化归因回归")
    ap.add_argument("--industry", required=True, help="fetch_industry.py 输出")
    ap.add_argument("--eastmoney", required=True)
    ap.add_argument("--fred", required=True)
    ap.add_argument("--out", default="attribution.json")
    ap.add_argument("--no-excess", action="store_true", help="不做超额收益处理")
    args = ap.parse_args()

    def load(p):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:  # noqa: BLE001
            print(f"[attrib] 读取 {p} 失败: {e}", file=sys.stderr)
            return {}

    industry = load(args.industry)
    em = load(args.eastmoney)
    fr = load(args.fred)
    res = compute(industry, em, fr, use_excess=not args.no_excess)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

    print(f"[attrib] 因子: {[x['key'] for x in res['factors']]}")
    print(f"[attrib] 行业数: {len(res['sectors'])}，样本月数: {res['n_obs']}")
    for s in res["sectors"]:
        bs = " ".join(f"{k}={v:+.2f}" for k, v in s["beta"].items())
        print(f"  {s['name']:8s} R²={s['r2']:.2f} n={s['n']:3d}  {bs}")
    print(f"[attrib] 已写入 {args.out}")


if __name__ == "__main__":
    main()
