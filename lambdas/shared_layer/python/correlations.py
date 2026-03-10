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
