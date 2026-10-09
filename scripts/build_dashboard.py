#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_dashboard.py — 组装单文件宏观看板 HTML

输入: eastmoney JSON + fred JSON + cycle JSON
输出: 自包含 HTML（内联 ECharts + 内嵌数据）

用法:
    python3 build_dashboard.py --eastmoney em.json --fred fr.json --cycle cycle.json \
        --out local-data/macro-dashboard.html

正式数据缺项留空；演示样本仅由 --demo 显式启用。
"""
import argparse
import json
import os
import sys
import datetime
from html import escape

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
ASSETS = os.path.join(SKILL_DIR, "assets")

# 因子-行业敏感度矩阵（见 references/transmission.md）
HEATMAP = {
    "factors": ["利率↓", "宽信用", "通胀↑", "人民币贬值", "美债利率↑"],
    "industries": ["银行", "券商", "地产", "有色", "科技成长", "必需消费", "公用事业", "出口链"],
    "matrix": [
        [-0.3, 0.6, 0.5, 0.2, 0.8, 0.1, 0.7, 0.2],
        [0.8, 0.7, 0.6, 0.5, 0.3, 0.2, 0.1, 0.4],
        [-0.2, -0.1, -0.3, 0.8, -0.4, -0.3, -0.2, -0.1],
        [-0.2, -0.3, -0.2, 0.1, -0.3, -0.1, 0.0, 0.7],
        [-0.3, -0.4, -0.2, 0.1, -0.7, -0.1, -0.2, -0.2],
    ],
}

# 传导链路（见 references/transmission.md）
CHAINS = [
    {"name": "货币宽松链", "from": "货币政策宽松", "mid": "利率↓/贴现率↓", "to": "估值扩张→成长股占优"},
    {"name": "信用扩张链", "from": "社融↑/宽信用", "mid": "中长贷↑/需求回暖", "to": "盈利↑→顺周期/银行"},
    {"name": "通胀链", "from": "CPI/PPI↑", "mid": "上游涨价/下游成本", "to": "资源股↑·中游承压"},
    {"name": "汇率链", "from": "人民币贬值", "mid": "外资流出压力", "to": "蓝筹承压·出口链受益"},
    {"name": "海外流动性链", "from": "美联储加息", "mid": "美债利率↑/风偏↓", "to": "新兴市场估值承压"},
]


def _load(path):
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def _align(dates, series, all_dates):
    """把 (dates, values) 对齐到 all_dates（缺失补 None）。"""
    m = dict(zip(dates, series))
    return [m.get(d) for d in all_dates]


def _align_to_monthly(dates, series, month_dates):
    """日频序列对齐到月频轴：每月取最后一个有效值。"""
    monthly = {}
    for d, v in zip(dates, series):
        if v is None:
            continue
        monthly[d[:7]] = v  # 后写覆盖 → 月内最后一个交易日
    return [monthly.get(d[:7]) for d in month_dates]


def _tail(lst, n):
    return lst[-n:] if lst else []


def build_payload(em_raw, fr_raw, cycle, long_cycle=None, long_wave=None,
                  attribution=None, policy=None, offline=False, credit=None):
    em = (em_raw or {}).get("indicators", {})
    fr = (fr_raw or {}).get("indicators", {})

    def em_series(key, field="value"):
        ind = em.get(key) or {}
        dates = ind.get("dates", [])
        vals = (ind.get("series") or {}).get(field, [])
        return dates, [v for v in vals]

    # ---------- KPI ----------
    def latest(key, field="value", src="em"):
        ind = (em if src == "em" else fr).get(key) or {}
        if src == "em":
            vals = [v for v in (ind.get("series") or {}).get(field, []) if v is not None]
        else:
            vals = [v for v in ind.get("values", []) if v is not None]
        return vals[-1] if vals else None

    def mom(key, field="value", src="em"):
        ind = (em if src == "em" else fr).get(key) or {}
        if src == "em":
            vals = [v for v in (ind.get("series") or {}).get(field, []) if v is not None]
        else:
            vals = [v for v in ind.get("values", []) if v is not None]
        return round(vals[-1] - vals[-2], 3) if len(vals) >= 2 else None

    m1y = _tail([v for v in (em.get("m1", {}).get("series", {}).get("yoy", [])) if v is not None], 1)
    m2y = _tail([v for v in (em.get("m2", {}).get("series", {}).get("yoy", [])) if v is not None], 1)
    scissors = round(m1y[-1] - m2y[-1], 2) if (m1y and m2y) else None

    kpi = {
        "gdp": None, "cpi": latest("cpi"), "cpi_mom": mom("cpi"),
        "ppi": latest("ppi"), "ppi_mom": mom("ppi"),
        "pmi": latest("pmi"), "pmi_mom": mom("pmi"),
        "retail": latest("retail", "yoy"), "retail_mom": mom("retail", "yoy"),
        "m1": latest("m1", "yoy"), "m1_mom": mom("m1", "yoy"),
        "m2": latest("m2", "yoy"), "m2_mom": mom("m2", "yoy"),
        "scissors": scissors, "scissors_mom": None,
        "us10y": latest("us10y", src="fr"), "us10y_mom": mom("us10y", src="fr"),
        "fedfunds": latest("fedfunds", src="fr"), "fedfunds_mom": mom("fedfunds", src="fr"),
        "usdcny": latest("usdcny", src="fr"), "usdcny_mom": mom("usdcny", src="fr"),
        "wti": latest("wti", src="fr"), "wti_mom": mom("wti", src="fr"),
    }
    # GDP 同比
    gdp_same = _tail([v for v in (em.get("gdp", {}).get("series", {}).get("yoy", [])) if v is not None], 1)
    kpi["gdp"] = gdp_same[-1] if gdp_same else None
    # 剪刀差环比
    m1all = [v for v in (em.get("m1", {}).get("series", {}).get("yoy", [])) if v is not None]
    m2all = [v for v in (em.get("m2", {}).get("series", {}).get("yoy", [])) if v is not None]
    if len(m1all) >= 2 and len(m2all) >= 2:
        kpi["scissors_mom"] = round((m1all[-1] - m2all[-1]) - (m1all[-2] - m2all[-2]), 2)

    # ---------- 国内 ----------
    def take(key, fields, n=36):
        ind = em.get(key) or {}
        d = _tail(ind.get("dates", []), n)
        return d, {k: _tail([v for v in (ind.get("series") or {}).get(k, [])], n) for k in fields}

    cpi_d, cpi_v = take("cpi", ["value", "mom"])
    ppi_d, ppi_v = take("ppi", ["value"])
    pmi_d, pmi_v = take("pmi", ["value", "non_mfg"])
    ret_d, ret_v = take("retail", ["value", "yoy"])
    m1_d, m1_v = take("m1", ["yoy"])
    m2_d, m2_v = take("m2", ["yoy"])
    gdp_d, gdp_v = take("gdp", ["value", "yoy"], n=20)

    # M1-M2 剪刀差序列（按日期对齐 + 剔除源数据孤立异常点）
    m1_map = {d: v for d, v in zip(m1_d, m1_v["yoy"]) if v is not None}
    m2_map = {d: v for d, v in zip(m2_d, m2_v["yoy"]) if v is not None}
    common = sorted(set(m1_map) & set(m2_map))
    sc_raw = [round(m1_map[d] - m2_map[d], 2) for d in common] if common else []
    sys.path.insert(0, HERE)
    from compute_cycle import _clean_outliers
    sc_clean, _ = _clean_outliers(common, sc_raw)
    scissors_series = sc_clean

    retail_yoy = [v for v in ret_v["yoy"]]
    sc_map = dict(zip(common, scissors_series))
    domestic = {
        "cpi": {"dates": cpi_d, "cpi": cpi_v["cpi" if "cpi" in cpi_v else "value"],
                "ppi": _align(ppi_d, ppi_v["value"], cpi_d)},
        "pmi": {"dates": pmi_d, "mfg": pmi_v["value"], "nonmfg": pmi_v["non_mfg"]},
        "money": {"dates": m1_d, "m1": m1_v["yoy"],
                  "m2": _align(m2_d, m2_v["yoy"], m1_d),
                  "scissors": [sc_map.get(d) for d in m1_d]},
        "retail": {"dates": ret_d, "retail": retail_yoy},
        "gdp": {"dates": gdp_d, "gdp": gdp_v["yoy"],
                "gdpGapped": _align(gdp_d, gdp_v["yoy"], ret_d)},
    }

    # ---------- 海外 ----------
    def fr_take(key, n=60):
        ind = fr.get(key) or {}
        return _tail(ind.get("dates", []), n), _tail([v for v in ind.get("values", [])], n)

    fd, fv = fr_take("fedfunds")
    ud, uv = fr_take("us10y", 260)          # 日频全量，对齐到月频轴
    cd, cv = fr_take("usdcny", 260)         # 日频
    xd, xv = fr_take("usd_index", 260)      # 日频
    pd_, pv = fr_take("us_cpi")
    nd, nv = fr_take("us_unrate")
    od, ov = fr_take("wti", 260)            # 日频

    overseas = {
        "rate": {"dates": fd, "fedfunds": fv, "us10y": _align_to_monthly(ud, uv, fd)},
        "fx": {"dates": cd, "usdcny": cv, "usdindex": _align(xd, xv, cd)},
        "us": {"dates": pd_, "cpi": pv, "unrate": _align(nd, nv, pd_)},
        "oil": {"dates": od, "wti": ov},
    }

    # ---------- P1 扩展周期数据 ----------
    xd2, xv2 = fr_take("usd_index", 260)
    rd, rv = fr_take("us10y_real", 260)
    rv_al = _align(rd, rv, xd2)
    cgd, cgv = fr_take("copper_gold", 60)
    spd, spv = fr_take("cn_us_spread", 60)
    vd, vv = fr_take("vix", 260)
    curve_dates, cv2 = fr_take("us_curve", 260)
    cv2_al = _align(curve_dates, cv2, vd)

    p1 = {
        "liquidity": {"dates": xd2, "usdindex": xv2, "real": rv_al},
        "copper_gold": {"dates": cgd, "values": cgv},
        "spread": {"dates": spd, "values": spv},
        "risk": {"dates": vd, "vix": vv, "curve": cv2_al},
    }

    # ---------- P2 扩展数据 ----------
    h = em.get("house") or {}
    hd = h.get("dates", [])
    hnew = (h.get("series") or {}).get("new", [])
    hsec = (h.get("series") or {}).get("second", [])
    ed, ev_ = fr_take("us_indpro", 60)
    rd2, rv2 = fr_take("us_retail", 60)
    p1["property"] = {"dates": hd, "new": hnew, "second": hsec}
    p1["earnings"] = {"dates": ed, "indpro": ev_, "retail": _align(rd2, rv2, ed)}

    # ---------- 数据表 ----------
    header = ["指标", "最新值", "单位", "上期", "变化"]
    body = []
    table_specs = [
        ("CPI同比", em.get("cpi"), "value", "%"),
        ("PPI同比", em.get("ppi"), "value", "%"),
        ("制造业PMI", em.get("pmi"), "value", ""),
        ("社零总额", em.get("retail"), "value", "亿元"),
        ("M1同比", em.get("m1"), "yoy", "%"),
        ("M2同比", em.get("m2"), "yoy", "%"),
    ]
    for name, ind, field, unit in table_specs:
        if not ind:
            continue
        vals = [v for v in (ind.get("series") or {}).get(field, []) if v is not None]
        if not vals:
            continue
        body.append([name, round(vals[-1], 2), unit,
                     round(vals[-2], 2) if len(vals) >= 2 else None,
                     round(vals[-1] - vals[-2], 2) if len(vals) >= 2 else None])
    for name, key, unit in [("10Y美债", "us10y", "%"), ("联邦基金利率", "fedfunds", "%"),
                            ("美元兑人民币", "usdcny", ""), ("美国CPI同比", "us_cpi", "%"),
                            ("WTI原油", "wti", "$/桶")]:
        ind = fr.get(key) or {}
        vals = [v for v in ind.get("values", []) if v is not None]
        if not vals:
            continue
        body.append([name, round(vals[-1], 2), unit,
                     round(vals[-2], 2) if len(vals) >= 2 else None,
                     round(vals[-1] - vals[-2], 2) if len(vals) >= 2 else None])

    from compute_credit import compute as compute_credit
    from data_evidence import build_evidence
    return {
        "evidence": build_evidence({"eastmoney": em_raw, "fred": fr_raw, "credit": credit}),
        "credit": compute_credit(credit, offline=offline),
        "kpi": kpi,
        "cycle": cycle,
        "domestic": domestic,
        "overseas": overseas,
        "p1": p1,
        "long_cycle": long_cycle or {},
        "long_wave": long_wave or {},
        "attribution": attribution or {},
        "policy": policy or {},
        "transmission": {"chains": CHAINS, "heatmap": HEATMAP},
        "table": {"header": header, "body": body},
        "offline": offline,
        "data_quality": {
            "status": "sample" if offline else (
                "partial" if any((source or {}).get("errors") for source in (em_raw, fr_raw)) else "live"),
            "errors": [error for source in (em_raw, fr_raw)
                       for error in (source or {}).get("errors", [])],
        },
    }


def render(payload, out_path, title="宏观全景看板"):
    with open(os.path.join(ASSETS, "echarts.min.js"), encoding="utf-8") as f:
        echarts_js = f.read()
    with open(os.path.join(ASSETS, "template.html"), encoding="utf-8") as f:
        html = f.read()

    offline = payload.get("offline")
    partial = (payload.get("data_quality", {}).get("status") == "partial"
               or payload.get("credit", {}).get("status") == "partial")
    badge_text = "示例数据" if offline else ("数据不完整" if partial else "实时数据")
    src_text = escape(str(payload.get("demo_source") or "东方财富 + FRED（离线示例快照）")) if offline else (
        "东方财富 + FRED；信用模块另含商务部数据（部分数据，见逐项来源）" if partial
        else "东方财富 + FRED（实时抓取）")

    html = html.replace("__TITLE__", title)
    html = html.replace("__BADGE__", badge_text)
    html = html.replace("__ASOF__", str((payload.get("cycle") or {}).get("as_of") or "—"))
    html = html.replace("__GENTIME__", datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    html = html.replace("__CALC_VERSION__", escape(str((payload.get("cycle") or {}).get("calculation_version") or "未登记")))
    html = html.replace("__SRCTEXT__", src_text)
    notice_files = ["LICENSE_SCOPE.md", "LICENSE", "third_party/echarts-5.5.1/LICENSE",
                    "third_party/echarts-5.5.1/NOTICE", "third_party/echarts-5.5.1/LICENSE-d3"]
    notices = []
    for name in notice_files:
        with open(os.path.join(SKILL_DIR, name), encoding="utf-8") as stream:
            notices.append(name + "\n" + stream.read())
    html = html.replace("__THIRD_PARTY_NOTICES__", escape("\n\n".join(notices)))
    html = html.replace("__ECHARTS__", echarts_js)
    html = html.replace("__DATA__", json.dumps(payload, ensure_ascii=False))

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


def main():
    ap = argparse.ArgumentParser(description="生成单文件宏观看板 HTML")
    ap.add_argument("--eastmoney", default="eastmoney_data.json")
    ap.add_argument("--fred", default="fred_data.json")
    ap.add_argument("--cycle", default="cycle.json")
    ap.add_argument("--longcycle", default="long_cycle.json")
    ap.add_argument("--attribution", default="attribution.json")
    ap.add_argument("--credit", default=None)
    ap.add_argument("--demo", action="store_true", help="仅演示：允许使用离线示例，不作正式研究")
    ap.add_argument("--demo-snapshot", default=None, help="仅配合--demo显式复现已有快照；需自行核对数据权利")
    ap.add_argument("--out", default="/workspace/macro-dashboard.html")
    ap.add_argument("--title", default="宏观全景看板")
    args = ap.parse_args()
    if args.demo_snapshot and not args.demo:
        raise SystemExit("--demo-snapshot 仅用于显式演示")

    em = _load(args.eastmoney)
    fr = _load(args.fred)
    cycle = _load(args.cycle)
    long_cycle = _load(args.longcycle)
    attribution = _load(args.attribution)
    credit = _load(args.credit)
    long_wave = _load(os.path.join(ASSETS, "long_wave.json")) or {}
    policy = _load(os.path.join(ASSETS, "policy_calendar.json")) or {}
    offline = False
    if not args.demo and any((source or {}).get("source") == "sample" for source in (em, fr, credit)):
        raise SystemExit("正式研究不能使用标记为sample的输入；演示请显式使用 --demo")

    if args.demo:
        if args.demo_snapshot:
            sample = _load(args.demo_snapshot) or {}
        else:
            from teaching_data import teaching_input
            sample = teaching_input()
        em, fr = sample.get("eastmoney"), sample.get("fred")
        if not any((source or {}).get("indicators") for source in (em, fr)):
            raise SystemExit("演示快照不可用")
        em, fr = dict(em, source="sample"), dict(fr, source="sample")
        credit, attribution = None, None
        cycle, long_cycle = None, None
        offline = True
    elif not any((source or {}).get("indicators") for source in (em, fr, credit)):
        raise SystemExit("没有可用真实数据；正式研究禁止示例兜底。演示请显式使用 --demo")
    em = em or {"indicators": {}, "errors": ["国内数据未取得"]}
    fr = fr or {"indicators": {}, "errors": ["海外数据未取得"]}
    if not em.get("indicators"):
        em.setdefault("errors", []).append("国内数据未取得")
    if not fr.get("indicators"):
        fr.setdefault("errors", []).append("海外数据未取得")
    if cycle is None:
        sys.path.insert(0, HERE)
        from compute_cycle import compute
        cycle = compute(em.get("indicators", {}), fr.get("indicators", {}),
                        as_of=em.get("as_of") or fr.get("as_of"))
    if long_cycle is None:
        from compute_long_cycle import compute as compute_long
        long_cycle = compute_long(fr.get("indicators", {}))

    payload = build_payload(em, fr, cycle, long_cycle=long_cycle,
                            long_wave=long_wave, attribution=attribution,
                            policy=policy, offline=offline, credit=credit)
    if args.demo and not args.demo_snapshot:
        payload["demo_source"] = "本仓库原创模拟数值（教学用，不来自实时接口）"
    path = render(payload, args.out, args.title)
    flag = "教学示例" if offline else "正式数据输入"
    print(f"[dashboard] 已生成 {path} ({flag})")


if __name__ == "__main__":
    main()
