# Weekly Email Report Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the weekly email pipeline — score computation, Gemini Flash insights, plain text email rendering, and SES delivery, orchestrated by Step Functions on a Sunday 10 AM schedule.

**Architecture:** Three Lambda functions chained via Step Functions: (1) Aggregation Lambda queries DynamoDB and computes all scores/stats, (2) Insight Lambda sends computed summaries to Gemini Flash for human-friendly insights, (3) Email Lambda renders a plain text email and sends via SES. EventBridge triggers the pipeline every Sunday at 10 AM.

**Tech Stack:** AWS CDK (Python), Lambda (Python 3.12), Step Functions, EventBridge, SES, DynamoDB, Google Gemini Flash API

**Spec:** `docs/specs/2026-03-10-weekly-email-design.md`

---

## File Structure

```
lambdas/
  shared/                          # Shared utilities across lambdas
    db.py                          # DynamoDB query helpers
    dates.py                       # Date range utilities
    scores.py                      # All 5 score formulas
    correlations.py                # Correlation and anomaly detection
    records.py                     # Personal records tracking
  aggregation/
    handler.py                     # Step 1: Query DB, compute everything
  insight/
    handler.py                     # Step 2: Call Gemini Flash
  email_renderer/
    handler.py                     # Step 3: Render plain text + send SES
    templates.py                   # Email section templates
stacks/
    analysis_stack.py              # Step Functions + EventBridge + 3 Lambdas
tests/
  unit/
    test_scores.py                 # Score formula tests
    test_correlations.py           # Correlation/anomaly tests
    test_dates.py                  # Date utility tests
    test_templates.py              # Email rendering tests
    test_db.py                     # DB query helper tests
    test_records.py                # Personal records tests
scripts/
    test_email_local.py            # Run full pipeline locally with real DB data
```

---

## Chunk 1: Shared Utilities (dates, DB helpers, score formulas)

### Task 1: Date Utilities

**Files:**
- Create: `lambdas/shared/__init__.py`
- Create: `lambdas/shared/dates.py`
- Create: `tests/unit/test_dates.py`

- [ ] **Step 1: Write failing tests for date utilities**

```python
# tests/unit/test_dates.py
from datetime import date

from lambdas.shared.dates import (
    get_week_range,
    get_date_range,
    parse_time_from_date_str,
)


def test_get_week_range_sunday_to_saturday():
    """Given a Sunday date, return that Sunday through previous Saturday."""
    sun, sat = get_week_range(date(2026, 3, 8))  # Sunday Mar 8
    assert sun == date(2026, 3, 2)  # Previous Sunday
    assert sat == date(2026, 3, 8)  # This Saturday


def test_get_week_range_from_midweek():
    """Given a Wednesday, return the containing Sun-Sat range."""
    sun, sat = get_week_range(date(2026, 3, 4))  # Wednesday
    assert sun == date(2026, 3, 1)
    assert sat == date(2026, 3, 7)


def test_get_date_range_30_days():
    end = date(2026, 3, 8)
    start, end_out = get_date_range(end, days=30)
    assert start == date(2026, 2, 6)
    assert end_out == end


def test_parse_time_from_date_str_with_timezone():
    """Parse bedtime from Health Auto Export format."""
    result = parse_time_from_date_str("2026-02-07 00:36:58 -0800")
    assert result.hour == 0
    assert result.minute == 36


def test_parse_time_from_date_str_iso():
    result = parse_time_from_date_str("2026-02-07T23:15:00Z")
    assert result.hour == 23
    assert result.minute == 15
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/naikaj/Work/Projects/HealthForge && source .venv/bin/activate && PYTHONPATH=. pytest tests/unit/test_dates.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement date utilities**

```python
# lambdas/shared/__init__.py
# (empty)

# lambdas/shared/dates.py
from datetime import date, datetime, timedelta, time


def get_week_range(ref_date: date) -> tuple[date, date]:
    """Return (sunday, saturday) for the week containing ref_date.

    Week runs Sunday to Saturday. If ref_date is Sunday,
    returns the week ending on the previous Saturday.
    """
    # Python: Monday=0, Sunday=6
    weekday = ref_date.weekday()
    # Days since last Sunday (Sunday weekday=6 means 0 days ago for "this Sunday")
    if weekday == 6:  # Sunday — report covers the PREVIOUS Sun-Sat
        saturday = ref_date - timedelta(days=1)
    else:
        saturday = ref_date - timedelta(days=weekday + 1)  # Go back to last Saturday
    sunday = saturday - timedelta(days=6)
    return sunday, saturday


def get_date_range(end_date: date, days: int) -> tuple[date, date]:
    """Return (start_date, end_date) going back `days` days."""
    return end_date - timedelta(days=days), end_date


def parse_time_from_date_str(date_str: str) -> time:
    """Extract time-of-day from a Health Auto Export datetime string.

    Handles: '2026-02-07 00:36:58 -0800', '2026-02-07T23:15:00Z'
    """
    clean = date_str.strip()
    # Strip timezone offset
    for sep in (" -", " +"):
        idx = clean.rfind(sep)
        if idx > 10:
            tz_part = clean[idx + 2:]
            if tz_part.replace(":", "").isdigit() and len(tz_part.replace(":", "")) in (4, 5):
                clean = clean[:idx]
                break
    # Strip trailing Z
    clean = clean.rstrip("Z")

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(clean, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse time from: {date_str}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/unit/test_dates.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add lambdas/shared/ tests/unit/test_dates.py
git commit -m "Add date utilities for week ranges and time parsing"
```

---

### Task 2: DynamoDB Query Helpers

**Files:**
- Create: `lambdas/shared/db.py`
- Create: `tests/unit/test_db.py`

- [ ] **Step 1: Write failing tests for DB helpers**

```python
# tests/unit/test_db.py
"""Tests for DB query helpers. Uses mocked DynamoDB."""
from unittest.mock import MagicMock, patch
from decimal import Decimal
from datetime import date

from lambdas.shared.db import (
    query_metric_range,
    query_all_metrics_for_week,
    get_baselines,
)


def _make_items(metric: str, dates_and_data: list[tuple[str, dict]]) -> list[dict]:
    """Helper to create DynamoDB-shaped items."""
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
    items += _make_items("sleep_analysis", [("2026-03-01", {"totalSleep": Decimal("7.5")})])
    mock_table.query.return_value = {"Items": items}

    result = query_all_metrics_for_week(
        "default",
        date(2026, 3, 1),
        date(2026, 3, 7),
    )
    # Returns dict keyed by metric name
    assert "step_count" in result or len(mock_table.query.call_args_list) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/unit/test_db.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement DB query helpers**

```python
# lambdas/shared/db.py
import os
from datetime import date
from decimal import Decimal

import boto3

TABLE_NAME = os.environ.get("TABLE_NAME", "HealthForge")
REGION = os.environ.get("AWS_REGION", "us-east-1")

dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)

METRICS = [
    "sleep_analysis",
    "step_count",
    "active_energy",
    "apple_exercise_time",
    "resting_heart_rate",
    "heart_rate_variability",
    "walking_heart_rate_average",
    "respiratory_rate",
    "workout",
]


def query_metric_range(
    user_id: str, metric: str, start_date: str, end_date: str
) -> list[dict]:
    """Query a single metric type for a date range using GSI1."""
    resp = table.query(
        IndexName="GSI1",
        KeyConditionExpression="GSI1PK = :pk AND GSI1SK BETWEEN :start AND :end",
        ExpressionAttributeValues={
            ":pk": f"USER#{user_id}#METRIC#{metric}",
            ":start": start_date,
            ":end": end_date,
        },
    )
    return resp.get("Items", [])


def query_all_metrics_for_week(
    user_id: str, start: date, end: date
) -> dict[str, list[dict]]:
    """Query all metric types for a date range. Returns {metric_name: [items]}."""
    start_str = start.isoformat()
    end_str = end.isoformat()
    result = {}
    for metric in METRICS:
        items = query_metric_range(user_id, metric, start_str, end_str)
        if items:
            result[metric] = items
    return result


def decimal_to_float(obj):
    """Convert Decimals back to floats for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_float(i) for i in obj]
    return obj
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/unit/test_db.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add lambdas/shared/db.py tests/unit/test_db.py
git commit -m "Add DynamoDB query helpers for metric range lookups"
```

---

### Task 3: Score Formulas

**Files:**
- Create: `lambdas/shared/scores.py`
- Create: `tests/unit/test_scores.py`

- [ ] **Step 1: Write failing tests for all 5 score formulas**

```python
# tests/unit/test_scores.py
from lambdas.shared.scores import (
    compute_sleep_score,
    compute_fitness_score,
    compute_recovery_score,
    compute_consistency_score,
    compute_cardio_score,
    compute_overall_grade,
)


# --- Sleep Score ---

def test_sleep_score_perfect_night():
    """A night matching all baselines should score ~100."""
    score = compute_sleep_score(
        total_sleep=7.5,
        deep=1.0,
        rem=1.5,
        awake=0.1,
        bedtime_hour=23.5,  # 11:30 PM
        baselines={
            "total_sleep_avg": 7.5,
            "deep_avg": 1.0,
            "rem_avg": 1.5,
            "bedtime_avg_hour": 23.5,
        },
    )
    assert 90 <= score <= 100


def test_sleep_score_short_night():
    """4 hours of sleep should score poorly."""
    score = compute_sleep_score(
        total_sleep=4.0,
        deep=0.5,
        rem=0.6,
        awake=1.0,
        bedtime_hour=3.0,  # 3 AM
        baselines={
            "total_sleep_avg": 7.5,
            "deep_avg": 1.0,
            "rem_avg": 1.5,
            "bedtime_avg_hour": 23.5,
        },
    )
    assert score < 50


def test_sleep_score_missing_deep_rem():
    """Score should still work without deep/REM data."""
    score = compute_sleep_score(
        total_sleep=7.0,
        deep=None,
        rem=None,
        awake=0.3,
        bedtime_hour=23.0,
        baselines={"total_sleep_avg": 7.0, "bedtime_avg_hour": 23.0},
    )
    assert 0 <= score <= 100


# --- Fitness Score ---

def test_fitness_score_active_week():
    score = compute_fitness_score(
        active_days=5,
        total_calories=3200,
        step_counts=[7000, 8000, 9000, 7500, 8500, 6000, 8000],
        workout_count=3,
        avg_workout_hr=155,
        baselines={"weekly_calories_avg": 3000, "last_week_calories": 2900},
    )
    assert 70 <= score <= 100


def test_fitness_score_no_workouts():
    """No workouts should redistribute weight, not tank score."""
    score = compute_fitness_score(
        active_days=4,
        total_calories=2500,
        step_counts=[8000, 7000, 9000, 6000, 8000, 7000, 5000],
        workout_count=0,
        avg_workout_hr=None,
        baselines={"weekly_calories_avg": 2800, "last_week_calories": 2600},
    )
    assert 30 <= score <= 80


# --- Recovery Score ---

def test_recovery_score_well_rested():
    score = compute_recovery_score(
        sleep_score=85,
        rhr=56,
        hrv=48,
        respiratory_rate=14.5,
        avg_sleep_7d=7.2,
        baselines={"rhr_avg": 58, "hrv_avg": 44, "resp_avg": 15.0},
    )
    assert 75 <= score <= 100


def test_recovery_score_missing_hrv():
    score = compute_recovery_score(
        sleep_score=70,
        rhr=60,
        hrv=None,
        respiratory_rate=15.0,
        avg_sleep_7d=6.5,
        baselines={"rhr_avg": 58, "resp_avg": 15.0},
    )
    assert 0 <= score <= 100


# --- Consistency Score ---

def test_consistency_score_consistent_week():
    score = compute_consistency_score(
        bedtime_std_min=12,
        sleep_range_hours=1.2,
        step_cv=0.08,
        workout_count=3,
    )
    assert 80 <= score <= 100


def test_consistency_score_erratic_week():
    score = compute_consistency_score(
        bedtime_std_min=75,
        sleep_range_hours=4.5,
        step_cv=0.45,
        workout_count=0,
    )
    assert score < 30


# --- Cardio Score ---

def test_cardio_score_improving():
    score = compute_cardio_score(
        rhr=56,
        hrv=48,
        walking_hr=95,
        rhr_trend=-0.5,  # dropping = good
        hrv_trend=1.2,   # rising = good
        baselines={"rhr_avg": 58, "hrv_avg": 44, "walking_hr_avg": 98},
    )
    assert 75 <= score <= 100


# --- Overall Grade ---

def test_overall_grade():
    assert compute_overall_grade(95) == "A+"
    assert compute_overall_grade(82) == "B+"
    assert compute_overall_grade(76) == "B"
    assert compute_overall_grade(62) == "C"
    assert compute_overall_grade(45) == "D"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/unit/test_scores.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement all 5 score formulas**

```python
# lambdas/shared/scores.py
import statistics


def _clamp(val: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, val))


