#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_pipeline.py — 宏观看板一键流水线

流程: 抓取(东财+FRED) → 周期研判 → 生成单文件 HTML 看板

用法:
    python3 run_pipeline.py                          # 默认输出 /workspace/macro-dashboard.html
    python3 run_pipeline.py --out /tmp/dash.html
    python3 run_pipeline.py --workdir /tmp/macro     # 中间文件目录

容错: 任一数据源失败 → 自动回退 assets/sample_data.json 并在看板标注「示例数据」。
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
    r = subprocess.run([sys.executable] + cmd, capture_output=True, text=True)
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
    args = ap.parse_args()

    workdir = args.workdir or tempfile.mkdtemp(prefix="macro_")
    os.makedirs(workdir, exist_ok=True)
    em_json = os.path.join(workdir, "eastmoney_data.json")
    fr_json = os.path.join(workdir, "fred_data.json")
    cycle_json = os.path.join(workdir, "cycle.json")
    lc_json = os.path.join(workdir, "long_cycle.json")

    print("[1/4] 抓取国内宏观数据（东方财富）...")
    ok_em = run([os.path.join(HERE, "fetch_eastmoney.py"), "--out", em_json])

    print("[2/4] 抓取海外宏观数据（FRED，含长周期全历史序列）...")
    ok_fr = run([os.path.join(HERE, "fetch_fred.py"), "--out", fr_json])

    print("[3/4] 周期研判（短周期 + 长周期梯队）...")
    ok_cycle = ok_em and ok_fr and run(
        [os.path.join(HERE, "compute_cycle.py"),
         "--eastmoney", em_json, "--fred", fr_json, "--out", cycle_json])

    # 长周期计算：即使短周期数据不全也尝试（长周期只依赖 FRED 长历史序列）
    if ok_fr:
        run([os.path.join(HERE, "compute_long_cycle.py"),
             "--fred", fr_json, "--out", lc_json])
    else:
        print("  [warn] FRED 数据缺失，长周期梯队将回退示例快照", file=sys.stderr)

    print("[4/4] 生成看板...")
    if ok_cycle:
        ok = run([os.path.join(HERE, "build_dashboard.py"),
                  "--eastmoney", em_json, "--fred", fr_json, "--cycle", cycle_json,
                  "--longcycle", lc_json,
                  "--out", args.out, "--title", args.title])
    else:
        print("[pipeline] 数据源不完整，使用离线示例数据兜底生成看板")
        ok = run([os.path.join(HERE, "build_dashboard.py"),
                  "--eastmoney", em_json if ok_em else "/nonexistent",
                  "--fred", fr_json if ok_fr else "/nonexistent",
                  "--cycle", cycle_json if os.path.exists(cycle_json) else "/nonexistent",
                  "--longcycle", lc_json if os.path.exists(lc_json) else "/nonexistent",
                  "--out", args.out, "--title", args.title])

    if ok and os.path.exists(args.out):
        print(f"[pipeline] 完成 → {args.out}")
    else:
        print("[pipeline] 失败：看板未生成", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
