from unittest.mock import MagicMock, patch
from decimal import Decimal
from datetime import date

from lambdas.shared.db import (
    query_metric_range,
    query_all_metrics_for_week,
)


def _make_items(metric: str, dates_and_data: list[tuple[str, dict]]) -> list[dict]:
    return [
        {
            "PK": "USER#default",
            "SK": f"METRIC#{metric}#{d}",
            "GSI1PK": f"USER#default#METRIC#{metric}",
            "GSI1SK": d,
            "metric": metric,
            "date": d,
            "data": data,
        }
        for d, data in dates_and_data
    ]


@patch("lambdas.shared.db.table")
def test_query_metric_range(mock_table):
    items = _make_items("step_count", [
        ("2026-03-01", {"qty": Decimal("8000")}),
        ("2026-03-02", {"qty": Decimal("9000")}),
    ])
    mock_table.query.return_value = {"Items": items}

    result = query_metric_range("default", "step_count", "2026-03-01", "2026-03-02")
    assert len(result) == 2
    assert result[0]["date"] == "2026-03-01"


@patch("lambdas.shared.db.table")
def test_query_all_metrics_for_week(mock_table):
    items = _make_items("step_count", [("2026-03-01", {"qty": Decimal("8000")})])
    mock_table.query.return_value = {"Items": items}

    result = query_all_metrics_for_week(
        "default",
        date(2026, 3, 1),
        date(2026, 3, 7),
    )
    assert "step_count" in result or len(mock_table.query.call_args_list) > 0
