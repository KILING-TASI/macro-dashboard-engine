"""Separate acquisition, definition review and original-release verification."""
import json
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[1] / "references" / "source_catalog.json"


def build_evidence(sources):
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    rows = []
    for provider, payload in sources.items():
        for key, indicator in (payload or {}).get("indicators", {}).items():
            definition = catalog["indicators"].get(f"{provider}:{key}", {})
            series = indicator.get("series") or {}
            sequences = [indicator["values"]] if "values" in indicator else list(series.values())
            points = [(d, v) for sequence in sequences
                      for d, v in zip(indicator.get("dates", []), sequence) if v is not None]
            verification = indicator.get("verification") or {}
            # A status flag alone is not original-release evidence.
            verified = (verification.get("status") == "original_verified"
                        and verification.get("original_url")
                        and verification.get("checked_at") and verification.get("locator"))
            rows.append({"key": key, "name": indicator.get("name", key),
                "provider": provider, "producer": definition.get("producer", "未登记"),
                "source_url": indicator.get("source_url", definition.get("retrieval_url", "")),
                "observed_through": max((d for d, _ in points), default=None),
                "fetched_at": (payload or {}).get("fetched_at"),
                "release_date": indicator.get("release_date"),
                "unit": indicator.get("unit", definition.get("unit")),
                "frequency": indicator.get("frequency", indicator.get("freq", definition.get("frequency"))),
                "seasonality": definition.get("seasonality", "未核验"),
                "stock_flow": definition.get("stock_flow", "未核验"),
                "definition_status": "已登记，观测未逐点核验" if definition else "未登记",
                "verification_status": "原文已核验" if verified else "仅取得数据，原文未核验",
                "verification": verification if verified else None,
                "breaks": definition.get("breaks", []),
                "revision": indicator.get("revision", "历史版本未取得"),
                "sample": (payload or {}).get("source") == "sample"})
    return {"rows": rows, "catalog_reviewed_at": catalog["reviewed_at"],
            "note": "取得数据不等于原文核验；空白发布日期不以观测期或抓取时间代替。"}
