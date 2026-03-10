from datetime import date, datetime, timedelta, time


def get_week_range(ref_date: date) -> tuple[date, date]:
    """Return (start, end) for the report period.

    - Sunday (auto trigger): previous Sun-Sat week
    - Any other day (manual trigger): last 7 days ending yesterday
    """
    weekday = ref_date.weekday()  # Monday=0, Sunday=6
    if weekday == 6:  # Sunday — report covers the PREVIOUS Sun-Sat
        end = ref_date - timedelta(days=1)  # Saturday
        start = end - timedelta(days=6)     # Sunday
    else:
        # Manual mid-week trigger: last 7 days ending yesterday
        end = ref_date - timedelta(days=1)
        start = end - timedelta(days=6)
    return start, end


def get_date_range(end_date: date, days: int) -> tuple[date, date]:
    """Return (start_date, end_date) going back `days` days."""
    return end_date - timedelta(days=days), end_date


def parse_time_from_date_str(date_str: str) -> time:
    """Extract time-of-day from a Health Auto Export datetime string."""
    clean = date_str.strip()
    for sep in (" -", " +"):
        idx = clean.rfind(sep)
        if idx > 10:
            tz_part = clean[idx + 2:]
            if tz_part.replace(":", "").isdigit() and len(tz_part.replace(":", "")) in (4, 5):
                clean = clean[:idx]
                break
    clean = clean.rstrip("Z")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(clean, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse time from: {date_str}")
