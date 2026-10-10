#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_pipeline.py — 宏观看板一键流水线

流程: 抓取(东财+FRED) → 周期研判 → 生成单文件 HTML 看板

用法:
    python3 run_pipeline.py                          # 默认输出独立运行目录
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


def run(cmd, overwrite=False):
    """Stage in destination directory; publish only successful nonempty output."""
    cmd = list(cmd)
    output = staged = None
    if "--out" in cmd:
        output = cmd[cmd.index("--out") + 1]
        if os.path.exists(output) and not overwrite:
            print(f"[warn] 输出已存在，保留旧结果；如需覆盖请显式指定 --overwrite: {output}", file=sys.stderr)
            return False
        os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
        fd, staged = tempfile.mkstemp(prefix=".macro-stage-", suffix=os.path.splitext(output)[1],
                                     dir=os.path.dirname(os.path.abspath(output)))
        os.close(fd)
        cmd[cmd.index("--out") + 1] = staged
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        r = subprocess.run([sys.executable] + cmd, capture_output=True, text=True,
                           encoding="utf-8", env=env)
        for line in (r.stdout or "").splitlines():
            print("  " + line)
        for line in (r.stderr or "").splitlines():
            print("  [warn]", line, file=sys.stderr)
        if r.returncode != 0 or (staged and os.path.getsize(staged) == 0):
            return False
        if staged:
            if overwrite:
                os.replace(staged, output)
            else:
                # Atomic no-clobber publication, including concurrent writers.
                os.link(staged, output)
        return True
    except OSError as error:
        print(f"[warn] 子任务/保存失败，旧结果保留: {error}", file=sys.stderr)
        return False
    finally:
        if staged and os.path.exists(staged):
            os.remove(staged)


def main():
    ap = argparse.ArgumentParser(description="宏观看板一键流水线")
    ap.add_argument("--out", default=None)
    ap.add_argument("--workdir", default=None, help="归档父目录；每次在其下创建独立run目录")
    ap.add_argument("--title", default="宏观全景看板")
    ap.add_argument("--demo", action="store_true", help="离线演示，不抓取真实数据")
    ap.add_argument("--demo-snapshot", default=None, help="显式演示快照；不附加第三方数据授权")
    ap.add_argument("--overwrite", action="store_true", help="成功后替换指定HTML；失败保留旧结果")
    args = ap.parse_args()
    if args.demo_snapshot and not args.demo:
        raise SystemExit("--demo-snapshot 仅可配合 --demo")
    base = args.workdir or tempfile.mkdtemp(prefix="macro_")
    os.makedirs(base, exist_ok=True)
    workdir = tempfile.mkdtemp(prefix="run_", dir=base)
    args.out = args.out or os.path.join(workdir, "macro-dashboard.html")
    if os.path.exists(args.out) and not args.overwrite:
        raise SystemExit("输出已存在；请指定新路径或显式使用 --overwrite")
    if args.demo:
        command = [os.path.join(HERE, "build_dashboard.py"), "--demo", "--out", args.out, "--title", args.title]
        if args.demo_snapshot:
            command.extend(["--demo-snapshot", args.demo_snapshot])
        if not run(command, overwrite=args.overwrite):
            raise SystemExit(1)
        print(f"[pipeline] 演示完成 → {args.out}")
        return

    em_json = os.path.join(workdir, "eastmoney_data.json")
    fr_json = os.path.join(workdir, "fred_data.json")
    cycle_json = os.path.join(workdir, "cycle.json")
    lc_json = os.path.join(workdir, "long_cycle.json")
    ind_json = os.path.join(workdir, "industry_data.json")
    attr_json = os.path.join(workdir, "attribution.json")
    credit_json = os.path.join(workdir, "credit_data.json")

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
                  "--out", args.out, "--title", args.title], overwrite=args.overwrite)
    else:
        print("[pipeline] 数据源不完整，只展示可用真实数据，缺项留空")
        ok = run([os.path.join(HERE, "build_dashboard.py"),
                  "--eastmoney", em_json if ok_em else "/nonexistent",
                  "--fred", fr_json if ok_fr else "/nonexistent",
                  "--cycle", cycle_json if os.path.exists(cycle_json) else "/nonexistent",
                  "--longcycle", lc_json if os.path.exists(lc_json) else "/nonexistent",
                  "--attribution", attr_json if os.path.exists(attr_json) else "/nonexistent",
                  "--credit", credit_json,
                  "--out", args.out, "--title", args.title], overwrite=args.overwrite)

    if ok and os.path.exists(args.out):
        print(f"[pipeline] 完成 → {args.out}")
    else:
        print("[pipeline] 失败：看板未生成", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
