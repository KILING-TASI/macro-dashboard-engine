"""货币与信用传导数据：保留来源、原始响应和逐序列日期，不补造缺项。"""
import argparse
import datetime
import json
import math
import os
import urllib.parse
import urllib.request

from fetch_eastmoney import BASE, HEADERS, _num, fetch_report
from fetch_fred import fetch_series

AFRE_URL = "https://data.mofcom.gov.cn/datamofcom/front/gnmy/shrzgmQuery"


def normalize(rows, date_key, field, name, unit, source, frequency="M"):
    points = {}
    for row in rows:
        date = str(row.get(date_key, ""))
        if len(date) == 6 and date.isdigit():
            date = date[:4] + "-" + date[4:]
        else:
            date = date[:7] if frequency != "D" else date[:10]
        value = _num(row.get(field))
        if value is not None and math.isfinite(value) and len(date) >= 7:
            points[date] = value
    dates = sorted(points)[-60:]
    if not dates:
        raise ValueError(f"{name}无有效数据")
    return {"name": name, "unit": unit, "source_url": source,
            "frequency": frequency, "dates": dates, "values": [points[d] for d in dates]}


def fetch_all():
    result = {"fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "indicators": {}, "errors": [], "raw": {}}
    def collect(label, callback):
        try:
            callback()
        except Exception as exc:
            result["errors"].append(f"{label}: {exc}")
    def afre():
        request = urllib.request.Request(AFRE_URL, data=b"")
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
        result["raw"]["afre"] = raw
        rows = json.loads(raw)
        for key, field, name in [
            ("afre_flow", "tiosfs", "社融月度增量"),
            ("afre_rmb", "rmblaon", "社融口径人民币贷款增量"),
            ("corporate_bonds", "bibae", "企业债券净融资"),
            ("equity", "sfinfe", "非金融企业境内股票融资")]:
            result["indicators"][key] = normalize(rows, "date", field, name, "亿元", AFRE_URL)
    def loans():
        rows = fetch_report("RPT_ECONOMY_RMB_LOAN", 60)
        result["raw"]["loans"] = rows
        result["indicators"]["bank_loans"] = normalize(
            rows, "REPORT_DATE", "RMB_LOAN", "金融机构人民币新增贷款", "亿元",
            "https://data.eastmoney.com/cjsj/xzxd.html")
    def lpr():
        url = BASE + "?" + urllib.parse.urlencode({"reportName": "RPTA_WEB_RATE",
            "columns": "ALL", "pageSize": 60, "sortColumns": "TRADE_DATE", "sortTypes": "-1"})
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=20) as response:
            raw = response.read().decode("utf-8")
        result["raw"]["lpr"] = raw
        payload = json.loads(raw)
        if not payload.get("success"):
            raise ValueError("LPR接口未返回成功状态")
        for key, field, name in [("lpr1y", "LPR1Y", "1年期LPR"), ("lpr5y", "LPR5Y", "5年期以上LPR")]:
            result["indicators"][key] = normalize(payload["result"]["data"], "TRADE_DATE",
                field, name, "%", "https://data.eastmoney.com/cjsj/globalRateLPR.html")
    def survey(key, series, name):
        points = fetch_series(series, timeout=20, retries=0)
        result["raw"][series] = points
        result["indicators"][key] = normalize([{"date": d, "value": v} for d, v in points],
            "date", "value", name, "%净占比", f"https://fred.stlouisfed.org/series/{series}", "Q")
    collect("社融", afre)
    collect("银行贷款", loans)
    collect("LPR", lpr)
    collect("美国放贷标准", lambda: survey("us_standards", "DRTSCILM", "美国银行收紧企业放贷标准净占比"))
    collect("美国贷款需求", lambda: survey("us_demand", "DRSDCILM", "美国企业贷款需求增强净占比"))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="credit_data.json")
    args = parser.parse_args()
    result = fetch_all()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[credit] 成功 {len(result['indicators'])} 条序列；失败 {len(result['errors'])} 项")
    for error in result["errors"]:
        print(f"[credit] {error}")
    if not result["indicators"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
