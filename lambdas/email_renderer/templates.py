from datetime import date, timedelta

DAY_ABBREVS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

GREETINGS = [
    "Here's how your week shaped up.",
    "Your weekly health snapshot is ready.",
    "Let's see how you did this week.",
]


def _greeting_for_date(d: str) -> str:
    """Pick a greeting based on week start date."""
    if not d:
        return GREETINGS[0]
    day_num = sum(int(c) for c in d if c.isdigit())
    return GREETINGS[day_num % len(GREETINGS)]


def _fmt_date_range(start: str, end: str) -> str:
    """Format date range nicely: Mar 3 - 9, 2026."""
    try:
        s = date.fromisoformat(start)
        e = date.fromisoformat(end)
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        if s.month == e.month:
            return f"{months[s.month-1]} {s.day} - {e.day}, {s.year}"
        return f"{months[s.month-1]} {s.day} - {months[e.month-1]} {e.day}, {e.year}"
    except (ValueError, IndexError):
        return f"{start} to {end}"


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


def render_score_bar(score: float, width: int = 16) -> str:
    filled = int((score / 100) * width)
    return "█" * filled + "░" * (width - filled)


def _wow_text(current: float | None, prior: float | None) -> str:
    """Week-over-week comparison text."""
    if current is None or prior is None:
        return ""
    diff = round(current - prior)
    if abs(diff) <= 1:
        return "→ steady"
    arrow = "↑" if diff > 0 else "↓"
    return f"{arrow}{abs(diff)} vs last wk"


def _pct_change(current: float, prior: float) -> str:
    if prior == 0:
        return "—"
    pct = round((current - prior) / prior * 100)
    if pct > 0:
        return f"↑{pct}%"
    elif pct < 0:
        return f"↓{abs(pct)}%"
    return "steady"


def _section_header(emoji: str, title: str) -> list[str]:
    return ["", f"{emoji}  {title}", "╌" * 44]


def _grade_emoji(grade: str) -> str:
    if grade.startswith("A"):
        return "🟢"
    if grade.startswith("B"):
        return "🔵"
    if grade.startswith("C"):
        return "🟡"
    return "🔴"


def render_weekly_scores(data: dict, prior_week: dict | None) -> str:
    scores = [
        ("Sleep", data.get("sleep", {}).get("avg_score"), prior_week.get("sleep", {}).get("avg_score") if prior_week else None),
        ("Fitness", data.get("fitness", {}).get("score"), prior_week.get("fitness", {}).get("score") if prior_week else None),
        ("Recovery", data.get("recovery", {}).get("avg_score"), prior_week.get("recovery", {}).get("avg_score") if prior_week else None),
        ("Consistency", data.get("consistency", {}).get("score"), prior_week.get("consistency", {}).get("score") if prior_week else None),
        ("Cardio", data.get("cardio", {}).get("score"), prior_week.get("cardio", {}).get("score") if prior_week else None),
    ]

    lines = _section_header("🏆", "WEEKLY SCORES")

    for name, score, prior in scores:
        s = score if score is not None else 0
        bar = render_score_bar(s)
        wow = _wow_text(score, prior)
        wow_str = f"  {wow}" if wow else ""
        lines.append(f"  {name:<12s} {s:3.0f}  {bar}{wow_str}")

    overall = data.get("overall", {})
    grade = overall.get("grade", "?")
    avg = overall.get("avg_score", 0)
    gem = _grade_emoji(grade)
    lines.append("")
    lines.append(f"  {gem} Overall: {grade} ({avg:.0f}/100)")

    return "\n".join(lines)


