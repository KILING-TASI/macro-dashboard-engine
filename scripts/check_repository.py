"""Offline repository and source-archive checks; no data collection."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ["README.md", "DISCLAIMER.md", "LICENSE", "THIRD_PARTY_NOTICES.md",
            "CHANGELOG.md", "ROADMAP.md", "SKILL.md", "docs/设计方案.md",
            "assets/echarts.min.js", "assets/template.html",
            "scripts/run_pipeline.py", "scripts/dated_series.py", "scripts/macro_contract.py",
            "references/macro_contract.md", "references/source_catalog.json",
            "references/examples/contract-input.json"]
REQUIRED += ["scripts/demo_preview.py", "assets/preview/macro-demo.png",
             "assets/preview/README.md", "assets/preview/provenance.json", "scripts/teaching_data.py",
             "LICENSE_SCOPE.md", "assets/SAMPLE_DATA_RIGHTS.md", ".gitattributes",
             "third_party/echarts-5.5.1/LICENSE", "third_party/echarts-5.5.1/NOTICE",
             "third_party/echarts-5.5.1/LICENSE-d3", "third_party/echarts-5.5.1/provenance.json"]


def check():
    for name in REQUIRED:
        if not (ROOT / name).is_file():
            raise ValueError("缺少分发资源: " + name)
    vendor = json.loads((ROOT / "third_party/echarts-5.5.1/provenance.json").read_text(encoding="utf-8"))
    library = (ROOT / "assets/echarts.min.js").read_text(encoding="utf-8").encode("utf-8")
    if hashlib.sha256(library).hexdigest() != vendor["upstream_dist_normalized_sha256"]:
        raise ValueError("内置ECharts与已核上游分发哈希不一致（换行已统一）")
    for script in (ROOT / "scripts").glob("*.py"):
        ast.parse(script.read_text(encoding="utf-8-sig"), feature_version=8)
    for document in ROOT.rglob("*.md"):
        if any(part in (".git", "local-data", ".venv") for part in document.parts):
            continue
        content = document.read_text(encoding="utf-8-sig")
        if re.search(r"^(<<<<<<< |=======\s*$|>>>>>>> )", content, re.M):
            raise ValueError("未解决冲突: " + str(document))
        for target in re.findall(r"\]\(([^)]+)\)", content):
            if "://" in target or target.startswith("#"):
                continue
            path = target.split("#")[0]
            if path and not (document.parent / path).exists():
                raise ValueError("链接不存在: " + str(document) + " -> " + target)
    print("Required resources, Python 3.8 syntax and relative documentation links checked.")


def check_archive():
    with tempfile.TemporaryDirectory(prefix="macro-source-check-") as temporary:
        folder = Path(temporary)
        archive = folder / "source.zip"
        subprocess.run(["git", "archive", "--format=zip", "--output=" + str(archive), "HEAD"],
                       cwd=ROOT, check=True)
        source = folder / "source"
        source.mkdir()
        with zipfile.ZipFile(archive) as package:
            for name in REQUIRED:
                if name not in package.namelist():
                    raise ValueError("源码归档缺少: " + name)
            if any(name.startswith("local-data/") for name in package.namelist()):
                raise ValueError("源码归档不应包含研究缓存")
            if "assets/sample_data.json" in package.namelist():
                raise ValueError("源码归档不应包含未核再分发权利的旧快照")
            package.extractall(source)
        subprocess.run([sys.executable, "scripts/run_pipeline.py", "--demo", "--workdir", "local-data/demo"],
                       cwd=source, check=True)
        if not list((source / "local-data/demo").glob("run_*/macro-dashboard.html")):
            raise ValueError("解压后演示未生成HTML")
        subprocess.run([sys.executable, "scripts/demo_preview.py", "--out-dir", "local-data/public-demo"],
                       cwd=source, check=True)
        if not (source / "local-data/public-demo/macro-demo.html").is_file():
            raise ValueError("解压后公开教学演示未生成HTML")
    print("Committed source archive includes notices/resources and runs the offline demo.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", action="store_true", help="检查HEAD源码归档并运行离线演示")
    args = parser.parse_args()
    check()
    if args.archive:
        check_archive()


if __name__ == "__main__":
    main()
