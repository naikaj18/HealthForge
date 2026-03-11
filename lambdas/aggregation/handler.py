# lambdas/aggregation/handler.py
import json
import os
import statistics
from datetime import date, datetime, timedelta
from decimal import Decimal

import boto3

# Shared utilities come from Lambda Layer (or PYTHONPATH locally)
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

KJ_TO_KCAL = 4.184

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


def _num(val) -> float:
    """Extract a number from a value that might be a dict like {"qty": 123, "units": "kJ"}."""
    if val is None:
        return 0.0
    if isinstance(val, dict):
        return float(val.get("qty", 0))
    return float(val)


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
    cal_vals = [float(i["data"].get("qty", 0)) / KJ_TO_KCAL for i in cal_items]
    if cal_vals:
        # Weekly average calories
        baselines["weekly_calories_avg"] = round(sum(cal_vals) / (len(cal_vals) / 7), 0)

    # Last week calories (for progressive load)
    last_week_start = end_date - timedelta(days=14)
    last_week_end = end_date - timedelta(days=7)
    last_cal = query_metric_range(user_id, "active_energy", last_week_start.isoformat(), last_week_end.isoformat())
    last_vals = [float(i["data"].get("qty", 0)) / KJ_TO_KCAL for i in last_cal]
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
    baselines = compute_baselines(user_id, sunday - timedelta(days=1))

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
    calories_by_date = {d: v / KJ_TO_KCAL for d, v in _extract_qty(week_data.get("active_energy", [])).items()}
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
            "avg_efficiency": (lambda eff_vals: round(statistics.mean(eff_vals), 1) if eff_vals else None)(
                [t / (t + a) * 100 for t, a in zip(totals, awakes) if t + a > 0]
            ),
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

    # Group workouts by day
    workouts_by_day = {}
    for w in workouts:
        d = w["date"]
        wdata = decimal_to_float(w["data"])
        entry = {
            "name": wdata.get("name", "Unknown"),
            "duration": round(_num(wdata.get("duration", 0)) / 60, 0),
            "calories": round(_num(wdata.get("activeEnergyBurned", wdata.get("totalEnergyBurned", 0))) / KJ_TO_KCAL, 0),
            "avg_hr": _num(wdata.get("avgHeartRate")) or None,
        }
        workouts_by_day.setdefault(d, []).append(entry)

    workout_days = len(workouts_by_day)

    # Workout-specific calories (sum from individual workouts)
    workout_cal = sum(
        entry["calories"]
        for day_workouts in workouts_by_day.values()
        for entry in day_workouts
    )

    result["fitness"] = {
        "score": fitness_score,
        "active_days": active_days,
        "total_calories": round(workout_cal, 0),
        "avg_steps": round(_safe_avg(step_list), 0) if step_list else 0,
        "avg_exercise_min": round(_safe_avg(list(exercise_by_date.values())), 0) if exercise_by_date else 0,
        "steps_by_day": {d: steps_by_date.get(d) for d in week_dates},
        "workouts_by_day": workouts_by_day,
        "workout_days": workout_days,
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

    # Normalize bedtimes around midnight: hours > 12 become negative
    # (e.g., 23:00 → -1, 0:30 → 0.5, 1:00 → 1) so stdev works across midnight
    normalized_bedtimes = [h - 24 if h > 12 else h for h in bedtime_hours]
    bedtime_std_min = (statistics.stdev(normalized_bedtimes) * 60) if len(normalized_bedtimes) >= 2 else 0
    sleep_totals = [float(s.get("totalSleep", 0)) for s in sleep_by_date.values()]
    sleep_range = (max(sleep_totals) - min(sleep_totals)) if len(sleep_totals) >= 2 else 0
    step_mean = _safe_avg(step_list) or 1
    step_cv = (statistics.stdev(step_list) / step_mean) if len(step_list) >= 3 else 0

    consistency_score = compute_consistency_score(
        bedtime_std_min=bedtime_std_min,
        sleep_range_hours=sleep_range,
        step_cv=step_cv,
        workout_count=workout_days,
    )

    result["consistency"] = {
        "score": consistency_score,
        "bedtime_std_min": round(bedtime_std_min, 0),
        "sleep_range_hours": round(sleep_range, 1),
        "step_cv": round(step_cv * 100, 1),
        "workout_count": workout_days,
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