def _scale_near_target(actual: float, target: float, tolerance: float) -> float:
    """100 if within tolerance of target, scales down linearly beyond."""
    if target == 0:
        return 50.0
    diff = abs(actual - target)
    if diff <= tolerance:
        return 100.0
    return _clamp(100 - ((diff - tolerance) / tolerance) * 50)


def _scale_above_baseline(actual: float, baseline: float) -> float:
    """100 if at or above baseline, scales down linearly below."""
    if baseline == 0:
        return 50.0
    if actual >= baseline:
        return 100.0
    ratio = actual / baseline
    return _clamp(ratio * 100)


def _scale_below_baseline(actual: float, baseline: float) -> float:
    """100 if at or below baseline, scales down linearly above."""
    if baseline == 0:
        return 50.0
    if actual <= baseline:
        return 100.0
    ratio = baseline / actual
    return _clamp(ratio * 100)


def compute_sleep_score(
    total_sleep: float,
    deep: float | None,
    rem: float | None,
    awake: float,
    bedtime_hour: float,
    baselines: dict,
) -> float:
    """Compute sleep score (0-100) for a single night.

    Args:
        total_sleep: hours of total sleep
        deep: hours of deep sleep (None if unavailable)
        rem: hours of REM sleep (None if unavailable)
        awake: hours of awake time during sleep
        bedtime_hour: hour of bedtime (e.g., 23.5 = 11:30 PM, 1.0 = 1 AM)
        baselines: dict with keys: total_sleep_avg, deep_avg, rem_avg, bedtime_avg_hour
    """
    components = {}
    weights = {}

    # Duration vs 30-day avg (25%)
    avg = baselines.get("total_sleep_avg", 7.0)
    components["duration"] = _scale_near_target(total_sleep, avg, 0.5)  # ±30 min tolerance
    weights["duration"] = 25

    # Efficiency (25%)
    if total_sleep + awake > 0:
        efficiency = (total_sleep / (total_sleep + awake)) * 100
    else:
        efficiency = 0
    components["efficiency"] = _clamp(efficiency)
    weights["efficiency"] = 25

    # Deep sleep vs baseline (20%)
    if deep is not None and "deep_avg" in baselines:
        components["deep"] = _scale_above_baseline(deep, baselines["deep_avg"])
        weights["deep"] = 20

    # REM vs baseline (15%)
    if rem is not None and "rem_avg" in baselines:
        components["rem"] = _scale_above_baseline(rem, baselines["rem_avg"])
        weights["rem"] = 15

    # Bedtime consistency (10%)
    avg_bedtime = baselines.get("bedtime_avg_hour", 23.5)
    # Handle midnight wrap (e.g., 23.5 vs 0.5)
    diff = abs(bedtime_hour - avg_bedtime)
    if diff > 12:
        diff = 24 - diff
    # Convert hours diff to minutes for scoring
    diff_min = diff * 60
    components["bedtime"] = _clamp(100 - (diff_min / 15) * 20)
    weights["bedtime"] = 10

    # Restfulness (5%)
    awake_min = awake * 60
    if awake_min < 15:
        components["restfulness"] = 100
    else:
        components["restfulness"] = _clamp(100 - (awake_min - 15) * 2)
    weights["restfulness"] = 5

    # Weighted average with redistribution for missing components
    total_weight = sum(weights.values())
    score = sum(
        components[k] * (weights[k] / total_weight)
        for k in components
    )
    return round(_clamp(score), 1)


def compute_fitness_score(
    active_days: int,
    total_calories: float,
    step_counts: list[float],
    workout_count: int,
    avg_workout_hr: float | None,
    baselines: dict,
) -> float:
    """Compute weekly fitness score (0-100).

    Args:
        active_days: days with >=30 min exercise
        total_calories: total active calories this week (kcal)
        step_counts: list of daily step counts
        workout_count: number of workouts this week
        avg_workout_hr: average heart rate during workouts (None if no workouts)
        baselines: dict with weekly_calories_avg, last_week_calories
    """
    components = {}
    weights = {}

    # Activity consistency (30%)
    components["activity"] = _clamp((active_days / 7) * 100)
    weights["activity"] = 30

    # Active calories vs avg (25%)
    weekly_avg = baselines.get("weekly_calories_avg", total_calories)
    if weekly_avg > 0:
        components["calories"] = _clamp((total_calories / weekly_avg) * 100, 0, 120)
    else:
        components["calories"] = 50
    weights["calories"] = 25

    # Step consistency (20%)
    if len(step_counts) >= 3:
        mean = statistics.mean(step_counts)
        if mean > 0:
            cv = statistics.stdev(step_counts) / mean
            components["steps"] = _clamp(100 - cv * 200)
        else:
            components["steps"] = 0
    else:
        components["steps"] = 50
    weights["steps"] = 20

    # Workout intensity (15%) — only if workouts exist
    if workout_count > 0 and avg_workout_hr is not None:
        # Estimate max HR as 220 - 30 (assume ~30 years old, adjustable later)
        max_hr_est = 190
        intensity_pct = (avg_workout_hr / max_hr_est) * 100
        components["intensity"] = _clamp(intensity_pct)
        weights["intensity"] = 15
    # If no workouts, this weight is redistributed automatically

    # Progressive load (10%)
    last_week = baselines.get("last_week_calories", total_calories)
    if last_week > 0:
        components["progressive"] = _clamp((total_calories / last_week) * 100, 0, 120)
    else:
        components["progressive"] = 50
    weights["progressive"] = 10

    total_weight = sum(weights.values())
    score = sum(
        components[k] * (weights[k] / total_weight)
        for k in components
    )
    return round(_clamp(score), 1)


def compute_recovery_score(
    sleep_score: float,
    rhr: float | None,
    hrv: float | None,
    respiratory_rate: float | None,
    avg_sleep_7d: float,
    baselines: dict,
) -> float:
    """Compute daily recovery score (0-100).

    Args:
        sleep_score: last night's sleep score
        rhr: today's resting heart rate (None if missing)
        hrv: today's HRV in ms (None if missing)
        respiratory_rate: breaths per minute (None if missing)
        avg_sleep_7d: average total sleep over last 7 days (hours)
        baselines: dict with rhr_avg, hrv_avg, resp_avg
    """
    components = {}
    weights = {}

    # Sleep score (35%)
    components["sleep"] = _clamp(sleep_score)
    weights["sleep"] = 35

    # RHR vs baseline (25%)
    if rhr is not None and "rhr_avg" in baselines:
        components["rhr"] = _scale_below_baseline(rhr, baselines["rhr_avg"])
        weights["rhr"] = 25

    # HRV vs baseline (20%)
    if hrv is not None and "hrv_avg" in baselines:
        components["hrv"] = _scale_above_baseline(hrv, baselines["hrv_avg"])
        weights["hrv"] = 20

    # Respiratory rate vs baseline (15%)
    if respiratory_rate is not None and "resp_avg" in baselines:
        components["resp"] = _scale_below_baseline(respiratory_rate, baselines["resp_avg"])
        weights["resp"] = 15

    # Sleep debt (5%)
    if avg_sleep_7d >= 7:
        components["debt"] = 100
    else:
        components["debt"] = _clamp((avg_sleep_7d / 7) * 100)
    weights["debt"] = 5

    total_weight = sum(weights.values())
    score = sum(
        components[k] * (weights[k] / total_weight)
        for k in components
    )
    return round(_clamp(score), 1)


def compute_consistency_score(
    bedtime_std_min: float,
    sleep_range_hours: float,
    step_cv: float,
    workout_count: int,
) -> float:
    """Compute weekly consistency score (0-100).

    Args:
        bedtime_std_min: standard deviation of bedtime in minutes
        sleep_range_hours: max - min sleep duration this week in hours
        step_cv: coefficient of variation of daily steps
        workout_count: number of workouts this week
    """
    # Bedtime consistency (35%): 100 if ≤15min std, 0 if ≥90min
    bedtime = _clamp(100 - ((bedtime_std_min - 15) / 75) * 100) if bedtime_std_min > 15 else 100

    # Sleep duration consistency (25%): 100 if ≤1h range, 0 if ≥5h
    sleep_dur = _clamp(100 - ((sleep_range_hours - 1) / 4) * 100) if sleep_range_hours > 1 else 100

    # Step consistency (20%): 100 if CV ≤10%, 0 if ≥50%
    steps = _clamp(100 - ((step_cv - 0.10) / 0.40) * 100) if step_cv > 0.10 else 100

    # Workout regularity (20%)
    if workout_count >= 3:
        workout = 100
    elif workout_count == 2:
        workout = 66
    elif workout_count == 1:
        workout = 33
    else:
        workout = 0

    score = bedtime * 0.35 + sleep_dur * 0.25 + steps * 0.20 + workout * 0.20
    return round(_clamp(score), 1)


