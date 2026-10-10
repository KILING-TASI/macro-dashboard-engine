"""Optional candidate vocabulary sidecar; does not replace macro_contract 1.0.0."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from macro_contract import CONTRACT_VERSION
from dated_series import paired, validate_frequency, period_number

PARSER_VERSION = "macro-sidecar-0.1.0"
CATALOG = Path(__file__).resolve().parents[1] / "references/source_catalog.json"


def build_sidecar(bundle):
    if bundle.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("仅适配macro_contract 1.0.0；未知版本拒绝")
    # This digest describes the parsed envelope, never the downloaded raw bytes.
    encoded = json.dumps(bundle, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))["indicators"]
    records, ids = [], set()
    for observation in bundle["observations"]:
        provider, key = observation["provider"], observation["indicator"]
        payload = observation["payload"]
        freq = validate_frequency(payload, observation["frequency"])
        definition = catalog.get(provider + ":" + key, {})
        synthetic = bundle.get("kind") == "teaching"
        sequences = {"values": payload["values"]} if "values" in payload else payload.get("series", {})
        for field, values in sequences.items():
            for d, value in paired(payload.get("dates", []), values):
                if freq in ("M", "Q"):
                    period_number(d, freq)
                record_id = ":".join((provider, key, field, d))
                if record_id in ids:
                    raise ValueError("重复候选记录身份")
                ids.add(record_id)
                unit = "%" if field == "yoy" else payload.get("unit")
                conflicts = []
                if payload.get("transformation") == "calendar-yoy-1.0.0" and unit not in ("%", "同比%"):
                    conflicts.append({"field": "unit", "input": unit, "expected": "%", "reason": "同比转换与输入单位冲突，保留原字段但不确认规范单位"})
                    unit = None
                records.append({"record_id": record_id, "subject_id": provider + ":" + key,
                    "metric_id": key + ":" + field, "value": value, "unit": unit,
                    "currency": payload.get("currency"), "observation_time": d,
                    "period_start": None, "period_end": None,
                    "published_at": None, "effective_at": None,
                    "acquired_at": observation.get("fetched_at"), "available_at": None,
                    "time_precision": {"observation_time": freq, "published_at": None,
                        "effective_at": None, "acquired_at": "input_timestamp_unverified" if observation.get("fetched_at") else None,
                        "available_at": None},
                    "producer": "本仓原创模拟" if synthetic else definition.get("producer"),
                    "provider": "original_synthetic" if synthetic else provider,
                    "source_url": None if synthetic else payload.get("source_url", definition.get("retrieval_url")),
                    "raw_sha256": None, "source_version": observation.get("revision"),
                    "parser_version": PARSER_VERSION, "method_version": payload.get("transformation"),
                    "verification_status": {"download_success": None, "original_page_found": None,
                        "semantic_verified": None, "synthetic": synthetic},
                    "missing": {"value": value is None, "reason": "explicit_null_in_input" if value is None else None},
                    "conflicts": conflicts, "coverage": {"frequency": freq, "provided_points": len(values),
                        "first_provided_period": payload.get("dates", [None])[0] if values else None,
                        "last_provided_period": payload.get("dates", [None])[-1] if values else None,
                        "expected_completeness": None},
                    "rights": "项目原创模拟；第三方组件许可独立" if synthetic else definition.get("license", "未核验"),
                    "extensions": {"macro": {"original_payload": deepcopy(payload),
                        "series_release_date": observation.get("release_date"),
                        "original_provider_key": provider, "original_field": field,
                        "original_parser_version": None, "cycle_method_version": bundle.get("calculation_version"),
                        "layer": "derived" if field == "yoy" or payload.get("transformation", "identity") != "identity" else "parsed_observation",
                        "frequency_basis": observation.get("frequency_basis"),
                        "seasonality": definition.get("seasonality"), "stock_flow": definition.get("stock_flow"),
                        "unit_basis": "field_semantics" if field == "yoy" else "input",
                        "unknown_reasons": {"available_at": "未取得逐期历史版本与可得时间",
                            "raw_sha256": "输入仅含解析后载荷，不能冒充原始响应摘要",
                            "published_at": "序列级release_date不能赋给每条观测",
                            "period_bounds": "保留原始期标签，未推定实际统计区间",
                            "currency": "仅采用显式输入，不从名称推定"}}}})
    return {"candidate_format": PARSER_VERSION, "status": "local_candidate_not_cross_repo_standard",
        "input_contract_version": CONTRACT_VERSION, "parsed_bundle_sha256": hashlib.sha256(encoded).hexdigest(),
        "source_catalog_sha256": hashlib.sha256(CATALOG.read_bytes()).hexdigest(),
        "records": records, "point_in_time": False,
        "limitations": ["不改变旧接口/输入/冻结输出", "不认证来源原文", "缺口记录不创造缺失基期事实", "跨仓验证未完成"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    bundle = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    result = build_sidecar(bundle)
    with Path(args.out).open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
