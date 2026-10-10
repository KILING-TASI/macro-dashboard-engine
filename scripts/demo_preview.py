"""Generate a public teaching preview using original synthetic numbers, offline."""
import argparse
import json
import sys
from pathlib import Path

from build_dashboard import build_payload, render, SKILL_DIR, RENDER_RESOURCES
from compute_cycle import compute


from teaching_data import teaching_input


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True, help="新目录，拒绝覆盖")
    args = parser.parse_args()
    folder = Path(args.out_dir)
    if folder.exists():
        raise SystemExit("输出目录已存在。请换一个未存在的目录（例如 local-data/public-demo-2），再运行相同命令。")
    missing = [name for name in RENDER_RESOURCES if not (Path(SKILL_DIR) / name).is_file()]
    if missing:
        raise SystemExit("源码资源缺失：" + ", ".join(missing) + "。请重新解压完整源码包；此入口不需要安装额外 Python 依赖。")
    source = teaching_input()
    cycle = compute(source["eastmoney"]["indicators"], {}, as_of=source["eastmoney"]["as_of"])
    payload = build_payload(source["eastmoney"], source["fred"], cycle, offline=True)
    payload["demo_source"] = "本仓库原创模拟数值（教学用，不来自实时接口）"
    folder.mkdir(parents=True)
    (folder / "demo-input.json").write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding="utf-8")
    (folder / "cycle.json").write_text(json.dumps(cycle, ensure_ascii=False, indent=2), encoding="utf-8")
    render(payload, str(folder / "macro-demo.html"), title="宏观教学看板 · 原创模拟数据")
    print("Teaching preview: " + str((folder / "macro-demo.html").resolve()))
    print("已生成宏观教学看板：原创模拟数据，非真实研究结论。", file=sys.stderr)
    print("结果目录：" + str(folder.resolve()), file=sys.stderr)
    print("请打开：" + str((folder / "macro-demo.html").resolve()), file=sys.stderr)
    print("复查输入与计算：demo-input.json、cycle.json。", file=sys.stderr)


if __name__ == "__main__":
    main()
