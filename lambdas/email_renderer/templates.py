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
