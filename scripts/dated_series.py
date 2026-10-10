"""Strict pairing and native-frequency continuity; no filling missing observations."""
from datetime import date, timedelta
import math
import re


def paired(dates, values):
    if len(dates) != len(values):
        raise ValueError("日期和值长度不一致，拒绝自动截断或尾部对齐")
    if len(set(dates)) != len(dates) or dates != sorted(dates):
        raise ValueError("日期重复或未升序，拒绝静默覆盖")
    return list(zip(dates, values))


def period_number(d, frequency):
    if frequency not in ("M", "Q"):
        raise ValueError("仅月季频可转换为日历期")
    if re.fullmatch(r"\d{4}-Q[1-4]", d) and frequency == "Q":
        year, quarter = int(d[:4]), int(d[-1])
        date(year, 1, 1)
        return year * 4 + quarter - 1
    if not re.fullmatch(r"\d{4}-\d{2}(?:-\d{2})?", d):
        raise ValueError("日期或季度格式无效")
    year, month = map(int, d[:7].split("-"))
    date.fromisoformat(d if len(d) == 10 else d + "-01")
    return year * 4 + (month - 1) // 3 if frequency == "Q" else year * 12 + month - 1


def validate_frequency(indicator, expected=None):
    declared = [indicator[k] for k in ("frequency", "freq") if indicator.get(k)]
    if len(set(declared)) > 1:
        raise ValueError("频率字段互相冲突")
    freq = declared[0] if declared else expected or "M"
    if freq not in ("M", "Q", "D", "W") or (expected and freq != expected):
        raise ValueError("指标频率不符合计算要求: " + str(freq))
    return freq


def adjacent(previous, current, frequency="M"):
    if frequency in ("M", "Q"):
        return period_number(current, frequency) - period_number(previous, frequency) == 1
    p, c = date.fromisoformat(previous), date.fromisoformat(current)
    if frequency == "W":
        return (c - p).days == 7
    if frequency == "D":
        # Business-day convention: weekends allowed, holidays not inferred.
        expected = p + timedelta(days=1)
        while expected.weekday() >= 5:
            expected += timedelta(days=1)
        return c == expected
    raise ValueError(f"未支持的频率: {frequency}")


def trailing(indicator, key="value", frequency=None):
    indicator = indicator or {}
    values = indicator.get("values", []) if "values" in indicator else (indicator.get("series") or {}).get(key, [])
    if not values:
        return []
    points = paired(indicator.get("dates", []), values)
    freq = validate_frequency(indicator, frequency)
    periods = [period_number(d, freq) if freq in ("M", "Q") else date.fromisoformat(d) for d, _ in points]
    if len(set(periods)) != len(periods):
        raise ValueError("同一原生观测期重复")
    tail = []
    for d, v in points:
        if v is None or not math.isfinite(v):
            tail = []
            continue
        if tail and not adjacent(tail[-1][0], d, freq):
            tail = []
        tail.append((d, v))
    return tail
