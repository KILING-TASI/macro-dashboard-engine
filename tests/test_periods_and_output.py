import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import compute_cycle as cycle
import regress_attribution as regression
import run_pipeline as pipeline
from dated_series import trailing


class PeriodAndOutputTests(unittest.TestCase):
    def test_gap_and_none_stop_monthly_window(self):
        for dates, values in [(["2026-01", "2026-03", "2026-04"], [1,3,4]),
                              (["2026-02", "2026-03", "2026-04"], [2,None,4])]:
            points = trailing({"dates": dates, "values": values, "freq":"M"})
            self.assertLess(len(points), 4)
            self.assertEqual(cycle.growth_score({"pmi":{"dates":dates,"values":values}}, {})[2],0)
        self.assertEqual(trailing({"dates":["2026-01","2026-02"],"values":[1,None]}), [])

    def test_quarter_and_business_day_continuity(self):
        self.assertEqual(len(trailing({"dates":["2025-01","2025-04","2025-07","2025-10"],
            "values":[1,2,3,4],"freq":"Q"})),4)
        self.assertEqual(len(trailing({"dates":["2025-01","2025-07"],"values":[1,3],"freq":"Q"})),1)
        self.assertEqual(len(trailing({"dates":["2026-10-02","2026-10-05"],"values":[1,2],"freq":"D"})),2)
        self.assertEqual(len(trailing({"dates":["2026-10-02","2026-10-06"],"values":[1,2],"freq":"D"})),1)

    def test_regression_rejects_misaligned_and_unordered_dates(self):
        for dates, values in [(["2026-01","2026-02"],[3]), (["2026-02","2026-01"],[2,1]),
                              (["2026-01","2026-01"],[1,2])]:
            with self.assertRaises(ValueError):
                regression._em_monthly_series({"indicators":{"pmi":{"dates":dates,"series":{"value":values}}}},"pmi")
            with self.assertRaises(ValueError):
                regression._fred_monthly_series({"indicators":{"us10y":{"dates":dates,"values":values}}},"us10y")
        self.assertEqual(regression._pct_change({"2025-12":2,"2026-02":4}),{})

    def test_credit_and_timeline_do_not_bridge_gap(self):
        dates = ["2026-01","2026-03","2026-04","2026-05"]
        em = {key:{"dates":dates,"series":{"yoy":values}} for key,values in [("m1",[1,2,3,4]),("m2",[1,1,1,1])]}
        self.assertEqual(cycle.credit_cycle(em)["state"],"数据不足")
        self.assertIsNone(cycle.build_timeline(em,{})["rows"][3]["scores"][-1])
        dates=["2026-01","2026-02","2026-03","2026-04","2026-05"]
        em={"m1":{"dates":dates,"series":{"yoy":[1,2,3,4,None]}},
            "m2":{"dates":dates,"series":{"yoy":[1,1,1,1,1]}}}
        self.assertEqual(cycle.credit_cycle(em)["state"],"数据不足")

    def test_growth_contributions_and_sensitivity(self):
        dates=[f"2026-{i:02d}" for i in range(1,13)]
        em={"pmi":{"dates":dates,"series":{"value":[49+i/10 for i in range(12)]}},
            "retail":{"dates":dates,"series":{"yoy":list(range(12))}},
            "gdp":{"dates":["2025-01","2025-04","2025-07","2025-10"],"series":{"yoy":[2,3,4,5]}}}
        details={}
        score,_,n=cycle.growth_score(em,{},details)
        self.assertEqual(n,3)
        self.assertAlmostEqual(sum(c["contribution"] for c in details["components"]),score,places=3)
        self.assertTrue(all(-1<=c["score"]<=1 for c in details["components"]))
        self.assertEqual(details["components"][-1]["frequency"],"Q")
        self.assertGreater(details["scale_sensitivity"]["0.5"],details["scale_sensitivity"]["2.0"])
        self.assertEqual(set(details["leave_one_out"]),{"pmi","retail","gdp"})

    def test_failed_output_retains_archive_and_success_requires_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/"old.json"
            out.write_text("old",encoding="utf-8")
            script=Path(folder)/"writer.py"
            script.write_text('import sys\nfrom pathlib import Path\nPath(sys.argv[2]).write_text("new")\nraise SystemExit(int(sys.argv[3]))',encoding="utf-8")
            command=[str(script),"--out",str(out),"1"]
            self.assertFalse(pipeline.run(command,overwrite=True))
            self.assertEqual(out.read_text(),"old")
            command[-1]="0"
            self.assertFalse(pipeline.run(command))
            self.assertEqual(out.read_text(),"old")
            self.assertTrue(pipeline.run(command,overwrite=True))
            self.assertEqual(out.read_text(),"new")
            self.assertFalse(list(Path(folder).glob(".macro-stage-*")))

    def test_empty_success_does_not_replace_and_runs_use_new_directories(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/"old.html"
            out.write_text("old",encoding="utf-8")
            script=Path(folder)/"empty.py"
            script.write_text("pass",encoding="utf-8")
            self.assertFalse(pipeline.run([str(script),"--out",str(out)],overwrite=True))
            self.assertEqual(out.read_text(),"old")
            paths=[]
            def fake_run(command, **kwargs):
                path=Path(command[command.index("--out")+1])
                path.write_text("demo",encoding="utf-8")
                paths.append(path)
                return True
            for _ in range(2):
                with patch.object(sys,"argv",["pipeline","--demo","--workdir",folder]), patch.object(pipeline,"run",side_effect=fake_run):
                    pipeline.main()
            self.assertNotEqual(paths[0].parent,paths[1].parent)
            self.assertTrue(all(p.exists() for p in paths))


if __name__ == "__main__":
    unittest.main()
