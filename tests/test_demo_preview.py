import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import demo_preview
import build_dashboard


class DemoPreviewTests(unittest.TestCase):
    def test_explicit_legacy_snapshot_is_available_without_becoming_default(self):
        snapshot = Path(__file__).resolve().parents[1] / "assets/sample_data.json"
        if not snapshot.exists():
            self.skipTest("旧快照不随源码归档分发")
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "legacy.html"
            with patch.object(sys, "argv", ["build", "--demo", "--demo-snapshot", str(snapshot), "--out", str(output)]):
                build_dashboard.main()
            page = output.read_text(encoding="utf-8")
            self.assertIn("离线示例快照", page)
            self.assertNotIn('"us10y": null', page)
            self.assertIn('"status": "sample"', page)

    def test_teaching_markers_dates_and_missing_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "preview"
            with patch.object(sys, "argv", ["preview", "--out-dir", str(folder)]):
                demo_preview.main()
            page = (folder / "macro-demo.html").read_text(encoding="utf-8")
            self.assertIn("示例数据", page)
            self.assertIn("原创模拟数值", page)
            self.assertIn('"producer": "本仓库原创模拟"', page)
            self.assertIn("计算版本：2.0.0", page)
            self.assertIn('id="asof">2026-08', page)
            self.assertIn('"us10y": null', page)
            self.assertIn('"status": "sample"', page)
            self.assertIn('id="third-party-notices"', page)
            self.assertIn("Copyright 2017-2024 The Apache Software Foundation", page)
            self.assertIn("BSD", page)
            source = json.loads((folder / "demo-input.json").read_text(encoding="utf-8"))
            self.assertFalse(source["fred"]["indicators"])
            before = (folder / "macro-demo.html").read_bytes()
            with patch.object(sys, "argv", ["preview", "--out-dir", str(folder)]):
                with self.assertRaises(SystemExit):
                    demo_preview.main()
            self.assertEqual(before, (folder / "macro-demo.html").read_bytes())


if __name__ == "__main__":
    unittest.main()
