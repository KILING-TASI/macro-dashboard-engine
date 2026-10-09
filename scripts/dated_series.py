"""Strict pairing and native-frequency continuity; no filling missing observations."""
from datetime import date, timedelta
import math


def paired(dates, values):
    if len(dates) != len(values):
        raise ValueError("日期和值长度不一致，拒绝自动截断或尾部对齐")
    if len(set(dates)) != len(dates) or dates != sorted(dates):
        raise ValueError("日期重复或未升序，拒绝静默覆盖")
    return list(zip(dates, values))


def period_number(d, frequency):
    if frequency == "Q" and "Q" in d:
        year, quarter = d.split("-Q")
        return int(year) * 4 + int(quarter) - 1
    year, month = map(int, d[:7].split("-"))
    if not 1 <= month <= 12:
        raise ValueError("月份无效")
    return year * 4 + (month - 1) // 3 if frequency == "Q" else year * 12 + month - 1


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
    freq = indicator.get("frequency", indicator.get("freq", frequency or "M"))
    tail = []
    for d, v in points:
        if v is None or not math.isfinite(v):
            tail = []
            continue
        if tail and not adjacent(tail[-1][0], d, freq):
            tail = []
        tail.append((d, v))
    return tail
