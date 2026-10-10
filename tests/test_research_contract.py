import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_dashboard as dashboard
from data_evidence import build_evidence


class ResearchContractTests(unittest.TestCase):
    def test_observed_through_supports_house_price_series(self):
        rows = build_evidence({"eastmoney": {"indicators": {"house": {
            "dates": ["2026-07", "2026-08"],
            "series": {"new": [1.0, None], "second": [0.5, 0.2]}}}}})["rows"]
        self.assertEqual(rows[0]["observed_through"], "2026-08")

    def test_formal_mode_never_loads_sample(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / "result.html"
            with patch.object(sys, "argv", ["build", "--eastmoney", d + "/missing",
                    "--fred", d + "/missing", "--cycle", d + "/missing", "--out", str(output)]):
                with self.assertRaises(SystemExit):
                    dashboard.main()
            self.assertFalse(output.exists())

    def test_one_real_source_generates_partial_without_samples(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "em.json"
            source.write_text(json.dumps({"indicators": {"pmi": {"dates": ["2026-08"],
                "series": {"value": [49.5]}}}, "as_of": "2026-08"}), encoding="utf-8")
            output = Path(d) / "result.html"
            with patch.object(sys, "argv", ["build", "--eastmoney", str(source),
                    "--fred", d + "/missing", "--cycle", d + "/missing", "--out", str(output)]):
                dashboard.main()
            html = output.read_text(encoding="utf-8")
            self.assertIn('"offline": false', html)
            self.assertIn('"status": "partial"', html)
            self.assertIn('"us10y": null', html)

    def test_status_alone_cannot_claim_original_verified(self):
        data = {"indicators": {"cpi": {"dates": ["2026-08"], "values": [0.8],
                "verification": {"status": "original_verified"}}}}
        row = build_evidence({"eastmoney": data})["rows"][0]
        self.assertEqual(row["verification_status"], "仅取得数据，原文未核验")
        self.assertIsNone(row["release_date"])

    def test_complete_verification_record_is_preserved(self):
        record = {"status": "original_verified", "original_url": "https://www.stats.gov.cn/",
                  "checked_at": "2026-10-09", "locator": "表1 CPI同比 2026-08"}
        rows = build_evidence({"eastmoney": {"indicators": {"cpi": {"verification": record}}}})["rows"]
        self.assertEqual(rows[0]["verification"], record)


if __name__ == "__main__":
    unittest.main()
