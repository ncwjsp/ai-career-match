"""Conservative month-precision employment dates and interval union."""

import re
from datetime import date

MONTHS = {
    name: i
    for i, name in enumerate(
        ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1
    )
}
DATE = r"(?:[A-Za-z]{3,9}\.?\s+\d{4}|\d{4}-\d{2}|\d{4}|present|current|now)"
RANGE = re.compile(rf"(?<!\w)({DATE})\s*(?:–|—|-|\bto\b)\s*({DATE})(?!\w)", re.I)


def parse_date(value: str) -> str | None:
    value = value.strip().casefold()
    if value in {"present", "current", "now"}:
        return "present"
    if re.fullmatch(r"\d{4}", value):
        return value if 1900 <= int(value) <= 2200 else None
    if re.fullmatch(r"\d{4}-\d{2}", value):
        year, month = map(int, value.split("-"))
        return value if 1900 <= year <= 2200 and 1 <= month <= 12 else None
    match = re.fullmatch(r"([a-z]{3,9})\.?\s+(\d{4})", value)
    if match and match[1][:3] in MONTHS and 1900 <= int(match[2]) <= 2200:
        # Avoid accepting invented month names sharing a three-letter prefix.
        names = {
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        }
        if match[1] in names or match[1] in MONTHS or match[1] == "sept":
            return f"{match[2]}-{MONTHS[match[1][:3]]:02d}"
    return None


def extract_dates(text: str) -> tuple[str | None, str | None, bool]:
    matches = list(RANGE.finditer(text))
    if len(matches) != 1:
        return None, None, False
    start, end = parse_date(matches[0][1]), parse_date(matches[0][2])
    return start, end, start is not None and start != "present" and end is not None


def union_years(periods: list[tuple[str | None, str | None]], as_of: date) -> float | None:
    """Count distinct reported months; present excludes the partial current month.

    Unknown/year-only/future/reversed intervals invalidate the aggregate instead
    of presenting a known subset as total experience. Closed months are inclusive.
    """
    if not periods:
        return None
    current = as_of.year * 12 + as_of.month - 1
    intervals = []
    for start, end in periods:
        if not start or not end or not re.fullmatch(r"\d{4}-\d{2}", start):
            return None
        if parse_date(start) != start:
            return None
        year, month = map(int, start.split("-"))
        lo = year * 12 + month - 1
        if end == "present":
            hi = current
        elif re.fullmatch(r"\d{4}-\d{2}", end):
            if parse_date(end) != end:
                return None
            year, month = map(int, end.split("-"))
            last = year * 12 + month - 1
            if last >= current or last < lo:
                return None  # Future or still-incomplete end month.
            hi = last + 1
        else:
            return None
        if lo > current or hi < lo:
            return None
        intervals.append((lo, hi))
    total = 0
    left, right = sorted(intervals)[0]
    for lo, hi in sorted(intervals)[1:]:
        if lo <= right:
            right = max(right, hi)
        else:
            total += right - left
            left, right = lo, hi
    return round((total + right - left) / 12, 2)
