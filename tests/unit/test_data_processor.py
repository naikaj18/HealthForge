import json
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "test-table")


@pytest.fixture()
def mod():
    with patch("boto3.resource") as mock_resource:
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        import importlib
        import lambdas.data_processor.handler as m
        importlib.reload(m)
        yield m, mock_table


# --- parse_date ---

def test_parse_date_with_timezone(mod):
    m, _ = mod
    assert m.parse_date("2026-03-08 00:00:00 -0800") == "2026-03-08"


def test_parse_date_iso(mod):
    m, _ = mod
    assert m.parse_date("2026-03-08T23:15:00Z") == "2026-03-08"


def test_parse_date_plain(mod):
    m, _ = mod
    assert m.parse_date("2026-03-08") == "2026-03-08"


def test_parse_date_datetime(mod):
    m, _ = mod
    assert m.parse_date("2026-03-08 23:15:00") == "2026-03-08"


# --- convert_floats ---

def test_convert_floats_nested(mod):
    m, _ = mod
    result = m.convert_floats({"a": 1.5, "b": [2.0, {"c": 3.0}], "d": "text"})
    assert result == {"a": Decimal("1.5"), "b": [Decimal("2.0"), {"c": Decimal("3.0")}], "d": "text"}


# --- slim_workout ---

def test_slim_workout_extracts_essentials(mod):
    m, _ = mod
    workout = {
        "name": "Running",
        "start": "2026-03-08T07:00:00",
        "end": "2026-03-08T07:30:00",
        "duration": 30,
        "totalEnergyBurned": 300,
        "activeEnergyBurned": 280,
        "isIndoor": False,
        "avgHeartRate": 155,
        "totalDistance": 5.0,
        "heartRate": {"min": 120, "avg": 155, "max": 175},
        "route": [{"lat": 0, "lon": 0}],  # should be excluded
    }
    result = m.slim_workout(workout)
    assert result["name"] == "Running"
    assert result["avgHeartRate"] == 155
    assert result["totalDistance"] == 5.0
    assert result["heartRateSummary"]["max"] == 175
    assert "route" not in result


# --- build_item ---

def test_build_item_keys(mod):
    m, _ = mod
    item = m.build_item("user1", "step_count", "2026-03-08", {"qty": 8000})
    assert item["PK"] == "USER#user1"
    assert item["SK"] == "METRIC#step_count#2026-03-08"
    assert item["GSI1PK"] == "USER#user1#METRIC#step_count"
    assert item["GSI1SK"] == "2026-03-08"


# --- build_workout_item ---

def test_build_workout_item_keys(mod):
    m, _ = mod
    workout = {"name": "Running", "start": "", "end": "", "duration": 30,
               "totalEnergyBurned": 300, "activeEnergyBurned": 280, "isIndoor": False}
    item = m.build_workout_item("user1", "2026-03-08", workout)
    assert item["SK"] == "METRIC#workout#2026-03-08#Running"
    assert item["metric"] == "workout"


# --- lambda_handler ---

def test_handler_writes_known_metrics(mod):
    m, mock_table = mod
    event = {
        "Records": [
            {
                "body": json.dumps({
                    "user_id": "default",
                    "data": {
                        "metrics": [
                            {
                                "name": "step_count",
                                "data": [{"date": "2026-03-08 00:00:00 -0800", "qty": 8000}],
                            }
                        ],
                        "workouts": [],
                    },
                })
            }
        ]
    }
    result = m.lambda_handler(event, None)
    assert result["written"] == 1
    mock_table.put_item.assert_called_once()