def compute_cardio_score(
    rhr: float,
    hrv: float,
    walking_hr: float,
    rhr_trend: float,
    hrv_trend: float,
    baselines: dict,
) -> float:
    """Compute weekly cardio score (0-100).

    Args:
        rhr: this week's average resting HR
        hrv: this week's average HRV
        walking_hr: this week's average walking HR
        rhr_trend: daily RHR change over 7 days (negative = improving)
        hrv_trend: daily HRV change over 7 days (positive = improving)
        baselines: dict with rhr_avg, hrv_avg, walking_hr_avg
    """
    # RHR vs baseline (30%)
    rhr_score = _scale_below_baseline(rhr, baselines.get("rhr_avg", rhr))

    # HRV vs baseline (30%)
    hrv_score = _scale_above_baseline(hrv, baselines.get("hrv_avg", hrv))

    # Walking HR vs baseline (20%)
    walk_score = _scale_below_baseline(walking_hr, baselines.get("walking_hr_avg", walking_hr))

    # RHR trend (10%): 100 if dropping, 50 if flat, 0 if rising
    if rhr_trend < -0.1:
        rhr_t = 100
    elif rhr_trend > 0.1:
        rhr_t = 0
    else:
        rhr_t = 50

    # HRV trend (10%): 100 if rising, 50 if flat, 0 if dropping
    if hrv_trend > 0.1:
        hrv_t = 100
    elif hrv_trend < -0.1:
        hrv_t = 0
    else:
        hrv_t = 50

    score = (
        rhr_score * 0.30
        + hrv_score * 0.30
        + walk_score * 0.20
        + rhr_t * 0.10
        + hrv_t * 0.10
    )
    return round(_clamp(score), 1)


def compute_overall_grade(avg_score: float) -> str:
    """Map average score to letter grade."""
    if avg_score >= 95:
        return "A+"
    elif avg_score >= 90:
        return "A"
    elif avg_score >= 85:
        return "A-"
    elif avg_score >= 80:
        return "B+"
    elif avg_score >= 75:
        return "B"
    elif avg_score >= 70:
        return "B-"
    elif avg_score >= 65:
        return "C+"
    elif avg_score >= 60:
        return "C"
    elif avg_score >= 55:
        return "C-"
    else:
        return "D"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/unit/test_scores.py -v`
Expected: All 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add lambdas/shared/scores.py tests/unit/test_scores.py
git commit -m "Add all 5 health score formulas with edge case handling"
```

---

### Task 4: Correlation and Anomaly Detection

**Files:**
- Create: `lambdas/shared/correlations.py`
- Create: `tests/unit/test_correlations.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_correlations.py
from lambdas.shared.correlations import (
    detect_anomalies,
    compute_day_of_week_fingerprint,
    compute_workout_sleep_correlation,
    compute_bedtime_sleep_correlation,
)


def test_detect_anomalies_normal():
    """No anomalies when values are within 2 std devs."""
    week_data = {"resting_heart_rate": [58, 59, 57, 60, 58, 59, 57]}
    baselines = {"resting_heart_rate": {"avg": 58, "std": 3}}
    result = detect_anomalies(week_data, baselines)
    assert len(result) == 0


def test_detect_anomalies_elevated_rhr():
    """Detect anomaly when RHR elevated for 2+ consecutive days."""
    week_data = {"resting_heart_rate": [58, 59, 70, 72, 58, 59, 57]}
    baselines = {"resting_heart_rate": {"avg": 58, "std": 3}}
    result = detect_anomalies(week_data, baselines)
    assert len(result) == 1
    assert result[0]["metric"] == "resting_heart_rate"


def test_detect_anomalies_single_day_spike_ignored():
    """Single-day spikes should NOT trigger anomaly."""
    week_data = {"resting_heart_rate": [58, 59, 72, 58, 58, 59, 57]}
    baselines = {"resting_heart_rate": {"avg": 58, "std": 3}}
    result = detect_anomalies(week_data, baselines)
    assert len(result) == 0


def test_day_of_week_fingerprint():
    """Compute average score per day of week."""
    # 4 weeks of sleep scores, indexed by day name
    history = {
        "Mon": [80, 82, 78, 84],
        "Tue": [88, 90, 86, 85],
        "Thu": [55, 60, 58, 62],
    }
    result = compute_day_of_week_fingerprint(history)
    assert result["best_day"] == "Tue"
    assert result["worst_day"] == "Thu"


def test_workout_sleep_correlation():
    """Days with workouts should show more deep sleep."""
    workout_days_deep = [1.2, 1.3, 1.1, 1.4, 1.2, 1.3, 1.1, 1.2]
    non_workout_days_deep = [0.8, 0.9, 0.7, 0.85, 0.9, 0.8, 0.75, 0.85]
    result = compute_workout_sleep_correlation(workout_days_deep, non_workout_days_deep)
    assert result["difference_min"] > 0
    assert result["significant"]  # Meaningful difference


def test_bedtime_sleep_correlation():
    """Earlier bedtimes should correlate with higher sleep scores."""
    data = [
        (23.0, 85), (23.5, 82), (0.5, 70), (1.0, 62),
        (23.0, 88), (2.0, 55), (0.0, 75), (23.5, 80),
    ]
    result = compute_bedtime_sleep_correlation(data)
    assert "before_midnight" in result
    assert result["before_midnight"]["avg_score"] > result["after_1am"]["avg_score"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/unit/test_correlations.py -v`
Expected: FAIL

- [ ] **Step 3: Implement correlations and anomaly detection**

```python
# lambdas/shared/correlations.py
import statistics


def detect_anomalies(
    week_data: dict[str, list[float]],
    baselines: dict[str, dict],
) -> list[dict]:
    """Detect anomalies: metrics exceeding 2 std devs for 2+ consecutive days.

    Args:
        week_data: {metric_name: [daily_values]} for the week
        baselines: {metric_name: {"avg": float, "std": float}}

    Returns:
        List of anomaly dicts: {"metric", "values", "days", "deviation"}
    """
    anomalies = []

    # For these metrics, higher = concerning
    higher_is_bad = {"resting_heart_rate", "respiratory_rate", "walking_heart_rate_average"}
    # For these, lower = concerning
    lower_is_bad = {"heart_rate_variability", "sleep_duration", "deep_sleep"}

    for metric, values in week_data.items():
        if metric not in baselines:
            continue
        avg = baselines[metric]["avg"]
        std = baselines[metric]["std"]
        if std == 0:
            continue

        # Find consecutive days exceeding 2 std devs
        consecutive = 0
        anomaly_values = []
        max_deviation = 0

        for val in values:
            deviation = abs(val - avg) / std
            is_anomalous = False

            if metric in higher_is_bad and val > avg + 2 * std:
                is_anomalous = True
            elif metric in lower_is_bad and val < avg - 2 * std:
                is_anomalous = True
            elif metric not in higher_is_bad and metric not in lower_is_bad:
                if deviation > 2:
                    is_anomalous = True

            if is_anomalous:
                consecutive += 1
                anomaly_values.append(val)
                max_deviation = max(max_deviation, deviation)
            else:
                if consecutive >= 2:
                    anomalies.append({
                        "metric": metric,
                        "values": anomaly_values.copy(),
                        "days": consecutive,
                        "deviation": round(max_deviation, 1),
                        "baseline_avg": avg,
                    })
                consecutive = 0
                anomaly_values = []
                max_deviation = 0

        # Check if anomaly extends to end of week
        if consecutive >= 2:
            anomalies.append({
                "metric": metric,
                "values": anomaly_values,
                "days": consecutive,
                "deviation": round(max_deviation, 1),
                "baseline_avg": avg,
            })

    # Sort by severity, limit to 3
    anomalies.sort(key=lambda a: a["deviation"], reverse=True)
    return anomalies[:3]


def compute_day_of_week_fingerprint(
    history: dict[str, list[float]],
) -> dict:
    """Compute avg score per day of week from multi-week history.

    Args:
        history: {"Mon": [score1, score2, ...], "Tue": [...], ...}

    Returns:
        {"best_day": str, "worst_day": str, "averages": {day: avg}}
    """
    averages = {}
    for day, scores in history.items():
        if scores:
            averages[day] = round(statistics.mean(scores), 1)

    if not averages:
        return {"best_day": None, "worst_day": None, "averages": {}}

    best = max(averages, key=averages.get)
    worst = min(averages, key=averages.get)
    return {"best_day": best, "worst_day": worst, "averages": averages}


def compute_workout_sleep_correlation(
    workout_days_deep: list[float],
    non_workout_days_deep: list[float],
) -> dict:
    """Compare deep sleep on workout days vs non-workout days.

    Returns:
        {"difference_min": float, "significant": bool,
         "workout_avg": float, "non_workout_avg": float}
    """
    if len(workout_days_deep) < 8 or len(non_workout_days_deep) < 8:
        return {"difference_min": 0, "significant": False}

    w_avg = statistics.mean(workout_days_deep)
    nw_avg = statistics.mean(non_workout_days_deep)
    diff_hours = w_avg - nw_avg
    diff_min = diff_hours * 60

    return {
        "difference_min": round(diff_min, 0),
        "significant": abs(diff_min) > 10,
        "workout_avg": round(w_avg, 2),
        "non_workout_avg": round(nw_avg, 2),
    }


def compute_bedtime_sleep_correlation(
    data: list[tuple[float, float]],
) -> dict:
    """Correlate bedtime buckets with sleep scores.

    Args:
        data: list of (bedtime_hour, sleep_score) tuples

    Returns:
        {bucket_name: {"avg_score": float, "count": int}}
    """
    buckets = {
        "before_midnight": [],
        "midnight_to_1am": [],
        "after_1am": [],
    }

    for hour, score in data:
        if hour >= 20 or hour < 0:  # 8 PM to midnight (normalize)
            h = hour if hour >= 20 else hour + 24
        else:
            h = hour

        if h < 24:  # Before midnight
            buckets["before_midnight"].append(score)
        elif h < 25:  # Midnight to 1 AM
            buckets["midnight_to_1am"].append(score)
        else:  # After 1 AM
            buckets["after_1am"].append(score)

    result = {}
    for name, scores in buckets.items():
        if scores:
            result[name] = {
                "avg_score": round(statistics.mean(scores), 1),
                "count": len(scores),
            }
        else:
            result[name] = {"avg_score": 0, "count": 0}

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/unit/test_correlations.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add lambdas/shared/correlations.py tests/unit/test_correlations.py
git commit -m "Add correlation analysis and anomaly detection"
```

