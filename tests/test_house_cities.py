import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import fetch_eastmoney as f

class CitiesTests(unittest.TestCase):
    def rows(self,month='2026-08'):
        return [dict(CITY='city'+str(i),REPORT_DATE=month+'-01',FIRST_COMHOUSE_SAME=100+i/100,FIRST_COMHOUSE_SEQUENTIAL=99.5,SECOND_HOUSE_SAME=98,SECOND_HOUSE_SEQUENTIAL=99) for i in range(70)]
    def test_keeps_four_sequences_and_does_not_label_yoy_change_mom(self):
        result=f.build_house_price_series(self.rows())
        self.assertEqual(len(result['citySeries']),70)
        self.assertEqual(result['citySeries']['city0']['series']['new_mom'],[99.5])
        self.assertIsNone(result['mom'])
    def test_partial_and_duplicate_data_not_silently_averaged(self):
        self.assertIsNone(f.build_house_price_series(self.rows()[:69])['latest'])
        with self.assertRaises(ValueError):f.build_house_price_series(self.rows()+self.rows()[:1])
    def test_missing_value_is_not_zero(self):
        rows=self.rows();rows[0]['FIRST_COMHOUSE_SAME']=None
        result=f.build_house_price_series(rows)
        self.assertIsNone(result['latest']);self.assertIsNone(result['citySeries']['city0']['series']['new_yoy'][0])
    def test_pagination_must_finish_and_metadata_must_match(self):
        pages=[dict(success=True,result=dict(pages=2,count=2,data=[{'id':1}])),dict(success=True,result=dict(pages=2,count=2,data=[{'id':2}]))]
        with patch.object(f,'_http_get',side_effect=pages):self.assertEqual(len(f.fetch_report('x',all_pages=True)),2)
        pages[1]['result']['count']=3
        with patch.object(f,'_http_get',side_effect=pages):
            with self.assertRaises(ValueError):f.fetch_report('x',all_pages=True)
