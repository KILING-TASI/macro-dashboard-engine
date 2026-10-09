"""Optional, lossless observation envelope and limited cycle export. No workbench dependency."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from compute_cycle import growth_score, inflation_score, classify_quadrant, inventory_cycle, credit_cycle, CALCULATION_VERSION
from data_evidence import build_evidence
from dated_series import paired

CONTRACT_VERSION = "1.0.0"
SELECTED = {"eastmoney": ("pmi", "retail", "gdp", "cpi", "ppi", "m1", "m2"), "fred": ("us_cpi",)}


def export_bundle(sources):
    observations, selected, gaps = [], {}, []
    for provider, keys in SELECTED.items():
        payload = sources.get(provider) or {}
        indicators = payload.get("indicators") or {}
        selected[provider] = {**deepcopy(payload), "indicators": {}}
        for key in keys:
            indicator = indicators.get(key)
            if not indicator:
                gaps.append({"provider": provider, "indicator": key, "reason": "未取得"})
                continue
            dates = indicator.get("dates") or []
            sequences = [indicator["values"]] if "values" in indicator else list((indicator.get("series") or {}).values())
            for values in sequences:
                paired(dates, values)
            selected[provider]["indicators"][key] = deepcopy(indicator)
            observations.append({"provider": provider, "indicator": key,
                "layer": "acquired_series", "payload": deepcopy(indicator),
                "frequency": indicator.get("frequency", indicator.get("freq", "Q" if key == "gdp" else "M")),
                "frequency_basis": "input" if "frequency" in indicator or "freq" in indicator else "catalog_assumption",
                "fetched_at": payload.get("fetched_at"), "release_date": indicator.get("release_date"),
                "revision": indicator.get("revision"), "source": payload.get("source"),
                "missing_dates": [d for i,d in enumerate(dates) if sequences and all(s[i] is None for s in sequences)]})
    em, fr = (selected[p]["indicators"] for p in ("eastmoney", "fred"))
    diagnostics = {}
    growth, growth_evidence, gd = growth_score(em, fr, diagnostics)
    inflation, inflation_evidence, idims = inflation_score(em, fr)
    quadrant = classify_quadrant(growth, inflation, gd, idims)[0]
    return {"contract_version": CONTRACT_VERSION, "calculation_version": CALCULATION_VERSION,
        "kind": "teaching" if any(p.get("source") == "sample" for p in sources.values()) else "research_observation",
        "observations": observations,
        "input_context": {p:{k:deepcopy(v) for k,v in payload.items() if k != "indicators"} for p,payload in selected.items()},
        "evidence": build_evidence(selected), "gaps": gaps,
        "cycle_observation": {"growth_momentum": growth, "inflation_momentum": inflation,
            "growth_dims": gd, "inflation_dims": idims, "quadrant": quadrant,
            "growth_evidence": growth_evidence, "inflation_evidence": inflation_evidence,
            "growth_diagnostics": diagnostics, "inventory_cycle": inventory_cycle(em), "credit_cycle": credit_cycle(em)},
        "point_in_time": False, "limitations": ["观测取得不等于官方原文核验", "未知发布与修订时点保持未知", "周期评分为研究假设；不含资产配置或预测", "不与工作台已有宏观模块宣称等价"]}


def restore_sources(bundle):
    if bundle.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("不支持的宏观契约版本")
    sources = {p:{**deepcopy(meta),"indicators":{}} for p,meta in bundle["input_context"].items()}
    for observation in bundle["observations"]:
        sources[observation["provider"]]["indicators"][observation["indicator"]] = deepcopy(observation["payload"])
    return sources


def main():
    parser = argparse.ArgumentParser(description="有限范围宏观观测与周期契约导出，不取数")
    parser.add_argument("--eastmoney", required=True)
    parser.add_argument("--fred", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    paths = {"eastmoney": Path(args.eastmoney), "fred": Path(args.fred)}
    sources = {p:json.loads(path.read_text(encoding="utf-8")) for p,path in paths.items()}
    bundle = export_bundle(sources)
    bundle["input_files"] = {p:{"name":path.name,"sha256":hashlib.sha256(path.read_bytes()).hexdigest()} for p,path in paths.items()}
    bundle["code_files"] = {name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                            for name in ("macro_contract.py", "compute_cycle.py", "dated_series.py", "data_evidence.py")}
    output = Path(args.out)
    serialized = json.dumps(bundle, ensure_ascii=False, indent=2, allow_nan=False)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(serialized)


if __name__ == "__main__":
    main()
