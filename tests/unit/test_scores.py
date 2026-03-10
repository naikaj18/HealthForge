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
