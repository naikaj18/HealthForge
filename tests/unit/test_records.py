# tests/unit/test_records.py
from lambdas.shared.records import check_records, format_records


def test_check_records_new_record():
    current_records = {
        "best_sleep_score": {"value": 90, "date": "2026-02-18"},
        "highest_steps": {"value": 12000, "date": "2026-02-22"},
    }
    this_week = {
        "best_sleep_score": 95,
        "highest_steps": 11000,
    }
    result = check_records(current_records, this_week)
    assert result["best_sleep_score"]["broken"]
    assert not result["highest_steps"]["broken"]


def test_check_records_close_to_record():
    current_records = {
        "highest_steps": {"value": 12000, "date": "2026-02-22"},
    }
    this_week = {"highest_steps": 11500}
    result = check_records(current_records, this_week)
    assert result["highest_steps"]["close"]  # Within 5%


def test_format_records():
    records_status = {
        "best_sleep_score": {
            "broken": True,
            "old_value": 90,
            "new_value": 95,
            "date": "2026-03-05",
        },
        "highest_steps": {
            "broken": False,
            "close": True,
            "value": 12000,
            "date": "2026-02-22",
            "this_week": 11500,
        },
    }
    lines = format_records(records_status)
    assert len(lines) > 0
    assert any("95" in line for line in lines)
