"""信用传导展示口径：不同地区、频率分别展示，不生成混合周期评分。"""
import datetime

SPECS = [
    ("lpr1y", "资金价格", "LPR是贷款报价参考，不等于DR007或实际贷款成交利率。"),
    ("lpr5y", "资金价格", "5年期以上贷款报价参考。"),
    ("bank_loans", "银行信用", "金融机构人民币新增贷款；与社融口径贷款范围不同，不相减。"),
    ("afre_flow", "融资结构", "社融月度增量；含政府融资，不直接等于私人部门需求。"),
    ("afre_rmb", "融资结构", "对实体经济发放的人民币贷款增量。"),
    ("corporate_bonds", "融资结构", "企业债券净融资。"),
    ("equity", "融资结构", "非金融企业境内股票融资。"),
    ("us_standards", "美国信用供给", "正值表示收紧标准的银行净占比；调查不是贷款增速。"),
    ("us_demand", "美国借款需求", "正值表示需求增强的银行净占比；不是中国需求信号。"),
    ("dr007", "资金价格", "存款类机构7天质押式回购利率。"),
    ("cn_demand", "国内借款需求", "人民银行贷款总体需求指数，不能与美国净占比直接比较。"),
    ("cn_approval", "国内信用供给", "人民银行银行贷款审批指数。"),
    ("household_long", "贷款结构", "居民中长期贷款月度增量。"),
    ("corporate_long", "贷款结构", "企业中长期贷款月度增量。"),
    ("government_bonds", "融资结构", "政府债券净融资；不能用社融减已知分项的残差代替。"),
    ("afre_stock_yoy", "信用存量", "社融存量同比。"),
    ("receivable_days", "现金流压力", "工业企业应收账款平均回收期。"),
]


def compute(raw, as_of=None, offline=False):
    today = datetime.date.fromisoformat(as_of) if as_of else datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=8))).date()
    indicators = (raw or {}).get("indicators", {})
    rows, gaps = [], []
    for key, stage, note in SPECS:
        indicator = indicators.get(key) or {}
        points = sorted((d, v) for d, v in zip(indicator.get("dates", []), indicator.get("values", []))
                        if v is not None and d[:7] <= today.isoformat()[:7])
        if not points:
            gaps.append({"key": key, "stage": stage, "name": indicator.get("name", key), "note": note})
            continue
        date, value = points[-1]
        frequency = indicator.get("frequency", "M")
        lag = (today.year - int(date[:4])) * 12 + today.month - int(date[5:7])
        rows.append({"key": key, "stage": stage, "name": indicator.get("name", key),
            "date": date, "value": value, "unit": indicator.get("unit", ""),
            "frequency": frequency, "lag_months": lag,
            "stale": lag > (6 if frequency == "Q" else 3), "note": note,
            "source_url": indicator.get("source_url", ""),
            "dates": [d for d, _ in points], "values": [v for _, v in points]})
    return {"rows": rows, "gaps": gaps, "errors": (raw or {}).get("errors", []),
            "status": "sample" if offline else ("partial" if gaps or (raw or {}).get("errors") else "live"),
            "note": "逐项保留日期；月度融资未经季调。未采集的分项留空，不据残差推算政府融资。",
            "m1_note": "2025年1月M1统计口径修订；未核验回溯可比口径前，不将跨断点变化解释为信用拐点。"}