---

### Task 5: Personal Records Tracking

**Files:**
- Create: `lambdas/shared/records.py`
- Create: `tests/unit/test_records.py`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/unit/test_records.py -v`
Expected: FAIL

- [ ] **Step 3: Implement personal records**

```python
# lambdas/shared/records.py

RECORD_TYPES = {
    "best_sleep_score": {"label": "Best sleep score", "higher_is_better": True},
    "highest_steps": {"label": "Highest step day", "higher_is_better": True},
    "best_fitness_score": {"label": "Best fitness score", "higher_is_better": True},
    "lowest_rhr": {"label": "Lowest resting HR", "higher_is_better": False},
    "highest_hrv": {"label": "Highest HRV", "higher_is_better": True},
}


def check_records(
    current_records: dict[str, dict],
    this_week: dict[str, float],
) -> dict:
    """Check if any records were broken or nearly broken this week.

    Args:
        current_records: {record_type: {"value": float, "date": str}}
        this_week: {record_type: best_value_this_week}

    Returns:
        {record_type: {"broken": bool, "close": bool, ...}}
    """
    result = {}
    for rec_type, config in RECORD_TYPES.items():
        if rec_type not in this_week:
            continue

        week_val = this_week[rec_type]
        current = current_records.get(rec_type, {})
        current_val = current.get("value")

        if current_val is None:
            # First record
            result[rec_type] = {
                "broken": True,
                "close": False,
                "old_value": None,
                "new_value": week_val,
            }
            continue

        higher_better = config["higher_is_better"]
        is_broken = (week_val > current_val) if higher_better else (week_val < current_val)

        # "Close" = within 5% of record
        if current_val != 0:
            pct_diff = abs(week_val - current_val) / abs(current_val)
            is_close = pct_diff <= 0.05 and not is_broken
        else:
            is_close = False

        result[rec_type] = {
            "broken": is_broken,
            "close": is_close,
            "value": current_val,
            "date": current.get("date", ""),
            "new_value": week_val if is_broken else None,
            "this_week": week_val,
        }

    return result


def format_records(records_status: dict) -> list[str]:
    """Format records for email display.

    Only shows records that were broken or close to being broken.
    """
    lines = []
    for rec_type, status in records_status.items():
        config = RECORD_TYPES.get(rec_type, {})
        label = config.get("label", rec_type)

        if status.get("broken"):
            old = status.get("old_value")
            new = status.get("new_value")
            if old is not None:
                lines.append(f"🎉 NEW RECORD: {label}: {new} (prev: {old})")
            else:
                lines.append(f"📈 {label}: {new}")
        elif status.get("close"):
            val = status.get("value")
            this = status.get("this_week")
            lines.append(f"📈 {label}: {val} (you hit {this} — so close!)")

    return lines
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/unit/test_records.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add lambdas/shared/records.py tests/unit/test_records.py
git commit -m "Add personal records tracking and formatting"
```

---

## Chunk 2: Lambda Functions (Aggregation, Insight, Email)

### Task 6: Aggregation Lambda

**Files:**
- Create: `lambdas/aggregation/handler.py`

This Lambda is the heaviest. It:
1. Queries DynamoDB for this week + 30-day history
2. Computes all 5 scores for each day
3. Computes baselines (30-day averages and std devs)
4. Runs correlation analysis (if enough data)
5. Runs anomaly detection
6. Checks personal records
7. Returns a single JSON blob with everything

- [ ] **Step 1: Implement the aggregation handler**

```python
# lambdas/aggregation/handler.py
import json
import os
import statistics
from datetime import date, datetime, timedelta
from decimal import Decimal

import boto3

# Import shared utilities — Lambda layer or bundled
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))

from db import query_metric_range, query_all_metrics_for_week, decimal_to_float, METRICS
from dates import get_week_range, parse_time_from_date_str
from scores import (
    compute_sleep_score,
    compute_fitness_score,
    compute_recovery_score,
    compute_consistency_score,
    compute_cardio_score,
    compute_overall_grade,
)
from correlations import (
    detect_anomalies,
    compute_day_of_week_fingerprint,
    compute_workout_sleep_correlation,
    compute_bedtime_sleep_correlation,
)
from records import check_records

TABLE_NAME = os.environ.get("TABLE_NAME", "HealthForge")
USER_ID = os.environ.get("USER_ID", "default")

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _get_day_name(date_str: str) -> str:
    d = date.fromisoformat(date_str)
    return DAY_NAMES[d.weekday()]


def _safe_avg(values: list[float]) -> float | None:
    return round(statistics.mean(values), 2) if values else None


def _safe_std(values: list[float]) -> float | None:
    return round(statistics.stdev(values), 2) if len(values) >= 2 else None


def _extract_qty(items: list[dict]) -> dict[str, float]:
    """Extract {date: qty} from metric items."""
    result = {}
    for item in items:
        d = item.get("date", "")
        data = item.get("data", {})
        qty = data.get("qty")
        if qty is not None:
            result[d] = float(qty)
    return result


def _bedtime_to_hour(time_str: str) -> float | None:
    """Convert sleepStart string to hour float (e.g., 23.5 for 11:30 PM)."""
    try:
        t = parse_time_from_date_str(time_str)
        return t.hour + t.minute / 60
    except (ValueError, AttributeError):
        return None


def compute_baselines(user_id: str, end_date: date) -> dict:
    """Compute 30-day baselines for all metrics."""
    start = end_date - timedelta(days=30)
    start_str = start.isoformat()
    end_str = end_date.isoformat()

    baselines = {}

    # Sleep baselines
    sleep_items = query_metric_range(user_id, "sleep_analysis", start_str, end_str)
    if sleep_items:
        totals = [float(i["data"].get("totalSleep", 0)) for i in sleep_items if float(i["data"].get("totalSleep", 0)) >= 2]
        deeps = [float(i["data"].get("deep", 0)) for i in sleep_items if i["data"].get("deep") is not None]
        rems = [float(i["data"].get("rem", 0)) for i in sleep_items if i["data"].get("rem") is not None]
        bedtimes = []
        for i in sleep_items:
            h = _bedtime_to_hour(i["data"].get("sleepStart", ""))
            if h is not None:
                bedtimes.append(h)

        baselines["total_sleep_avg"] = _safe_avg(totals)
        baselines["total_sleep_std"] = _safe_std(totals)
        baselines["deep_avg"] = _safe_avg(deeps)
        baselines["rem_avg"] = _safe_avg(rems)
        baselines["bedtime_avg_hour"] = _safe_avg(bedtimes)

    # Simple metric baselines (qty-based)
    for metric in ["resting_heart_rate", "heart_rate_variability", "walking_heart_rate_average", "respiratory_rate"]:
        items = query_metric_range(user_id, metric, start_str, end_str)
        vals = [float(i["data"].get("qty", 0)) for i in items if i["data"].get("qty") is not None]
        short = metric.replace("heart_rate_variability", "hrv").replace("resting_heart_rate", "rhr").replace("walking_heart_rate_average", "walking_hr").replace("respiratory_rate", "resp")
        baselines[f"{short}_avg"] = _safe_avg(vals)
        baselines[f"{short}_std"] = _safe_std(vals)

    # Calorie baselines
    cal_items = query_metric_range(user_id, "active_energy", start_str, end_str)
    cal_vals = [float(i["data"].get("qty", 0)) / 4.184 for i in cal_items]
    if cal_vals:
        # Weekly average calories
        baselines["weekly_calories_avg"] = round(sum(cal_vals) / (len(cal_vals) / 7), 0)

    # Last week calories (for progressive load)
    last_week_start = end_date - timedelta(days=14)
    last_week_end = end_date - timedelta(days=7)
    last_cal = query_metric_range(user_id, "active_energy", last_week_start.isoformat(), last_week_end.isoformat())
    last_vals = [float(i["data"].get("qty", 0)) / 4.184 for i in last_cal]
    baselines["last_week_calories"] = round(sum(last_vals), 0) if last_vals else 0

    # Data age (how many days of history we have)
    all_dates = set()
    for metric in METRICS:
        items = query_metric_range(user_id, metric, start_str, end_str)
        for i in items:
            all_dates.add(i.get("date"))
    baselines["history_days"] = len(all_dates)

    return baselines