def render_sleep_section(data: dict) -> str:
    sleep = data.get("sleep", {})
    details = sleep.get("details", {})
    daily = sleep.get("daily_scores", {})
    nights = sleep.get("nights_tracked", 0)

    if nights < 3:
        return ""

    dates = sorted(daily.keys())

    lines = _section_header("😴", "SLEEP")

    # Daily scores row
    day_headers = []
    day_scores = []
    for d in dates:
        dt = date.fromisoformat(d)
        day_headers.append(f"{DAY_ABBREVS[dt.weekday()]:>4s}")
        score = daily.get(d)
        day_scores.append(f"{score:4.0f}" if score is not None else "   —")

    lines.append("  " + " ".join(day_headers))
    lines.append("  " + " ".join(day_scores))

    avg_str = f"avg {sleep['avg_score']:.0f}" if sleep.get("avg_score") else ""
    tracked_str = f" ({nights}/7 nights)" if nights < 7 else ""
    if avg_str:
        lines.append(f"  {'':>28s}{avg_str}{tracked_str}")

    lines.append("")
    lines.append(f"  Duration    {format_hours_minutes(details.get('avg_total_sleep'))}")
    lines.append(f"  Deep        {format_hours_minutes(details.get('avg_deep'))}")
    lines.append(f"  REM         {format_hours_minutes(details.get('avg_rem'))}")
    eff = details.get("avg_efficiency")
    lines.append(f"  Efficiency  {eff:.0f}%" if eff else "  Efficiency  —")

    best = details.get("best_night")
    worst = details.get("worst_night")
    if best or worst:
        lines.append("")
    if best:
        best_dt = date.fromisoformat(best)
        best_score = daily.get(best, 0)
        lines.append(f"  ▲ Best   {DAY_ABBREVS[best_dt.weekday()]} ({best_score:.0f})")
    if worst:
        worst_dt = date.fromisoformat(worst)
        worst_score = daily.get(worst, 0)
        lines.append(f"  ▼ Worst  {DAY_ABBREVS[worst_dt.weekday()]} ({worst_score:.0f})")

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

    dates = sorted(steps_by_day.keys())
    workouts_by_day = fitness.get("workouts_by_day", {})
    workout_days = fitness.get("workout_days", 0)

    lines = _section_header("🚶", "STEPS & FITNESS")

    lines.append(f"  Daily avg  {fitness.get('avg_steps', 0):,.0f} steps")

    # Steps by day
    day_headers = []
    day_steps = []
    for d in dates:
        dt = date.fromisoformat(d)
        day_headers.append(f"{DAY_ABBREVS[dt.weekday()]:>5s}")
        s = steps_by_day.get(d)
        day_steps.append(f"{format_steps(s):>5s}")

    lines.append("")
    lines.append("  " + "".join(day_headers))
    lines.append("  " + "".join(day_steps))

    # Workouts
    lines.append("")
    lines.append(f"  🏋️ Workouts: {workout_days}/7 days"
                 f"  •  {fitness.get('total_calories', 0):,.0f} kcal")

    if workouts_by_day:
        lines.append("")
        best_day_cal = 0
        best_day_name = None
        for d in dates:
            dt = date.fromisoformat(d)
            day_name = DAY_ABBREVS[dt.weekday()]
            day_workouts = workouts_by_day.get(d)
            if not day_workouts:
                lines.append(f"  {day_name}  ·")
            else:
                day_cal = sum(w["calories"] for w in day_workouts)
                names = ", ".join(f"{w['name']} ({w['duration']:.0f}m)" for w in day_workouts)
                hrs = [w.get("avg_hr") for w in day_workouts if w.get("avg_hr")]
                hr_str = f"  HR {sum(hrs)/len(hrs):.0f}" if hrs else ""
                lines.append(f"  {day_name}  {names}")
                lines.append(f"       {day_cal:.0f} cal{hr_str}")
                if day_cal > best_day_cal:
                    best_day_cal = day_cal
                    best_day_name = day_name

        if best_day_name:
            lines.append("")
            lines.append(f"  ⭐ Best: {best_day_name} — {best_day_cal:.0f} cal")
    else:
        lines.append("  Rest week — no workouts logged")

    return "\n".join(lines)


