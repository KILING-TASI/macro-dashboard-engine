import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import demo_preview


class DemoPreviewTests(unittest.TestCase):
    def test_teaching_markers_dates_and_missing_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "preview"
            with patch.object(sys, "argv", ["preview", "--out-dir", str(folder)]):
                demo_preview.main()
            page = (folder / "macro-demo.html").read_text(encoding="utf-8")
            self.assertIn("示例数据", page)
            self.assertIn("原创模拟数值", page)
            self.assertIn("计算版本：2.0.0", page)
            self.assertIn('id="asof">2026-08', page)
            self.assertIn('"us10y": null', page)
            self.assertIn('"status": "sample"', page)
            source = json.loads((folder / "demo-input.json").read_text(encoding="utf-8"))
            self.assertFalse(source["fred"]["indicators"])
            before = (folder / "macro-demo.html").read_bytes()
            with patch.object(sys, "argv", ["preview", "--out-dir", str(folder)]):
                with self.assertRaises(SystemExit):
                    demo_preview.main()
            self.assertEqual(before, (folder / "macro-demo.html").read_bytes())


if __name__ == "__main__":
    unittest.main()
