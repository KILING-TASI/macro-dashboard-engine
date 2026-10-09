#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compute_cycle.py — 宏观周期研判

输入: fetch_eastmoney.py / fetch_fred.py 产出的 JSON（或合并后的 dict）
输出: 结构化研判结论 JSON（美林时钟象限 + 库存周期 + 信用周期 + 配置建议）

方法论见 references/cycle_framework.md
"""
import argparse
import json
import math
import os
import sys
from dated_series import paired, trailing, adjacent, validate_frequency


CALCULATION_VERSION = "2.1.0"

# ---------- 工具 ----------

def _series(ind, key="value", frequency=None):
    """取指标序列（东财用 series.value，FRED 用 values）。"""
    return [v for _, v in trailing(ind, key, frequency)]


def _yoy_series(ind, frequency="M"):
    """取同比序列，优先 series.yoy。"""
    if not ind or "yoy" not in (ind.get("series") or {}):
        return []
    return [v for _, v in trailing(ind, "yoy", frequency)]


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _zscore(x, xs, period=12):
    """x 相对近 period 期的标准分，用于衡量动能强度。"""
    window = xs[-period:]
    if len(window) < 3:
        return 0.0
    m = _mean(window)
    var = _mean([(v - m) ** 2 for v in window])
    sd = var ** 0.5 if var else 0.0
    if not sd:
        return 0.0
    return round((x - m) / sd, 3)


def _momentum(xs, period=12):
    """动能 = 最新值 - 近 period 期均值（>0 上行，<0 下行）。"""
    if len(xs) < 4:
        return 0.0
    base = _mean(xs[-period:])
    if base is None:
        return 0.0
    return round(xs[-1] - base, 4)


def _trend_momentum(xs, short=3, long=12):
    """短期 vs 长期均值差，衡量近期改善/恶化，更适合判断方向。"""
    if len(xs) < 4:
        return 0.0
    long = min(long, len(xs))
    s = _mean(xs[-short:])
    l = _mean(xs[-long:])
    if s is None or l is None:
        return 0.0
    return round(s - l, 4)


def _level_and_dir(series, level_ref=None, scale=1.0):
    """融合'绝对水平'与'变化方向'判断动能方向，返回 (signed_score, level_z, dir_z)。

    - level_ref 非 None 时（如 PMI 的荣枯线 50）：水平项 = (最新值 - 参考值)/scale，
      但取 saturating（tanh）避免极端值主导。
    - 方向项：序列 >= 8 期用 trend_momentum(3,12)，否则用最近 3 期斜率近似；
      统一按 scale 归一化后 tanh 饱和。
    最终分值 = 0.6*水平 + 0.6*方向（方向权重不低于水平的一半），保证'低位改善'
    与'高位恶化'都能被识别。
    """
    if not series:
        return 0.0, 0.0, 0.0
    last = series[-1]
    # 水平项
    if level_ref is not None:
        lz = math.tanh((last - level_ref) / (scale * 3))
    else:
        base = _mean(series[-12:]) if len(series) >= 4 else _mean(series)
        lz = math.tanh((last - base) / (scale * 3)) if base is not None else 0.0
    # 方向项
    if len(series) >= 8:
        d = _trend_momentum(series, 3, min(len(series), 12))
    elif len(series) >= 3:
        d = series[-1] - series[-min(len(series), 3)]
    else:
        d = 0.0
    dz = math.tanh(d / (scale * 2)) if scale else 0.0
    score = round(0.6 * lz + 0.6 * dz, 4)
    return score, round(lz, 3), round(dz, 3)


# ---------- 维度合成 ----------

def growth_score(em, fr, diagnostics=None):
    """增长动能：PMI（水平+方向）+ 社零同比 + GDP 同比。
    返回 (score, evidence[], n_dims)。n_dims=0 表示无可用数据。"""
    ev, parts, components = [], [], []

    pmi = _series(em.get("pmi"), frequency="M")
    if len(pmi) >= 4:
        s, lz, dz = _level_and_dir(pmi, level_ref=50.0, scale=1.0)
        parts.append(s / 1.2)
        components.append({"indicator": "pmi", "raw": s, "scale": 1.2, "transform": "divide", "frequency": "M", "n": len(pmi)})
        trend = "改善" if dz > 0.05 else ("走弱" if dz < -0.05 else "持平")
        ev.append(f"制造业PMI {pmi[-1]:.1f}（{'荣枯线上' if pmi[-1] >= 50 else '荣枯线下'}，"
                  f"近期趋势{trend}）")

    retail_yoy = _yoy_series(em.get("retail"))
    if retail_yoy and len(retail_yoy) >= 4:
        m = _trend_momentum(retail_yoy, 3, 12)
        parts.append(math.tanh(m / 2.0))
        components.append({"indicator": "retail", "raw": m, "scale": 2.0, "transform": "tanh", "frequency": "M", "n": len(retail_yoy)})
        ev.append(f"社零同比 {retail_yoy[-1]:.1f}%（连续{len(retail_yoy)}月；短长窗口差 {m:+.2f}pct）")

    gdp_yoy = _yoy_series(em.get("gdp"), "Q")
    if gdp_yoy and len(gdp_yoy) >= 4:
        m = _trend_momentum(gdp_yoy, 2, min(len(gdp_yoy), 8))
        parts.append(math.tanh(m / 1.0))
        components.append({"indicator": "gdp", "raw": m, "scale": 1.0, "transform": "tanh", "frequency": "Q", "n": len(gdp_yoy)})
        ev.append(f"GDP同比 {gdp_yoy[-1]:.1f}%（连续{len(gdp_yoy)}季；短长窗口差 {m:+.2f}pct）")

    if not parts:
        return 0.0, ["缺少增长类指标（PMI/社零/GDP）"], 0
    for component, part in zip(components, parts):
        component.update(score=part, weight=1/len(parts), contribution=part/len(parts))
    if diagnostics is not None:
        diagnostics.update(components=components,
            scale_sensitivity={str(factor): round(_mean([
                c["score"] if c["transform"] == "divide" else math.tanh(c["raw"]/(c["scale"]*factor))
                for c in components]), 4) for factor in (0.5, 1.0, 2.0)},
            leave_one_out={c["indicator"]: round(_mean([p for j,p in enumerate(parts) if j != i]),4)
                for i,c in enumerate(components)} if len(parts)>1 else {},
            minimum_coverage="至少4个连续有效原生频率观测；不足12月/8季使用已有连续窗口，并披露n",
            interpretation="当前资料的事后描述；发布与修订时点未取得，不作当时可用预测")
    ev.append("增长贡献：可用维度等权；PMI分数÷1.2、社零趋势tanh(百分点÷2)、GDP趋势tanh(百分点÷1)，均限制在[-1,1]；参数是研究假设")
    ev.extend(f"维度{j+1}：归一化分数{part:+.4f}，权重{1/len(parts):.4f}，贡献{part/len(parts):+.4f}" for j, part in enumerate(parts))
    ev.append("尺度敏感性（社零/GDP尺度减半或加倍）及删维度结果见growth_diagnostics；不代表实时预测")
    return round(_mean(parts), 3), ev, len(parts)


def inflation_score(em, fr):
    """通胀动能：CPI/PPI 同比方向（这类指标本身即增速，重点看方向）。
    返回 (score, evidence[], n_dims)。"""
    ev, parts = [], []

    cpi = _yoy_series(em.get("cpi"), frequency="M") or _series(em.get("cpi"), frequency="M")
    if cpi and len(cpi) >= 4:
        d = _trend_momentum(cpi, 3, min(len(cpi), 12)) if len(cpi) >= 8 else (cpi[-1] - cpi[0])
        parts.append(d * 0.5)
        ev.append(f"CPI同比 {cpi[-1]:.2f}%（近3月-近12月 {d:+.2f}pct）")

    ppi = _series(em.get("ppi"), frequency="M")
    if ppi and len(ppi) >= 4:
        d = _trend_momentum(ppi, 3, min(len(ppi), 12)) if len(ppi) >= 8 else (ppi[-1] - ppi[0])
        parts.append(d * 0.5)
        ev.append(f"PPI同比 {ppi[-1]:.2f}%（近3月-近12月 {d:+.2f}pct）")

    us_cpi = _series(fr.get("us_cpi"))
    if us_cpi and len(us_cpi) >= 4:
        d = _trend_momentum(us_cpi, 3, min(len(us_cpi), 12))
        parts.append(d * 0.25)
        ev.append(f"美国CPI同比 {us_cpi[-1]:.2f}%")

    if not parts:
        return 0.0, ["缺少通胀类指标（CPI/PPI）"], 0
    return round(_mean(parts), 3), ev, len(parts)


def classify_quadrant(g, i, g_dims=3, i_dims=2):
    """象限判定。若某维度无数据(n_dims=0)，则判定降级为"数据不足"，不给误导性结论。"""
    if g_dims == 0 or i_dims == 0:
        return "数据不足", "—", "—", "增长或通胀维度缺少有效数据，暂无法定位周期象限"
    if g >= 0 and i < 0:
        return "复苏", "股票", "成长", "增长回暖 + 通胀回落，盈利改善与估值扩张共振"
    if g >= 0 and i >= 0:
        return "过热", "大宗商品", "周期", "增长强劲 + 通胀上行，上游资源盈利弹性最大"
    if g < 0 and i >= 0:
        return "滞胀", "现金", "防御", "增长下行 + 通胀高企，杀估值，宜避险"
    return "衰退", "债券", "价值/高股息", "增长通胀双降，利率下行，稳健资产占优"


# ---------- 库存 / 信用 ----------

def inventory_cycle(em):
    """用 PPI 同比方向近似库存周期（无库存数据时的降级方案）。"""
    ppi = _series(em.get("ppi"), frequency="M")
    pmi = _series(em.get("pmi"), frequency="M")
    ev = []
    inv_up = need_up = None
    if len(ppi) >= 4:
        inv_up = _trend_momentum(ppi, 3, 12) > 0
        ev.append(f"PPI同比 {ppi[-1]:.2f}%（{'上行→补库倾向' if inv_up else '下行→去库倾向'}）")
    if pmi:
        need_up = pmi[-1] >= 50
        ev.append(f"PMI {pmi[-1]:.1f}（{'需求扩张' if need_up else '需求收缩'}）")

    if inv_up is None or need_up is None:
        return {"phase": "数据不足", "evidence": ev or ["缺少 PPI/PMI 数据"]}

    table = {
        (True, True): "主动补库",
        (True, False): "被动补库",
        (False, False): "主动去库",
        (False, True): "被动去库",
    }
    return {"phase": table[(inv_up, need_up)], "evidence": ev}


def _clean_outliers(dates, values, threshold=5.0, enabled=False):
    """默认保留原值；显式启用时仅屏蔽两侧一致的孤立点，非官方纠错。"""
    paired(dates, values)
    if not math.isfinite(threshold) or threshold <= 0:
        raise ValueError("清洗阈值须为正有限数")
    out, removed = list(values), []
    if enabled:
        for i in range(1, len(values) - 1):
            left, v, right = values[i-1:i+2]
            if any(x is None or not math.isfinite(x) for x in (left, v, right)):
                continue
            if not (adjacent(dates[i-1], dates[i], "M") and adjacent(dates[i], dates[i+1], "M")):
                continue
            if abs(left-right) <= threshold and abs(v-left) > threshold and abs(v-right) > threshold:
                out[i] = None
                removed.append(f"{dates[i]}({v:+.2f})")
    return out, removed


def credit_cycle(em, clean_outliers=False):
    """信用周期：以 M1-M2 剪刀差为主（社融不可得时的降级方案）。按日期对齐，避免错位。"""
    m1 = em.get("m1") or {}
    m2 = em.get("m2") or {}
    validate_frequency(m1, "M")
    validate_frequency(m2, "M")
    trailing(m1, "yoy", "M")
    trailing(m2, "yoy", "M")
    m1_dates = m1.get("dates") or []
    m2_dates = m2.get("dates") or []
    m1_map = {d: v for d, v in paired(m1_dates, (m1.get("series") or {}).get("yoy", []))
              if v is not None}
    m2_map = {d: v for d, v in paired(m2_dates, (m2.get("series") or {}).get("yoy", []))
              if v is not None}
    common = sorted(set(m1_map) & set(m2_map))
    if not common:
        return {"state": "数据不足", "evidence": ["缺少 M1/M2 数据"]}
    if common[-1] != max(m1_dates[-1], m2_dates[-1]):
        return {"state": "数据不足", "evidence": ["M1/M2最新观测期未共同取得，不用较早共同期替代"]}

    scissors_raw = [round(m1_map[d] - m2_map[d], 2) for d in common]
    scissors, removed = _clean_outliers(common, scissors_raw, enabled=clean_outliers)
    audit = {"scissors_raw_dates": common, "scissors_raw_series": scissors_raw,
             "cleaning": {"mode": "isolated-neighbor" if clean_outliers else "none",
                          "threshold_pct_points": 5.0, "masked_points": removed,
                          "assumption": "可选研究屏蔽，不认定原始发布错误"}}
    # 取最后一个有效值与 3 期前有效值判断方向
    valid = trailing({"dates": common, "values": scissors, "freq": "M"})
    if len(valid) < 4:
        return {**audit, "state": "数据不足", "evidence": ["信用变化需要最近4个连续有效月份，不跨缺月或剔除点计算"]}
    cur = valid[-1][1]
    mom = round(cur - valid[-4][1], 2) if len(valid) >= 4 else 0.0
    ev = [f"M1同比 {m1_map[valid[-1][0]]:.1f}% / M2同比 {m2_map[valid[-1][0]]:.1f}% "
          f"→ M1-M2 剪刀差 {cur:+.2f}pct（{valid[-1][0]}）"]
    ev.append(f"剪刀差近3月变化 {mom:+.2f}pct（{'走阔→资金活化' if mom > 0 else '收窄→资金淤积'}）")
    if removed:
        ev.append(f"按显式研究假设屏蔽孤立点: {', '.join(removed)}（偏离邻月过大）")

    state = "宽信用" if mom > 0 else "紧信用"
    return {**audit, "state": state, "scissors": cur, "scissors_mom": mom,
            "scissors_dates": common[-12:], "scissors_series": scissors[-12:],
            "evidence": ev}

# ---------- P1 新增周期 ----------

def percentile_rank(series, window=None):
    """计算最新值在历史序列中的分位（0-100）。window=None 用全样本。"""
    vals = [v for v in (series or []) if v is not None]
    if not vals:
        return None
    w = vals[-window:] if window else vals
    cur = w[-1]
    below = sum(1 for v in w if v <= cur)
    return round(below / len(w) * 100, 1)


def liquidity_cycle(fr):
    """货币/流动性周期：以美元指数、美债实际利率、VIX、美债利差综合判断全球流动性松紧。
    返回 state ∈ {宽松, 中性, 收紧}。"""
    ev, parts = [], []

    usd = _series(fr.get("usd_index"))
    if usd and len(usd) >= 20:
        chg = (usd[-1] / usd[-20] - 1) * 100
        parts.append(-chg)  # 美元走弱=流动性宽松
        ev.append(f"美元指数 {usd[-1]:.1f}（20期 {chg:+.1f}%，{'走弱→宽松' if chg < 0 else '走强→收紧'}）")

    real = _series(fr.get("us10y_real"))
    if real and len(real) >= 20:
        d = real[-1] - real[-20]
        parts.append(-d * 2)  # 实际利率上行=收紧
        ev.append(f"10Y美债实际利率 {real[-1]:.2f}%（20期 {d:+.2f}pct）")

    vix = _series(fr.get("vix"))
    if vix:
        parts.append(-(vix[-1] - 15) / 5)  # VIX 高于15偏紧
        ev.append(f"VIX {vix[-1]:.1f}（{'避险升温' if vix[-1] > 20 else '风险偏好平稳'}）")

    if not parts:
        return {"state": "数据不足", "evidence": ["缺少美元/实际利率/VIX 数据"]}

    score = round(_mean(parts), 3)
    state = "宽松" if score > 0.3 else ("收紧" if score < -0.3 else "中性")
    return {"state": state, "score": score, "evidence": ev}


def valuation_cycle(em, fr):
    """估值周期：以股权风险溢价 ERP = 1/PE - 10Y 国债收益率 近似。
    本版用 A股估值代理：以 M2 同比与盈利预期缺口 + 利率水平粗算 ERP 分位。
    （注：无实时 A 股 PE 源时的降级方案，用利率分位代表估值环境）"""
    ev = []
    # 用中国利率水平 + 美国利率，构造"利率环境"分位（利率越低越利于估值）
    cn = _series(fr.get("cn_rate"))
    us = _series(fr.get("us10y"))
    if not cn and not us:
        return {"state": "数据不足", "erp_pct": None, "evidence": ["缺少利率数据"]}

    if cn:
        pct = percentile_rank(cn, window=60)
        ev.append(f"中国3月期利率 {cn[-1]:.2f}%（最近至多60个连续原生频率观测分位 {pct}%）")
    else:
        pct = None
    if us:
        upct = percentile_rank(us, window=60)
        ev.append(f"10Y美债 {us[-1]:.2f}%（最近至多60个连续原生频率观测分位 {upct}%）")

    # 利率分位越低 → 估值环境越友好（宽松）
    ref = pct if pct is not None else upct
    if ref is None:
        state = "数据不足"
    elif ref < 33:
        state = "低估/友好"
    elif ref < 66:
        state = "中性"
    else:
        state = "高估/承压"
    return {"state": state, "rate_pct": ref, "evidence": ev}


def copper_gold_cycle(fr):
    """铜金比周期：铜金比上行=增长预期改善（顺周期），下行=避险（逆周期）。"""
    cg = _series(fr.get("copper_gold"))
    if not cg or len(cg) < 4:
        return {"state": "数据不足", "evidence": ["缺少铜金比数据"]}
    mom = _trend_momentum(cg, 3, min(len(cg), 12)) if len(cg) >= 8 else (cg[-1] - cg[0])
    pct = percentile_rank(cg, window=60)
    if mom > 0:
        state = "上行（顺周期）"
    else:
        state = "下行（避险）"
    ev = [f"铜金比 {cg[-1]:.1f}（近3月-近12月 {mom:+.1f}，历史分位 {pct}%）",
          "铜金比上行→增长预期改善，利好周期/资源股" if mom > 0
          else "铜金比下行→避险情绪占优，利好防御/债券"]
    return {"state": state, "percentile": pct, "evidence": ev}


def rate_spread_cycle(fr):
    """中美利差周期：中美利差影响汇率与外资流向。"""
    sp = _series(fr.get("cn_us_spread"))
    fx = _series(fr.get("usdcny"))
    ev = []
    if not sp or len(sp) < 4:
        return {"state": "数据不足", "evidence": ["缺少中美利差数据"]}
    cur = sp[-1]
    mom = round(sp[-1] - sp[-4], 3) if len(sp) >= 4 else 0.0
    ev.append(f"中美利差 {cur:+.2f}pct（近3期 {mom:+.2f}pct）")
    if fx and len(fx) >= 20:
        dep = (fx[-1] / fx[-20] - 1) * 100
        ev.append(f"美元兑人民币 {fx[-1]:.3f}（20期 {dep:+.2f}%）")

    # 利差为负且走阔(更负) → 人民币贬值压力大
    if cur < 0 and mom < 0:
        state = "承压（外资流出压力）"
    elif cur < 0 and mom >= 0:
        state = "边际改善"
    else:
        state = "有利（利差为正/走阔）"
    return {"state": state, "spread": cur, "evidence": ev}


# ---------- P2 新增周期 ----------

def earnings_cycle(em, fr):
    """盈利周期：用工业生产、零售销售、非农的同比方向合成（盈利的宏观代理）。
    返回 state ∈ {扩张, 走平, 收缩}。"""
    ev, parts = [], []

    ind = _series(fr.get("us_indpro"))
    if ind and len(ind) >= 4:
        d = _trend_momentum(ind, 3, min(len(ind), 12)) if len(ind) >= 8 else (ind[-1] - ind[0])
        parts.append(d)
        ev.append(f"美国工业生产指数同比 {ind[-1]:.1f}%（趋势 {d:+.2f}）")

    ret = _series(fr.get("us_retail"))
    if ret and len(ret) >= 4:
        d = _trend_momentum(ret, 3, min(len(ret), 12)) if len(ret) >= 8 else (ret[-1] - ret[0])
        parts.append(d)
        ev.append(f"美国零售销售同比 {ret[-1]:.1f}%（趋势 {d:+.2f}）")

    pay = _series(fr.get("us_payems"))
    if pay and len(pay) >= 4:
        d = _trend_momentum(pay, 3, min(len(pay), 12)) if len(pay) >= 8 else (pay[-1] - pay[0])
        parts.append(d * 0.5)
        ev.append(f"美国非农就业同比 {pay[-1]:.2f}%")

    # 国内 PPI 作为企业盈利的领先代理
    ppi = _series(em.get("ppi"), frequency="M")
    if ppi and len(ppi) >= 4:
        d = _trend_momentum(ppi, 3, min(len(ppi), 12)) if len(ppi) >= 8 else (ppi[-1] - ppi[0])
        parts.append(d * 0.5)
        ev.append(f"PPI同比 {ppi[-1]:.2f}%（企业盈利领先指标）")

    if not parts:
        return {"state": "数据不足", "evidence": ["缺少工业生产/零售/就业/PPI 数据"]}
    score = round(_mean(parts), 3)
    state = "扩张" if score > 0.05 else ("收缩" if score < -0.05 else "走平")
    return {"state": state, "score": score, "evidence": ev}


def sentiment_cycle(fr):
    """市场情绪周期：以 VIX、美债利差、美元综合判断风险偏好（全球视角代理 A 股情绪）。
    返回 state ∈ {risk-on, 中性, risk-off}。"""
    ev, parts = [], []

    vix = _series(fr.get("vix"))
    if vix and len(vix) >= 5:
        cur = vix[-1]
        pct = percentile_rank(vix, window=60)
        parts.append(-(cur - 15) / 5)
        ev.append(f"VIX {cur:.1f}（近60期分位 {pct}%）"
                  + ("，恐慌升温" if cur > 25 else ("，情绪平稳" if cur < 18 else "")))

    curve = _series(fr.get("us_curve"))
    if curve:
        parts.append(curve[-1] * 0.5)  # 利差为正=经济预期健康
        ev.append(f"美债10Y-2Y利差 {curve[-1]:+.2f}pct（{'曲线正常' if curve[-1] > 0 else '倒挂→衰退担忧'}）")

    if not parts:
        return {"state": "数据不足", "evidence": ["缺少 VIX/利差 数据"]}
    score = round(_mean(parts), 3)
    state = "risk-on（偏乐观）" if score > 0.2 else ("risk-off（偏避险）" if score < -0.2 else "中性")
    return {"state": state, "score": score, "evidence": ev}


def property_cycle(em):
    """地产周期：以 70 城新房/二手房价格指数均值方向判断。"""
    h = em.get("house") or {}
    new = _series(h, "new")
    second = _series(h, "second")
    ev = []
    if not new and not second:
        return {"state": "数据不足", "evidence": ["缺少房价数据"]}

    parts = []
    if new and len(new) >= 4:
        d = new[-1] - new[-4] if len(new) >= 4 else (new[-1] - new[0])
        parts.append(d)
        ev.append(f"70城新房价格指数 {new[-1]:.2f}（近3月 {d:+.2f}，100=持平）")
    if second and len(second) >= 4:
        d2 = second[-1] - second[-4] if len(second) >= 4 else (second[-1] - second[0])
        parts.append(d2)
        ev.append(f"70城二手房价指数 {second[-1]:.2f}（近3月 {d2:+.2f}）")

    if not parts:
        return {"state": "数据不足", "evidence": ["房价趋势需要最近4个连续有效月份"]}
    score = round(_mean(parts), 3)
    if score > 0.1:
        state = "企稳回升"
    elif score < -0.1:
        state = "继续下行"
    else:
        state = "低位筑底"
    return {"state": state, "score": score, "evidence": ev}


# ---------- 配置建议 ----------

def allocation(quadrant, style_base, credit_state, us10y, usdcny):
    style, sectors, logic = style_base, [], []
    base_map = {
        "复苏": ["科技", "消费"],
        "过热": ["有色", "能源", "化工"],
        "滞胀": ["公用事业", "必需消费"],
        "衰退": ["银行", "高股息"],
    }
    sectors = base_map.get(quadrant, [])

    if quadrant == "数据不足":
        # 周期未定位时不强行给方向性建议，只提示补充数据
        return {"style": "待定", "sectors": [],
                "logic": ["增长/通胀维度数据不足，周期未定位，暂不输出方向性配置建议",
                          "建议补充 PMI、CPI、PPI 等核心指标后重跑"]}

    # 修正1: 信用周期
    if credit_state == "宽信用":
        sectors = list(dict.fromkeys(sectors + ["券商", "顺周期"]))
        logic.append("宽信用 → 顺周期/金融板块权重上调")
    elif credit_state == "紧信用":
        logic.append("紧信用 → 控制顺周期敞口，偏向确定性")
    else:
        logic.append("信用周期数据不足，未做信用维度修正")

    # 修正2: 美债利率
    us10y_vals = _series(us10y)
    if us10y_vals and len(us10y_vals) >= 20:
        chg = round(us10y_vals[-1] - us10y_vals[-20], 2)
        if chg > 0.2:
            sectors = [s for s in sectors if s not in ("科技", "消费")]
            logic.append(f"美债利率上行 {chg:+.2f}pct → 下调成长板块（贴现率敏感）")
        elif chg < -0.2:
            logic.append(f"美债利率下行 {chg:+.2f}pct → 利好成长/新兴市场估值")

    # 修正3: 汇率
    fx = _series(usdcny)
    if fx and len(fx) >= 20:
        dep = (fx[-1] / fx[-20] - 1) * 100
        if dep > 1:
            sectors = list(dict.fromkeys(sectors + ["出口链"]))
            logic.append(f"人民币贬值 {dep:.1f}% → 利好出口链，外资敏感大盘蓝筹承压")

    return {"style": style, "sectors": sectors, "logic": logic}


# ---------- 主流程 ----------

def compute(em, fr, as_of=None, clean_credit_outliers=False):
    growth_diagnostics = {}
    g, g_ev, g_dims = growth_score(em, fr, growth_diagnostics)
    i, i_ev, i_dims = inflation_score(em, fr)
    quad, best_asset, style, qlogic = classify_quadrant(g, i, g_dims, i_dims)

    inv = inventory_cycle(em)
    cred = credit_cycle(em, clean_outliers=clean_credit_outliers)
    # P1 新增周期
    liq = liquidity_cycle(fr)
    val = valuation_cycle(em, fr)
    cg = copper_gold_cycle(fr)
    spread = rate_spread_cycle(fr)
    # P2 新增周期
    earn = earnings_cycle(em, fr)
    senti = sentiment_cycle(fr)
    prop = property_cycle(em)

    alloc = allocation(quad, style, cred.get("state"), fr.get("us10y"), fr.get("usdcny"))
    if quad != "数据不足":
        alloc["logic"] = [qlogic] + alloc["logic"]
        # P1 周期修正
        if liq.get("state") == "宽松":
            alloc["logic"].append("全球流动性宽松 → 利好风险资产估值")
        elif liq.get("state") == "收紧":
            alloc["logic"].append("全球流动性收紧 → 压制高估值板块")
        # 铜金比上行利好周期股，但在滞胀象限（避险主导）时弱化为提示，避免与防御定位冲突
        if cg.get("state", "").startswith("上行"):
            if quad in ("复苏", "过热"):
                alloc["sectors"] = list(dict.fromkeys(alloc["sectors"] + ["有色", "资源"]))
                alloc["logic"].append("铜金比上行 → 上调周期/资源板块")
            else:
                alloc["logic"].append("铜金比上行（顺周期信号），但当前周期偏防御，仅作观察不作配置依据")
        if "承压" in (spread.get("state") or ""):
            alloc["logic"].append("中美利差承压 → 关注外资流出对外资重仓板块的影响")
        # P2 周期修正
        if earn.get("state") == "扩张":
            alloc["logic"].append("盈利周期扩张 → 支撑顺周期与成长盈利兑现")
        elif earn.get("state") == "收缩":
            alloc["logic"].append("盈利周期收缩 → 关注盈利确定性，规避高估值")
        if prop.get("state") == "企稳回升":
            alloc["sectors"] = list(dict.fromkeys(alloc["sectors"] + ["地产链"]))
            alloc["logic"].append("地产企稳回升 → 关注地产链修复机会")
        if senti.get("state", "").startswith("risk-off"):
            alloc["logic"].append("市场情绪偏避险 → 控制仓位，等待情绪修复")
        elif senti.get("state", "").startswith("risk-on"):
            alloc["logic"].append("市场情绪偏乐观 → 可适度提升风险资产配置")

    # 多周期综合时间轴（供 P2 可视化）
    timeline = build_timeline(em, fr)

    return {
        "as_of": as_of or em.get("as_of") or fr.get("as_of"),
        "calculation_version": CALCULATION_VERSION,
        "period_policy": "日期和值严格配对；仅使用末端连续有效原生频率窗口。M按相邻月，Q按相邻季，D按工作日（仅容许周末，未推定节假日），W按7天；趋势至少4期，长窗口不足则缩短并披露。",
        "point_in_time": False,
        "merrill_clock": {
            "quadrant": quad,
            "growth_momentum": g,
            "inflation_momentum": i,
            "growth_dims": g_dims,
            "inflation_dims": i_dims,
            "growth_evidence": g_ev,
            "growth_diagnostics": growth_diagnostics,
            "inflation_evidence": i_ev,
            "best_asset": best_asset,
            "stock_style": style,
        },
        "inventory_cycle": inv,
        "credit_cycle": cred,
        # P1 新增
        "liquidity_cycle": liq,
        "valuation_cycle": val,
        "copper_gold_cycle": cg,
        "rate_spread_cycle": spread,
        # P2 新增
        "earnings_cycle": earn,
        "sentiment_cycle": senti,
        "property_cycle": prop,
        "timeline": timeline,
        "allocation": alloc,
        "disclaimer": "基于公开宏观数据的历史规律可视化，周期框架为经验性方法论，不构成投资建议。",
    }


def build_timeline(em, fr):
    """多周期综合时间轴：对每个周期按月给出方向评分(+1改善/-1恶化)，用于热力时间轴。"""
    rows, months = [], []

    def em_yoy(key):
        ind = em.get(key) or {}
        return (ind.get("dates") or []), list((ind.get("series") or {}).get("yoy", []))

    def em_val(key, field="value"):
        ind = em.get(key) or {}
        return (ind.get("dates") or []), list((ind.get("series") or {}).get(field, []))

    def fr_vals(key):
        ind = fr.get(key) or {}
        return (ind.get("dates") or []), list(ind.get("values", []))

    dims = {}
    d, v = em_val("pmi"); dims["增长(PMI)"] = (d, v, 50, "level")
    d, v = em_val("cpi"); dims["通胀(CPI)"] = (d, v, None, "dir")
    d, v = em_val("ppi"); dims["盈利(PPI)"] = (d, v, None, "dir")
    d, v = em_yoy("m1"); dims["信用(M1)"] = (d, v, None, "dir")
    d, v = fr_vals("us10y_real"); dims["流动性(实际利率)"] = (d, v, None, "inv")
    d, v = fr_vals("copper_gold"); dims["周期(铜金比)"] = (d, v, None, "dir")
    d, v = fr_vals("vix"); dims["情绪(VIX)"] = (d, v, None, "inv")
    h = em.get("house") or {}
    d = h.get("dates") or []; v = (h.get("series") or {}).get("new", [])
    dims["地产(房价)"] = (d, v, None, "dir")

    # 统一到最近 24 个月（日频序列按月末值归到 YYYY-MM）
    def to_monthly(dd, vv):
        m = {}
        for d, v in paired(dd, vv):
            if v is None or not d:
                continue
            m[d[:7]] = v  # 后写覆盖 → 月内最后一个值
        return m

    dims_m = {name: (to_monthly(dd, vv), ref, mode) for name, (dd, vv, ref, mode) in dims.items()}
    all_months = sorted({mon for (mm, _, _) in dims_m.values() for mon in mm})
    months = all_months[-24:]
    for name, (m_map, ref, mode) in dims_m.items():
        seq = [m_map.get(m) for m in months]
        # 计算方向分：与 3 期前比
        scores = [None] * len(months)
        for i in range(3, len(seq)):
            cur, prev = seq[i], seq[i - 3]
            if any(v is None for v in seq[i-3:i+1]) or not all(adjacent(months[j-1], months[j]) for j in range(i-2,i+1)):
                continue
            if mode == "level":
                s = 1 if cur > (ref or 0) else -1
            elif mode == "inv":
                s = 1 if cur < prev else (-1 if cur > prev else 0)
            else:
                s = 1 if cur > prev else (-1 if cur < prev else 0)
            scores[i] = s
        rows.append({"name": name, "scores": scores})

    return {"months": months, "rows": rows}


def load_payload(em_path, fr_path):
    em, fr, as_of = {}, {}, None
    for path, target in ((em_path, "em"), (fr_path, "fr")):
        if not path or not os.path.exists(path):
            continue
        try:
            d = json.load(open(path, encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"[warn] 跳过无法解析的数据文件 {path}: {e}", file=sys.stderr)
            continue
        if not isinstance(d, dict):
            print(f"[warn] 数据文件格式异常（非对象）: {path}", file=sys.stderr)
            continue
        if target == "em":
            em = d.get("indicators", {}) or {}
            as_of = d.get("as_of") or as_of
        else:
            fr = d.get("indicators", {}) or {}
            as_of = as_of or d.get("as_of")
    if not em and not fr:
        raise SystemExit("未找到可用的东财/FRED 数据，请先运行 fetch_eastmoney.py 与 fetch_fred.py")
    return em, fr, as_of


def main():
    ap = argparse.ArgumentParser(description="宏观周期研判")
    ap.add_argument("--eastmoney", default="eastmoney_data.json")
    ap.add_argument("--fred", default="fred_data.json")
    ap.add_argument("--out", default="cycle.json")
    ap.add_argument("--clean-credit-outliers", action="store_true", help="显式启用孤立点屏蔽研究假设；默认保留原值")
    args = ap.parse_args()

    em, fr, as_of = load_payload(args.eastmoney, args.fred)
    result = compute(em, fr, as_of=as_of, clean_credit_outliers=args.clean_credit_outliers)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    mc = result["merrill_clock"]
    print(f"[cycle] 美林时钟象限: {mc['quadrant']}  (增长动能 {mc['growth_momentum']:+.3f}, "
          f"通胀动能 {mc['inflation_momentum']:+.3f})")
    print(f"[cycle] 库存周期: {result['inventory_cycle']['phase']} | "
          f"信用周期: {result['credit_cycle'].get('state')}")
    print(f"[cycle] 配置: {result['allocation']['style']} → {', '.join(result['allocation']['sectors'])}")
    print(f"[cycle] 已写入 {args.out}")


if __name__ == "__main__":
    main()
