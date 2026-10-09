#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compute_long_cycle.py — 长周期（长波梯队）计算引擎

职责：从全历史宏观序列中，用【带通滤波】提取中长周期分量，输出：
  - 朱格拉周期（Juglar, 7-11 年，设备投资/产能）
  - 库兹涅茨周期（Kuznets, 15-25 年，地产/建筑）
  - 债务周期（Dalio 长债代理，加杠杆/去杠杆阶段）

方法说明（重要，避免误导）：
  1. 先把季/月频序列统一重采样为【季度】，消除频率差异；
  2. 用「带通滤波 = 中心移动平均的差」提取目标频段分量：
       band(t) = MA(short)(x) - MA(long)(x)
     其中 short/long 取周期上/下限对应的窗口长度。
     这是 Christano-Fitzgerald / BK 滤波的简化实现，无需 scipy。
  3. 对分量做 z-score 标准化，用「水平 + 方向」融合判断所处阶段。

注意：康波(Kondratiev)/熊彼特(Schumpeter) 属技术革命定性判断，
不由本引擎计算，见 assets/long_wave.json 与 references/long_wave.md。
"""
import json
import math
import sys


# ---------------------------------------------------------------- 基础工具

def _resample_quarterly(dates, values, freq):
    """把任意频率序列重采样为季度（每个季度取最后一个有效值）。"""
    buckets = {}
    order = []
    for d, v in zip(dates, values):
        if v is None:
            continue
        y = int(d[:4])
        if freq == "Q":
            q = (int(d[5:7]) - 1) // 3 + 1 if len(d) >= 7 else 1
        else:
            m = int(d[5:7]) if len(d) >= 7 else 1
            q = (m - 1) // 3 + 1
        key = (y, q)
        if key not in buckets:
            order.append(key)
        buckets[key] = v
    order.sort()
    labels = [f"{y}Q{q}" for y, q in order]
    series = [buckets[k] for k in order]
    return labels, series


def _moving_average(series, window):
    """中心移动平均，窗口不足处用边界值填充（保证长度一致）。"""
    n = len(series)
    if n == 0 or window <= 1:
        return list(series)
    half = window // 2
    out = []
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        seg = [x for x in series[lo:hi] if x is not None]
        out.append(sum(seg) / len(seg) if seg else None)
    return out


def _fill_none(series):
    """线性插值填充 None（边界用最近有效值）。"""
    n = len(series)
    idx = [i for i, v in enumerate(series) if v is not None]
    if not idx:
        return [0.0] * n
    out = list(series)
    for i in range(n):
        if out[i] is None:
            prev = [j for j in idx if j < i]
            nxt = [j for j in idx if j > i]
            if prev and nxt:
                p, q = prev[-1], nxt[0]
                r = (i - p) / (q - p)
                out[i] = out[p] + (out[q] - out[p]) * r
            elif prev:
                out[i] = out[prev[-1]]
            else:
                out[i] = out[nxt[0]]
    return out


def _detrend(series, window):
    """去掉长趋势：原序列减去长窗口移动平均。"""
    ma = _moving_average(series, window)
    return [s - m if (s is not None and m is not None) else None
            for s, m in zip(series, ma)]


def bandpass(series, short_win, long_win):
    """
    带通分量 = MA(short)(x) - MA(long)(x)。
    结果为「中周期偏离长期趋势」的部分，即目标周期分量。
    short_win / long_win 单位为「季度数」。
    """
    x = _fill_none(series)
    s = _moving_average(x, short_win)
    l = _moving_average(x, long_win)
    return [a - b for a, b in zip(s, l)]


def _zscore(series):
    vals = [v for v in series if v is not None]
    if len(vals) < 2:
        return [0.0] * len(series)
    m = sum(vals) / len(vals)
    var = sum((v - m) ** 2 for v in vals) / len(vals)
    sd = math.sqrt(var) or 1.0
    return [((v - m) / sd if v is not None else 0.0) for v in series]


def _slope(series, span=4):
    """近 span 期斜率（用首尾差 / span）。"""
    vals = [v for v in series[-span:] if v is not None]
    if len(vals) < 2:
        return 0.0
    return (vals[-1] - vals[0]) / (len(vals) - 1)


def _stages(series, labels, peak_th=0.6, trough_th=-0.6, min_gap=2, min_span_q=12):
    """
    识别长周期峰谷：在标准化分量上找局部极值点。
    - min_gap:     相邻同类点最小间隔（季），滤掉抖动
    - min_span_q:  峰→峰 / 谷→谷 的最小跨度（季），短于此视为噪声不分轮
    """
    pts = []
    n = len(series)
    for i in range(2, n - 2):
        w = series[max(0, i - 2):i + 3]
        if series[i] == max(w) and series[i] >= peak_th:
            pts.append({"i": i, "date": labels[i], "type": "peak",
                        "value": round(series[i], 2)})
        elif series[i] == min(w) and series[i] <= trough_th:
            pts.append({"i": i, "date": labels[i], "type": "trough",
                        "value": round(series[i], 2)})
    # 一级去重：同类相邻太近只留更极端
    d1 = []
    for p in pts:
        if d1 and d1[-1]["type"] == p["type"] and p["i"] - d1[-1]["i"] <= min_gap:
            if (p["type"] == "peak" and p["value"] > d1[-1]["value"]) or \
               (p["type"] == "trough" and p["value"] < d1[-1]["value"]):
                d1[-1] = p
        else:
            d1.append(p)
    # 二级过滤：同类间隔 < min_span_q 视为同一轮，保留更极端
    out = []
    for p in d1:
        prev_same = [q for q in out if q["type"] == p["type"]]
        if prev_same and p["i"] - prev_same[-1]["i"] < min_span_q:
            q = prev_same[-1]
            if (p["type"] == "peak" and p["value"] > q["value"]) or \
               (p["type"] == "trough" and p["value"] < q["value"]):
                out[out.index(q)] = p
        else:
            out.append(p)
    return out


def _phase(level, direction, name, period_txt):
    """
    用「水平(z) + 方向(斜率)」融合给出阶段判断。
    返回 (阶段标签, 说明, 建议)。
    """
    lv, dr = level, direction
    if lv >= 0.6 and dr <= 0:
        stage, tip = "周期见顶", f"{name}处于长周期高位且动能减弱，警惕回落风险"
    elif lv >= 0.6 and dr > 0:
        stage, tip = "高位扩张末段", f"{name}仍在上行但已在历史高位区，接近周期顶部"
    elif lv >= 0 and dr > 0:
        stage, tip = "扩张中段", f"{name}处于上行通道，长周期偏强"
    elif lv >= 0 and dr <= 0:
        stage, tip = "扩张转弱", f"{name}由负转正区回落，扩张动能衰减"
    elif lv < 0 and dr <= 0:
        stage, tip = "收缩/筑底中", f"{name}处于长周期低位且仍在下行，尚未见底"
    elif lv < 0 and dr > 0:
        stage, tip = "底部回升", f"{name}从长周期低位开始修复，关注拐点"
    else:
        stage, tip = "中性", f"{name}处于周期中枢附近"
    return stage, tip, f"（{period_txt}）"


# ---------------------------------------------------------------- 三大长周期

def _cycle_block(name, period_txt, engine, labels, series, short_win, long_win,
                 note=""):
    """
    通用长周期计算块。
    series 为已标准化(z-score)的合成序列；先去除超长趋势，再带通提取目标频段。
    """
    # 先去除 100 季以上的超长趋势（避免单调趋势污染），再做带通
    detr = _detrend(series, long_win * 2)
    comp = bandpass(detr, short_win, long_win)
    # 标准化分量并截断尖刺（±3σ）
    z = _zscore(comp)
    z = [max(-3.0, min(3.0, v)) for v in z]
    cur = z[-1] if z else 0.0
    direction = _slope(z, span=4)
    stage, tip, tail = _phase(cur, direction, name, period_txt)
    pts = _stages(z, labels)
    return {
        "name": name,
        "engine": engine,
        "period": period_txt,
        "labels": labels,
        "component": [round(v, 3) for v in z],
        "raw": [round(v, 3) if v is not None else None for v in series],
        "latest": round(cur, 3),
        "direction": round(direction, 4),
        "stage": stage,
        "note": (tip + tail) if tip else note,
        "turns": pts,
        "n_obs": len(labels),
    }


def juglar_cycle(fred):
    """
    朱格拉周期（7-11 年，设备投资）：
    用设备投资同比 + 固定资产投资同比的带通分量平均。
    7 年 ≈ 28 季，11 年 ≈ 44 季；带通取 [short=20, long=48]。
    """
    comps, labels_ref = [], None
    for key in ("lj_equip", "lj_gfcf"):
        s = fred.get(key)
        if not s or len(s.get("dates", [])) < 60:
            continue
        labels, vals = _resample_quarterly(s["dates"], s["values"], s.get("freq", "Q"))
        z = _zscore(vals)
        comps.append(z)
        labels_ref = labels if labels_ref is None else labels_ref

    if not comps:
        return None
    n = min(len(c) for c in comps)
    avg = [sum(c[i] for c in comps) / len(comps) for i in range(n)]
    labels = labels_ref[-n:]
    # 朱格拉带通：中周期 7-11 年
    return _cycle_block("朱格拉周期", "设备投资 7-11 年",
                        "bandpass(20Q,48Q)", labels, avg, 20, 48,
                        note="设备投资/产能投资的中周期，对应企业资本开支轮动")


def kuznets_cycle(fred):
    """
    库兹涅茨周期（15-25 年，地产/建筑）：
    住宅投资同比 + 新屋开工 + 房价同比 的带通分量。
    15 年 ≈ 60 季，25 年 ≈ 100 季；带通取 [short=40, long=100]。
    """
    comps, labels_ref = [], None
    for key in ("lj_house", "lj_houst", "lj_cs"):
        s = fred.get(key)
        if not s or len(s.get("dates", [])) < 60:
            continue
        labels, vals = _resample_quarterly(s["dates"], s["values"], s.get("freq", "M"))
        if len(vals) < 60:
            continue
        comps.append(_zscore(vals))
        labels_ref = labels if labels_ref is None else labels_ref
    if not comps:
        return None
    n = min(len(c) for c in comps)
    avg = [sum(c[i] for c in comps) / len(comps) for i in range(n)]
    labels = labels_ref[-n:]
    return _cycle_block("库兹涅茨周期", "地产/建筑 15-25 年",
                        "bandpass(40Q,100Q)", labels, avg, 40, 100,
                        note="以住宅投资与房价刻画的长地产周期，跨越代际")


def debt_cycle(fred):
    """
    债务周期（Dalio 长债代理）：
    用【债务/GDP 的年度变化(Δ)】+【银行信贷脉冲】刻画加杠杆/去杠杆动能。
    注意：债务/GDP 水平单调上升，水平 z-score 无判别力，
    必须用「变化率」才能识别加杠杆/去杠杆阶段。
    """
    dg = fred.get("lj_debtgdp")
    if not dg or not dg.get("dates"):
        return None
    labels_all, vals_all = _resample_quarterly(dg["dates"], dg["values"], dg.get("freq", "Q"))
    if len(vals_all) < 8:
        return None
    # 债务/GDP 同比变化（百分点），即加杠杆速度
    delta = []
    for i in range(4, len(vals_all)):
        delta.append(vals_all[i] - vals_all[i - 4])
    labels = labels_all[4:]
    dz = _zscore(delta)
    dz = [max(-3.0, min(3.0, v)) for v in dz]
    cur_level = dz[-1]
    dir_level = _slope(dz, span=4)

    # 信贷脉冲：银行信贷同比变化的标准化
    pulse_z = None
    credit_note = ""
    cr = fred.get("lj_credit")
    if cr and cr.get("dates"):
        cl, cvals = _resample_quarterly(cr["dates"], cr["values"], cr.get("freq", "W"))
        if len(cvals) >= 8:
            yoy = [((cvals[i] / cvals[i - 4] - 1) * 100) for i in range(4, len(cvals)) if cvals[i - 4]]
            if len(yoy) >= 8:
                pulse = [yoy[i] - yoy[i - 1] for i in range(1, len(yoy))]
                pulse_z = round(_zscore(pulse)[-1], 3)
                credit_note = f"信贷脉冲 z={pulse_z:+.2f}"

    if cur_level > 0.5 and dir_level > 0:
        stage, tip = "加速加杠杆", "债务/GDP 加速抬升，信用处于扩张末段，长期风险积累"
    elif cur_level > 0.5 and dir_level <= 0:
        stage, tip = "高位去杠杆", "加杠杆速度已见顶回落，进入长期债务消化阶段"
    elif cur_level > -0.5 and dir_level > 0:
        stage, tip = "温和加杠杆", "债务/GDP 缓慢抬升，信用扩张温和"
    elif cur_level > -0.5 and dir_level <= 0:
        stage, tip = "温和去杠杆", "加杠杆速度回落，信用趋于收缩"
    else:
        stage, tip = "深度去杠杆", "债务/GDP 增速处历史低位，处于去杠杆/债务出清期"

    # 可视化：变化率曲线 + 原始债务/GDP 水平（双轴）
    k = len(labels)
    pulse_series = None
    if cr and cr.get("dates"):
        cl, cvals = _resample_quarterly(cr["dates"], cr["values"], cr.get("freq", "W"))
        yoy = [((cvals[i] / cvals[i - 4] - 1) * 100) for i in range(4, len(cvals)) if cvals[i - 4]]
        pulse = [round(yoy[i] - yoy[i - 1], 3) for i in range(1, len(yoy))]
        kk = min(len(pulse), k)
        pulse_series = pulse[-kk:]

    return {
        "name": "债务周期",
        "engine": "debt/credit",
        "period": "长债 50-75 年（代理）",
        "labels": labels[-k:],
        "component": [round(v, 3) for v in dz[-k:]],
        "raw": [round(v, 2) for v in vals_all[-k:]],   # 债务/GDP 水平（右轴）
        "latest": round(cur_level, 3),
        "direction": round(dir_level, 4),
        "stage": stage,
        "note": tip + ("；" + credit_note if credit_note else ""),
        "turns": _stages([round(v, 3) for v in dz], labels, 0.8, -0.8),
        "pulse": pulse_series,
        "debt_gdp_latest": round(vals_all[-1], 2),
        "delta_latest": round(delta[-1], 2),
        "n_obs": len(labels),
    }


# ---------------------------------------------------------------- 总装

def compute(fred_indicators):
    """输入 fetch_fred 的 indicators dict，输出长周期梯队结果。"""
    out = {"cycles": {}, "available": [], "missing": []}
    builders = [("juglar", juglar_cycle), ("kuznets", kuznets_cycle),
                ("debt", debt_cycle)]
    for key, fn in builders:
        try:
            r = fn(fred_indicators)
            if r:
                out["cycles"][key] = r
                out["available"].append(key)
            else:
                out["missing"].append(key)
        except Exception as e:  # noqa: BLE001
            out["missing"].append(key)
            print(f"[long_cycle] {key} 计算失败: {e}", file=sys.stderr)
    return out


def load_payload(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:  # noqa: BLE001
        print(f"[long_cycle] 读取 {path} 失败: {e}", file=sys.stderr)
        return {}


def main():
    import argparse
    ap = argparse.ArgumentParser(description="长周期（朱格拉/库兹涅茨/债务）计算")
    ap.add_argument("--fred", required=True, help="fetch_fred.py 输出的 JSON")
    ap.add_argument("--out", default="long_cycle.json")
    args = ap.parse_args()
    fred = load_payload(args.fred)
    ind = fred.get("indicators", fred)
    res = compute(ind)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(f"[long_cycle] 可用周期: {res['available']}，缺失: {res['missing']}")
    for k, c in res["cycles"].items():
        print(f"  {k}: {c['name']} -> {c['stage']} (z={c['latest']:+.2f}, "
              f"dir={c['direction']:+.3f}, n={c['n_obs']})")
    print(f"[long_cycle] 已写入 {args.out}")


if __name__ == "__main__":
    main()