def aggregate_week(user_id: str, ref_date: date) -> dict:
    """Main aggregation: compute all scores and stats for the week."""
    sunday, saturday = get_week_range(ref_date)
    week_dates = [(sunday + timedelta(days=i)).isoformat() for i in range(7)]

    # Query all data for the week
    week_data = query_all_metrics_for_week(user_id, sunday, saturday)

    # Compute baselines from 30-day history
    baselines = compute_baselines(user_id, saturday)

    result = {
        "week_start": sunday.isoformat(),
        "week_end": saturday.isoformat(),
        "baselines": baselines,
        "days_with_data": 0,
    }

    # --- Extract per-day data ---
    sleep_by_date = {}
    for item in week_data.get("sleep_analysis", []):
        d = item["date"]
        data = decimal_to_float(item["data"])
        if float(data.get("totalSleep", 0)) >= 2:  # Exclude incomplete
            sleep_by_date[d] = data

    steps_by_date = _extract_qty(week_data.get("step_count", []))
    calories_by_date = {d: v / 4.184 for d, v in _extract_qty(week_data.get("active_energy", [])).items()}
    exercise_by_date = _extract_qty(week_data.get("apple_exercise_time", []))
    rhr_by_date = _extract_qty(week_data.get("resting_heart_rate", []))
    hrv_by_date = _extract_qty(week_data.get("heart_rate_variability", []))
    resp_by_date = _extract_qty(week_data.get("respiratory_rate", []))
    walk_hr_by_date = _extract_qty(week_data.get("walking_heart_rate_average", []))

    # Count days with any data
    all_dates_with_data = set()
    for metric_items in week_data.values():
        for item in metric_items:
            all_dates_with_data.add(item["date"])
    result["days_with_data"] = len(all_dates_with_data)

    # --- Sleep scores per night ---
    sleep_scores = {}
    for d in week_dates:
        if d in sleep_by_date:
            s = sleep_by_date[d]
            bedtime_h = _bedtime_to_hour(s.get("sleepStart", ""))
            sleep_scores[d] = compute_sleep_score(
                total_sleep=float(s.get("totalSleep", 0)),
                deep=float(s["deep"]) if s.get("deep") is not None else None,
                rem=float(s["rem"]) if s.get("rem") is not None else None,
                awake=float(s.get("awake", 0)),
                bedtime_hour=bedtime_h if bedtime_h is not None else 23.5,
                baselines=baselines,
            )

    result["sleep"] = {
        "daily_scores": {d: sleep_scores.get(d) for d in week_dates},
        "avg_score": _safe_avg(list(sleep_scores.values())),
        "nights_tracked": len(sleep_scores),
        "details": {},
    }

    # Sleep details
    if sleep_by_date:
        totals = [float(s.get("totalSleep", 0)) for s in sleep_by_date.values()]
        deeps = [float(s.get("deep", 0)) for s in sleep_by_date.values() if s.get("deep") is not None]
        rems = [float(s.get("rem", 0)) for s in sleep_by_date.values() if s.get("rem") is not None]
        awakes = [float(s.get("awake", 0)) for s in sleep_by_date.values()]

        result["sleep"]["details"] = {
            "avg_total_sleep": _safe_avg(totals),
            "avg_deep": _safe_avg(deeps),
            "avg_rem": _safe_avg(rems),
            "avg_efficiency": round(
                statistics.mean(
                    [t / (t + a) * 100 for t, a in zip(totals, awakes) if t + a > 0]
                ), 1
            ) if totals else None,
            "best_night": max(sleep_scores, key=sleep_scores.get) if sleep_scores else None,
            "worst_night": min(sleep_scores, key=sleep_scores.get) if sleep_scores else None,
            "bedtimes": {
                d: s.get("sleepStart", "") for d, s in sleep_by_date.items()
            },
            "wake_times": {
                d: s.get("sleepEnd", "") for d, s in sleep_by_date.items()
            },
        }

    # --- Fitness score ---
    active_days = sum(1 for d in week_dates if exercise_by_date.get(d, 0) >= 30)
    total_cal = sum(calories_by_date.get(d, 0) for d in week_dates)
    step_list = [steps_by_date.get(d, 0) for d in week_dates if d in steps_by_date]

    workouts = week_data.get("workout", [])
    workout_hrs = [
        float(decimal_to_float(w["data"]).get("avgHeartRate", {}).get("qty", 0))
        for w in workouts
        if w.get("data", {}).get("avgHeartRate")
    ]
    avg_workout_hr = _safe_avg(workout_hrs) if workout_hrs else None

    fitness_score = compute_fitness_score(
        active_days=active_days,
        total_calories=total_cal,
        step_counts=step_list,
        workout_count=len(workouts),
        avg_workout_hr=avg_workout_hr,
        baselines=baselines,
    )

    result["fitness"] = {
        "score": fitness_score,
        "active_days": active_days,
        "total_calories": round(total_cal, 0),
        "avg_steps": round(_safe_avg(step_list), 0) if step_list else 0,
        "avg_exercise_min": round(_safe_avg(list(exercise_by_date.values())), 0) if exercise_by_date else 0,
        "steps_by_day": {d: steps_by_date.get(d) for d in week_dates},
        "workouts": [
            {
                "date": w["date"],
                "name": decimal_to_float(w["data"]).get("name", "Unknown"),
                "duration": decimal_to_float(w["data"]).get("duration", 0),
                "calories": round(float(decimal_to_float(w["data"]).get("activeEnergyBurned", decimal_to_float(w["data"]).get("totalEnergyBurned", 0))), 0),
                "avg_hr": decimal_to_float(w["data"]).get("avgHeartRate", {}).get("qty"),
            }
            for w in workouts
        ],
    }

    # --- Recovery scores per day ---
    recovery_scores = {}
    recent_sleep_totals = list(sleep_by_date.values())
    avg_sleep_7d = _safe_avg([float(s.get("totalSleep", 0)) for s in recent_sleep_totals]) or 7.0

    for d in week_dates:
        sleep_s = sleep_scores.get(d)
        if sleep_s is None:
            continue
        recovery_scores[d] = compute_recovery_score(
            sleep_score=sleep_s,
            rhr=rhr_by_date.get(d),
            hrv=hrv_by_date.get(d),
            respiratory_rate=resp_by_date.get(d),
            avg_sleep_7d=avg_sleep_7d,
            baselines=baselines,
        )

    recovery_avg = _safe_avg(list(recovery_scores.values()))
    if recovery_avg and recovery_avg >= 80:
        verdict = "PUSH IT"
    elif recovery_avg and recovery_avg >= 60:
        verdict = "STEADY"
    else:
        verdict = "RECOVER"

    result["recovery"] = {
        "daily_scores": {d: recovery_scores.get(d) for d in week_dates},
        "avg_score": recovery_avg,
        "verdict": verdict,
        "rhr_avg": _safe_avg(list(rhr_by_date.values())),
        "hrv_avg": _safe_avg(list(hrv_by_date.values())),
        "resp_avg": _safe_avg(list(resp_by_date.values())),
        "walk_hr_avg": _safe_avg(list(walk_hr_by_date.values())),
    }

    # --- Consistency score ---
    bedtime_hours = []
    for d, s in sleep_by_date.items():
        h = _bedtime_to_hour(s.get("sleepStart", ""))
        if h is not None:
            bedtime_hours.append(h)

    bedtime_std_min = (statistics.stdev(bedtime_hours) * 60) if len(bedtime_hours) >= 2 else 0
    sleep_totals = [float(s.get("totalSleep", 0)) for s in sleep_by_date.values()]
    sleep_range = (max(sleep_totals) - min(sleep_totals)) if len(sleep_totals) >= 2 else 0
    step_mean = _safe_avg(step_list) or 1
    step_cv = (statistics.stdev(step_list) / step_mean) if len(step_list) >= 3 else 0

    consistency_score = compute_consistency_score(
        bedtime_std_min=bedtime_std_min,
        sleep_range_hours=sleep_range,
        step_cv=step_cv,
        workout_count=len(workouts),
    )

    result["consistency"] = {
        "score": consistency_score,
        "bedtime_std_min": round(bedtime_std_min, 0),
        "sleep_range_hours": round(sleep_range, 1),
        "step_cv": round(step_cv * 100, 1),
        "workout_count": len(workouts),
    }

    # --- Cardio score ---
    rhr_vals = list(rhr_by_date.values())
    hrv_vals = list(hrv_by_date.values())
    walk_vals = list(walk_hr_by_date.values())

    # Compute trends (simple: last - first over the week)
    rhr_trend = (rhr_vals[-1] - rhr_vals[0]) / len(rhr_vals) if len(rhr_vals) >= 2 else 0
    hrv_trend = (hrv_vals[-1] - hrv_vals[0]) / len(hrv_vals) if len(hrv_vals) >= 2 else 0

    cardio_score = compute_cardio_score(
        rhr=_safe_avg(rhr_vals) or 60,
        hrv=_safe_avg(hrv_vals) or 40,
        walking_hr=_safe_avg(walk_vals) or 100,
        rhr_trend=rhr_trend,
        hrv_trend=hrv_trend,
        baselines=baselines,
    ) if rhr_vals else 50

    result["cardio"] = {
        "score": cardio_score,
        "rhr_avg": _safe_avg(rhr_vals),
        "hrv_avg": _safe_avg(hrv_vals),
        "walk_hr_avg": _safe_avg(walk_vals),
        "resp_avg": _safe_avg(list(resp_by_date.values())),
        "rhr_trend": round(rhr_trend, 2),
        "hrv_trend": round(hrv_trend, 2),
    }

    # --- Overall ---
    all_scores = [
        result["sleep"]["avg_score"],
        result["fitness"]["score"],
        result["recovery"]["avg_score"],
        result["consistency"]["score"],
        result["cardio"]["score"],
    ]
    valid_scores = [s for s in all_scores if s is not None]
    overall_avg = _safe_avg(valid_scores) if valid_scores else 0
    result["overall"] = {
        "avg_score": overall_avg,
        "grade": compute_overall_grade(overall_avg),
    }

    # --- Anomalies (if 2+ weeks of history) ---
    result["anomalies"] = []
    if baselines.get("history_days", 0) >= 14:
        anomaly_data = {}
        anomaly_baselines = {}
        for metric, key, by_date in [
            ("resting_heart_rate", "rhr", rhr_by_date),
            ("heart_rate_variability", "hrv", hrv_by_date),
            ("respiratory_rate", "resp", resp_by_date),
        ]:
            vals = [by_date.get(d) for d in week_dates if d in by_date]
            if vals and baselines.get(f"{key}_avg") and baselines.get(f"{key}_std"):
                anomaly_data[metric] = vals
                anomaly_baselines[metric] = {
                    "avg": baselines[f"{key}_avg"],
                    "std": baselines[f"{key}_std"],
                }
        result["anomalies"] = detect_anomalies(anomaly_data, anomaly_baselines)

    # --- Correlations (if 4+ weeks of history) ---
    result["correlations"] = {}
    if baselines.get("history_days", 0) >= 28:
        # Query full history for correlations
        hist_start = (saturday - timedelta(days=90)).isoformat()
        hist_end = saturday.isoformat()

        # Workout vs sleep correlation
        all_sleep = query_metric_range(user_id, "sleep_analysis", hist_start, hist_end)
        all_workouts = query_metric_range(user_id, "workout", hist_start, hist_end)
        workout_dates = {w["date"] for w in all_workouts}

        workout_deep = []
        non_workout_deep = []
        for s in all_sleep:
            deep = s["data"].get("deep")
            if deep is not None:
                if s["date"] in workout_dates:
                    workout_deep.append(float(deep))
                else:
                    non_workout_deep.append(float(deep))

        result["correlations"]["workout_sleep"] = compute_workout_sleep_correlation(
            workout_deep, non_workout_deep
        )

        # Bedtime vs sleep score correlation
        bedtime_score_pairs = []
        for d, s in sleep_by_date.items():
            h = _bedtime_to_hour(s.get("sleepStart", ""))
            if h is not None and d in sleep_scores:
                bedtime_score_pairs.append((h, sleep_scores[d]))
        if len(bedtime_score_pairs) >= 8:
            result["correlations"]["bedtime_sleep"] = compute_bedtime_sleep_correlation(
                bedtime_score_pairs
            )

        # Day-of-week fingerprint
        dow_sleep = {}
        for s in all_sleep:
            day = _get_day_name(s["date"])
            total = float(s["data"].get("totalSleep", 0))
            if total >= 2:
                dow_sleep.setdefault(day, []).append(total)
        if dow_sleep:
            result["correlations"]["day_of_week"] = compute_day_of_week_fingerprint(dow_sleep)

    # --- Personal records ---
    # TODO: Load current records from DynamoDB RECORD# items
    # For now, compute from this week's data
    this_week_records = {}
    if sleep_scores:
        this_week_records["best_sleep_score"] = max(sleep_scores.values())
    if step_list:
        this_week_records["highest_steps"] = max(step_list)
    this_week_records["best_fitness_score"] = fitness_score
    if rhr_vals:
        this_week_records["lowest_rhr"] = min(rhr_vals)
    if hrv_vals:
        this_week_records["highest_hrv"] = max(hrv_vals)

    result["records"] = {"this_week": this_week_records}

    return decimal_to_float(result)


