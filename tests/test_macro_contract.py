import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from macro_contract import export_bundle, restore_sources, SELECTED
from compute_cycle import compute


class MacroContractTests(unittest.TestCase):
    def test_sample_roundtrip_and_same_version_calculation(self):
        sources=json.loads((Path(__file__).resolve().parents[1]/"references/examples/contract-input.json").read_text(encoding="utf-8"))
        bundle=export_bundle(sources)
        restored=restore_sources(json.loads(json.dumps(bundle,ensure_ascii=False)))
        self.assertEqual(restored,sources)
        self.assertEqual(bundle["kind"],"teaching")
        self.assertFalse(bundle["point_in_time"])
        self.assertEqual(bundle["observations"][0]["payload"]["series"]["value"][0],49.123456)
        retail=next(x for x in bundle["observations"] if x["indicator"]=="retail")
        self.assertEqual(retail["missing_dates"],["2026-02"])
        direct=compute(sources["eastmoney"]["indicators"],sources["fred"]["indicators"])
        for key in ("growth_momentum","inflation_momentum","quadrant","growth_diagnostics"):
            self.assertEqual(bundle["cycle_observation"][key],direct["merrill_clock"][key])
        self.assertEqual(bundle["cycle_observation"]["credit_cycle"],direct["credit_cycle"])
        self.assertIsNone(bundle["observations"][0]["release_date"])
        self.assertTrue(bundle["gaps"])

    def test_unknown_version_rejected(self):
        with self.assertRaises(ValueError):
            restore_sources({"contract_version":"9.0.0"})


if __name__=="__main__":
    unittest.main()