def render_recovery_section(data: dict) -> str:
    recovery = data.get("recovery", {})
    daily = recovery.get("daily_scores", {})

    if not daily or all(v is None for v in daily.values()):
        return ""

    dates = sorted(daily.keys())
    lines = _section_header("❤️", "RECOVERY")

    day_headers = []
    day_scores = []
    for d in dates:
        dt = date.fromisoformat(d)
        day_headers.append(f"{DAY_ABBREVS[dt.weekday()]:>4s}")
        score = daily.get(d)
        day_scores.append(f"{score:4.0f}" if score is not None else "   —")

    lines.append("  " + " ".join(day_headers))
    lines.append("  " + " ".join(day_scores))

    avg = recovery.get("avg_score")
    if avg:
        lines.append(f"  {'':>28s}avg {avg:.0f}")

    lines.append("")
    rhr = recovery.get("rhr_avg")
    hrv = recovery.get("hrv_avg")
    resp = recovery.get("resp_avg")
    walk = recovery.get("walk_hr_avg")
    baselines = data.get("baselines", {})

    if rhr:
        bl = baselines.get('rhr_avg')
        bl_str = f"  (30d: {bl:.0f})" if bl else ""
        lines.append(f"  Resting HR   {rhr:.0f} bpm{bl_str}")
    if hrv:
        bl = baselines.get('hrv_avg')
        bl_str = f"  (30d: {bl:.0f})" if bl else ""
        lines.append(f"  HRV          {hrv:.0f} ms{bl_str}")
    if resp:
        lines.append(f"  Resp rate    {resp:.1f} /min")
    if walk:
        lines.append(f"  Walking HR   {walk:.0f} bpm")

    verdict = recovery.get("verdict", "STEADY")
    verdict_emoji = {"PUSH IT": "🟢", "MAINTAIN": "🔵", "STEADY": "🔵", "REST": "🔴"}.get(verdict, "⚪")
    lines.append("")
    lines.append(f"  {verdict_emoji} Verdict: {verdict}")

    return "\n".join(lines)


def render_consistency_section(data: dict) -> str:
    c = data.get("consistency", {})
    if c.get("score") is None:
        return ""

    lines = _section_header("📊", "CONSISTENCY")

    lines.append(f"  Bedtime spread    ±{c.get('bedtime_std_min', 0):.0f} min")
    lines.append(f"  Step variability  CV {c.get('step_cv', 0):.0f}%")
    lines.append(f"  Workout days      {c.get('workout_count', 0)}/7")
    lines.append(f"  Sleep range       {format_hours_minutes(c.get('sleep_range_hours'))}")

    return "\n".join(lines)


def render_cardio_section(data: dict) -> str:
    cardio = data.get("cardio", {})
    baselines = data.get("baselines", {})

    if cardio.get("rhr_avg") is None:
        return ""

    lines = _section_header("🫀", "CARDIO")

    rhr_trend = cardio.get("rhr_trend", 0)
    rhr_dir = "↓ good" if rhr_trend < -0.1 else ("↑ watch" if rhr_trend > 0.1 else "stable")
    lines.append(f"  Resting HR   {cardio['rhr_avg']:.0f} bpm  ({rhr_dir})")

    if cardio.get("walk_hr_avg"):
        lines.append(f"  Walking HR   {cardio['walk_hr_avg']:.0f} bpm")

    hrv_trend = cardio.get("hrv_trend", 0)
    hrv_dir = "↑ good" if hrv_trend > 0.1 else ("↓ watch" if hrv_trend < -0.1 else "stable")
    if cardio.get("hrv_avg"):
        lines.append(f"  HRV trend    {hrv_dir}")

    if cardio.get("resp_avg"):
        lines.append(f"  Resp rate    {cardio['resp_avg']:.1f} /min")

    return "\n".join(lines)