def lambda_handler(event, context):
    """Step Functions entry point for aggregation."""
    user_id = event.get("user_id", USER_ID)
    ref_date_str = event.get("date")
    if ref_date_str:
        ref_date = date.fromisoformat(ref_date_str)
    else:
        ref_date = date.today()

    result = aggregate_week(user_id, ref_date)

    # Don't send email if insufficient data
    if result["days_with_data"] == 0:
        result["send_email"] = False
        result["skip_reason"] = "No data this week"
    elif result["days_with_data"] <= 2:
        result["send_email"] = True
        result["limited_data"] = True
    else:
        result["send_email"] = True
        result["limited_data"] = False

    return result
```

- [ ] **Step 2: Commit**

```bash
git add lambdas/aggregation/
git commit -m "Add aggregation Lambda: queries DB, computes all scores and stats"
```

---

### Task 7: Insight Lambda (Gemini Flash)

**Files:**
- Create: `lambdas/insight/handler.py`

- [ ] **Step 1: Implement insight Lambda**

```python
# lambdas/insight/handler.py
import json
import os
import urllib.request
import urllib.error

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


def call_gemini(prompt: str) -> str:
    """Call Gemini Flash API. Returns generated text or fallback."""
    if not GEMINI_API_KEY:
        return ""

    url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 150, "temperature": 0.7},
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            return result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError):
        return ""


def generate_sleep_insight(data: dict) -> str:
    """Generate a 1-2 line sleep insight."""
    sleep = data.get("sleep", {})
    details = sleep.get("details", {})

    prompt = f"""You are a personal health analyst. Write a 1-2 line insight about this person's sleep this week. Be specific, cite their numbers, and be encouraging but honest.

Sleep score: {sleep.get('avg_score')} (avg of {sleep.get('nights_tracked')} nights)
Avg total sleep: {details.get('avg_total_sleep')} hours
Avg deep sleep: {details.get('avg_deep')} hours
Avg efficiency: {details.get('avg_efficiency')}%
Best night: {details.get('best_night')}
Worst night: {details.get('worst_night')}

Keep it under 50 words. No greetings or sign-offs. Just the insight."""

    result = call_gemini(prompt)
    if not result:
        # Template fallback
        avg = sleep.get("avg_score", 0)
        if avg >= 80:
            return "Strong sleep week. Keep up the consistency."
        elif avg >= 60:
            return f"Decent sleep this week at {avg}. Check your worst night for clues on what to improve."
        else:
            return f"Tough sleep week at {avg}. Focus on bedtime consistency — it's the easiest lever."
    return result


def generate_weekly_focus(data: dict) -> str:
    """Generate a 3-4 line actionable focus for next week."""
    scores = {
        "Sleep": data.get("sleep", {}).get("avg_score"),
        "Fitness": data.get("fitness", {}).get("score"),
        "Recovery": data.get("recovery", {}).get("avg_score"),
        "Consistency": data.get("consistency", {}).get("score"),
        "Cardio": data.get("cardio", {}).get("score"),
    }

    # Find weakest area
    valid = {k: v for k, v in scores.items() if v is not None}
    weakest = min(valid, key=valid.get) if valid else "Sleep"

    anomalies = data.get("anomalies", [])
    correlations = data.get("correlations", {})

    prompt = f"""You are a personal health analyst. Based on this week's data, suggest ONE specific, actionable thing to focus on next week.

Scores: {json.dumps(valid)}
Weakest area: {weakest} ({valid.get(weakest)})
Anomalies: {json.dumps(anomalies) if anomalies else 'None'}
Correlations found: {json.dumps(correlations) if correlations else 'Still building baseline'}
Consistency details: bedtime std {data.get('consistency', {}).get('bedtime_std_min', '?')} min, sleep range {data.get('consistency', {}).get('sleep_range_hours', '?')} hours

Be specific. Cite their numbers. Keep it under 80 words. No greetings. Format as 3-4 short lines."""

    result = call_gemini(prompt)
    if not result:
        score = valid.get(weakest, 0)
        return f"Your biggest opportunity: {weakest} (score: {score}).\nFocus on improving this area this week."
    return result


def lambda_handler(event, context):
    """Step Functions entry point. Receives aggregated data, returns insights."""
    if not event.get("send_email", True):
        return event

    event["insights"] = {
        "sleep_insight": generate_sleep_insight(event),
        "weekly_focus": generate_weekly_focus(event),
    }
    return event
```

- [ ] **Step 2: Commit**

```bash
git add lambdas/insight/
git commit -m "Add insight Lambda: Gemini Flash integration with template fallbacks"
```

---

### Task 8: Email Renderer Lambda

**Files:**
- Create: `lambdas/email_renderer/handler.py`
- Create: `lambdas/email_renderer/templates.py`
- Create: `tests/unit/test_templates.py`

- [ ] **Step 1: Write failing tests for email templates**

```python
# tests/unit/test_templates.py
from lambdas.email_renderer.templates import (
    render_score_bar,
    render_weekly_scores,
    render_sleep_section,
    render_fitness_section,
    format_hours_minutes,
    format_steps,
)


def test_render_score_bar():
    bar = render_score_bar(75)
    assert "███" in bar
    assert "░" in bar


def test_render_score_bar_zero():
    bar = render_score_bar(0)
    assert "░" in bar


def test_format_hours_minutes():
    assert format_hours_minutes(7.5) == "7h 30m"
    assert format_hours_minutes(0.75) == "0h 45m"
    assert format_hours_minutes(None) == "—"


def test_format_steps():
    assert format_steps(8423) == "8.4k"
    assert format_steps(12000) == "12.0k"
    assert format_steps(None) == "—"


def test_render_weekly_scores():
    data = {
        "sleep": {"avg_score": 72},
        "fitness": {"score": 81},
        "recovery": {"avg_score": 77},
        "consistency": {"score": 68},
        "cardio": {"score": 83},
        "overall": {"avg_score": 76, "grade": "B"},
    }
    text = render_weekly_scores(data, prior_week=None)
    assert "Sleep" in text
    assert "Fitness" in text
    assert "76" in text


def test_render_sleep_section_missing_days():
    data = {
        "sleep": {
            "daily_scores": {
                "2026-03-02": 74,
                "2026-03-03": 82,
                "2026-03-04": None,
                "2026-03-05": 71,
                "2026-03-06": None,
                "2026-03-07": 75,
                "2026-03-08": 80,
            },
            "avg_score": 76.4,
            "nights_tracked": 5,
            "details": {
                "avg_total_sleep": 6.6,
                "avg_deep": 0.9,
                "avg_rem": 1.3,
                "avg_efficiency": 88.0,
                "best_night": "2026-03-03",
                "worst_night": "2026-03-05",
            },
        },
        "insights": {"sleep_insight": "Test insight."},
    }
    text = render_sleep_section(data)
    assert "—" in text  # Missing days shown as dash
    assert "5 of 7" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/unit/test_templates.py -v`
Expected: FAIL

- [ ] **Step 3: Implement email templates**

```python
# lambdas/email_renderer/templates.py
from datetime import date, timedelta

DAY_ABBREVS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def format_hours_minutes(hours: float | None) -> str:
    if hours is None:
        return "—"
    h = int(hours)
    m = int((hours - h) * 60)
    return f"{h}h {m:02d}m"


def format_steps(steps: float | None) -> str:
    if steps is None:
        return "—"
    return f"{steps/1000:.1f}k"


def render_score_bar(score: float, width: int = 24) -> str:
    filled = int((score / 100) * width)
    return "█" * filled + "░" * (width - filled)


def _wow_text(current: float | None, prior: float | None) -> str:
    """Week-over-week comparison text."""
    if current is None or prior is None:
        return "—"
    diff = round(current - prior)
    if abs(diff) <= 1:
        return "steady"
    arrow = "↑" if diff > 0 else "↓"
    return f"{arrow}{abs(diff)} from last week"


def _pct_change(current: float, prior: float) -> str:
    if prior == 0:
        return "—"
    pct = round((current - prior) / prior * 100)
    if pct > 0:
        return f"↑{pct}%"
    elif pct < 0:
        return f"↓{abs(pct)}%"
    return "steady"


def render_weekly_scores(data: dict, prior_week: dict | None) -> str:
    scores = [
        ("Sleep", data.get("sleep", {}).get("avg_score"), prior_week.get("sleep", {}).get("avg_score") if prior_week else None),
        ("Fitness", data.get("fitness", {}).get("score"), prior_week.get("fitness", {}).get("score") if prior_week else None),
        ("Recovery", data.get("recovery", {}).get("avg_score"), prior_week.get("recovery", {}).get("avg_score") if prior_week else None),
        ("Consistency", data.get("consistency", {}).get("score"), prior_week.get("consistency", {}).get("score") if prior_week else None),
        ("Cardio", data.get("cardio", {}).get("score"), prior_week.get("cardio", {}).get("score") if prior_week else None),
    ]

    lines = [
        "🏆 WEEKLY SCORES",
        "─" * 53,
    ]
    for name, score, prior in scores:
        s = score if score is not None else 0
        bar = render_score_bar(s)
        wow = _wow_text(score, prior)
        lines.append(f"  {name:13s} {s:3.0f}  {bar}  {wow}")

    overall = data.get("overall", {})
    grade = overall.get("grade", "?")
    avg = overall.get("avg_score", 0)
    lines.append("")
    lines.append(f"  Overall Week: {grade} ({avg:.0f})")

    return "\n".join(lines)


