import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fetch_fred import _yoy, _yoy_quarterly
from dated_series import trailing
from compute_cycle import growth_score, credit_cycle, _clean_outliers


class MethodCounterexamples(unittest.TestCase):
    def test_missing_december_does_not_shift_yoy_base(self):
        points = [(f"2025-{i:02d}", 99+i) for i in range(1,12)]
        points += [("2026-01",112),("2026-02",113)]
        self.assertEqual(_yoy(points), [("2026-01",12.0),("2026-02",11.881)])

    def test_missing_quarter_uses_same_quarter_last_year(self):
        points = [("2025-Q1",100),("2025-Q2",200),("2025-Q3",300),
                  ("2026-Q1",110),("2026-Q2",240),("2026-Q4",500)]
        self.assertEqual(_yoy_quarterly(points), [("2026-Q1",10.0),("2026-Q2",20.0)])
        self.assertEqual(_yoy([("2025-01",0),("2026-01",5)]), [])

    def test_illegal_quarter_and_duplicate_period_rejected(self):
        for d in ("2025-Q0", "2025-Q5", "2025-13", "2025-02-30"):
            with self.assertRaises(ValueError):
                trailing({"dates":[d], "values":[None], "freq":"Q"})
        with self.assertRaises(ValueError):
            _yoy([("2025-01-01",100),("2025-01-30",101)])

    def test_quarterly_pmi_is_not_scored_as_monthly(self):
        with self.assertRaises(ValueError):
            growth_score({"pmi":{"dates":["2025-Q1","2025-Q2","2025-Q3","2025-Q4"],
                                  "values":[49,50,51,52],"freq":"Q"}}, {})
        with self.assertRaises(ValueError):
            trailing({"dates":["2025-01"],"values":[1],"freq":"M","frequency":"Q"})

    def test_step_preserved_and_cleaning_is_explicit(self):
        dates = [f"2026-{i:02d}" for i in range(1,9)]
        step = [-5]*4+[10]*4
        for enabled in (False, True):
            self.assertEqual(_clean_outliers(dates,step,enabled=enabled), (step,[]))
        spike = [0,0,20,0,0,0,0,0]
        self.assertEqual(_clean_outliers(dates,spike)[0], spike)
        cleaned, masked = _clean_outliers(dates,spike,enabled=True)
        self.assertIsNone(cleaned[2])
        self.assertEqual(len(masked),1)
        self.assertEqual(spike[2],20)
        em = {"m1":{"dates":dates,"series":{"yoy":spike}},
              "m2":{"dates":dates,"series":{"yoy":[0]*8}}}
        result = credit_cycle(em, clean_outliers=True)
        self.assertEqual(result["scissors_raw_series"], spike)
        self.assertEqual(result["cleaning"]["mode"], "isolated-neighbor")
        short = {k:{"dates":dates[:4],"series":{"yoy":v["series"]["yoy"][:4]}} for k,v in em.items()}
        insufficient = credit_cycle(short, clean_outliers=True)
        self.assertEqual(insufficient["state"], "数据不足")
        self.assertEqual(insufficient["scissors_raw_series"], spike[:4])


if __name__ == "__main__":
    unittest.main()
