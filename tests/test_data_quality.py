import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import fetch_fred as fred
import fetch_eastmoney as em
import build_dashboard as dashboard
import regress_attribution as attribution

class DataQualityTests(unittest.TestCase):
    def test_spread_subtracts_and_keeps_zero_rate(self):
        with patch.object(fred, 'fetch_series', side_effect=[ [('2026-01-01', 2), ('2026-02-01', 3)], [('2026-01-01', 4), ('2026-02-01', 0)] ]):
            result = fred._derive_ratio('cn_rate', 'fedfunds', 'spread', 'pct', operation='spread')
        self.assertEqual(result['values'], [-2, 3])
        self.assertIn('-', result['series_id'])

    def test_alignment_preserves_missing_dates(self):
        fr = {'indicators': {k: {'dates': d, 'values': v} for k,d,v in [
            ('usd_index', ['2026-01-01','2026-01-02'], [100,101]),
            ('us10y_real', ['2026-01-02'], [2]),
            ('vix', ['2026-01-01','2026-01-02'], [15,16]),
            ('us_curve', ['2026-01-02'], [-1])]}}
        p = dashboard.build_payload({'indicators':{}, 'errors':['PMI failed']}, fr, {})
        self.assertEqual(p['p1']['liquidity']['real'], [None,2])
        self.assertEqual(p['p1']['risk']['curve'], [None,-1])
        self.assertEqual(p['data_quality']['status'], 'partial')
        with tempfile.TemporaryDirectory() as d:
            output = Path(d)/'dashboard.html'
            dashboard.render(p, str(output))
            self.assertIn('数据不完整',output.read_text(encoding='utf-8'))

    def test_empty_fetch_is_error(self):
        with patch.object(em,'fetch_indicator', return_value={'dates':[], 'series':{}}):
            result=em.fetch_all(['pmi'])
        self.assertFalse(result['indicators'])
        self.assertTrue(result['errors'])

    def test_no_change_across_missing_month(self):
        self.assertEqual(attribution._diff({'2025-12':1, '2026-01':2, '2026-03':4}), {'2026-01':1})

    def test_fred_empty_fetch_is_error(self):
        with patch.object(fred, 'build', return_value={'dates': []}), patch.object(fred, '_derive_ratio', return_value={'dates': []}):
            result = fred.fetch_all(['us10y'])
        self.assertFalse(result['indicators'])
        self.assertTrue(result['errors'])

    def test_offline_generation_uses_sample(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / 'offline.html'
            with patch.object(sys, 'argv', ['build_dashboard.py', '--eastmoney', str(Path(d)/'missing-em.json'), '--fred', str(Path(d)/'missing-fr.json'), '--cycle', str(Path(d)/'missing-cycle.json'), '--out', str(output)]):
                dashboard.main()
            html = output.read_text(encoding='utf-8')
            self.assertIn('示例数据', html)
            self.assertNotIn('__DATA__', html)
            self.assertIn('"status": "sample"', html)

    def test_standardized_beta_and_complete_benchmark(self):
        months=[f'{2024+i//12}-{i%12+1:02d}' for i in range(24)]
        x=[math.sin(i) for i in range(24)]
        factors={'growth':dict(zip(months,x))}
        bench=[[m,1] for m in months[:-1]]
        industry={'indices':{'sh000300':{'returns':bench}, 'sh000928':{'returns':[[m,1+3*v] for m,v in zip(months,x)]}}}
        with patch.object(attribution,'build_factors',return_value=factors):
            result=attribution.compute(industry,{}, {})
        sector=result['sectors'][0]
        self.assertEqual(sector['n'],23)
        self.assertAlmostEqual(sector['beta']['growth'],1)
        self.assertEqual(sector['end_month'], months[-2])
        with patch.object(attribution,'build_factors',return_value=factors):
            self.assertFalse(attribution.compute({'indices':{'sh000928':industry['indices']['sh000928']}},{},{})['sectors'])

if __name__=='__main__':
    unittest.main()
