"""Generate a public teaching preview using original synthetic numbers, offline."""
import argparse
import json
from pathlib import Path

from build_dashboard import build_payload, render
from compute_cycle import compute


def teaching_input():
    dates = [f"{2025 + (8+i)//12}-{(8+i)%12+1:02d}" for i in range(12)]
    def indicator(name, values, unit="%", field="value", period_dates=None, frequency="M"):
        return {"name": name, "dates": period_dates or dates, "series": {field: values},
                "unit": unit, "frequency": frequency, "latest": values[-1], "prev": values[-2]}
    em = {"source": "sample", "as_of": "2026-08", "fetched_at": None,
          "provenance": "Original synthetic teaching numbers; not official observations.",
          "indicators": {
              "pmi": indicator("制造业PMI", [49.0,49.2,49.4,49.5,49.6,49.8,50.0,50.1,50.3,50.4,50.5,50.6], "指数"),
              "cpi": indicator("CPI同比", [0.2,0.2,0.3,0.3,0.4,0.4,0.5,0.5,0.6,0.6,0.7,0.8]),
              "ppi": indicator("PPI同比", [-1.1,-1.0,-0.9,-0.8,-0.7,-0.6,-0.5,-0.4,-0.3,-0.2,-0.1,0.0]),
              "retail": indicator("社零同比", [1.0,1.2,1.4,1.6,1.8,2.0,2.2,2.4,2.6,2.8,3.0,3.2], field="yoy"),
              "gdp": indicator("GDP同比", [3.5,3.7,3.9,4.1], field="yoy", period_dates=["2025-09","2025-12","2026-03","2026-06"], frequency="Q"),
              "m1": indicator("M1同比", [1.0,1.1,1.2,1.3,1.4,1.5,1.6,1.7,1.8,1.9,2.0,2.1], field="yoy"),
              "m2": indicator("M2同比", [7.0]*12, field="yoy")}}
    return {"eastmoney": em, "fred": {"source": "sample", "indicators": {}},
            "note": "All numbers are fictional; missing foreign/credit/industry observations remain missing."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True, help="新目录，拒绝覆盖")
    args = parser.parse_args()
    folder = Path(args.out_dir)
    if folder.exists():
        raise SystemExit("输出目录已存在，请另选新目录")
    source = teaching_input()
    cycle = compute(source["eastmoney"]["indicators"], {}, as_of=source["eastmoney"]["as_of"])
    payload = build_payload(source["eastmoney"], source["fred"], cycle, offline=True)
    payload["demo_source"] = "本仓库原创模拟数值（教学用，不来自实时接口）"
    folder.mkdir(parents=True)
    (folder / "demo-input.json").write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding="utf-8")
    (folder / "cycle.json").write_text(json.dumps(cycle, ensure_ascii=False, indent=2), encoding="utf-8")
    render(payload, str(folder / "macro-demo.html"), title="宏观教学看板 · 原创模拟数据")
    print("Teaching preview: " + str((folder / "macro-demo.html").resolve()))


if __name__ == "__main__":
    main()
