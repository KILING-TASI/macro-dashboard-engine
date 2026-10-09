"""Original synthetic teaching data; no third-party observations."""

def teaching_input():
    dates = [f"{2025 + (8+i)//12}-{(8+i)%12+1:02d}" for i in range(12)]
    def indicator(name, values, unit="%", field="value", period_dates=None, frequency="M"):
        return {"name": name, "dates": period_dates or dates, "series": {field: values},
                "unit": unit, "frequency": frequency, "latest": values[-1], "prev": values[-2]}
    em = {"source": "sample", "as_of": "2026-08", "fetched_at": None,
          "provenance": "Original synthetic teaching numbers; not official observations.",
          "indicators": {
              "pmi": indicator("制造业PMI", [49.0,49.2,49.4,49.5,49.6,49.8,50.0,50.1,50.3,50.4,50.5,50.6], "指数"),
              "cpi": indicator("CPI同比", [0.2,0.2,0.3,0.3,0.4,0.4,0.5,0.5,0.6,0.6,0.7,0.8]),
              "ppi": indicator("PPI同比", [-1.1,-1.0,-0.9,-0.8,-0.7,-0.6,-0.5,-0.4,-0.3,-0.2,-0.1,0.0]),
              "retail": indicator("社零同比", [1.0,1.2,1.4,1.6,1.8,2.0,2.2,2.4,2.6,2.8,3.0,3.2], field="yoy"),
              "gdp": indicator("GDP同比", [3.5,3.7,3.9,4.1], field="yoy", period_dates=["2025-09","2025-12","2026-03","2026-06"], frequency="Q"),
              "m1": indicator("M1同比", [1.0,1.1,1.2,1.3,1.4,1.5,1.6,1.7,1.8,1.9,2.0,2.1], field="yoy"),
              "m2": indicator("M2同比", [7.0]*12, field="yoy")}}
    return {"eastmoney": em, "fred": {"source": "sample", "indicators": {}},
            "note": "All numbers are fictional; missing foreign/credit/industry observations remain missing."}


