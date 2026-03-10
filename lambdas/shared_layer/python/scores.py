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
