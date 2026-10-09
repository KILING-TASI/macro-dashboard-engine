#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_pipeline.py — 宏观看板一键流水线

流程: 抓取(东财+FRED) → 周期研判 → 生成单文件 HTML 看板

用法:
    python3 run_pipeline.py                          # 默认输出 /workspace/macro-dashboard.html
    python3 run_pipeline.py --out /tmp/dash.html
    python3 run_pipeline.py --workdir /tmp/macro     # 中间文件目录

容错: 正式研究只使用真实数据，缺项留空；--demo 显式离线演示。
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)


def run(cmd):
    """运行子命令，返回 (ok, output_path)。"""
    if "--out" in cmd:
        output = cmd[cmd.index("--out") + 1]
        if os.path.isfile(output):
            os.remove(output)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable] + cmd, capture_output=True, text=True,
                       encoding="utf-8", env=env)
    for line in (r.stdout or "").splitlines():
        print("  " + line)
    for line in (r.stderr or "").splitlines():
        print("  [warn]", line, file=sys.stderr)
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser(description="宏观看板一键流水线")
    ap.add_argument("--out", default="/workspace/macro-dashboard.html")
    ap.add_argument("--workdir", default=None, help="中间 JSON 目录，默认临时目录")
    ap.add_argument("--title", default="宏观全景看板")
    ap.add_argument("--demo", action="store_true", help="离线演示，不抓取真实数据")
    args = ap.parse_args()
    if args.demo:
        if not run([os.path.join(HERE, "build_dashboard.py"), "--demo", "--out", args.out, "--title", args.title]):
            raise SystemExit(1)
        return

    workdir = args.workdir or tempfile.mkdtemp(prefix="macro_")
    os.makedirs(workdir, exist_ok=True)
    em_json = os.path.join(workdir, "eastmoney_data.json")
    fr_json = os.path.join(workdir, "fred_data.json")
    cycle_json = os.path.join(workdir, "cycle.json")
    lc_json = os.path.join(workdir, "long_cycle.json")
    ind_json = os.path.join(workdir, "industry_data.json")
    attr_json = os.path.join(workdir, "attribution.json")
    credit_json = os.path.join(workdir, "credit_data.json")
    for path in (cycle_json, lc_json, attr_json):
        if os.path.isfile(path):
            os.remove(path)

    print("[1/5] 抓取国内宏观数据（东方财富）...")
    ok_em = run([os.path.join(HERE, "fetch_eastmoney.py"), "--out", em_json])

    print("[2/5] 抓取海外宏观数据（FRED，含长周期全历史序列）...")
    ok_fr = run([os.path.join(HERE, "fetch_fred.py"), "--out", fr_json])

    print("[3/5] 抓取行业指数行情（新浪）...")
    ok_ind = run([os.path.join(HERE, "fetch_industry.py"),
                  "--months", "36", "--out", ind_json])
    print("[credit] 抓取货币与银行信用传导数据...")
    run([os.path.join(HERE, "fetch_credit.py"), "--out", credit_json])

    print("[4/5] 周期研判（短周期 + 长周期梯队）+ 量化归因...")
    ok_cycle = (ok_em or ok_fr) and run(
        [os.path.join(HERE, "compute_cycle.py"),
         "--eastmoney", em_json, "--fred", fr_json, "--out", cycle_json])

    if ok_fr:
        run([os.path.join(HERE, "compute_long_cycle.py"),
             "--fred", fr_json, "--out", lc_json])
    else:
        print("  [warn] FRED 数据缺失，长周期梯队留空", file=sys.stderr)

    if ok_ind and ok_em and ok_fr:
        run([os.path.join(HERE, "regress_attribution.py"),
             "--industry", ind_json, "--eastmoney", em_json,
             "--fred", fr_json, "--out", attr_json])
    else:
        print("  [warn] 行业数据不全，量化归因留空", file=sys.stderr)

    print("[5/5] 生成看板...")
    if ok_cycle:
        ok = run([os.path.join(HERE, "build_dashboard.py"),
                  "--eastmoney", em_json, "--fred", fr_json, "--cycle", cycle_json,
                  "--longcycle", lc_json, "--attribution", attr_json,
                  "--credit", credit_json,
                  "--out", args.out, "--title", args.title])
    else:
        print("[pipeline] 数据源不完整，只展示可用真实数据，缺项留空")
        ok = run([os.path.join(HERE, "build_dashboard.py"),
                  "--eastmoney", em_json if ok_em else "/nonexistent",
                  "--fred", fr_json if ok_fr else "/nonexistent",
                  "--cycle", cycle_json if os.path.exists(cycle_json) else "/nonexistent",
                  "--longcycle", lc_json if os.path.exists(lc_json) else "/nonexistent",
                  "--attribution", attr_json if os.path.exists(attr_json) else "/nonexistent",
                  "--credit", credit_json,
                  "--out", args.out, "--title", args.title])

    if ok and os.path.exists(args.out):
        print(f"[pipeline] 完成 → {args.out}")
    else:
        print("[pipeline] 失败：看板未生成", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
