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
