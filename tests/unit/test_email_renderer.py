from lambdas.email_renderer.templates import render_full_email


def _base_data(**overrides):
    data = {
        "week_start": "2026-03-02",
        "week_end": "2026-03-08",
        "overall": {"grade": "B+", "avg_score": 82},
        "sleep": {
            "avg_score": 78,
            "nights_tracked": 7,
            "daily_scores": {f"2026-03-0{i}": 70 + i for i in range(2, 9)},
            "details": {
                "avg_total_sleep": 7.2,
                "avg_deep": 1.0,
                "avg_rem": 1.5,
                "avg_efficiency": 90,
                "best_night": "2026-03-07",
                "worst_night": "2026-03-02",
            },
        },
        "fitness": {
            "score": 75,
            "steps_by_day": {f"2026-03-0{i}": 8000 for i in range(2, 9)},
            "avg_steps": 8000,
            "workout_days": 3,
            "total_calories": 2500,
            "workouts_by_day": {},
        },
        "recovery": {
            "avg_score": 80,
            "daily_scores": {f"2026-03-0{i}": 80 for i in range(2, 9)},
            "rhr_avg": 58,
            "hrv_avg": 45,
        },
        "consistency": {"score": 70, "bedtime_std_min": 20, "step_cv": 15, "workout_count": 3, "sleep_range_hours": 1.5},
        "cardio": {"score": 72, "rhr_avg": 58, "hrv_avg": 45, "rhr_trend": -0.2, "hrv_trend": 0.5},
    }
    data.update(overrides)
    return data


def test_render_full_email_returns_subject_and_bodies():
    subject, html_body, text_body = render_full_email(_base_data())
    assert isinstance(subject, str)
    assert isinstance(html_body, str)
    assert isinstance(text_body, str)
    assert len(subject) > 0
    assert "<html" in html_body.lower() or "<table" in html_body.lower()


def test_subject_includes_grade_and_scores():
    subject, _, _ = render_full_email(_base_data())
    assert "B+" in subject
    assert "Sleep 78" in subject
    assert "Fitness 75" in subject
    assert "Recovery 80" in subject


def test_limited_data_warning_in_html():
    _, html_body, _ = render_full_email(_base_data(limited_data=True))
    assert "Limited data" in html_body or "limited data" in html_body.lower()


def test_section_omitted_when_insufficient_data():
    """Sleep section requires >= 3 nights; 1 night should omit it."""
    data = _base_data()
    data["sleep"] = {"avg_score": 50, "nights_tracked": 1, "daily_scores": {}, "details": {}}
    _, html_body, _ = render_full_email(data)
    # Sleep section title should not appear
    assert "Sleep</span>" not in html_body or html_body.count("Sleep") <= 2  # only in scores card, not in section


def test_recovery_section_omitted_when_no_data():
    data = _base_data()
    data["recovery"] = {"daily_scores": {}}
    _, html_body, _ = render_full_email(data)
    assert "Recovery</span>" not in html_body or "Verdict" not in html_body
