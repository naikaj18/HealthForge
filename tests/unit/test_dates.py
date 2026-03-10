from datetime import date

from lambdas.shared.dates import (
    get_week_range,
    get_date_range,
    parse_time_from_date_str,
)


def test_get_week_range_sunday_to_saturday():
    """Sunday Mar 8 → covers previous Sun Mar 1 to Sat Mar 7."""
    start, end = get_week_range(date(2026, 3, 8))  # Sunday Mar 8
    assert start == date(2026, 3, 1)  # Previous Sunday
    assert end == date(2026, 3, 7)    # Previous Saturday


def test_get_week_range_from_midweek():
    """Wednesday Mar 4 (manual) → last 7 days: Thu Feb 26 to Tue Mar 3."""
    start, end = get_week_range(date(2026, 3, 4))  # Wednesday
    assert end == date(2026, 3, 3)    # Yesterday (Tuesday)
    assert start == date(2026, 2, 25) # 7 days back


def test_get_week_range_tuesday():
    """Tuesday Mar 10 (manual) → Mon Mar 3 to Mon Mar 9."""
    start, end = get_week_range(date(2026, 3, 10))
    assert end == date(2026, 3, 9)    # Yesterday (Monday)
    assert start == date(2026, 3, 3)  # 7 days back


def test_get_date_range_30_days():
    end = date(2026, 3, 8)
    start, end_out = get_date_range(end, days=30)
    assert start == date(2026, 2, 6)
    assert end_out == end


def test_parse_time_from_date_str_with_timezone():
    result = parse_time_from_date_str("2026-02-07 00:36:58 -0800")
    assert result.hour == 0
    assert result.minute == 36


def test_parse_time_from_date_str_iso():
    result = parse_time_from_date_str("2026-02-07T23:15:00Z")
    assert result.hour == 23
    assert result.minute == 15
