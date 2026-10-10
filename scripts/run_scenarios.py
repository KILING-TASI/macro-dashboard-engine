"""Run bounded, fictional macro scenarios via real CLIs; save reviewable evidence."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
from teaching_data import teaching_input
from compute_cycle import CALCULATION_VERSION

HERE = Path(__file__).resolve().parent


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def run_scenarios(folder):
    folder = Path(folder).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    results = []
    env = dict(os.environ, PYTHONUTF8="1", PYTHONNOUSERSITE="1")
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)

    def command(case, script, *args, code=None):
        argv = [sys.executable, str(HERE / script)] + [str(v) for v in args] if code is None else [sys.executable, "-c", code] + [str(v) for v in args]
        result = subprocess.run(argv, cwd=case, env=env, capture_output=True, text=True, encoding="utf-8")
        return {"argv": argv, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}

    for name in ("normal_unknown_availability", "missing_month_yoy", "structural_step", "illegal_quarter", "frequency_conflict", "all_missing"):
        case = folder / name
        case.mkdir()
        source = deepcopy(teaching_input())
        expected, actual, logs = {}, {}, []
        if name == "missing_month_yoy":
            levels = [(f"2025-{i:02d}", 99+i) for i in range(1,12)] + [("2026-01",112),("2026-02",113)]
            write(case / "levels.json", levels)
            # Only the remote fetch is replaced by a local fictional fixture; build is unchanged.
            code = """import sys,json
sys.path.insert(0,sys.argv[1])
import fetch_fred
from unittest.mock import patch
points=json.load(open(sys.argv[2],encoding='utf-8'))
with patch.object(fetch_fred,'fetch_series',return_value=points):
    result=fetch_fred.build('us_cpi')
json.dump(result,open(sys.argv[3],'w',encoding='utf-8'),ensure_ascii=False,indent=2)
"""
            logs.append(command(case, None, HERE, case / "levels.json", case / "transformed.json", code=code))
            transformed = json.loads((case / "transformed.json").read_text(encoding="utf-8"))
            expected = {"dates": ["2026-01","2026-02"], "values": [12.0,11.881],
                "basis": "100*(112/100-1)=12;100*(113/101-1)=11.881 rounded; missing December cannot shift bases"}
            assert transformed["dates"] == expected["dates"] and transformed["values"] == expected["values"]
            source["fred"]["indicators"]["us_cpi"] = transformed
            actual["transformed"] = transformed
        if name == "structural_step":
            dates = [f"2026-{i:02d}" for i in range(1,9)]
            for key, values in (("m1",[-5]*4+[10]*4),("m2",[0]*8)):
                source["eastmoney"]["indicators"][key] = {"dates":dates,"series":{"yoy":values},"frequency":"M","unit":"%"}
            expected = {"raw": [-5]*4+[10]*4,"cleaning_mode":"none","scissors_mom":0.0,
                "basis":"M1 minus zero M2 equals original step; latest four points all10, endpoint change10-10=0"}
        if name == "illegal_quarter":
            source["eastmoney"]["indicators"]["gdp"]["dates"][-1] = "2026-Q5"
            expected = {"error_contains":"日期或季度格式无效", "preserve_existing_output":True}
        if name == "frequency_conflict":
            source["eastmoney"]["indicators"]["pmi"]["frequency"] = "Q"
            expected = {"error_contains":"指标频率不符合计算要求", "preserve_existing_output":True}
        if name == "all_missing":
            source = {"eastmoney":{"indicators":{}},"fred":{"indicators":{}}}
            expected = {"error_contains":"未找到可用", "preserve_existing_output":True}
        write(case / "input.json", source)
        for provider in ("eastmoney","fred"):
            write(case / (provider + ".json"), source[provider])
        cycle_path = case / "cycle.json"
        failing = name in ("illegal_quarter","frequency_conflict","all_missing")
        if failing:
            write(cycle_path, {"frozen_prior_result": True})
            before = hashlib.sha256(cycle_path.read_bytes()).hexdigest()
        logs.append(command(case,"compute_cycle.py","--eastmoney",case/"eastmoney.json","--fred",case/"fred.json","--out",cycle_path))
        if failing:
            assert logs[-1]["exit_code"] != 0 and expected["error_contains"] in logs[-1]["stderr"]
            assert hashlib.sha256(cycle_path.read_bytes()).hexdigest() == before
            actual.update(old_output_preserved=True, error=logs[-1]["stderr"])
            if name == "all_missing":
                page = case / "report.html"
                page.write_text("FROZEN-PRIOR-REPORT",encoding="utf-8")
                logs.append(command(case,"build_dashboard.py","--eastmoney",case/"eastmoney.json","--fred",case/"fred.json","--out",page))
                assert logs[-1]["exit_code"] != 0 and "没有可用真实数据" in logs[-1]["stderr"]
                assert page.read_text(encoding="utf-8") == "FROZEN-PRIOR-REPORT"
                actual["old_report_preserved"] = True
        else:
            assert logs[-1]["exit_code"] == 0
            cycle = json.loads(cycle_path.read_text(encoding="utf-8"))
            assert cycle["calculation_version"] == CALCULATION_VERSION and cycle["point_in_time"] is False
            if name == "normal_unknown_availability":
                expected = {"scissors":-4.9,"scissors_mom":0.3,"point_in_time":False,
                    "basis":"2.1-7=-4.9; latest minus three months earlier=(2.1-7)-(1.8-7)=0.3; no release/vintage evidence"}
                assert cycle["credit_cycle"]["scissors"] == -4.9 and cycle["credit_cycle"]["scissors_mom"] == 0.3
            if name == "structural_step":
                assert cycle["credit_cycle"]["scissors_raw_series"] == expected["raw"]
                assert cycle["credit_cycle"]["cleaning"]["mode"] == "none"
                assert cycle["credit_cycle"]["scissors_mom"] == 0
            actual["cycle"] = cycle
            logs.append(command(case,"build_dashboard.py","--demo","--demo-snapshot",case/"input.json","--out",case/"report.html"))
            assert logs[-1]["exit_code"] == 0
            html = (case / "report.html").read_text(encoding="utf-8")
            assert "教学" in html and CALCULATION_VERSION in html and "MIT License" in html
            embedded = json.loads(re.search(r"const DATA = (.*?);\r?\n", html).group(1))
            assert embedded["cycle"]["credit_cycle"] == cycle["credit_cycle"]
            assert embedded["cycle"]["point_in_time"] is False
            actual["report_cycle_matches_cli"] = True
        record = {"scenario":name,"input_kind":"original_synthetic","expected":expected,"actual":actual,
            "method_version":CALCULATION_VERSION,"commands":logs,"status":"passed",
            "scope":"Offline CLI/report execution; no live source, causal, predictive or visual certification"}
        write(case / "verification.json", record)
        results.append({"scenario":name,"status":"passed","evidence":name+"/verification.json"})
    write(folder / "index.json", {"scenarios":results,"method_version":CALCULATION_VERSION,
        "coverage":"6 representative scenarios; quarterly gaps/zero baselines/opt-in cleaning reused from unit tests",
        "not_covered":["real source evidence","historical vintages","causal prediction","browser visual","cross-repository consumers"]})
    print("Scenario evidence: " + str(folder / "index.json"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    run_scenarios(args.out_dir)


if __name__ == "__main__":
    main()
