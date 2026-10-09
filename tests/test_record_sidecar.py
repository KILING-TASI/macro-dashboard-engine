import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from macro_contract import export_bundle
from record_sidecar import build_sidecar
from fetch_fred import _yoy


class SidecarTests(unittest.TestCase):
    def test_normal_and_missing_base_preserve_value_and_unknowns(self):
        levels = [("2025-01",100),("2026-01",112),("2026-02",113)]
        calculated = dict(_yoy(levels))
        source = {"fred":{"source":"sample", "fetched_at":"2026-10-10T00:00:00+00:00",
            "indicators":{"us_cpi":{"dates":["2026-01","2026-02"],
                "values":[calculated.get("2026-01"),calculated.get("2026-02")],
                "unit":"%", "freq":"M", "transformation":"calendar-yoy-1.0.0",
                "release_date":"2026-10-09", "dependency_gap":"2025-02 baseline missing"}}}}
        bundle = export_bundle(source)
        before = copy.deepcopy(bundle)
        result = build_sidecar(bundle)
        normal, gap = result["records"]
        self.assertEqual(normal["value"], 12.0)
        self.assertIsNone(gap["value"])
        self.assertTrue(gap["missing"]["value"])
        self.assertIsNone(gap["available_at"])
        self.assertIsNone(normal["published_at"])
        self.assertIsNone(normal["raw_sha256"])
        self.assertEqual(normal["acquired_at"], source["fred"]["fetched_at"])
        self.assertEqual(gap["extensions"]["macro"]["original_payload"], source["fred"]["indicators"]["us_cpi"])
        self.assertEqual(bundle, before)
        self.assertFalse(result["point_in_time"])
        conflicted = copy.deepcopy(bundle)
        conflicted["observations"][0]["payload"]["unit"] = "指数"
        bad_unit = build_sidecar(conflicted)["records"][0]
        self.assertIsNone(bad_unit["unit"])
        self.assertTrue(bad_unit["conflicts"])
        self.assertEqual(bad_unit["extensions"]["macro"]["original_payload"]["unit"], "指数")

    def test_unknown_contract_rejected_without_upgrade(self):
        with self.assertRaises(ValueError):
            build_sidecar({"contract_version":"2.0.0"})


if __name__ == "__main__":
    unittest.main()
