"""Generate a public teaching preview using original synthetic numbers, offline."""
import argparse
import json
from pathlib import Path

from build_dashboard import build_payload, render
from compute_cycle import compute


from teaching_data import teaching_input


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