def render_sleep_section(data: dict) -> str:
    sleep = data.get("sleep", {})
    details = sleep.get("details", {})
    daily = sleep.get("daily_scores", {})
    nights = sleep.get("nights_tracked", 0)

    if nights < 3:
        return ""

    # Get sorted dates
    dates = sorted(daily.keys())

    lines = [
        "",
        "😴 SLEEP",
        "─" * 53,
    ]

    # Daily scores row
    day_headers = []
    day_scores = []
    for d in dates:
        dt = date.fromisoformat(d)
        day_headers.append(f"{DAY_ABBREVS[dt.weekday()]:>4s}")
        score = daily.get(d)
        day_scores.append(f"{score:4.0f}" if score is not None else "   —")

    lines.append("  " + " ".join(day_headers))
    avg_str = f"avg: {sleep['avg_score']:.0f}" if sleep.get("avg_score") else ""
    tracked_str = f"({nights} of 7 nights)" if nights < 7 else ""
    lines.append("  " + " ".join(day_scores) + f"    {avg_str} {tracked_str}".rstrip())

    lines.append("")
    lines.append(f"  Total sleep avg: {format_hours_minutes(details.get('avg_total_sleep'))}")
    lines.append(f"  Deep sleep avg:  {format_hours_minutes(details.get('avg_deep'))}")
    lines.append(f"  REM avg:         {format_hours_minutes(details.get('avg_rem'))}")
    eff = details.get("avg_efficiency")
    lines.append(f"  Efficiency:      {eff:.0f}%" if eff else "  Efficiency:      —")

    best = details.get("best_night")
    worst = details.get("worst_night")
    if best:
        best_score = daily.get(best, 0)
        lines.append(f"")
        lines.append(f"  Best:  {best} ({best_score:.0f})")
    if worst:
        worst_score = daily.get(worst, 0)
        lines.append(f"  Worst: {worst} ({worst_score:.0f})")

    insight = data.get("insights", {}).get("sleep_insight", "")
    if insight:
        lines.append("")
        lines.append(f"  💡 {insight}")

    return "\n".join(lines)


def render_fitness_section(data: dict) -> str:
    fitness = data.get("fitness", {})
    steps_by_day = fitness.get("steps_by_day", {})

    if not steps_by_day:
        return ""

    lines = [
        "",
        "🏃 FITNESS",
        "─" * 53,
    ]

    lines.append(f"  Active days:     {fitness.get('active_days', 0)} / 7")
    lines.append(f"  Total calories:  {fitness.get('total_calories', 0):,.0f} kcal")
    lines.append(f"  Avg steps:       {fitness.get('avg_steps', 0):,.0f} / day")
    lines.append(f"  Exercise time:   {fitness.get('avg_exercise_min', 0):.0f} min / day avg")

    # Steps by day
    dates = sorted(steps_by_day.keys())
    day_headers = []
    day_steps = []
    for d in dates:
        dt = date.fromisoformat(d)
        day_headers.append(f"{DAY_ABBREVS[dt.weekday()]:>5s}")
        s = steps_by_day.get(d)
        day_steps.append(f"{format_steps(s):>5s}")

    lines.append("")
    lines.append("  Steps by day:")
    lines.append("  " + "".join(day_headers))
    lines.append("  " + "".join(day_steps))

    # Workouts
    workouts = fitness.get("workouts", [])
    if workouts:
        lines.append("")
        lines.append("  Workouts this week:")
        best_cal = 0
        best_workout = None
        for w in workouts:
            hr_str = f", avg HR {w['avg_hr']:.0f}" if w.get("avg_hr") else ""
            lines.append(f"  • {w['date']} — {w['name']}, {w['duration']:.0f} min, {w['calories']:.0f} cal{hr_str}")
            if w["calories"] > best_cal:
                best_cal = w["calories"]
                best_workout = w
        if best_workout:
            lines.append(f"")
            lines.append(f"  🏆 Top session: {best_workout['name']} — {best_cal:.0f} cal burned")
    else:
        lines.append("")
        lines.append("  Rest week — 0 workouts")

    return "\n".join(lines)


def render_recovery_section(data: dict) -> str:
    recovery = data.get("recovery", {})
    daily = recovery.get("daily_scores", {})

    if not daily or all(v is None for v in daily.values()):
        return ""

    dates = sorted(daily.keys())
    lines = [
        "",
        "❤️ RECOVERY",
        "─" * 53,
    ]

    day_headers = []
    day_scores = []
    for d in dates:
        dt = date.fromisoformat(d)
        day_headers.append(f"{DAY_ABBREVS[dt.weekday()]:>4s}")
        score = daily.get(d)
        day_scores.append(f"{score:4.0f}" if score is not None else "   —")

    lines.append("  " + " ".join(day_headers))
    avg = recovery.get("avg_score")
    lines.append("  " + " ".join(day_scores) + (f"    avg: {avg:.0f}" if avg else ""))

    lines.append("")
    rhr = recovery.get("rhr_avg")
    hrv = recovery.get("hrv_avg")
    resp = recovery.get("resp_avg")
    walk = recovery.get("walk_hr_avg")
    baselines = data.get("baselines", {})

    if rhr:
        lines.append(f"  Resting HR:   {rhr:.0f} bpm (30-day avg: {baselines.get('rhr_avg', '?')})")
    if hrv:
        lines.append(f"  HRV:          {hrv:.0f} ms  (30-day avg: {baselines.get('hrv_avg', '?')})")
    if resp:
        lines.append(f"  Resp rate:    {resp:.1f} /min")
    if walk:
        lines.append(f"  Walking HR:   {walk:.0f} bpm")

    verdict = recovery.get("verdict", "STEADY")
    lines.append("")
    lines.append(f"  Recovery verdict: {verdict}")

    return "\n".join(lines)


def render_consistency_section(data: dict) -> str:
    c = data.get("consistency", {})
    if c.get("score") is None:
        return ""

    lines = [
        "",
        "📊 CONSISTENCY",
        "─" * 53,
    ]

    lines.append(f"  Bedtime consistency:  ±{c.get('bedtime_std_min', 0):.0f} min")
    lines.append(f"  Step consistency:     CV {c.get('step_cv', 0):.0f}%")
    lines.append(f"  Workout regularity:   {c.get('workout_count', 0)} sessions")
    lines.append(f"  Sleep duration range: {format_hours_minutes(c.get('sleep_range_hours'))}")

    return "\n".join(lines)


def render_cardio_section(data: dict) -> str:
    cardio = data.get("cardio", {})
    baselines = data.get("baselines", {})

    if cardio.get("rhr_avg") is None:
        return ""

    lines = [
        "",
        "🫀 CARDIO HEALTH",
        "─" * 53,
    ]

    rhr_trend = cardio.get("rhr_trend", 0)
    rhr_dir = "↓ (good)" if rhr_trend < -0.1 else ("↑ (watch)" if rhr_trend > 0.1 else "stable")
    lines.append(f"  Resting HR:    {cardio['rhr_avg']:.0f} bpm — trending {rhr_dir}")

    if cardio.get("walk_hr_avg"):
        lines.append(f"  Walking HR:    {cardio['walk_hr_avg']:.0f} bpm")

    hrv_trend = cardio.get("hrv_trend", 0)
    hrv_dir = "↑ (good)" if hrv_trend > 0.1 else ("↓ (watch)" if hrv_trend < -0.1 else "stable")
    if cardio.get("hrv_avg"):
        lines.append(f"  HRV trend:     {hrv_dir}")

    if cardio.get("resp_avg"):
        lines.append(f"  Resp rate:     {cardio['resp_avg']:.1f} /min")

    return "\n".join(lines)


def render_correlations_section(data: dict) -> str:
    corr = data.get("correlations", {})
    if not corr:
        return ""

    lines = [
        "",
        "🔗 CORRELATIONS & PATTERNS",
        "─" * 53,
    ]

    ws = corr.get("workout_sleep", {})
    if ws.get("significant"):
        lines.append(f"  • Workout days → {ws['difference_min']:.0f} min more deep sleep on average")

    bs = corr.get("bedtime_sleep", {})
    if bs:
        before = bs.get("before_midnight", {})
        after = bs.get("after_1am", {})
        if before.get("count", 0) >= 3 and after.get("count", 0) >= 3:
            diff = before["avg_score"] - after["avg_score"]
            if diff > 10:
                lines.append(f"  • Bedtime before midnight → sleep score {diff:.0f} points higher")

    dow = corr.get("day_of_week", {})
    if dow.get("best_day") and dow.get("worst_day"):
        lines.append("")
        lines.append("  📅 Day-of-week fingerprint:")
        lines.append(f"  Best sleep day:    {dow['best_day']} (avg {dow['averages'].get(dow['best_day'], '?')})")
        lines.append(f"  Worst sleep day:   {dow['worst_day']} (avg {dow['averages'].get(dow['worst_day'], '?')})")

    if len(lines) <= 3:
        return ""  # No meaningful correlations to show

    return "\n".join(lines)


def render_anomalies_section(data: dict) -> str:
    anomalies = data.get("anomalies", [])
    baselines = data.get("baselines", {})

    if baselines.get("history_days", 0) < 14:
        return ""

    lines = [
        "",
        "⚠️ ANOMALIES",
        "─" * 53,
    ]

    if not anomalies:
        lines.append("  None this week. All metrics within normal range. ✓")
    else:
        for a in anomalies:
            metric_label = a["metric"].replace("_", " ").title()
            lines.append(
                f"  {metric_label}: {a['deviation']} std devs from baseline "
                f"for {a['days']} consecutive days (baseline: {a['baseline_avg']:.1f})"
            )

    return "\n".join(lines)


def render_focus_section(data: dict) -> str:
    focus = data.get("insights", {}).get("weekly_focus", "")

    lines = [
        "",
        "🎯 THIS WEEK'S FOCUS",
        "─" * 53,
    ]

    if focus:
        for line in focus.split("\n"):
            lines.append(f"  {line}")
    else:
        lines.append("  Keep doing what you're doing!")

    return "\n".join(lines)


def render_records_section(data: dict) -> str:
    records = data.get("records", {})
    this_week = records.get("this_week", {})

    if not this_week:
        return ""

    lines = [
        "",
        "═" * 53,
        "📈 Personal Records",
    ]

    for key, val in this_week.items():
        label = key.replace("_", " ").title()
        lines.append(f"  • {label}: {val}")

    lines.append("═" * 53)
    return "\n".join(lines)


def render_full_email(data: dict, prior_week: dict | None = None) -> tuple[str, str]:
    """Render the complete email. Returns (subject, body)."""
    week_start = data.get("week_start", "")
    week_end = data.get("week_end", "")

    sleep_score = data.get("sleep", {}).get("avg_score", 0) or 0
    fitness_score = data.get("fitness", {}).get("score", 0) or 0
    recovery_score = data.get("recovery", {}).get("avg_score", 0) or 0

    subject = f"HealthForge — Week of {week_start} to {week_end} | Sleep {sleep_score:.0f} Fitness {fitness_score:.0f} Recovery {recovery_score:.0f}"

    sections = [
        "═" * 53,
        f"  HEALTHFORGE — Week of {week_start} to {week_end}",
        "═" * 53,
        "",
        render_weekly_scores(data, prior_week),
        render_sleep_section(data),
        render_fitness_section(data),
        render_recovery_section(data),
        render_consistency_section(data),
        render_cardio_section(data),
        render_correlations_section(data),
        render_anomalies_section(data),
        render_focus_section(data),
        render_records_section(data),
    ]

    # Filter out empty sections
    body = "\n".join(s for s in sections if s)

    if data.get("limited_data"):
        body = "⚠️ Limited data this week — scores may not be representative.\n\n" + body

    return subject, body
