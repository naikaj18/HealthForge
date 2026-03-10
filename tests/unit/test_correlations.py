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
