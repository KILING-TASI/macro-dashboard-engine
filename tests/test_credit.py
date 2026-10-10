import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from compute_credit import compute
from fetch_credit import normalize


class CreditTests(unittest.TestCase):
    def test_missing_data_is_gap_not_zero(self):
        result = compute({}, "2026-10-09")
        self.assertFalse(result["rows"])
        self.assertEqual(len(result["gaps"]), 17)
        self.assertEqual(result["status"], "partial")

    def test_zero_is_valid_and_old_data_flagged(self):
        result = compute({"indicators": {"afre_flow": {
            "dates": ["2026-04"], "values": [0], "frequency": "M"}}}, "2026-10-09")
        self.assertEqual(result["rows"][0]["value"], 0)
        self.assertTrue(result["rows"][0]["stale"])

    def test_quarterly_dates_are_not_monthly_filled(self):
        result = compute({"indicators": {"us_demand": {"dates": ["2026-01", "2026-04"],
            "values": [5, 10], "frequency": "Q"}}}, "2026-10-09")
        self.assertEqual(result["rows"][0]["dates"], ["2026-01", "2026-04"])
        self.assertIn("不是中国", result["rows"][0]["note"])

    def test_normalize_sorts_and_excludes_missing_and_nonfinite(self):
        result = normalize([{"date": "202602", "v": 0}, {"date": "202601", "v": -3},
                            {"date": "202603", "v": None}, {"date": "202604", "v": float("nan")}],
                           "date", "v", "融资", "亿元", "https://example.com")
        self.assertEqual(result["dates"], ["2026-01", "2026-02"])
        self.assertEqual(result["values"], [-3, 0])


if __name__ == "__main__":
    unittest.main()