def render_correlations_section(data: dict) -> str:
    corr = data.get("correlations", {})
    if not corr:
        return ""

    lines = _section_header("🔗", "PATTERNS")

    ws = corr.get("workout_sleep", {})
    if ws.get("significant"):
        lines.append(f"  • Workout days → +{ws['difference_min']:.0f}m"
                     f" deep sleep")

    bs = corr.get("bedtime_sleep", {})
    if bs:
        before = bs.get("before_midnight", {})
        after = bs.get("after_1am", {})
        if before.get("count", 0) >= 3 and after.get("count", 0) >= 3:
            diff = before["avg_score"] - after["avg_score"]
            if diff > 10:
                lines.append(f"  • Early bedtime → +{diff:.0f}pt"
                             f" sleep score")

    dow = corr.get("day_of_week", {})
    if dow.get("best_day") and dow.get("worst_day"):
        best = dow['best_day']
        worst = dow['worst_day']
        b_avg = dow['averages'].get(best, '?')
        w_avg = dow['averages'].get(worst, '?')
        lines.append(f"  • Best sleep: {best} (avg {b_avg})"
                     f"  Worst: {worst} (avg {w_avg})")

    if len(lines) <= 3:
        return ""

    return "\n".join(lines)


def render_anomalies_section(data: dict) -> str:
    anomalies = data.get("anomalies", [])
    baselines = data.get("baselines", {})

    if baselines.get("history_days", 0) < 14:
        return ""

    lines = _section_header("⚠️", "ANOMALIES")

    if not anomalies:
        lines.append("  All clear — metrics in normal range ✓")
    else:
        for a in anomalies:
            metric_label = a["metric"].replace("_", " ").title()
            lines.append(
                f"  {metric_label}: {a['deviation']} σ from"
                f" baseline ({a['baseline_avg']:.1f})"
                f" for {a['days']} days"
            )

    return "\n".join(lines)


def render_focus_section(data: dict) -> str:
    focus = data.get("insights", {}).get("weekly_focus", "")

    lines = _section_header("🎯", "THIS WEEK'S FOCUS")

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

    lines = ["", "  ┌─────────────────────────────────────┐"]
    lines.append("  │  📈  NEW PERSONAL RECORDS           │")
    lines.append("  ├─────────────────────────────────────┤")

    for key, val in this_week.items():
        label = key.replace("_", " ").title()
        if isinstance(val, float):
            entry = f"  │  • {label}: {val:.1f}"
        else:
            entry = f"  │  • {label}: {val}"
        lines.append(f"{entry:<40s}│")

    lines.append("  └─────────────────────────────────────┘")
    return "\n".join(lines)


def render_full_email(data: dict, prior_week: dict | None = None) -> tuple[str, str]:
    """Render the complete email. Returns (subject, body)."""
    week_start = data.get("week_start", "")
    week_end = data.get("week_end", "")

    sleep_score = data.get("sleep", {}).get("avg_score", 0) or 0
    fitness_score = data.get("fitness", {}).get("score", 0) or 0
    recovery_score = data.get("recovery", {}).get("avg_score", 0) or 0

    overall = data.get("overall", {})
    grade = overall.get("grade", "?")

    date_range = _fmt_date_range(week_start, week_end)

    subject = (f"Your week: {grade} overall"
               f" — Sleep {sleep_score:.0f}"
               f" / Fitness {fitness_score:.0f}"
               f" / Recovery {recovery_score:.0f}")

    # Build body
    greeting = _greeting_for_date(week_start)

    header = [
        f"Hey! {greeting}",
        f"{date_range}",
        "",
    ]

    sections = [
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

    footer = [
        "",
        "─" * 44,
        "Stay consistent. Small wins compound.",
        "— HealthForge",
    ]

    parts = header + [s for s in sections if s] + footer

    body = "\n".join(parts)

    if data.get("limited_data"):
        body = ("⚠️ Limited data this week —"
                " scores may not be representative.\n\n" + body)

    return subject, body
