# SPDX-License-Identifier: MIT
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from industry_evidence_review import review

class IndustryEvidenceTest(unittest.TestCase):
    def setUp(self):self.spec=json.loads((ROOT/'examples/expansion-teaching/industry-evidence-teaching.json').read_text(encoding='utf-8'))
    def test_four_families_and_unknown(self):
        r=review(self.spec)
        self.assertEqual(r['missingFamilies'],['库存'])
        self.assertEqual(r['records'][0]['change'],'100')
        self.assertIsNone(r['records'][-1]['change'])
    def test_changed_source_and_unit(self):
        self.spec['records'][0]['benchmark']['sourceVersion']='other'
        with self.assertRaises(ValueError):review(self.spec)
    def test_future_excluded_and_not_finite(self):
        self.spec['records'][0]['acquiredAt']='2026-10-02T09:00:00+08:00'
        self.assertIn('price',review(self.spec)['excludedAfterCutoff'])
        self.spec['records'][1]['value']='NaN'
        with self.assertRaises(ValueError):review(self.spec)

if __name__=='__main__':unittest.main()