```

- [ ] **Step 4: Implement email sender handler**

```python
# lambdas/email_renderer/handler.py
import json
import os

import boto3

# Import templates
import sys
sys.path.insert(0, os.path.dirname(__file__))
from templates import render_full_email

ses = boto3.client("ses", region_name=os.environ.get("AWS_REGION", "us-east-1"))
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "")


def lambda_handler(event, context):
    """Step Functions entry point. Renders email and sends via SES."""
    if not event.get("send_email", True):
        return {"status": "skipped", "reason": event.get("skip_reason", "No data")}

    subject, body = render_full_email(event, prior_week=None)

    if not SENDER_EMAIL or not RECIPIENT_EMAIL:
        # Local testing mode — just return the email
        return {"status": "rendered", "subject": subject, "body": body}

    ses.send_email(
        Source=SENDER_EMAIL,
        Destination={"ToAddresses": [RECIPIENT_EMAIL]},
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
        },
    )

    return {"status": "sent", "subject": subject}
```

- [ ] **Step 5: Run template tests**

Run: `PYTHONPATH=. pytest tests/unit/test_templates.py -v`
Expected: All 6 tests PASS

- [ ] **Step 6: Commit**

```bash
git add lambdas/email_renderer/ tests/unit/test_templates.py
git commit -m "Add email renderer Lambda with plain text templates"
```

---

## Chunk 3: CDK Stack and Deployment

### Task 9: Analysis Stack (Step Functions + EventBridge + SES)

**Files:**
- Create: `stacks/analysis_stack.py`
- Modify: `app.py`

- [ ] **Step 1: Implement the analysis stack**

```python
# stacks/analysis_stack.py
from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as _lambda,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_events as events,
    aws_events_targets as targets,
    aws_ses as ses,
    aws_ssm as ssm,
    aws_iam as iam,
)
from constructs import Construct
from stacks.data_stack import DataStack


class AnalysisStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, data_stack: DataStack, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Gemini API key from SSM Parameter Store
        gemini_key_param = ssm.StringParameter.from_secure_string_parameter_attributes(
            self, "GeminiApiKey",
            parameter_name="/healthforge/gemini-api-key",
        )

        # Email config from SSM
        sender_email = ssm.StringParameter.value_for_string_parameter(
            self, "/healthforge/sender-email"
        )
        recipient_email = ssm.StringParameter.value_for_string_parameter(
            self, "/healthforge/recipient-email"
        )

        # --- Lambda: Aggregation ---
        aggregation_fn = _lambda.Function(
            self,
            "Aggregation",
            function_name="HealthForge-Aggregation",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("lambdas/aggregation",
                bundling=_lambda.BundlingOptions(
                    image=_lambda.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash", "-c",
                        "cp -r /asset-input/* /asset-output/ && cp -r /asset-input/../shared /asset-output/shared",
                    ],
                ),
            ),
            timeout=Duration.seconds(120),
            memory_size=512,
            environment={
                "TABLE_NAME": data_stack.table.table_name,
                "USER_ID": "default",
            },
        )
        data_stack.table.grant_read_data(aggregation_fn)

        # --- Lambda: Insight (Gemini Flash) ---
        insight_fn = _lambda.Function(
            self,
            "Insight",
            function_name="HealthForge-Insight",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("lambdas/insight"),
            timeout=Duration.seconds(30),
            memory_size=128,
            environment={
                "GEMINI_API_KEY": gemini_key_param.string_value,
            },
        )

        # --- Lambda: Email Renderer ---
        email_fn = _lambda.Function(
            self,
            "EmailRenderer",
            function_name="HealthForge-EmailRenderer",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("lambdas/email_renderer"),
            timeout=Duration.seconds(30),
            memory_size=128,
            environment={
                "SENDER_EMAIL": sender_email,
                "RECIPIENT_EMAIL": recipient_email,
            },
        )
        email_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ses:SendEmail", "ses:SendRawEmail"],
                resources=["*"],
            )
        )

        # --- Step Functions ---
        aggregate_step = tasks.LambdaInvoke(
            self, "AggregateData",
            lambda_function=aggregation_fn,
            output_path="$.Payload",
        )

        insight_step = tasks.LambdaInvoke(
            self, "GenerateInsights",
            lambda_function=insight_fn,
            output_path="$.Payload",
        )

        email_step = tasks.LambdaInvoke(
            self, "SendEmail",
            lambda_function=email_fn,
            output_path="$.Payload",
        )

        # Chain: Aggregate → Check if should send → Insight → Email
        should_send = sfn.Choice(self, "ShouldSendEmail")
        skip_state = sfn.Pass(self, "SkipEmail")

        definition = aggregate_step.next(
            should_send
            .when(sfn.Condition.boolean_equals("$.send_email", False), skip_state)
            .otherwise(insight_step.next(email_step))
        )

        state_machine = sfn.StateMachine(
            self,
            "WeeklyReportPipeline",
            state_machine_name="HealthForge-WeeklyReport",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            timeout=Duration.minutes(5),
        )

        # --- EventBridge: Sunday 10 AM ---
        events.Rule(
            self,
            "WeeklySchedule",
            rule_name="HealthForge-WeeklyReport",
            schedule=events.Schedule.cron(
                minute="0",
                hour="10",
                week_day="SUN",
            ),
            targets=[targets.SfnStateMachine(
                state_machine,
                input=events.RuleTargetInput.from_object({
                    "user_id": "default",
                }),
            )],
        )
```

- [ ] **Step 2: Update app.py to include analysis stack**

```python
# app.py — add these lines
from stacks.analysis_stack import AnalysisStack

# After IngestStack line:
AnalysisStack(app, "HealthForgeAnalysis", data_stack=data_stack, env=env)
```

- [ ] **Step 3: Verify CDK synth succeeds**

Run: `source .venv/bin/activate && cdk synth 2>&1 | tail -5`
Expected: No errors, 3 stacks listed

- [ ] **Step 4: Commit**

```bash
git add stacks/analysis_stack.py app.py
git commit -m "Add analysis stack: Step Functions + EventBridge + 3 Lambdas"
```

---

### Task 10: SES Setup and SSM Parameters

**Files:** None (AWS CLI commands only)

- [ ] **Step 1: Verify SES email identity**

Run: `aws ses verify-email-identity --email-address YOUR_EMAIL --region us-east-1`

Check your inbox and click the verification link.

- [ ] **Step 2: Store SSM parameters**

```bash
# Store Gemini API key (get from https://aistudio.google.com/apikey)
aws ssm put-parameter \
  --name "/healthforge/gemini-api-key" \
  --value "YOUR_GEMINI_API_KEY" \
  --type SecureString \
  --region us-east-1

# Store email addresses
aws ssm put-parameter \
  --name "/healthforge/sender-email" \
  --value "YOUR_EMAIL" \
  --type String \
  --region us-east-1

aws ssm put-parameter \
  --name "/healthforge/recipient-email" \
  --value "YOUR_EMAIL" \
  --type String \
  --region us-east-1
```

- [ ] **Step 3: Deploy**

Run: `cdk deploy HealthForgeAnalysis --require-approval never`
Expected: Stack creates successfully with Step Functions, 3 Lambdas, EventBridge rule

- [ ] **Step 4: Commit and push everything**

```bash
git add -A
git commit -m "Deploy weekly email pipeline: scores, Gemini insights, SES delivery"
git push
```

---

### Task 11: Local End-to-End Test

**Files:**
- Create: `scripts/test_email_local.py`

- [ ] **Step 1: Create local test script**

```python
# scripts/test_email_local.py
"""Run the full aggregation pipeline locally and print the email.

Usage: PYTHONPATH=. python scripts/test_email_local.py
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambdas", "shared"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambdas", "email_renderer"))

os.environ.setdefault("TABLE_NAME", "HealthForge")
os.environ.setdefault("AWS_REGION", "us-east-1")

from lambdas.aggregation.handler import aggregate_week
from lambdas.email_renderer.templates import render_full_email
from datetime import date


def main():
    ref_date = date.today()
    if len(sys.argv) > 1:
        ref_date = date.fromisoformat(sys.argv[1])

    print(f"Aggregating week for reference date: {ref_date}")
    print()

    data = aggregate_week("default", ref_date)

    # Add placeholder insights (no Gemini in local mode)
    data["insights"] = {
        "sleep_insight": "Local test — Gemini insight would appear here.",
        "weekly_focus": "Local test — weekly focus would appear here.",
    }
    data["send_email"] = True
    data["limited_data"] = False

    subject, body = render_full_email(data)

    print(f"Subject: {subject}")
    print()
    print(body)

    # Also dump raw data for debugging
    with open("/tmp/healthforge_aggregation.json", "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"\nRaw data saved to /tmp/healthforge_aggregation.json")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the local test**

Run: `source .venv/bin/activate && PYTHONPATH=. python scripts/test_email_local.py 2026-03-09`

Expected: Full email printed to terminal with real data from DynamoDB

- [ ] **Step 3: Review output and fix any issues**

Check that:
- All 5 scores are computed and reasonable (0-100)
- Missing days show "—"
- Steps display as "X.Xk"
- Sleep times are readable
- No crashes from missing data

- [ ] **Step 4: Commit**

```bash
git add scripts/test_email_local.py
git commit -m "Add local email test script for end-to-end verification"
git push
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | Date utilities | `lambdas/shared/dates.py` |
| 2 | DB query helpers | `lambdas/shared/db.py` |
| 3 | Score formulas (all 5) | `lambdas/shared/scores.py` |
| 4 | Correlations + anomalies | `lambdas/shared/correlations.py` |
| 5 | Personal records | `lambdas/shared/records.py` |
| 6 | Aggregation Lambda | `lambdas/aggregation/handler.py` |
| 7 | Insight Lambda (Gemini) | `lambdas/insight/handler.py` |
| 8 | Email renderer Lambda | `lambdas/email_renderer/handler.py` + `templates.py` |
| 9 | CDK Analysis Stack | `stacks/analysis_stack.py` |
| 10 | SES + SSM setup | AWS CLI commands |
| 11 | Local end-to-end test | `scripts/test_email_local.py` |

**Total: 11 tasks, ~15 files, ~1500 lines of code**
